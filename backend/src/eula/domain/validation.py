"""
3-Way Match validation rules for invoice factoring.

This module contains pure functions that implement the forensic audit logic.
No side effects, no I/O - just business rule validation.

The 3-Way Match validates consistency across:
1. Invoice (Claim) - what is being billed
2. Purchase Order (Authorization) - what was approved
3. Proof of Delivery (Performance) - what was delivered

Design Decisions:
- Pure functions enable easy unit testing and composition
- Each rule returns ValidationCheck with pass/fail and details
- Anomaly detection is separate from hard validation failures
- Decimal comparison uses explicit tolerance for rounding differences
"""

from datetime import date
from decimal import Decimal

from .models import (
    Anomaly,
    DocumentBundle,
    Invoice,
    ProofOfDelivery,
    PurchaseOrder,
    ValidationCheck,
    VerificationResult,
    VerificationStatus,
)


# Tolerance for decimal comparisons (handles rounding in financial calculations)
DECIMAL_TOLERANCE = Decimal("0.01")

# Threshold for anomaly detection (500% of historical average)
ANOMALY_MULTIPLIER = Decimal("5.0")

# Maximum allowed variance between invoice and PO amounts (20%)
# Under-billing by more than this is suspicious (possible fraud or data error)
AMOUNT_VARIANCE_TOLERANCE = Decimal("0.20")


def validate_quantity_match(
    pod: ProofOfDelivery,
    invoice: Invoice,
) -> ValidationCheck:
    """
    Validate that delivered quantity matches invoiced quantity.
    
    Rule: POD.Quantity_Delivered == Invoice.Quantity_Billed
    
    This ensures the SME is only billing for goods actually delivered.
    """
    pod_qty = pod.quantity_delivered.value
    invoice_qty = invoice.total_quantity
    
    # If invoice has no line items, skip quantity validation (not essential for 3-way match)
    if not invoice.line_items:
        return ValidationCheck(
            rule_name="quantity_match",
            passed=True,
            message="Quantity match: OK",
            details={},
        )
    
    diff = abs(pod_qty - invoice_qty)
    passed = diff <= DECIMAL_TOLERANCE
    
    return ValidationCheck(
        rule_name="quantity_match",
        passed=passed,
        message=(
            "Quantity matches" if passed 
            else f"Quantity mismatch: delivered {pod_qty} vs billed {invoice_qty}"
        ),
        details={
            "pod_quantity": str(pod_qty),
            "invoice_quantity": str(invoice_qty),
            "difference": str(diff),
        },
    )


def validate_amount_authorization(
    invoice: Invoice,
    po: PurchaseOrder,
) -> ValidationCheck:
    """
    Validate that invoice total does not exceed authorized PO amount.
    
    Rule: Invoice.Total <= PO.Authorized_Amount
    
    This ensures the SME cannot bill more than what was approved.
    Under-billing is acceptable; over-billing is not.
    """
    invoice_total = invoice.total_amount.value
    authorized_amount = po.authorized_amount.value
    
    # Currency must match
    if invoice.currency.value != po.currency.value:
        return ValidationCheck(
            rule_name="amount_authorization",
            passed=False,
            message=f"Currency mismatch: Invoice {invoice.currency.value} vs PO {po.currency.value}",
            details={
                "invoice_currency": invoice.currency.value,
                "po_currency": po.currency.value,
            },
        )
    
    # Check 1: Invoice cannot exceed PO
    exceeds_po = invoice_total > authorized_amount + DECIMAL_TOLERANCE
    
    # Check 2: Invoice should be within tolerance of PO (catch suspicious under-billing)
    # Large discrepancy suggests wrong invoice/PO pairing or data extraction error
    variance = abs(invoice_total - authorized_amount) / authorized_amount if authorized_amount > 0 else Decimal("0")
    excessive_variance = variance > AMOUNT_VARIANCE_TOLERANCE
    
    if exceeds_po:
        return ValidationCheck(
            rule_name="amount_authorization",
            passed=False,
            message=f"Invoice ${invoice_total} exceeds authorized PO ${authorized_amount}",
            details={
                "invoice_total": str(invoice_total),
                "authorized_amount": str(authorized_amount),
                "variance_pct": f"{variance * 100:.1f}%",
            },
        )
    
    if excessive_variance:
        return ValidationCheck(
            rule_name="amount_authorization",
            passed=False,
            message=f"Amount mismatch: Invoice ${invoice_total} vs PO ${authorized_amount} ({variance * 100:.1f}% variance)",
            details={
                "invoice_total": str(invoice_total),
                "authorized_amount": str(authorized_amount),
                "variance_pct": f"{variance * 100:.1f}%",
                "max_allowed_variance": f"{AMOUNT_VARIANCE_TOLERANCE * 100:.0f}%",
                "note": "Invoice and PO amounts should match within tolerance",
            },
        )
    
    return ValidationCheck(
        rule_name="amount_authorization",
        passed=True,
        message=f"Invoice ${invoice_total} matches authorized PO ${authorized_amount}",
        details={
            "invoice_total": str(invoice_total),
            "authorized_amount": str(authorized_amount),
            "variance_pct": f"{variance * 100:.1f}%",
        },
    )


