"""
Document verification endpoints.

Handles document upload, verification, and result retrieval.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from eula.api.schemas import (
    AnomalyResponse,
    DIDStatusEnum,
    DIDVerificationResponse,
    ExtractedDataResponse,
    ValidationCheckResponse,
    VerificationResponse,
    VerificationStatusEnum,
    VerifyDocumentsRequest,
)
from eula.config import get_settings
from eula.domain.hashing import compute_bundle_hash
from eula.domain.models import DocumentType, VerificationStatus
from eula.services.did import DIDVerifier
from eula.services.forensic import DocumentInput, ForensicService
from eula.services.ocr import OCREngine
from eula.services.xrpl import XRPLNetwork, XRPLService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verification", tags=["verification"])


# Service instances (would be injected via dependency injection in production)
_forensic_service: ForensicService | None = None


def get_forensic_service() -> ForensicService:
    """Get or create forensic service instance."""
    global _forensic_service
    if _forensic_service is None:
        settings = get_settings()
        _forensic_service = ForensicService(
            ocr=OCREngine(),
            xrpl=XRPLService(network=XRPLNetwork(settings.xrpl_network)),
            did=DIDVerifier(network=settings.xrpl_network),
            confidence_threshold=settings.ocr_confidence_threshold,
        )
    return _forensic_service


@router.post(
    "/verify",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid request or document format"},
        422: {"description": "Validation error"},
    },
)
async def verify_documents(
    wallet_address: Annotated[str, Form(description="XRPL wallet address")],
    invoice: Annotated[UploadFile, File(description="Invoice document (PDF/image)")],
    purchase_order: Annotated[UploadFile, File(description="Purchase order document")],
    proof_of_delivery: Annotated[UploadFile, File(description="Proof of delivery document")],
    skip_did_check: Annotated[bool, Form()] = False,
) -> VerificationResponse:
    """
    Upload and verify a document bundle (3-way match).
    
    Accepts Invoice, Purchase Order, and Proof of Delivery documents.
    Returns verification status with detailed check results.
    
    **Process:**
    1. Validate wallet DID (business identity)
    2. Extract data via layout-aware OCR (docTR)
    3. Run 3-way match validation
    4. Check for duplicate invoice hashes
    5. Return comprehensive verification result
    """
    # Validate file types
    allowed_types = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}
    
    for doc, name in [(invoice, "invoice"), (purchase_order, "purchase_order"), (proof_of_delivery, "proof_of_delivery")]:
        if doc.content_type and doc.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type for {name}: {doc.content_type}. Allowed: PDF, PNG, JPG",
            )
    
    # Read document content
    try:
        invoice_content = await invoice.read()
        po_content = await purchase_order.read()
        pod_content = await proof_of_delivery.read()
    except Exception as e:
        logger.exception("Failed to read uploaded files")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}",
        )
    
    # Validate content is not empty
    if not invoice_content or not po_content or not pod_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more documents are empty",
        )
    
    # Create document inputs
    invoice_input = DocumentInput(
        content=invoice_content,
        filename=invoice.filename or "invoice.pdf",
        document_type=DocumentType.INVOICE,
    )
    po_input = DocumentInput(
        content=po_content,
        filename=purchase_order.filename or "po.pdf",
        document_type=DocumentType.PURCHASE_ORDER,
    )
    pod_input = DocumentInput(
        content=pod_content,
        filename=proof_of_delivery.filename or "pod.pdf",
        document_type=DocumentType.PROOF_OF_DELIVERY,
    )
    
    # Run forensic verification
    service = get_forensic_service()
    
    try:
        result = await service.verify_documents(
            wallet_address=wallet_address,
            invoice=invoice_input,
            purchase_order=po_input,
            proof_of_delivery=pod_input,
            check_duplicate=True,
            verify_did=not skip_did_check,
        )
    except Exception as e:
        logger.exception("Verification failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification error: {str(e)}",
        )
    
    # Generate verification ID
    verification_id = str(uuid4())
    
    # Map status
    status_map = {
        VerificationStatus.PENDING: VerificationStatusEnum.PENDING,
        VerificationStatus.PROCESSING: VerificationStatusEnum.PROCESSING,
        VerificationStatus.PASSED: VerificationStatusEnum.PASSED,
        VerificationStatus.FAILED: VerificationStatusEnum.FAILED,
        VerificationStatus.REQUIRES_REVIEW: VerificationStatusEnum.REQUIRES_REVIEW,
    }
    
    # Build response
    checks = [
        ValidationCheckResponse(
            rule_name=check.rule_name,
            passed=check.passed,
            message=check.message,
            details=check.details,
        )
        for check in result.verification.checks
    ]
    
    anomalies = [
        AnomalyResponse(
            code=a.code,
            message=a.message,
            severity=a.severity,
            field_path=a.field_path,
        )
        for a in result.verification.anomalies
    ]
    
    # Extract display data from bundle
    extracted = ExtractedDataResponse()
    if result.bundle:
        inv = result.bundle.invoice
        po = result.bundle.purchase_order
        pod = result.bundle.proof_of_delivery
        
        extracted = ExtractedDataResponse(
            invoice_number=inv.invoice_number.value,
            total_amount=str(inv.total_amount.value),
            currency=inv.currency.value,
            invoice_date=inv.invoice_date.value,
            due_date=inv.due_date.value,
            payee_name=inv.payee_name.value,
            payer_name=inv.payer_name.value,
            po_number=po.po_number.value,
            pod_reference=pod.delivery_reference.value,
        )
    
    # Compute bundle hash
    bundle_hash = None
    if result.invoice_hash and result.po_hash and result.pod_hash:
        bundle_hash = compute_bundle_hash(
            result.invoice_hash,
            result.po_hash,
            result.pod_hash,
        )
    
    return VerificationResponse(
        verification_id=verification_id,
        status=status_map[result.verification.status],
        checks=checks,
        anomalies=anomalies,
        review_flags=result.verification.review_flags,
        extracted_data=extracted,
        invoice_hash=result.invoice_hash,
        po_hash=result.po_hash,
        pod_hash=result.pod_hash,
        bundle_hash=bundle_hash,
        created_at=datetime.now(timezone.utc),
    )


@router.get(
    "/did/{wallet_address}",
    response_model=DIDVerificationResponse,
    responses={
        404: {"description": "DID not found"},
    },
)
async def check_did(
    wallet_address: str,
    refresh: bool = False,
) -> DIDVerificationResponse:
    """
    Check DID verification status for a wallet.
    
    Returns business identity information if DID is valid.
    """
    settings = get_settings()
    verifier = DIDVerifier(network=settings.xrpl_network)
    
    # Use async method
    result = await verifier.verify_wallet(wallet_address, bypass_cache=refresh)
    
    status_map = {
        "verified": DIDStatusEnum.VERIFIED,
        "not_found": DIDStatusEnum.NOT_FOUND,
        "expired": DIDStatusEnum.EXPIRED,
        "revoked": DIDStatusEnum.REVOKED,
        "invalid": DIDStatusEnum.INVALID,
        "pending": DIDStatusEnum.PENDING,
        "skipped": DIDStatusEnum.SKIPPED,
    }
    
    business_name = None
    registration_number = None
    country = None
    
    if result.did_document:
        business_name = result.did_document.business_name
        registration_number = result.did_document.registration_number
        country = result.did_document.country
    
    return DIDVerificationResponse(
        wallet_address=wallet_address,
        status=status_map.get(result.status.value, DIDStatusEnum.INVALID),
        business_name=business_name,
        registration_number=registration_number,
        country=country,
        message=result.message,
    )
