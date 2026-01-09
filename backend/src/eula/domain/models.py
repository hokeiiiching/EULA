"""
Domain models for supply chain document verification.

These models represent the core business entities extracted from documents.
Each model includes confidence scores and bounding box information from OCR
to support manual review workflows for low-confidence extractions.

Design Decisions:
- Using dataclasses for immutable, typed domain objects
- ExtractedField wrapper provides OCR metadata without polluting business logic  
- Separate models for each document type to enforce distinct validation rules
- Decimal for all monetary values to avoid floating-point errors
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any


class DocumentType(Enum):
    """Types of documents in the 3-way match process."""
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    PROOF_OF_DELIVERY = "proof_of_delivery"


class VerificationStatus(Enum):
    """Overall verification status for a document bundle."""
    PENDING = "pending"
    PROCESSING = "processing"
    PASSED = "passed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True)
class BoundingBox:
    """
    Bounding box coordinates from OCR.
    
    Coordinates are normalized to 0-1 range relative to page dimensions.
    This allows consistent positioning across different document sizes.
    """
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    page: int = 0

    def __post_init__(self) -> None:
        """Validate coordinate ranges."""
        if not (0 <= self.x_min <= self.x_max <= 1):
            raise ValueError(f"Invalid x coordinates: {self.x_min}, {self.x_max}")
        if not (0 <= self.y_min <= self.y_max <= 1):
            raise ValueError(f"Invalid y coordinates: {self.y_min}, {self.y_max}")


@dataclass(frozen=True)
class ExtractedField[T]:
    """
    A field extracted from a document via OCR.
    
    Wraps the actual value with metadata about extraction quality.
    This enables downstream logic to handle low-confidence fields
    differently (e.g., flagging for manual review).
    
    Type Parameters:
        T: The type of the extracted value (str, Decimal, date, etc.)
    """
    value: T
    confidence: float
    bounding_box: BoundingBox | None = None
    raw_text: str | None = None  # Original OCR text before normalization
    
    @property
    def requires_review(self) -> bool:
        """Flag if confidence is below typical acceptance threshold."""
        return self.confidence < 0.7
    
    def __post_init__(self) -> None:
        """Validate confidence range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0-1, got {self.confidence}")


@dataclass(frozen=True)
class LineItem:
    """
    A single line item from an invoice.
    
    Used for line-item sum validation: sum(line_items.total) == invoice.total
    """
    description: ExtractedField[str]
    quantity: ExtractedField[Decimal]
    unit_price: ExtractedField[Decimal]
    total: ExtractedField[Decimal]
    
    @property
    def calculated_total(self) -> Decimal:
        """Compute expected total from quantity * unit_price."""
        return self.quantity.value * self.unit_price.value
    
    @property
    def has_math_error(self) -> bool:
        """Check if line item total matches quantity * unit_price."""
        # Allow small rounding differences (< 1 cent)
        diff = abs(self.calculated_total - self.total.value)
        return diff > Decimal("0.01")


@dataclass(frozen=True)
class Invoice:
    """
    Invoice document - the claim for payment.
    
    This is the primary document in invoice factoring. The face value
    determines the financing amount, and the due date determines the term.
    """
    invoice_number: ExtractedField[str]
    total_amount: ExtractedField[Decimal]
    currency: ExtractedField[str]
    invoice_date: ExtractedField[date]
    due_date: ExtractedField[date]
    payee_name: ExtractedField[str]  # The SME receiving payment
    payer_name: ExtractedField[str]  # The debtor owing payment
    line_items: list[LineItem] = field(default_factory=list)
    
    @property
    def total_quantity(self) -> Decimal:
        """Sum of all line item quantities."""
        return sum((item.quantity.value for item in self.line_items), Decimal(0))
    
    @property
    def calculated_total(self) -> Decimal:
        """Sum of all line item totals."""
        return sum((item.total.value for item in self.line_items), Decimal(0))
    
    @property
    def has_sum_mismatch(self) -> bool:
        """Check if line items sum to invoice total."""
        if not self.line_items:
            return False  # Can't validate without line items
        diff = abs(self.calculated_total - self.total_amount.value)
        return diff > Decimal("0.01")


@dataclass(frozen=True)
class PurchaseOrder:
    """
    Purchase Order - the authorization for goods/services.
    
    The PO establishes the maximum authorized amount and provides
    evidence that the transaction was pre-approved by the payer.
    """
    po_number: ExtractedField[str]
    authorized_amount: ExtractedField[Decimal]
    currency: ExtractedField[str]
    po_date: ExtractedField[date]
    buyer_name: ExtractedField[str]  # The payer
    vendor_name: ExtractedField[str]  # The SME
    
    # Optional: individual line items for detailed matching
    line_items: list[LineItem] = field(default_factory=list)
    
    @property
    def total_quantity(self) -> Decimal:
        """Sum of all line item quantities."""
        return sum((item.quantity.value for item in self.line_items), Decimal(0))


@dataclass(frozen=True)
class ProofOfDelivery:
    """
    Proof of Delivery - evidence that goods/services were received.
    
    The POD confirms that the SME fulfilled their obligation,
    which is required before the invoice becomes a valid receivable.
    """
    delivery_reference: ExtractedField[str]
    quantity_delivered: ExtractedField[Decimal]
    delivery_date: ExtractedField[date]
    recipient_name: ExtractedField[str]
    recipient_signature: bool = False  # Whether signature was detected
    
    # Link to PO if present on document
    po_reference: ExtractedField[str] | None = None


@dataclass(frozen=True)
class DocumentBundle:
    """
    A complete set of documents for 3-way match verification.
    
    All three documents must be present and consistent to pass
    the forensic audit and be eligible for tokenization.
    """
    invoice: Invoice
    purchase_order: PurchaseOrder
    proof_of_delivery: ProofOfDelivery
    
    # Document hashes for deduplication and tamper detection
    invoice_hash: str | None = None
    po_hash: str | None = None
    pod_hash: str | None = None


@dataclass(frozen=True) 
class Anomaly:
    """
    An anomaly detected during forensic analysis.
    
    Anomalies don't necessarily mean fraud - they flag items
    for additional scrutiny before tokenization.
    """
    code: str
    message: str
    severity: str  # "warning" or "error"
    field_path: str  # e.g., "invoice.total_amount"
    expected_value: Any | None = None
    actual_value: Any | None = None


@dataclass
class ValidationCheck:
    """
    Result of a single validation rule.
    
    Mutable because checks are built incrementally during validation.
    """
    rule_name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """
    Complete result of forensic verification on a document bundle.
    
    Aggregates all validation checks, anomalies, and determines
    the overall status for the bundle.
    """
    status: VerificationStatus
    checks: list[ValidationCheck] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    
    # Fields requiring manual review (low OCR confidence)
    review_flags: list[str] = field(default_factory=list)
    
    @property
    def all_checks_passed(self) -> bool:
        """True if all validation checks passed."""
        return all(check.passed for check in self.checks)
    
    @property
    def has_blocking_anomalies(self) -> bool:
        """True if any anomalies are severity 'error'."""
        return any(a.severity == "error" for a in self.anomalies)
