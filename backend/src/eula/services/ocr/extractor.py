"""
Smart field extraction using hybrid regex + label proximity.

This module provides intelligent extraction of document fields using:
1. Regex patterns to find ALL potential matches in the text
2. Label proximity to pick the best match when ambiguous
3. Confidence scoring based on pattern strength and proximity

Works with any document layout without position-based assumptions.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from eula.domain.models import ExtractedField

logger = logging.getLogger(__name__)


# =============================================================================
# Regex Patterns for Common Document Fields
# =============================================================================

# Invoice/PO/Reference numbers - capture FULL number including prefix
INVOICE_NUMBER_PATTERNS = [
    r'(?:Invoice\s*No\s*[:\s]*)(\d{5,})',  # Invoice No : 00000003 (InvoiceNow SG)
    r'(?:Invoice\s*No\s*[:\s]*)([A-Z0-9\-]+)',  # Invoice No: ABC-123
    r'(INV[-\s]?\d{4}[-\s]?\d{3,})',  # INV-2024-001 as full match
    r'(?:Invoice\s*#?\s*)([A-Z0-9\-]+)',  # Invoice #12345
    r'(?:Invoice\s+(?:No|Number)[:\s]*)([A-Z0-9\-]+)',  # Invoice Number: ABC-123
    r'#\s*([A-Z]{2,4}\-?\d{4,})',  # #INV-12345
]

PO_NUMBER_PATTERNS = [
    r'(?:P\.O\.\s*Number\s*[:\s]*)([A-Z0-9\-]+)',  # P.O. Number PO-SG-2023-001 (InvoiceNow)
    r'(?:PO|Purchase\s*Order)[#:\-\s]*([A-Z0-9\-]+)',  # PO-2024-001
    r'(?:P\.?O\.?\s*(?:No|Number|#)?[:\s]*)([A-Z0-9\-]+)',  # P.O. #12345
    r'Order\s*(?:No|Number|#)?[:\s]*([A-Z0-9\-]+)',  # Order #12345
]

DELIVERY_REF_PATTERNS = [
    r'(?:Delivery\s+Ref\s*[:\s]*)([A-Z0-9\-]+)',  # Delivery Ref : DEL-SG-2023-001 (InvoiceNow)
    r'(?:DEL|Delivery|DN)[#:\-\s]*([A-Z0-9\-]+)',  # DEL-2024-001
    r'(?:Delivery\s+(?:Note|Ref|Reference)?[:\s]*)([A-Z0-9\-]+)',
    r'(?:Receipt|Received)[#:\-\s]*([A-Z0-9\-]+)',
]

# Monetary amounts - support multiple currencies
AMOUNT_PATTERNS = [
    r'S\$\s*([\d,]+\.?\d{0,2})',  # S$1,000.00 (Singapore)
    r'SGD\s*([\d,]+\.?\d{0,2})',  # SGD 1000.00
    r'SS([\d,]+\.?\d{0,2})',  # SS1,000.00 (OCR misread of S$)
    r'[\$]\s*([\d,]+\.?\d{0,2})',  # $8,000.00
    r'([\d,]+\.?\d{0,2})\s*(?:USD|dollars?|SGD)',  # 8000.00 USD
    r'(?:Total|Amount|Due|Subtotal|Balance)[:\s]*[S\$]*\s*([\d,]+\.?\d{0,2})',  # Total: S$8000
    r'([\d]{1,3}(?:,\d{3})*\.?\d{0,2})',  # 8,000.00 (general number with commas)
]

# Dates - multiple formats
DATE_PATTERNS = [
    # ISO format: 2024-01-05
    (r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', '%Y-%m-%d'),
    # US format: 01/05/2024, 1/5/24
    (r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', '%m/%d/%Y'),
    # Long format: January 5, 2024
    (r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})', '%B %d, %Y'),
    # Short month: Jan 5, 2024
    (r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})', '%b %d, %Y'),
]

# Quantity patterns
QUANTITY_PATTERNS = [
    r'(?:Qty|Quantity|Units?|Received)[:\s]*(\d+)',  # Qty: 50
    r'(\d+)\s*(?:units?|pcs?|items?)',  # 50 units
    r'Total\s+Quantity[:\s]*(\d+)',  # Total Quantity: 200
]


@dataclass
class PatternMatch:
    """A regex pattern match with metadata."""
    value: str
    pattern: str
    start: int
    end: int
    confidence: float = 0.9


class SmartFieldExtractor:
    """
    Intelligent field extractor using hybrid regex + label proximity.
    
    Example:
        extractor = SmartFieldExtractor()
        
        invoice_num = extractor.extract_invoice_number(ocr_result)
        total = extractor.extract_amount(ocr_result, ["total", "amount due"])
        inv_date = extractor.extract_date(ocr_result, ["invoice date", "date"])
    """
    
    def __init__(self, proximity_window: int = 5):
        """
        Initialize extractor.
        
        Args:
            proximity_window: How many text blocks to search after a label match
        """
        self.proximity_window = proximity_window
    
    def extract_invoice_number(
        self,
        ocr_result,
        labels: list[str] | None = None,
    ) -> ExtractedField:
        """Extract invoice number using regex patterns."""
        labels = labels or ["invoice", "inv", "invoice no", "invoice #", "invoice number"]
        return self._extract_with_patterns(
            ocr_result,
            INVOICE_NUMBER_PATTERNS,
            labels,
            "invoice_number",
        )
    
    def extract_po_number(
        self,
        ocr_result,
        labels: list[str] | None = None,
    ) -> ExtractedField:
        """Extract purchase order number."""
        labels = labels or ["po", "purchase order", "po #", "order"]
        return self._extract_with_patterns(
            ocr_result,
            PO_NUMBER_PATTERNS,
            labels,
            "po_number",
        )
    
    def extract_delivery_reference(
        self,
        ocr_result,
        labels: list[str] | None = None,
    ) -> ExtractedField:
        """Extract delivery reference number."""
        labels = labels or ["delivery", "del", "receipt", "reference"]
        return self._extract_with_patterns(
            ocr_result,
            DELIVERY_REF_PATTERNS,
            labels,
            "delivery_reference",
        )
    
    def extract_amount(
        self,
        ocr_result,
        labels: list[str],
        prefer_largest: bool = False,
    ) -> ExtractedField:
        """
        Extract monetary amount.
        
        Args:
            ocr_result: OCR output
            labels: Labels to search near (e.g., ["total", "amount due"])
            prefer_largest: If True, return largest amount found near labels
        """
        full_text = ocr_result.full_text
        
        # Find all amounts in the text
        all_amounts: list[tuple[Decimal, float, str]] = []  # (value, confidence, raw)
        
        for pattern in AMOUNT_PATTERNS:
            for match in re.finditer(pattern, full_text, re.IGNORECASE):
                try:
                    raw_value = match.group(1)
                    # Clean and parse
                    cleaned = raw_value.replace(',', '').replace('$', '').strip()
                    if cleaned and cleaned != '.':
                        amount = Decimal(cleaned)
                        if amount > 0:
                            all_amounts.append((amount, 0.85, raw_value))
                except (InvalidOperation, ValueError, IndexError):
                    continue
        
        if not all_amounts:
            logger.debug("No amounts found in text")
            return ExtractedField(value=Decimal("0"), confidence=0.0, raw_text="")
        
        # Find amounts near labels
        scored_amounts: list[tuple[Decimal, float, str]] = []
        
        for label in labels:
            label_pos = full_text.lower().find(label.lower())
            if label_pos == -1:
                continue
            
            # Get text window after label
            window_text = full_text[label_pos:label_pos + 200]
            
            for pattern in AMOUNT_PATTERNS:
                for match in re.finditer(pattern, window_text, re.IGNORECASE):
                    try:
                        raw_value = match.group(1)
                        cleaned = raw_value.replace(',', '').replace('$', '').strip()
                        if cleaned and cleaned != '.':
                            amount = Decimal(cleaned)
                            if amount > 0:
                                # Higher confidence for amounts near labels
                                scored_amounts.append((amount, 0.95, raw_value))
                    except (InvalidOperation, ValueError, IndexError):
                        continue
        
        # Pick the best amount
        if scored_amounts:
            if prefer_largest:
                best = max(scored_amounts, key=lambda x: x[0])
            else:
                best = max(scored_amounts, key=lambda x: x[1])
            
            logger.info(f"Amount extracted: {best[0]} (conf: {best[1]:.0%}, raw: '{best[2]}')")
            return ExtractedField(value=best[0], confidence=best[1], raw_text=best[2])
        
        # Fallback to any amount found
        if all_amounts:
            best = max(all_amounts, key=lambda x: x[0])  # Largest amount
            logger.warning(f"Amount from fallback (no label match): {best[0]}")
            return ExtractedField(value=best[0], confidence=0.6, raw_text=best[2])
        
        return ExtractedField(value=Decimal("0"), confidence=0.0, raw_text="")
    
    def extract_date(
        self,
        ocr_result,
        labels: list[str],
    ) -> ExtractedField:
        """
        Extract date field.
        
        Tries multiple date formats and returns the best match near labels.
        Uses exact label matching to avoid confusing "Due Date" with "Date".
        """
        full_text = ocr_result.full_text
        
        # Find all dates in the text with their positions
        all_dates: list[tuple[date, float, str, int]] = []  # (date, conf, raw, position)
        
        for pattern, fmt in DATE_PATTERNS:
            for match in re.finditer(pattern, full_text, re.IGNORECASE):
                try:
                    raw_value = match.group(1)
                    # Normalize separators and newlines
                    normalized = raw_value.replace('-', '/').replace(',', '').replace('\n', ' ')
                    
                    # Try parsing with the expected format
                    parsed = None
                    for try_fmt in [fmt, '%B %d %Y', '%b %d %Y', '%m/%d/%Y', '%Y/%m/%d']:
                        try:
                            parsed = datetime.strptime(normalized, try_fmt).date()
                            break
                        except ValueError:
                            continue
                    
                    if parsed:
                        all_dates.append((parsed, 0.85, raw_value, match.start()))
                except (ValueError, IndexError):
                    continue
        
        if not all_dates:
            logger.debug("No dates found in text")
            return ExtractedField(value=date.today(), confidence=0.0, raw_text="")
        
        # Find dates near labels - use EXACT label matching with position
        # Sort labels by specificity (longer = more specific = check first)
        sorted_labels = sorted(labels, key=len, reverse=True)
        
        for label in sorted_labels:
            # Find the label in text
            label_lower = label.lower()
            text_lower = full_text.lower()
            label_pos = text_lower.find(label_lower)
            
            if label_pos == -1:
                continue
            
            # Find the closest date AFTER this label
            dates_after_label = [
                (d, conf, raw, pos) 
                for d, conf, raw, pos in all_dates 
                if pos > label_pos and pos < label_pos + 150  # Within 150 chars
            ]
            
            if dates_after_label:
                # Get the closest one
                closest = min(dates_after_label, key=lambda x: x[3] - label_pos)
                logger.info(f"Date extracted for '{label}': {closest[0]} (raw: '{closest[2][:20]}')")
                return ExtractedField(value=closest[0], confidence=0.95, raw_text=closest[2])
        
        # Fallback to first date found
        if all_dates:
            best = all_dates[0]
            logger.warning(f"Date from fallback (no label match): {best[0]}")
            return ExtractedField(value=best[0], confidence=0.6, raw_text=best[2])
        
        return ExtractedField(value=date.today(), confidence=0.0, raw_text="")
    
    def extract_quantity(
        self,
        ocr_result,
        labels: list[str],
    ) -> ExtractedField:
        """Extract quantity/count field."""
        full_text = ocr_result.full_text
        
        # Find quantities near labels
        for label in labels:
            label_pos = full_text.lower().find(label.lower())
            if label_pos == -1:
                continue
            
            window_text = full_text[label_pos:label_pos + 100]
            
            for pattern in QUANTITY_PATTERNS:
                match = re.search(pattern, window_text, re.IGNORECASE)
                if match:
                    try:
                        qty = Decimal(match.group(1))
                        logger.info(f"Quantity extracted: {qty}")
                        return ExtractedField(value=qty, confidence=0.9, raw_text=match.group(1))
                    except (InvalidOperation, ValueError):
                        continue
        
        # Fallback: find any number after labels
        for label in labels:
            label_pos = full_text.lower().find(label.lower())
            if label_pos == -1:
                continue
            
            window_text = full_text[label_pos:label_pos + 50]
            match = re.search(r'(\d+)', window_text)
            if match:
                try:
                    qty = Decimal(match.group(1))
                    return ExtractedField(value=qty, confidence=0.7, raw_text=match.group(1))
                except (InvalidOperation, ValueError):
                    continue
        
        return ExtractedField(value=Decimal("0"), confidence=0.0, raw_text="")
    
    def extract_name(
        self,
        ocr_result,
        labels: list[str],
    ) -> ExtractedField:
        """Extract a company/person name near labels, stripping label prefixes.
        
        Handles InvoiceNow format: Bill To/Ship To sections, footer company names.
        """
        blocks = ocr_result.all_blocks
        full_text = ocr_result.full_text
        
        # Common label parts to strip from names
        label_prefixes = [
            '(seller):', '(buyer):', 'seller:', 'buyer:', 
            'from:', 'to:', 'vendor:', 'customer:', 'company:',
            'bill to:', 'ship to:', 'sold by:', 'sold to:',
            'from (buyer):', 'to (vendor):', 'deliver to:',
            'from (shipper):', 'shipper:', 'recipient:',
        ]
        
        # Words to skip - document headers and formatting
        skip_words = [
            'tax', 'invoice', 'purchase', 'order', 'delivery', 'proof',
            'gst', 'reg', 'page', 'date', 'number', 'no', 'total',
            'p.o.', 'po-', 'del-', 'inv-',  # Reference number prefixes
        ]
        
        # Pattern for reference numbers to skip
        import re
        ref_pattern = re.compile(r'^[A-Z]{2,4}[-\s]?[A-Z0-9]{2,4}[-\s]?\d{3,}', re.IGNORECASE)
        
        for i, block in enumerate(blocks):
            text_lower = block.text.lower().strip()
            
            for label in labels:
                if label.lower() in text_lower:
                    # Get the next few blocks as potential names
                    name_parts = []
                    total_conf = 0
                    
                    for j in range(i + 1, min(i + 6, len(blocks))):
                        next_block = blocks[j]
                        next_text = next_block.text.strip()
                        next_lower = next_text.lower()
                        
                        # Stop at common delimiters
                        if any(kw in next_lower for kw in ['date:', 'invoice no', 'po:', 'total:', 'amount:', 'qty:', 'phone:', 'fax:']):
                            break
                        
                        # Skip short words that are likely labels
                        if len(next_text) <= 2:
                            continue
                        
                        # Skip if it's just a label prefix
                        if next_lower.rstrip(':') in ['seller', 'buyer', 'from', 'to', 'vendor', 'customer', 'ship', 'bill']:
                            continue
                        
                        # Skip document header words and reference prefixes
                        if any(skip in next_lower for skip in skip_words):
                            continue
                        
                        # Skip reference numbers (e.g., PO-SG-2023-001)
                        if ref_pattern.match(next_text):
                            continue
                            
                        # Clean the part - remove label prefixes
                        cleaned = next_text
                        for prefix in label_prefixes:
                            if cleaned.lower().startswith(prefix):
                                cleaned = cleaned[len(prefix):].strip()
                        
                        if cleaned and len(cleaned) > 1:
                            name_parts.append(cleaned)
                            total_conf += next_block.confidence
                    
                    if name_parts:
                        name = ' '.join(name_parts[:3])  # Max 3 parts
                        avg_conf = total_conf / len(name_parts)
                        logger.info(f"Name extracted for '{label}': '{name}' (conf: {avg_conf:.0%})")
                        return ExtractedField(value=name, confidence=avg_conf, raw_text=name)
        
        # Fallback: Look for company name patterns (e.g., "XYZ PTE LTD" at end)
        company_patterns = [
            r'([A-Z][A-Z\s]+(?:PTE\.?\s*LTD\.?|LTD\.?|INC\.?|CORP\.?|LLC))',  # CLEARWATER PTE LTD
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s+(?:Ltd|Inc|Corp|LLC))',  # Acme Supplies Ltd
        ]
        
        for pattern in company_patterns:
            matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
            if matches:
                # Return the first company name found
                name = matches[0].group(1).strip()
                logger.info(f"Name extracted via pattern: '{name}'")
                return ExtractedField(value=name, confidence=0.75, raw_text=name)
        
        return ExtractedField(value="UNKNOWN", confidence=0.0, raw_text="")

    
    def _extract_with_patterns(
        self,
        ocr_result,
        patterns: list[str],
        labels: list[str],
        field_name: str,
    ) -> ExtractedField:
        """Generic extraction using regex patterns + label proximity."""
        full_text = ocr_result.full_text
        
        # Find all matches for all patterns
        all_matches: list[PatternMatch] = []
        
        for pattern in patterns:
            for match in re.finditer(pattern, full_text, re.IGNORECASE):
                try:
                    value = match.group(1)
                    if value and len(value) >= 2:  # Minimum length
                        all_matches.append(PatternMatch(
                            value=value,
                            pattern=pattern,
                            start=match.start(),
                            end=match.end(),
                            confidence=0.85,
                        ))
                except IndexError:
                    continue
        
        if not all_matches:
            logger.warning(f"No {field_name} patterns matched")
            return ExtractedField(value="UNKNOWN", confidence=0.0, raw_text="")
        
        # Boost confidence for matches near labels
        for label in labels:
            label_pos = full_text.lower().find(label.lower())
            if label_pos == -1:
                continue
            
            for match in all_matches:
                # If match is within 100 chars of label, boost confidence
                distance = abs(match.start - label_pos)
                if distance < 100:
                    match.confidence = min(0.98, match.confidence + 0.1)
        
        # Pick the best match
        best = max(all_matches, key=lambda m: m.confidence)
        
        logger.info(f"{field_name} extracted: '{best.value}' (conf: {best.confidence:.0%})")
        return ExtractedField(value=best.value, confidence=best.confidence, raw_text=best.value)