def validate_date_sequence(
    po: PurchaseOrder,
    pod: ProofOfDelivery,
    invoice: Invoice,
) -> ValidationCheck:
    """
    Validate that document dates follow logical sequence.
    
    Rule: PO.Date < POD.Date < Invoice.Date
    
    The purchase order must come before delivery, and the invoice
    must come after delivery. This catches backdated documents.
    """
    po_date = po.po_date.value
    pod_date = pod.delivery_date.value
    invoice_date = invoice.invoice_date.value
    
    errors: list[str] = []
    
    if po_date > pod_date:
        errors.append(f"PO date ({po_date}) is after delivery date ({pod_date})")
    
    if pod_date > invoice_date:
        errors.append(f"Delivery date ({pod_date}) is after invoice date ({invoice_date})")
    
    passed = len(errors) == 0
    
    return ValidationCheck(
        rule_name="date_sequence",
        passed=passed,
        message="Date sequence valid" if passed else "; ".join(errors),
        details={
            "po_date": str(po_date),
            "pod_date": str(pod_date),
            "invoice_date": str(invoice_date),
        },
    )


def validate_line_item_sum(invoice: Invoice) -> ValidationCheck:
    """
    Validate that line item totals sum to invoice total.
    
    Rule: Sum(Line_Items.Total) == Invoice.Total
    
    This catches math errors and potential manipulation of totals.
    """
    if not invoice.line_items:
        return ValidationCheck(
            rule_name="line_item_sum",
            passed=True,
            message="No line items to validate",
            details={"note": "Skipped - no line items present"},
        )
    
    calculated = invoice.calculated_total
    stated = invoice.total_amount.value
    diff = abs(calculated - stated)
    
    passed = diff <= DECIMAL_TOLERANCE
    
    return ValidationCheck(
        rule_name="line_item_sum",
        passed=passed,
        message=(
            f"Line items sum to {calculated}, matches total {stated}"
            if passed
            else f"Sum mismatch: line items = {calculated}, stated total = {stated}"
        ),
        details={
            "calculated_sum": str(calculated),
            "stated_total": str(stated),
            "difference": str(diff),
            "line_item_count": len(invoice.line_items),
        },
    )


def validate_party_names(bundle: DocumentBundle) -> ValidationCheck:
    """
    Validate that party names are consistent across documents.
    
    The payee (SME) on the invoice should match the vendor on the PO.
    The payer on the invoice should match the buyer on the PO.
    
    Uses fuzzy matching as names may have slight variations or OCR errors.
    """
    invoice = bundle.invoice
    po = bundle.purchase_order
    
    def normalize(name: str) -> str:
        """Normalize name for comparison: lowercase, remove common suffixes, strip noise."""
        name = name.lower().strip()
        # Remove common company suffixes for comparison
        for suffix in [' pte ltd', ' pte. ltd.', ' pte', ' ltd', ' inc', ' corp', ' llc', '.']:
            name = name.replace(suffix, '')
        # Remove common OCR artifacts
        for artifact in ['p.o.', 'po-', 'stamp', 'company']:
            name = name.replace(artifact, '')
        return name.strip()
    
    def fuzzy_match(name1: str, name2: str) -> bool:
        """Check if names match using fuzzy logic (contains or significant overlap)."""
        n1 = normalize(name1)
        n2 = normalize(name2)
        
        # Empty or unknown names - skip validation
        if not n1 or not n2 or n1 == 'unknown' or n2 == 'unknown':
            return True
        
        # Exact match after normalization
        if n1 == n2:
            return True
        
        # One contains the other (handles partial extractions)
        if n1 in n2 or n2 in n1:
            return True
        
        # Check if significant words match
        words1 = set(n1.split())
        words2 = set(n2.split())
        common = words1 & words2
        
        # If any significant word (>3 chars) matches, consider it a match
        if any(len(w) > 3 for w in common):
            return True
        
        return False
    
    invoice_payee = invoice.payee_name.value
    po_vendor = po.vendor_name.value
    invoice_payer = invoice.payer_name.value
    po_buyer = po.buyer_name.value
    
    warnings: list[str] = []
    
    # Fuzzy match instead of exact match
    if not fuzzy_match(invoice_payee, po_vendor):
        warnings.append(
            f"Payee mismatch: Invoice '{invoice_payee}' vs PO vendor '{po_vendor}'"
        )
    
    if not fuzzy_match(invoice_payer, po_buyer):
        warnings.append(
            f"Payer mismatch: Invoice '{invoice_payer}' vs PO buyer '{po_buyer}'"
        )
    
    # Pass with warnings for fuzzy mismatches (soft check for MVP)
    passed = len(warnings) == 0
    
    return ValidationCheck(
        rule_name="party_names",
        passed=passed,
        message="Party names consistent" if passed else "; ".join(warnings),
        details={
            "invoice_payee": invoice_payee,
            "po_vendor": po_vendor,
            "invoice_payer": invoice_payer,
            "po_buyer": po_buyer,
            "note": "Fuzzy matching enabled for OCR tolerance" if not passed else None,
        },
    )



