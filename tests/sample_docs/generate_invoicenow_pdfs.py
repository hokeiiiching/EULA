"""
Generate InvoiceNow-style (Singapore IMDA format) test PDF documents.

These documents match the Singapore InvoiceNow format used by businesses.

Run: python generate_invoicenow_pdfs.py
Requires: pip install reportlab
"""

from pathlib import Path
from datetime import date


def create_invoicenow_invoice(filename: str, data: dict) -> None:
    """Create an InvoiceNow-style Tax Invoice PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
    except ImportError:
        print("Install reportlab: pip install reportlab")
        return
    
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    # Colors
    header_blue = HexColor("#000080")
    border_blue = HexColor("#4169E1")
    
    # Border
    c.setStrokeColor(border_blue)
    c.setLineWidth(2)
    c.rect(10*mm, 10*mm, width - 20*mm, height - 20*mm)
    
    # Header - "Tax Invoice"
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(header_blue)
    c.drawRightString(width - 20*mm, height - 25*mm, "Tax Invoice")
    
    # GST Reg No
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#000000"))
    c.drawRightString(width - 20*mm, height - 35*mm, f"GST Reg No: {data.get('gst_reg', '')}")
    
    # Bill To section
    y = height - 30*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, y, "Bill To:")
    c.setFont("Helvetica", 9)
    y -= 5*mm
    for line in data["bill_to"]:
        c.drawString(20*mm, y, line)
        y -= 4*mm
    
    # Ship To section
    y -= 3*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, y, "Ship To:")
    c.setFont("Helvetica", 9)
    y -= 5*mm
    for line in data["ship_to"]:
        c.drawString(20*mm, y, line)
        y -= 4*mm
    
    # Invoice details box (right side)
    box_x = 120*mm
    box_y = height - 55*mm
    box_width = 60*mm
    box_height = 25*mm
    
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(0.5)
    c.rect(box_x, box_y, box_width, box_height)
    
    # Invoice number, date, page
    c.setFont("Helvetica-Bold", 9)
    c.drawString(box_x + 2*mm, box_y + 18*mm, "Invoice No :")
    c.drawString(box_x + 2*mm, box_y + 11*mm, "Date :")
    c.drawString(box_x + 2*mm, box_y + 4*mm, "Page :")
    
    c.setFont("Helvetica", 9)
    c.drawString(box_x + 30*mm, box_y + 18*mm, data["invoice_no"])
    c.drawString(box_x + 30*mm, box_y + 11*mm, data["date"])
    c.drawString(box_x + 30*mm, box_y + 4*mm, "1")
    
    # Contact info
    y = height - 95*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20*mm, y, f"Attn: {data.get('attn', '')}")
    c.drawString(70*mm, y, f"Phone: {data.get('phone', '')}")
    c.drawString(130*mm, y, f"Fax: {data.get('fax', '')}")
    
    # Order details table header
    y -= 10*mm
    c.setLineWidth(0.5)
    c.rect(20*mm, y - 8*mm, width - 40*mm, 10*mm)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(22*mm, y - 5*mm, "SalesPerson")
    c.drawString(55*mm, y - 5*mm, "P.O. Number")
    c.drawString(90*mm, y - 5*mm, "Date Shipped")
    c.drawString(125*mm, y - 5*mm, "Shipped Via")
    c.drawString(160*mm, y - 5*mm, "Terms")
    
    # Terms row
    y -= 18*mm
    c.setFont("Helvetica", 9)
    c.drawString(160*mm, y, data.get("terms", "Net 30th after EOM"))
    
    # Line items header
    y -= 10*mm
    c.setLineWidth(0.5)
    c.rect(20*mm, y - 8*mm, width - 40*mm, 10*mm)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(22*mm, y - 5*mm, "Description")
    c.drawRightString(width - 22*mm, y - 5*mm, f"Amount ({data.get('currency', 'S$')})")
    
    # Line items
    y -= 18*mm
    c.setFont("Helvetica", 9)
    for item in data["items"]:
        c.drawString(22*mm, y, item["description"])
        c.drawRightString(width - 22*mm, y, f"{data.get('currency', 'S$')}{item['amount']:,.2f}")
        y -= 6*mm
    
    # Totals section (bottom right)
    y = 65*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20*mm, y + 10*mm, "Memo:")
    
    # Totals
    totals = [
        ("Total", data["total"]),
        ("Freight", data.get("freight", 0)),
        ("Add: GST", data.get("gst", 0)),
        ("Total Inc GST", data.get("total_inc_gst", data["total"])),
        ("Less: Deposit", data.get("deposit", 0)),
        ("Balance Due", data.get("balance_due", data["total"])),
    ]
    
    for label, amount in totals:
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(135*mm, y, f"{label}")
        c.setFont("Helvetica", 9)
        c.drawRightString(width - 22*mm, y, f"{data.get('currency', 'S$')}{amount:,.2f}")
        y -= 6*mm
    
    # Company name at bottom
    y = 30*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 22*mm, y, data["company_name"])
    
    # E. & O.E.
    c.setFont("Helvetica", 8)
    c.drawString(20*mm, 25*mm, "E. & O. E")
    
    # Signature block
    c.setLineWidth(0.5)
    c.rect(20*mm, 12*mm, width - 40*mm, 12*mm)
    c.setFont("Helvetica", 8)
    c.drawString(22*mm, 16*mm, "RECEIVED BY")
    c.drawString(55*mm, 16*mm, "DATE")
    c.drawString(90*mm, 16*mm, "COMPANY STAMP")
    c.drawRightString(width - 25*mm, 16*mm, data["company_name"])
    
    c.save()
    print(f"Created: {filename}")


def create_invoicenow_po(filename: str, data: dict) -> None:
    """Create a Purchase Order matching InvoiceNow style."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
    except ImportError:
        print("Install reportlab: pip install reportlab")
        return
    
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    # Border
    c.setStrokeColor(HexColor("#4169E1"))
    c.setLineWidth(2)
    c.rect(10*mm, 10*mm, width - 20*mm, height - 20*mm)
    
    # Header
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(HexColor("#000080"))
    c.drawRightString(width - 20*mm, height - 25*mm, "Purchase Order")
    
    c.setFillColor(HexColor("#000000"))
    
    # Buyer info (left)
    y = height - 40*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, y, "From (Buyer):")
    c.setFont("Helvetica", 9)
    y -= 5*mm
    for line in data["buyer"]:
        c.drawString(20*mm, y, line)
        y -= 4*mm
    
    # Vendor info
    y -= 5*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, y, "To (Vendor):")
    c.setFont("Helvetica", 9)
    y -= 5*mm
    for line in data["vendor"]:
        c.drawString(20*mm, y, line)
        y -= 4*mm
    
    # PO details box (right)
    box_x = 120*mm
    box_y = height - 65*mm
    
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(0.5)
    c.rect(box_x, box_y, 60*mm, 25*mm)
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(box_x + 2*mm, box_y + 18*mm, "P.O. Number :")
    c.drawString(box_x + 2*mm, box_y + 11*mm, "Date :")
    c.drawString(box_x + 2*mm, box_y + 4*mm, "Page :")
    
    c.setFont("Helvetica", 9)
    c.drawString(box_x + 30*mm, box_y + 18*mm, data["po_number"])
    c.drawString(box_x + 30*mm, box_y + 11*mm, data["date"])
    c.drawString(box_x + 30*mm, box_y + 4*mm, "1")
    
    # Items table header
    y = height - 110*mm
    c.setLineWidth(0.5)
    c.rect(20*mm, y - 8*mm, width - 40*mm, 10*mm)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(22*mm, y - 5*mm, "Description")
    c.drawString(100*mm, y - 5*mm, "Qty")
    c.drawRightString(width - 22*mm, y - 5*mm, f"Amount ({data.get('currency', 'S$')})")
    
    # Items
    y -= 18*mm
    c.setFont("Helvetica", 9)
    total_qty = 0
    for item in data["items"]:
        c.drawString(22*mm, y, item["description"])
        c.drawString(100*mm, y, str(item.get("qty", 1)))
        c.drawRightString(width - 22*mm, y, f"{data.get('currency', 'S$')}{item['amount']:,.2f}")
        total_qty += item.get("qty", 1)
        y -= 6*mm
    
    # Total
    y -= 10*mm
    c.line(120*mm, y + 6*mm, width - 20*mm, y + 6*mm)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(120*mm, y, "Total Authorized Amount:")
    c.drawRightString(width - 22*mm, y, f"{data.get('currency', 'S$')}{data['total']:,.2f}")
    
    # Authorization
    y -= 20*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20*mm, y, f"Authorized By: {data.get('authorized_by', '')}")
    y -= 6*mm
    c.drawString(20*mm, y, f"Title: {data.get('title', 'Procurement Manager')}")
    
    # Company stamp area
    y = 30*mm
    c.rect(120*mm, y, 60*mm, 25*mm)
    c.setFont("Helvetica", 8)
    c.drawString(122*mm, y + 18*mm, "Company Stamp")
    
    c.save()
    print(f"Created: {filename}")


