"""
Generate sample test PDF documents for EULA verification testing.

Run: python generate_test_pdfs.py
Requires: pip install reportlab
"""

from pathlib import Path

def create_pdf(filename: str, lines: list[str]) -> None:
    """Create a simple PDF with text lines."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
    except ImportError:
        print("Install reportlab: pip install reportlab")
        return
    
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    y = height - inch
    for line in lines:
        if line.startswith("# "):
            c.setFont("Helvetica-Bold", 16)
            c.drawString(inch, y, line[2:])
            y -= 24
        elif line.startswith("## "):
            c.setFont("Helvetica-Bold", 12)
            c.drawString(inch, y, line[3:])
            y -= 18
        elif line == "---":
            c.line(inch, y, width - inch, y)
            y -= 12
        else:
            c.setFont("Helvetica", 10)
            c.drawString(inch, y, line)
            y -= 14
        
        if y < inch:
            c.showPage()
            y = height - inch
    
    c.save()
    print(f"Created: {filename}")


def generate_valid_set():
    """Generate a matching set of Invoice, PO, and POD."""
    
    # Invoice
    create_pdf("invoice_valid.pdf", [
        "# INVOICE",
        "",
        "Invoice Number: INV-2024-001",
        "Invoice Date: January 5, 2024",
        "Due Date: February 5, 2024",
        "",
        "---",
        "",
        "## From (Seller):",
        "Acme Supplies Ltd",
        "123 Industrial Way",
        "Business City, BC 12345",
        "",
        "## To (Buyer):",
        "TechCorp Industries",
        "456 Technology Park",
        "Tech Valley, TV 67890",
        "",
        "---",
        "",
        "## Line Items:",
        "",
        "Description              Qty    Unit Price    Amount",
        "---",
        "Widget Pro X100          50     $100.00       $5,000.00",
        "Connector Cable 2m       100    $15.00        $1,500.00",
        "Mounting Kit Standard    50     $30.00        $1,500.00",
        "",
        "---",
        "",
        "Subtotal: $8,000.00",
        "Tax (0%): $0.00",
        "TOTAL DUE: $8,000.00",
        "",
        "Reference PO: PO-2024-001",
    ])
    
    # Purchase Order
    create_pdf("po_valid.pdf", [
        "# PURCHASE ORDER",
        "",
        "PO Number: PO-2024-001",
        "Date: January 2, 2024",
        "",
        "---",
        "",
        "## Buyer:",
        "TechCorp Industries",
        "456 Technology Park",
        "Tech Valley, TV 67890",
        "",
        "## Vendor:",
        "Acme Supplies Ltd",
        "123 Industrial Way",
        "Business City, BC 12345",
        "",
        "---",
        "",
        "## Order Details:",
        "",
        "Description              Qty    Unit Price    Amount",
        "---",
        "Widget Pro X100          50     $100.00       $5,000.00",
        "Connector Cable 2m       100    $15.00        $1,500.00",
        "Mounting Kit Standard    50     $30.00        $1,500.00",
        "",
        "---",
        "",
        "Total Authorized Amount: $8,000.00",
        "",
        "Authorized By: John Smith",
        "Title: Procurement Manager",
    ])
    
    # Proof of Delivery
    create_pdf("pod_valid.pdf", [
        "# PROOF OF DELIVERY",
        "",
        "Delivery Reference: DEL-2024-001",
        "Delivery Date: January 4, 2024",
        "",
        "---",
        "",
        "## Shipper:",
        "Acme Supplies Ltd",
        "",
        "## Recipient:",
        "TechCorp Industries",
        "456 Technology Park",
        "",
        "---",
        "",
        "## Items Delivered:",
        "",
        "Description              Quantity    Status",
        "---",
        "Widget Pro X100          50          Received",
        "Connector Cable 2m       100         Received", 
        "Mounting Kit Standard    50          Received",
        "",
        "Total Quantity: 200 units",
        "",
        "---",
        "",
        "Condition: Good - No damage",
        "",
        "Received By: Jane Doe",
        "Signature: [SIGNED]",
        "Date: January 4, 2024",
    ])


def generate_mismatch_set():
    """Generate a set with quantity mismatch for testing failures."""
    
    create_pdf("invoice_qty_mismatch.pdf", [
        "# INVOICE",
        "",
        "Invoice Number: INV-2024-002",
        "Invoice Date: January 5, 2024",
        "Due Date: February 5, 2024",
        "",
        "## From: Acme Supplies Ltd",
        "## To: TechCorp Industries",
        "",
        "---",
        "",
        "Description              Qty    Amount",
        "---",
        "Widget Pro X100          60     $6,000.00",  # Mismatch: 60 vs 50 in PO
        "",
        "TOTAL: $6,000.00",
        "",
        "Reference PO: PO-2024-001",
    ])


if __name__ == "__main__":
    # Create output directory
    output_dir = Path(__file__).parent
    import os
    os.chdir(output_dir)
    
    print("Generating valid document set...")
    generate_valid_set()
    
    print("\nGenerating mismatch document set...")
    generate_mismatch_set()
    
    print("\nDone! Use these PDFs to test the verification API.")
