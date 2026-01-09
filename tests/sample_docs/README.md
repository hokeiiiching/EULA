# Test Documents for EULA 3-Way Match Verification

This directory contains sample documents for testing the EULA verification pipeline.

## Document Set 1: Valid Matching Documents

These documents should **PASS** the 3-way match verification.

### Invoice (invoice_valid.pdf)
```
INVOICE
Invoice #: INV-2024-001
Date: January 5, 2024
Due Date: February 5, 2024

From: Acme Supplies Ltd
To: TechCorp Industries

| Item Description      | Qty  | Unit Price | Amount    |
|-----------------------|------|------------|-----------|
| Widget Pro X100       | 50   | $100.00    | $5,000.00 |
| Connector Cable 2m    | 100  | $15.00     | $1,500.00 |
| Mounting Kit Standard | 50   | $30.00     | $1,500.00 |

Subtotal: $8,000.00
Tax (0%): $0.00
TOTAL: $8,000.00

PO Reference: PO-2024-001
```

### Purchase Order (po_valid.pdf)
```
PURCHASE ORDER
PO #: PO-2024-001
Date: January 2, 2024

From: TechCorp Industries (Buyer)
To: Acme Supplies Ltd (Vendor)

| Item Description      | Qty  | Unit Price | Amount    |
|-----------------------|------|------------|-----------|
| Widget Pro X100       | 50   | $100.00    | $5,000.00 |
| Connector Cable 2m    | 100  | $15.00     | $1,500.00 |
| Mounting Kit Standard | 50   | $30.00     | $1,500.00 |

Authorized Amount: $8,000.00
Authorized By: John Smith, Procurement Manager
```

### Proof of Delivery (pod_valid.pdf)
```
PROOF OF DELIVERY
Delivery Reference: DEL-2024-001
Date: January 4, 2024

Delivered To: TechCorp Industries
Delivered By: Acme Supplies Ltd

Items Received:
- Widget Pro X100: 50 units ✓
- Connector Cable 2m: 100 units ✓
- Mounting Kit Standard: 50 units ✓

Total Quantity Received: 200 units
Condition: Good

Received By: Jane Doe
Signature: [signed]
Date: January 4, 2024
```

---

## Document Set 2: Mismatched Quantity (Should FAIL)

### Invoice (invoice_qty_mismatch.pdf)
Same as above but with Qty = 60 for Widget Pro X100

### PO (po_valid.pdf)
Same as valid

### POD (pod_qty_mismatch.pdf)
Shows only 40 units of Widget Pro received

**Expected Result**: FAILED - quantity_match check fails

---

## Document Set 3: Amount Exceeds Authorization (Should FAIL)

### Invoice (invoice_over_auth.pdf)
Total: $10,000.00 (exceeds PO authorized amount)

### PO (po_valid.pdf)
Authorized: $8,000.00

### POD (pod_valid.pdf)
Same as valid

**Expected Result**: FAILED - amount_authorization check fails

---

## Document Set 4: InvoiceNow (Singapore Format)

These documents follow the Singapore InvoiceNow (PEPPOL) style, as used by Singaporean businesses.

### Valid Set (Passes 3-Way Match)
- **Invoice**: `invoicenow_valid.pdf` (Total: S$1,000.00)
- **PO**: `po_invoicenow_valid.pdf` (Authorized: S$1,000.00)
- **POD**: `pod_invoicenow_valid.pdf` (Qty: 1)

### Invalid Set (Fails 3-Way Match)
- **Invoice**: `invoicenow_invalid.pdf` (Total: S$1,500.00)
- **PO**: `po_invoicenow_invalid.pdf` (Authorized: S$1,000.00)
- **POD**: `pod_invoicenow_invalid.pdf` (Qty: 2)

**Expected Result**: FAILED - amount mismatch between Invoice and PO.

---

## How to Create Test PDFs

### Option 1: Use Online PDF Generators
1. Go to https://www.sejda.com/html-to-pdf
2. Copy the text above into an HTML template
3. Download as PDF

### Option 2: Use Python Scripts
The following scripts in this directory can generate matching document sets automatically:

1. **Standard Format**: `python generate_test_pdfs.py`
2. **InvoiceNow (SG) Format**: `python generate_invoicenow_pdfs.py` (Matches Singapore IMDA/PEPPOL style)

Requires `reportlab`: `pip install reportlab`

---

---

## Quick Test via curl

```bash
# Test with uploaded files
curl -X POST http://localhost:8000/api/v1/verification/verify \
  -F "wallet_address=rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe" \
  -F "invoice=@invoice_valid.pdf" \
  -F "purchase_order=@po_valid.pdf" \
  -F "proof_of_delivery=@pod_valid.pdf" \
  -F "skip_did_check=true"
```

## Expected API Response (Passed)

```json
{
  "verification_id": "abc-123",
  "status": "passed",
  "checks": [
    {"rule_name": "quantity_match", "passed": true, "message": "..."},
    {"rule_name": "amount_authorization", "passed": true, "message": "..."},
    {"rule_name": "date_sequence", "passed": true, "message": "..."}
  ],
  "anomalies": [],
  "extracted_data": {
    "invoice_number": "INV-2024-001",
    "total_amount": "8000.00",
    "currency": "USD"
  }
}
```