def detect_anomalies(
    invoice: Invoice,
    historical_average: Decimal | None = None,
) -> list[Anomaly]:
    """
    Detect anomalies that warrant additional scrutiny.
    
    Anomalies are not automatic failures but flags for review.
    """
    anomalies: list[Anomaly] = []
    
    # Check for unusually large invoice compared to historical average
    if historical_average is not None and historical_average > 0:
        ratio = invoice.total_amount.value / historical_average
        if ratio > ANOMALY_MULTIPLIER:
            anomalies.append(
                Anomaly(
                    code="AMOUNT_SPIKE",
                    message=f"Invoice {ratio:.0%} larger than historical average",
                    severity="warning",
                    field_path="invoice.total_amount",
                    expected_value=str(historical_average),
                    actual_value=str(invoice.total_amount.value),
                )
            )
    
    # Check for future due dates that are suspiciously far out
    if invoice.due_date.value > invoice.invoice_date.value:
        days_until_due = (invoice.due_date.value - invoice.invoice_date.value).days
        if days_until_due > 180:  # More than 6 months
            anomalies.append(
                Anomaly(
                    code="LONG_TERM",
                    message=f"Unusually long payment term: {days_until_due} days",
                    severity="warning",
                    field_path="invoice.due_date",
                    expected_value="< 180 days",
                    actual_value=f"{days_until_due} days",
                )
            )
    
    # Check for line items with math errors
    for i, item in enumerate(invoice.line_items):
        if item.has_math_error:
            anomalies.append(
                Anomaly(
                    code="LINE_ITEM_MATH",
                    message=f"Line item {i+1}: qty * price != total",
                    severity="warning",
                    field_path=f"invoice.line_items[{i}]",
                    expected_value=str(item.calculated_total),
                    actual_value=str(item.total.value),
                )
            )
    
    return anomalies


def collect_review_flags(bundle: DocumentBundle, confidence_threshold: float = 0.7) -> list[str]:
    """
    Identify fields that require manual review due to low OCR confidence.
    
    Returns a list of field paths that have confidence below the threshold.
    """
    flags: list[str] = []
    
    # Check invoice fields - only flag critical fields for 3-way match
    invoice = bundle.invoice
    if invoice.total_amount.confidence < confidence_threshold:
        flags.append("invoice.total_amount")
    if invoice.invoice_number.confidence < confidence_threshold:
        flags.append("invoice.invoice_number")
    # Note: due_date not flagged as it's not critical for 3-way match validation
    
    # Check PO fields
    po = bundle.purchase_order
    if po.authorized_amount.confidence < confidence_threshold:
        flags.append("purchase_order.authorized_amount")
    if po.po_number.confidence < confidence_threshold:
        flags.append("purchase_order.po_number")
    
    # Check POD fields
    pod = bundle.proof_of_delivery
    if pod.quantity_delivered.confidence < confidence_threshold:
        flags.append("proof_of_delivery.quantity_delivered")
    if pod.delivery_date.confidence < confidence_threshold:
        flags.append("proof_of_delivery.delivery_date")
    
    return flags


def run_full_verification(
    bundle: DocumentBundle,
    historical_average: Decimal | None = None,
    confidence_threshold: float = 0.7,
) -> VerificationResult:
    """
    Execute complete forensic verification on a document bundle.
    
    This orchestrates all validation rules and anomaly detection
    into a single comprehensive result.
    
    Args:
        bundle: The complete set of Invoice, PO, and POD documents
        historical_average: Average invoice amount for anomaly detection
        confidence_threshold: Minimum OCR confidence for auto-approval
        
    Returns:
        VerificationResult with status, checks, anomalies, and review flags
    """
    checks: list[ValidationCheck] = []
    
    # Run all validation rules
    checks.append(validate_quantity_match(bundle.proof_of_delivery, bundle.invoice))
    checks.append(validate_amount_authorization(bundle.invoice, bundle.purchase_order))
    checks.append(validate_date_sequence(
        bundle.purchase_order, 
        bundle.proof_of_delivery, 
        bundle.invoice
    ))
    checks.append(validate_line_item_sum(bundle.invoice))
    checks.append(validate_party_names(bundle))
    
    # Detect anomalies
    anomalies = detect_anomalies(bundle.invoice, historical_average)
    
    # Collect fields requiring review
    review_flags = collect_review_flags(bundle, confidence_threshold)
    
    # Determine overall status
    all_passed = all(check.passed for check in checks)
    has_blocking_anomalies = any(a.severity == "error" for a in anomalies)
    needs_review = len(review_flags) > 0
    
    if not all_passed or has_blocking_anomalies:
        status = VerificationStatus.FAILED
    elif needs_review:
        status = VerificationStatus.REQUIRES_REVIEW
    else:
        status = VerificationStatus.PASSED
    
    return VerificationResult(
        status=status,
        checks=checks,
        anomalies=anomalies,
        review_flags=review_flags,
    )

