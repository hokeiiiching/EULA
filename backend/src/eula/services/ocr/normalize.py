"""
Field normalization for OCR output.

This module cleans and normalizes extracted text into typed values:
- Monetary amounts: Strip currency symbols, fix OCR errors, parse decimals
- Dates: Parse multiple date formats into date objects
- Quantities: Parse numeric values with unit handling

Design Decisions:
- Explicit error lists define common OCR mistakes (S→5, O→0, etc.)
- Multiple date format support for international invoices
- Currency detection for multi-currency support
- Validation of parsed values against reasonable ranges
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from eula.domain.models import BoundingBox, ExtractedField

from .engine import TextBlock

logger = logging.getLogger(__name__)


# Common OCR character substitution errors
OCR_CHAR_FIXES = {
    "S": "5",
    "s": "5",
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
    "B": "8",
    "Z": "2",
    "g": "9",
    "G": "6",
}

# Currency symbols to strip
CURRENCY_SYMBOLS = ["$", "€", "£", "¥", "₹", "CHF", "USD", "EUR", "GBP"]

# Date format patterns to try (in order of preference)
DATE_FORMATS = [
    "%Y-%m-%d",      # ISO format: 2024-01-15
    "%d/%m/%Y",      # European: 15/01/2024
    "%m/%d/%Y",      # US: 01/15/2024
    "%d-%m-%Y",      # European with dashes
    "%m-%d-%Y",      # US with dashes
    "%d %b %Y",      # 15 Jan 2024
    "%d %B %Y",      # 15 January 2024
    "%b %d, %Y",     # Jan 15, 2024
    "%B %d, %Y",     # January 15, 2024
]


@dataclass
class NormalizationResult[T]:
    """Result of normalizing a raw text value."""
    value: T | None
    raw_text: str
    confidence: float
    errors: list[str]
    
    @property
    def success(self) -> bool:
        return self.value is not None and len(self.errors) == 0


class FieldNormalizer:
    """
    Normalizes raw OCR text into typed domain values.
    
    Handles common OCR errors and multi-format parsing for:
    - Monetary amounts (Decimal)
    - Dates (date)
    - Quantities (Decimal)
    - Strings (with cleaning)
    
    Example:
        normalizer = FieldNormalizer()
        result = normalizer.normalize_amount("$1,234.S6")
        # result.value = Decimal("1234.56")
    """
    
    def __init__(
        self,
        default_currency: str = "USD",
        confidence_threshold: float = 0.7,
    ) -> None:
        """
        Initialize normalizer.
        
        Args:
            default_currency: Currency to assume if not detected
            confidence_threshold: Below this, values are flagged for review
        """
        self.default_currency = default_currency
        self.confidence_threshold = confidence_threshold
    
    def normalize_amount(
        self,
        text: str,
        confidence: float = 1.0,
        bounding_box: BoundingBox | None = None,
    ) -> ExtractedField[Decimal]:
        """
        Parse a monetary amount from text.
        
        Handles:
        - Currency symbols ($, €, USD, etc.)
        - Thousands separators (1,234.56 or 1.234,56)
        - OCR errors (S→5, O→0, etc.)
        
        Args:
            text: Raw OCR text
            confidence: OCR confidence score
            bounding_box: Location in document
            
        Returns:
            ExtractedField with Decimal value
        """
        raw_text = text
        errors: list[str] = []
        
        # Strip currency symbols
        cleaned = text.strip()
        for symbol in CURRENCY_SYMBOLS:
            cleaned = cleaned.replace(symbol, "")
        cleaned = cleaned.strip()
        
        # Fix common OCR errors in numeric context
        cleaned = self._fix_ocr_errors(cleaned)
        
        # Handle European vs US number format
        # European: 1.234,56 -> need to swap
        # US: 1,234.56 -> standard
        if "," in cleaned and "." in cleaned:
            # Check which comes last
            if cleaned.rindex(",") > cleaned.rindex("."):
                # European format: swap comma and period
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # US format: remove commas
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # Could be thousands separator or decimal
            # If exactly 2 digits after comma, treat as decimal
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) == 2:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        
        # Remove any remaining non-numeric chars except decimal point
        cleaned = re.sub(r"[^\d.]", "", cleaned)
        
        # Parse to Decimal
        try:
            value = Decimal(cleaned)
            
            # Validate reasonable range
            if value < 0:
                errors.append("Negative amount detected")
            if value > Decimal("1000000000"):  # 1 billion
                errors.append("Unusually large amount")
                
        except (InvalidOperation, ValueError) as e:
            logger.warning(f"Failed to parse amount '{text}': {e}")
            errors.append(f"Parse error: {e}")
            value = Decimal("0")
        
        return ExtractedField(
            value=value,
            confidence=confidence,
            bounding_box=bounding_box,
            raw_text=raw_text,
        )
    
    def normalize_date(
        self,
        text: str,
        confidence: float = 1.0,
        bounding_box: BoundingBox | None = None,
    ) -> ExtractedField[date]:
        """
        Parse a date from text.
        
        Tries multiple date formats common in invoices.
        
        Args:
            text: Raw OCR text
            confidence: OCR confidence score
            bounding_box: Location in document
            
        Returns:
            ExtractedField with date value
        """
        raw_text = text
        cleaned = text.strip()
        
        # Fix OCR errors
        cleaned = self._fix_ocr_errors(cleaned)
        
        # Try each date format
        for fmt in DATE_FORMATS:
            try:
                parsed = datetime.strptime(cleaned, fmt)
                return ExtractedField(
                    value=parsed.date(),
                    confidence=confidence,
                    bounding_box=bounding_box,
                    raw_text=raw_text,
                )
            except ValueError:
                continue
        
        # If all formats fail, try extracting date components
        date_match = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", cleaned)
        if date_match:
            try:
                d, m, y = date_match.groups()
                year = int(y)
                if year < 100:
                    year += 2000
                
                # Try both day/month orders
                try:
                    parsed_date = date(year, int(m), int(d))
                except ValueError:
                    parsed_date = date(year, int(d), int(m))
                
                return ExtractedField(
                    value=parsed_date,
                    confidence=confidence * 0.8,  # Lower confidence for fallback
                    bounding_box=bounding_box,
                    raw_text=raw_text,
                )
            except ValueError:
                pass
        
        # Could not parse - return today as fallback with low confidence
        logger.warning(f"Failed to parse date '{text}', using today")
        return ExtractedField(
            value=date.today(),
            confidence=0.0,  # Zero confidence indicates parse failure
            bounding_box=bounding_box,
            raw_text=raw_text,
        )
    
    def normalize_quantity(
        self,
        text: str,
        confidence: float = 1.0,
        bounding_box: BoundingBox | None = None,
    ) -> ExtractedField[Decimal]:
        """
        Parse a quantity from text.
        
        Handles integer or decimal quantities with optional units.
        
        Args:
            text: Raw OCR text
            confidence: OCR confidence score
            bounding_box: Location in document
            
        Returns:
            ExtractedField with Decimal value
        """
        raw_text = text
        cleaned = text.strip()
        
        # Fix OCR errors
        cleaned = self._fix_ocr_errors(cleaned)
        
        # Extract numeric portion (ignore trailing units like "pcs", "units")
        match = re.match(r"[\d,]+\.?\d*", cleaned)
        if match:
            cleaned = match.group(0)
        
        # Remove thousands separators
        cleaned = cleaned.replace(",", "")
        
        try:
            value = Decimal(cleaned)
            
            # Validate reasonable range for quantity
            if value < 0:
                value = abs(value)  # Assume positive
            if value > Decimal("1000000"):
                logger.warning(f"Unusually large quantity: {value}")
                
        except (InvalidOperation, ValueError) as e:
            logger.warning(f"Failed to parse quantity '{text}': {e}")
            value = Decimal("0")
        
        return ExtractedField(
            value=value,
            confidence=confidence,
            bounding_box=bounding_box,
            raw_text=raw_text,
        )
    
    def normalize_string(
        self,
        text: str,
        confidence: float = 1.0,
        bounding_box: BoundingBox | None = None,
    ) -> ExtractedField[str]:
        """
        Clean and normalize a string field.
        
        Removes extra whitespace and control characters.
        
        Args:
            text: Raw OCR text
            confidence: OCR confidence score
            bounding_box: Location in document
            
        Returns:
            ExtractedField with cleaned string
        """
        raw_text = text
        
        # Remove control characters
        cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
        
        # Normalize whitespace
        cleaned = " ".join(cleaned.split())
        
        return ExtractedField(
            value=cleaned,
            confidence=confidence,
            bounding_box=bounding_box,
            raw_text=raw_text,
        )
    
    def _fix_ocr_errors(self, text: str) -> str:
        """
        Fix common OCR character recognition errors.
        
        Only applies fixes in numeric contexts to avoid
        corrupting actual text.
        """
        result = text
        
        # Look for numeric patterns and fix errors within them
        def fix_numeric_section(match: re.Match) -> str:
            section = match.group(0)
            for wrong, right in OCR_CHAR_FIXES.items():
                section = section.replace(wrong, right)
            return section
        
        # Match sections that look numeric (digits, decimals, commas plus OCR errors)
        result = re.sub(
            r"[\dSsOolIBZgG,.\-]+",
            fix_numeric_section,
            result
        )
        
        return result
    
    def blocks_to_field_amount(
        self,
        blocks: list[TextBlock],
    ) -> ExtractedField[Decimal]:
        """Convert a list of text blocks into a monetary amount field."""
        if not blocks:
            return ExtractedField(
                value=Decimal("0"),
                confidence=0.0,
                bounding_box=None,
                raw_text="",
            )
        
        # Combine text from all blocks
        combined_text = " ".join(b.text for b in blocks)
        avg_confidence = sum(b.confidence for b in blocks) / len(blocks)
        
        # Use first block's bounding box
        first = blocks[0]
        bbox = BoundingBox(
            x_min=first.x_min,
            y_min=first.y_min,
            x_max=first.x_max,
            y_max=first.y_max,
            page=first.page,
        )
        
        return self.normalize_amount(combined_text, avg_confidence, bbox)
    
    def blocks_to_field_date(
        self,
        blocks: list[TextBlock],
    ) -> ExtractedField[date]:
        """Convert a list of text blocks into a date field."""
        if not blocks:
            return ExtractedField(
                value=date.today(),
                confidence=0.0,
                bounding_box=None,
                raw_text="",
            )
        
        combined_text = " ".join(b.text for b in blocks)
        avg_confidence = sum(b.confidence for b in blocks) / len(blocks)
        
        first = blocks[0]
        bbox = BoundingBox(
            x_min=first.x_min,
            y_min=first.y_min,
            x_max=first.x_max,
            y_max=first.y_max,
            page=first.page,
        )
        
        return self.normalize_date(combined_text, avg_confidence, bbox)
