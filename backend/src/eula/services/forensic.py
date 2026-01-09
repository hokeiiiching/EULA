"""
Forensic audit orchestrator service.

Coordinates the full verification pipeline:
1. OCR extraction from documents
2. Field normalization
3. 3-way match validation
4. Duplicate detection
5. DID verification

This is the primary interface for document verification.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from eula.domain.hashing import compute_document_hash
from eula.domain.models import (
    DocumentBundle,
    DocumentType,
    Invoice,
    ProofOfDelivery,
    PurchaseOrder,
    VerificationResult,
    VerificationStatus,
)
from eula.domain.validation import run_full_verification

from .did import DIDVerificationResult, DIDVerifier, DIDStatus, create_skipped_result
from .ocr import FieldNormalizer, OCREngine, TableDetector, SmartFieldExtractor
from .xrpl import DuplicateCheckResult, XRPLService

logger = logging.getLogger(__name__)


@dataclass
class DocumentInput:
    """Input document for verification."""
    content: bytes
    filename: str
    document_type: DocumentType
    
    @property
    def file_extension(self) -> str:
        """Extract file extension from filename."""
        return Path(self.filename).suffix.lstrip(".")


@dataclass
class ForensicAuditResult:
    """
    Complete result of forensic audit on a document bundle.
    
    Aggregates all stages of verification:
    - OCR extraction results
    - Validation results
    - Duplicate check
    - DID verification
    """
    verification: VerificationResult
    duplicate_check: DuplicateCheckResult | None = None
    did_verification: DIDVerificationResult | None = None
    bundle: DocumentBundle | None = None
    
    # Tracking for audit trail
    invoice_hash: str | None = None
    po_hash: str | None = None
    pod_hash: str | None = None
    
    @property
    def passed(self) -> bool:
        """True if all stages passed."""
        if self.verification.status != VerificationStatus.PASSED:
            return False
        if self.duplicate_check and self.duplicate_check.is_duplicate:
            return False
        if self.did_verification and not self.did_verification.is_verified:
            return False
        return True
    
    @property
    def can_mint(self) -> bool:
        """True if document bundle is eligible for NFT minting."""
        return self.passed or self.verification.status == VerificationStatus.REQUIRES_REVIEW


class ForensicService:
    """
    Orchestrates the complete forensic verification pipeline.
    
    This service coordinates OCR, validation, duplicate detection,
    and DID verification to produce a comprehensive audit result.
    
    Example:
        service = ForensicService(
            ocr=OCREngine(),
            xrpl=XRPLService(network=XRPLNetwork.TESTNET),
            did=DIDVerifier(xrpl_url="wss://..."),
        )
        
        result = await service.verify_documents(
            wallet_address="rWallet...",
            invoice=invoice_doc,
            purchase_order=po_doc,
            proof_of_delivery=pod_doc,
        )
        
        if result.can_mint:
            # Proceed to NFT minting
    """
    
    def __init__(
        self,
        ocr: OCREngine | None = None,
        table_detector: TableDetector | None = None,
        normalizer: FieldNormalizer | None = None,
        xrpl: XRPLService | None = None,
        did: DIDVerifier | None = None,
        confidence_threshold: float = 0.7,
    ) -> None:
        """
        Initialize forensic service.
        
        Args:
            ocr: OCR engine instance (created if None)
            table_detector: Table detector instance (created if None)
            normalizer: Field normalizer instance (created if None)
            xrpl: XRPL service for duplicate checks (optional)
            did: DID verifier service (optional)
            confidence_threshold: Minimum OCR confidence for auto-approval
        """
        self.ocr = ocr or OCREngine()
        self.table_detector = table_detector or TableDetector()
        self.normalizer = normalizer or FieldNormalizer()
        self.extractor = SmartFieldExtractor()  # New smart extractor
        self.xrpl = xrpl
        self.did = did
        self.confidence_threshold = confidence_threshold
    
    async def verify_documents(
        self,
        wallet_address: str,
        invoice: DocumentInput,
        purchase_order: DocumentInput,
        proof_of_delivery: DocumentInput,
        check_duplicate: bool = True,
        verify_did: bool = True,
    ) -> ForensicAuditResult:
        """
        Run complete forensic verification on a document bundle.
        
        Args:
            wallet_address: XRPL wallet of the SME
            invoice: Invoice document
            purchase_order: Purchase order document
            proof_of_delivery: Proof of delivery document
            check_duplicate: Whether to check for duplicate hashes
            verify_did: Whether to verify wallet DID
            
        Returns:
            ForensicAuditResult with comprehensive verification status
        """
        # Step 1: Compute document hashes
        invoice_hash = compute_document_hash(invoice.content)
        po_hash = compute_document_hash(purchase_order.content)
        pod_hash = compute_document_hash(proof_of_delivery.content)
        
        logger.info(f"Processing documents: invoice={invoice_hash[:20]}...")
        
        # Step 2: Check for duplicates (sync method)
        duplicate_result = None
        if check_duplicate and self.xrpl:
            duplicate_result = self.xrpl.check_duplicate(invoice_hash)
            if duplicate_result.is_duplicate:
                logger.warning(f"Duplicate invoice detected: {invoice_hash}")
                return ForensicAuditResult(
                    verification=VerificationResult(
                        status=VerificationStatus.FAILED,
                        checks=[],
                        anomalies=[],
                    ),
                    duplicate_check=duplicate_result,
                    invoice_hash=invoice_hash,
                    po_hash=po_hash,
                    pod_hash=pod_hash,
                )
        
        # Step 3: Verify DID (async method)
        did_result = None
        if verify_did and self.did:
            did_result = await self.did.verify_wallet(wallet_address)
            if not did_result.is_verified and did_result.status != DIDStatus.NOT_FOUND:
                # Only fail on actual verification failure, not "not found"
                logger.warning(f"DID verification failed for {wallet_address}")
                return ForensicAuditResult(
                    verification=VerificationResult(
                        status=VerificationStatus.FAILED,
                        checks=[],
                        anomalies=[],
                    ),
                    duplicate_check=duplicate_result,
                    did_verification=did_result,
                    invoice_hash=invoice_hash,
                    po_hash=po_hash,
                    pod_hash=pod_hash,
                )
            elif not did_result.is_verified:
                # DID not found - log warning but continue
                logger.info(f"No DID found for {wallet_address}, proceeding anyway")
        elif not verify_did:
            # Explicitly skipped
            did_result = create_skipped_result(wallet_address)
            logger.info("DID verification skipped by request")
        
        # Step 4: OCR extraction
        try:
            invoice_data = self._extract_invoice(invoice)
            po_data = self._extract_purchase_order(purchase_order)
            pod_data = self._extract_proof_of_delivery(proof_of_delivery)
        except Exception as e:
            logger.exception("OCR extraction failed")
            return ForensicAuditResult(
                verification=VerificationResult(
                    status=VerificationStatus.FAILED,
                    checks=[],
                    anomalies=[],
                ),
                duplicate_check=duplicate_result,
                did_verification=did_result,
                invoice_hash=invoice_hash,
                po_hash=po_hash,
                pod_hash=pod_hash,
            )
        
        # Step 5: Build bundle and run validation
        bundle = DocumentBundle(
            invoice=invoice_data,
            purchase_order=po_data,
            proof_of_delivery=pod_data,
            invoice_hash=invoice_hash,
            po_hash=po_hash,
            pod_hash=pod_hash,
        )
        
        verification = run_full_verification(
            bundle=bundle,
            historical_average=None,  # Would come from database
            confidence_threshold=self.confidence_threshold,
        )
        
        logger.info(
            f"Verification complete: status={verification.status.value}, "
            f"checks_passed={verification.all_checks_passed}"
        )
        
        return ForensicAuditResult(
            verification=verification,
            duplicate_check=duplicate_result,
            did_verification=did_result,
            bundle=bundle,
            invoice_hash=invoice_hash,
            po_hash=po_hash,
            pod_hash=pod_hash,
        )
    
    def _extract_invoice(self, doc: DocumentInput) -> Invoice:
        """Extract invoice data using OCR and smart regex extraction."""
        from datetime import date
        from decimal import Decimal
        
        logger.info(f"=== EXTRACTING INVOICE: {doc.filename} ===")
        logger.info(f"File size: {len(doc.content)} bytes, type: {doc.file_extension}")
        
        # Run OCR
        ocr_result = self.ocr.process_document(doc.content, doc.file_extension)
        
        # Log OCR summary
        logger.info(
            f"OCR complete: {ocr_result.total_blocks} blocks, "
            f"avg confidence: {ocr_result.avg_confidence:.1%}"
        )
        
        # Log full text for debugging
        logger.debug(f"Full extracted text:\n{ocr_result.full_text[:1000]}...")
        
        # Log low confidence blocks
        low_conf = ocr_result.low_confidence_blocks
        if low_conf:
            logger.warning(f"Low confidence blocks ({len(low_conf)} total):")
            for block in low_conf[:5]:
                logger.warning(f"  [{block.confidence:.0%}] '{block.text}'")
        
        # Detect tables for line items
        tables = self.table_detector.detect_tables(ocr_result)
        logger.info(f"Tables detected: {len(tables)}")
        
        # === SMART EXTRACTION using regex + label proximity ===
        
        # Extract invoice number
        invoice_number = self.extractor.extract_invoice_number(ocr_result)
        logger.info(f"Invoice Number: '{invoice_number.value}' (conf: {invoice_number.confidence:.0%})")
        
        # Extract total amount
        total_amount = self.extractor.extract_amount(
            ocr_result,
            ["total", "amount due", "balance due", "grand total", "total due"],
            prefer_largest=True,
        )
        logger.info(f"Total Amount: '{total_amount.value}' (conf: {total_amount.confidence:.0%})")
        
        # Extract dates
        invoice_date = self.extractor.extract_date(
            ocr_result,
            ["invoice date", "date", "issued"],
        )
        logger.info(f"Invoice Date: '{invoice_date.value}' (conf: {invoice_date.confidence:.0%})")
        
        due_date = self.extractor.extract_date(
            ocr_result,
            ["due date", "payment due", "pay by", "due"],
        )
        logger.info(f"Due Date: '{due_date.value}' (conf: {due_date.confidence:.0%})")
        
        # Extract party names
        payee_name = self.extractor.extract_name(
            ocr_result,
            ["from", "seller", "vendor", "company", "sold by"],
        )
        logger.info(f"Payee (Seller): '{payee_name.value}' (conf: {payee_name.confidence:.0%})")
        
        payer_name = self.extractor.extract_name(
            ocr_result,
            ["to", "bill to", "buyer", "customer", "sold to"],
        )
        logger.info(f"Payer (Buyer): '{payer_name.value}' (conf: {payer_name.confidence:.0%})")
        
        # Extract line items from table if found
        line_items = []
        if tables:
            line_items = self._extract_line_items(tables[0])
            logger.info(f"Line items extracted: {len(line_items)}")
            for i, item in enumerate(line_items[:5]):
                logger.debug(f"  Item {i+1}: {item.description.value} x{item.quantity.value} = {item.total.value}")
        else:
            logger.warning("No tables found - line items will be empty")
        
        logger.info("=== INVOICE EXTRACTION COMPLETE ===")
        
        return Invoice(
            invoice_number=invoice_number,
            total_amount=total_amount,
            currency=self.normalizer.normalize_string("USD", 1.0),
            invoice_date=invoice_date,
            due_date=due_date,
            payee_name=payee_name,
            payer_name=payer_name,
            line_items=line_items,
        )
    
    def _extract_purchase_order(self, doc: DocumentInput) -> PurchaseOrder:
        """Extract purchase order data using OCR."""
        from datetime import date
        from decimal import Decimal
        
        logger.info(f"=== EXTRACTING PURCHASE ORDER: {doc.filename} ===")
        
        ocr_result = self.ocr.process_document(doc.content, doc.file_extension)
        logger.info(f"OCR: {ocr_result.total_blocks} blocks, avg conf: {ocr_result.avg_confidence:.1%}")
        
        # === SMART EXTRACTION ===
        po_number = self.extractor.extract_po_number(ocr_result)
        logger.info(f"PO Number: '{po_number.value}' (conf: {po_number.confidence:.0%})")
        
        authorized_amount = self.extractor.extract_amount(
            ocr_result,
            ["total", "amount", "order total", "authorized", "authorized amount"],
            prefer_largest=True,
        )
        logger.info(f"Authorized Amount: '{authorized_amount.value}' (conf: {authorized_amount.confidence:.0%})")
        
        po_date = self.extractor.extract_date(
            ocr_result,
            ["date", "order date", "po date"],
        )
        logger.info(f"PO Date: '{po_date.value}' (conf: {po_date.confidence:.0%})")
        
        vendor_name = self.extractor.extract_name(
            ocr_result,
            # Include "(vendor)" since OCR may split "To (Vendor):" into separate blocks
            ["(vendor)", "to (vendor)", "vendor", "supplier", "ship to", "deliver to"],
        )
        logger.info(f"Vendor: '{vendor_name.value}' (conf: {vendor_name.confidence:.0%})")
        
        buyer_name = self.extractor.extract_name(
            ocr_result,
            # Include "(buyer)" since OCR may split "From (Buyer):" into separate blocks
            ["(buyer)", "from (buyer)", "buyer", "from", "ordered by", "purchaser"],
        )
        logger.info(f"Buyer: '{buyer_name.value}' (conf: {buyer_name.confidence:.0%})")
        
        logger.info("=== PO EXTRACTION COMPLETE ===")
        
        return PurchaseOrder(
            po_number=po_number,
            authorized_amount=authorized_amount,
            currency=self.normalizer.normalize_string("USD", 1.0),
            po_date=po_date,
            vendor_name=vendor_name,
            buyer_name=buyer_name,
        )
    
    def _extract_proof_of_delivery(self, doc: DocumentInput) -> ProofOfDelivery:
        """Extract proof of delivery data using OCR and smart extraction."""
        from datetime import date
        from decimal import Decimal
        
        logger.info(f"=== EXTRACTING PROOF OF DELIVERY: {doc.filename} ===")
        
        ocr_result = self.ocr.process_document(doc.content, doc.file_extension)
        logger.info(f"OCR: {ocr_result.total_blocks} blocks, avg conf: {ocr_result.avg_confidence:.1%}")
        
        # === SMART EXTRACTION ===
        delivery_ref = self.extractor.extract_delivery_reference(ocr_result)
        logger.info(f"Delivery Ref: '{delivery_ref.value}' (conf: {delivery_ref.confidence:.0%})")
        
        quantity = self.extractor.extract_quantity(
            ocr_result,
            ["quantity", "qty", "units", "received", "total quantity", "items"],
        )
        logger.info(f"Quantity: '{quantity.value}' (conf: {quantity.confidence:.0%})")
        
        delivery_date = self.extractor.extract_date(
            ocr_result,
            ["delivery date", "received date", "date"],
        )
        logger.info(f"Delivery Date: '{delivery_date.value}' (conf: {delivery_date.confidence:.0%})")
        
        recipient = self.extractor.extract_name(
            ocr_result,
            ["received by", "recipient", "signed by", "signature"],
        )
        logger.info(f"Recipient: '{recipient.value}' (conf: {recipient.confidence:.0%})")
        
        # Check for signature presence
        full_text = ocr_result.full_text.lower()
        has_signature = "signature" in full_text or "signed" in full_text or "[signed]" in full_text
        logger.info(f"Signature detected: {has_signature}")
        
        logger.info("=== POD EXTRACTION COMPLETE ===")
        
        return ProofOfDelivery(
            delivery_reference=delivery_ref,
            quantity_delivered=quantity,
            delivery_date=delivery_date,
            recipient_name=recipient,
            recipient_signature=has_signature,
        )
    
    def _find_field_value(
        self,
        ocr_result,
        labels: list[str],
    ):
        """Find a field value following a label."""
        from eula.domain.models import ExtractedField
        
        blocks = ocr_result.all_blocks
        
        for i, block in enumerate(blocks):
            text = block.text.lower()
            for label in labels:
                if label in text:
                    # Look for value in same block or next block
                    value = text.replace(label, "").strip(":. ")
                    if value and len(value) > 1:
                        return self.normalizer.normalize_string(
                            value, block.confidence
                        )
                    elif i + 1 < len(blocks):
                        next_block = blocks[i + 1]
                        return self.normalizer.normalize_string(
                            next_block.text, next_block.confidence
                        )
        
        # Default fallback
        return ExtractedField(value="UNKNOWN", confidence=0.0, raw_text="")
    
    def _find_amount_field(
        self,
        ocr_result,
        labels: list[str],
    ):
        """Find a monetary amount field."""
        from decimal import Decimal
        from eula.domain.models import ExtractedField
        
        blocks = ocr_result.all_blocks
        
        for i, block in enumerate(blocks):
            text = block.text.lower()
            for label in labels:
                if label in text:
                    # Look for amount in next blocks
                    for j in range(i, min(i + 3, len(blocks))):
                        candidate = blocks[j].text
                        # Check if looks like amount (contains digits)
                        if any(c.isdigit() for c in candidate):
                            return self.normalizer.normalize_amount(
                                candidate, blocks[j].confidence
                            )
        
        return ExtractedField(value=Decimal("0"), confidence=0.0, raw_text="")
    
    def _find_date_field(
        self,
        ocr_result,
        labels: list[str],
    ):
        """Find a date field."""
        from datetime import date
        from eula.domain.models import ExtractedField
        
        blocks = ocr_result.all_blocks
        
        for i, block in enumerate(blocks):
            text = block.text.lower()
            for label in labels:
                if label in text:
                    # Look for date in next blocks
                    for j in range(i, min(i + 3, len(blocks))):
                        candidate = blocks[j].text
                        if any(c.isdigit() for c in candidate):
                            return self.normalizer.normalize_date(
                                candidate, blocks[j].confidence
                            )
        
        return ExtractedField(value=date.today(), confidence=0.0, raw_text="")
    
    def _find_quantity_field(
        self,
        ocr_result,
        labels: list[str],
    ):
        """Find a quantity field."""
        from decimal import Decimal
        from eula.domain.models import ExtractedField
        
        blocks = ocr_result.all_blocks
        
        for i, block in enumerate(blocks):
            text = block.text.lower()
            for label in labels:
                if label in text:
                    for j in range(i, min(i + 3, len(blocks))):
                        candidate = blocks[j].text
                        if any(c.isdigit() for c in candidate):
                            return self.normalizer.normalize_quantity(
                                candidate, blocks[j].confidence
                            )
        
        return ExtractedField(value=Decimal("0"), confidence=0.0, raw_text="")
    
    def _extract_line_items(self, table):
        """Extract line items from a detected table."""
        from eula.domain.models import LineItem
        
        items = []
        qty_col = table.get_column_by_name("quantity")
        desc_col = table.get_column_by_name("description")
        price_col = table.get_column_by_name("unit_price")
        amount_col = table.get_column_by_name("amount")
        
        for row in table.iter_data_rows():
            try:
                # Get cell values with fallback
                qty_cell = row.get_cell(qty_col) if qty_col is not None else None
                desc_cell = row.get_cell(desc_col) if desc_col is not None else None
                price_cell = row.get_cell(price_col) if price_col is not None else None
                amount_cell = row.get_cell(amount_col) if amount_col is not None else None
                
                if qty_cell and amount_cell:
                    items.append(LineItem(
                        description=self.normalizer.normalize_string(
                            desc_cell.text if desc_cell else "", 
                            desc_cell.min_confidence if desc_cell else 0.0
                        ),
                        quantity=self.normalizer.normalize_quantity(
                            qty_cell.text, qty_cell.min_confidence
                        ),
                        unit_price=self.normalizer.normalize_amount(
                            price_cell.text if price_cell else "0",
                            price_cell.min_confidence if price_cell else 0.0
                        ),
                        total=self.normalizer.normalize_amount(
                            amount_cell.text, amount_cell.min_confidence
                        ),
                    ))
            except Exception as e:
                logger.warning(f"Failed to parse line item: {e}")
                continue
        
        return items