def create_invoicenow_pod(filename: str, data: dict) -> None:
    """Create a Proof of Delivery matching InvoiceNow style."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
    except ImportError:
        print("Install reportlab: pip install reportlab")
        return
    
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    # Border
    c.setStrokeColor(HexColor("#4169E1"))
    c.setLineWidth(2)
    c.rect(10*mm, 10*mm, width - 20*mm, height - 20*mm)
    
    # Header
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(HexColor("#000080"))
    c.drawRightString(width - 20*mm, height - 25*mm, "Delivery Order")
    
    c.setFillColor(HexColor("#000000"))
    
    # Shipper info
    y = height - 40*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, y, "From (Shipper):")
    c.setFont("Helvetica", 9)
    y -= 5*mm
    for line in data["shipper"]:
        c.drawString(20*mm, y, line)
        y -= 4*mm
    
    # Recipient info
    y -= 5*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, y, "Deliver To:")
    c.setFont("Helvetica", 9)
    y -= 5*mm
    for line in data["recipient"]:
        c.drawString(20*mm, y, line)
        y -= 4*mm
    
    # Delivery details box
    box_x = 120*mm
    box_y = height - 65*mm
    
    c.setStrokeColor(HexColor("#000000"))
    c.setLineWidth(0.5)
    c.rect(box_x, box_y, 60*mm, 25*mm)
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(box_x + 2*mm, box_y + 18*mm, "Delivery Ref :")
    c.drawString(box_x + 2*mm, box_y + 11*mm, "Date :")
    c.drawString(box_x + 2*mm, box_y + 4*mm, "Invoice Ref :")
    
    c.setFont("Helvetica", 9)
    c.drawString(box_x + 28*mm, box_y + 18*mm, data["delivery_ref"])
    c.drawString(box_x + 28*mm, box_y + 11*mm, data["date"])
    c.drawString(box_x + 28*mm, box_y + 4*mm, data.get("invoice_ref", ""))
    
    # Items table header
    y = height - 110*mm
    c.setLineWidth(0.5)
    c.rect(20*mm, y - 8*mm, width - 40*mm, 10*mm)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(22*mm, y - 5*mm, "Description")
    c.drawString(100*mm, y - 5*mm, "Qty")
    c.drawString(130*mm, y - 5*mm, "Status")
    
    # Items
    y -= 18*mm
    c.setFont("Helvetica", 9)
    total_qty = 0
    for item in data["items"]:
        c.drawString(22*mm, y, item["description"])
        c.drawString(100*mm, y, str(item.get("qty", 1)))
        c.drawString(130*mm, y, item.get("status", "Delivered"))
        total_qty += item.get("qty", 1)
        y -= 6*mm
    
    # Total quantity
    y -= 10*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(90*mm, y, f"Total Quantity Delivered: {total_qty}")
    
    # Condition
    y -= 15*mm
    c.drawString(20*mm, y, f"Condition: {data.get('condition', 'Good - No damage')}")
    
    # Signature section
    y -= 25*mm
    c.setLineWidth(0.5)
    c.rect(20*mm, y, width - 40*mm, 20*mm)
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(22*mm, y + 13*mm, "Received By:")
    c.drawString(80*mm, y + 13*mm, "Signature:")
    c.drawString(140*mm, y + 13*mm, "Date:")
    
    c.setFont("Helvetica", 9)
    c.drawString(22*mm, y + 5*mm, data.get("received_by", ""))
    c.drawString(80*mm, y + 5*mm, "[SIGNED]")
    c.drawString(140*mm, y + 5*mm, data["date"])
    
    c.save()
    print(f"Created: {filename}")


def generate_invoicenow_valid_set():
    """Generate a matching InvoiceNow-style document set."""
    
    # Based on the uploaded InvoiceNow Tax Invoice
    invoice_data = {
        "company_name": "CLEARWATER PTE LTD",
        "invoice_no": "00000003",
        "date": "7/4/2023",
        "gst_reg": "",
        "bill_to": [
            "Sales Automation",
            "3 Mount Elizabeth Road #08-02",
            "MOUNT ELIZABETH MEDICAL CENTRE",
            "228510",
            "Singapore",
        ],
        "ship_to": [
            "Customer B",
            "3 Mount Elizabeth Road #08-02",
            "MOUNT ELIZABETH MEDICAL CENTRE",
            "228510",
        ],
        "attn": "Mrs Beth",
        "phone": "+6567373529",
        "fax": "+6567373528",
        "terms": "Net 30th after EOM",
        "currency": "S$",
        "items": [
            {"description": "sales", "amount": 1000.00, "qty": 1},
        ],
        "total": 1000.00,
        "freight": 0.00,
        "gst": 0.00,
        "total_inc_gst": 1000.00,
        "deposit": 0.00,
        "balance_due": 1000.00,
    }
    
    create_invoicenow_invoice("invoicenow_valid.pdf", invoice_data)
    
    # Matching Purchase Order
    po_data = {
        "po_number": "PO-SG-2023-001",
        "date": "1/4/2023",
        "currency": "S$",
        "buyer": [
            "Sales Automation",
            "3 Mount Elizabeth Road #08-02",
            "MOUNT ELIZABETH MEDICAL CENTRE",
            "Singapore 228510",
        ],
        "vendor": [
            "CLEARWATER PTE LTD",
            "Singapore",
        ],
        "items": [
            {"description": "sales", "qty": 1, "amount": 1000.00},
        ],
        "total": 1000.00,
        "authorized_by": "Mrs Beth",
        "title": "Procurement Manager",
    }
    
    create_invoicenow_po("po_invoicenow_valid.pdf", po_data)
    
    # Matching Proof of Delivery
    pod_data = {
        "delivery_ref": "DEL-SG-2023-001",
        "date": "5/4/2023",
        "invoice_ref": "00000003",
        "shipper": [
            "CLEARWATER PTE LTD",
            "Singapore",
        ],
        "recipient": [
            "Customer B",
            "3 Mount Elizabeth Road #08-02",
            "MOUNT ELIZABETH MEDICAL CENTRE",
            "Singapore 228510",
            "Attn: Mrs Beth",
        ],
        "items": [
            {"description": "sales", "qty": 1, "status": "Delivered"},
        ],
        "condition": "Good - No damage",
        "received_by": "Mrs Beth",
    }
    
    create_invoicenow_pod("pod_invoicenow_valid.pdf", pod_data)


def generate_invoicenow_mismatch_set():
    """Generate InvoiceNow-style documents with mismatches for testing failures."""
    
    # Invoice with DIFFERENT amount than PO
    invoice_data = {
        "company_name": "CLEARWATER PTE LTD",
        "invoice_no": "00000004",
        "date": "7/4/2023",
        "gst_reg": "",
        "bill_to": [
            "Sales Automation",
            "3 Mount Elizabeth Road #08-02",
            "MOUNT ELIZABETH MEDICAL CENTRE",
            "228510",
            "Singapore",
        ],
        "ship_to": [
            "Customer B",
            "3 Mount Elizabeth Road #08-02",
            "MOUNT ELIZABETH MEDICAL CENTRE",
            "228510",
        ],
        "attn": "Mrs Beth",
        "phone": "+6567373529",
        "fax": "+6567373528",
        "terms": "Net 30th after EOM",
        "currency": "S$",
        "items": [
            {"description": "sales", "amount": 1500.00, "qty": 1},  # MISMATCH: 1500 vs 1000
        ],
        "total": 1500.00,
        "freight": 0.00,
        "gst": 0.00,
        "total_inc_gst": 1500.00,
        "deposit": 0.00,
        "balance_due": 1500.00,
    }
    
    create_invoicenow_invoice("invoicenow_invalid.pdf", invoice_data)
    
    # PO with DIFFERENT amount
    po_data = {
        "po_number": "PO-SG-2023-002",
        "date": "1/4/2023",
        "currency": "S$",
        "buyer": [
            "Sales Automation",
            "3 Mount Elizabeth Road #08-02",
            "MOUNT ELIZABETH MEDICAL CENTRE",
            "Singapore 228510",
        ],
        "vendor": [
            "CLEARWATER PTE LTD",
            "Singapore",
        ],
        "items": [
            {"description": "sales", "qty": 1, "amount": 1000.00},  # Original amount
        ],
        "total": 1000.00,
        "authorized_by": "Mrs Beth",
        "title": "Procurement Manager",
    }
    
    create_invoicenow_po("po_invoicenow_invalid.pdf", po_data)
    
    # POD with DIFFERENT quantity
    pod_data = {
        "delivery_ref": "DEL-SG-2023-002",
        "date": "5/4/2023",
        "invoice_ref": "00000004",
        "shipper": [
            "CLEARWATER PTE LTD",
            "Singapore",
        ],
        "recipient": [
            "Customer B",
            "3 Mount Elizabeth Road #08-02",
            "MOUNT ELIZABETH MEDICAL CENTRE",
            "Singapore 228510",
            "Attn: Mrs Beth",
        ],
        "items": [
            {"description": "sales", "qty": 2, "status": "Delivered"},  # MISMATCH: qty 2 vs 1
        ],
        "condition": "Good - No damage",
        "received_by": "Mrs Beth",
    }
    
    create_invoicenow_pod("pod_invoicenow_invalid.pdf", pod_data)


if __name__ == "__main__":
    output_dir = Path(__file__).parent
    import os
    os.chdir(output_dir)
    
    print("Generating InvoiceNow VALID document set...")
    generate_invoicenow_valid_set()
    
    print("\nGenerating InvoiceNow INVALID document set (with mismatches)...")
    generate_invoicenow_mismatch_set()
    
    print("\n=== Generated Files ===")
    print("VALID set (should pass 3-way match):")
    print("  - invoicenow_valid.pdf")
    print("  - po_invoicenow_valid.pdf")
    print("  - pod_invoicenow_valid.pdf")
    print("\nINVALID set (should fail 3-way match):")
    print("  - invoicenow_invalid.pdf")
    print("  - po_invoicenow_invalid.pdf")
    print("  - pod_invoicenow_invalid.pdf")
    print("\nDone! Use these PDFs to test InvoiceNow format verification.")
