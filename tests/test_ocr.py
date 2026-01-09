#!/usr/bin/env python3
"""
OCR Testing CLI - Debug and test the EULA OCR pipeline.

Usage (from project root):
    python tests/test_ocr.py tests/sample_docs/invoice_valid.pdf
    python tests/test_ocr.py tests/sample_docs/*.pdf --debug --save-json

Or from backend directory:
    python ../tests/test_ocr.py ../tests/sample_docs/invoice_valid.pdf
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add backend/src to path for imports
project_root = Path(__file__).parent.parent
backend_src = project_root / "backend" / "src"
sys.path.insert(0, str(backend_src))

from eula.services.ocr import OCREngine, FieldNormalizer, TableDetector, SmartFieldExtractor


def setup_logging(level: str = "INFO"):
    """Configure logging for the test script."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    
    # Set eula loggers to debug if requested
    if log_level == logging.DEBUG:
        logging.getLogger("eula").setLevel(logging.DEBUG)


def test_single_file(
    file_path: Path,
    debug: bool = False,
    save_json: bool = False,
    show_tables: bool = False,
) -> dict:
    """Test OCR on a single file."""
    print(f"\n{'=' * 70}")
    print(f"Processing: {file_path.name}")
    print(f"{'=' * 70}")
    
    # Initialize engines
    ocr = OCREngine(debug=debug)
    table_detector = TableDetector()
    extractor = SmartFieldExtractor()  # New smart extractor!
    
    # Run OCR
    result = ocr.process_file(file_path, save_debug=save_json)
    
    # Print summary
    result.print_summary()
    
    # Detect tables
    if show_tables:
        print("\n" + "-" * 70)
        print("TABLE DETECTION")
        print("-" * 70)
        
        tables = table_detector.detect_tables(result)
        
        if tables:
            for i, table in enumerate(tables):
                print(f"\nTable {i + 1}:")
                print(f"  Rows: {len(table.rows)}")
                print(f"  Columns: {len(table.columns)}")
                print(f"  Headers: {table.header_row}")
                
                # Print first few rows
                for row_idx, row in enumerate(table.rows[:5]):
                    cells = [str(c.text)[:15] for c in row.cells]
                    print(f"  Row {row_idx}: {' | '.join(cells)}")
        else:
            print("  No tables detected")
    
    # === SMART FIELD EXTRACTION using regex + label proximity ===
    print("\n" + "-" * 70)
    print("SMART FIELD EXTRACTION (regex + label proximity)")
    print("-" * 70)
    
    # Invoice fields
    invoice_num = extractor.extract_invoice_number(result)
    print(f"  Invoice Number: '{invoice_num.value}' (conf: {invoice_num.confidence:.0%})")
    
    po_num = extractor.extract_po_number(result)
    print(f"  PO Number:      '{po_num.value}' (conf: {po_num.confidence:.0%})")
    
    total = extractor.extract_amount(result, ["total", "amount due", "grand total", "total due"])
    print(f"  Total Amount:   ${total.value} (conf: {total.confidence:.0%})")
    
    inv_date = extractor.extract_date(result, ["invoice date", "date", "issued"])
    print(f"  Invoice Date:   {inv_date.value} (conf: {inv_date.confidence:.0%})")
    
    due_date = extractor.extract_date(result, ["due date", "payment due", "pay by"])
    print(f"  Due Date:       {due_date.value} (conf: {due_date.confidence:.0%})")
    
    qty = extractor.extract_quantity(result, ["quantity", "qty", "total quantity", "units"])
    print(f"  Quantity:       {qty.value} (conf: {qty.confidence:.0%})")
    
    seller = extractor.extract_name(result, ["from", "seller", "vendor", "sold by"])
    print(f"  Seller:         '{seller.value}' (conf: {seller.confidence:.0%})")
    
    buyer = extractor.extract_name(result, ["to", "bill to", "buyer", "sold to"])
    print(f"  Buyer:          '{buyer.value}' (conf: {buyer.confidence:.0%})")
    
    # Save JSON output
    if save_json:
        output_path = file_path.with_suffix(".ocr_output.json")
        result.save_debug_output(output_path)
        print(f"\nJSON output saved to: {output_path}")
    
    return {
        "file": str(file_path),
        "pages": len(result.pages),
        "blocks": result.total_blocks,
        "avg_confidence": result.avg_confidence,
        "low_confidence": len(result.low_confidence_blocks),
        "processing_time_ms": result.processing_time_ms,
        "extracted": {
            "invoice_number": invoice_num.value,
            "total_amount": str(total.value),
            "invoice_date": str(inv_date.value),
            "due_date": str(due_date.value),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Test EULA OCR pipeline on documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic OCR test (from project root)
  python tests/test_ocr.py tests/sample_docs/invoice_valid.pdf
  
  # Debug mode with full output
  python tests/test_ocr.py invoice.pdf --debug --save-json
  
  # Test all PDFs in a directory
  python tests/test_ocr.py tests/sample_docs/*.pdf
  
  # Show table detection
  python tests/test_ocr.py invoice.pdf --tables
        """,
    )
    
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="PDF or image files to process",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode with detailed output",
    )
    parser.add_argument(
        "--save-json", "-j",
        action="store_true",
        help="Save OCR output as JSON file",
    )
    parser.add_argument(
        "--tables", "-t",
        action="store_true",
        help="Show table detection results",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    results = []
    
    for file_path in args.files:
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            continue
        
        try:
            result = test_single_file(
                file_path,
                debug=args.debug,
                save_json=args.save_json,
                show_tables=args.tables,
            )
            results.append(result)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
    
    # Print summary if multiple files
    if len(results) > 1:
        print("\n" + "=" * 70)
        print("BATCH SUMMARY")
        print("=" * 70)
        
        total_blocks = sum(r["blocks"] for r in results)
        avg_conf = sum(r["avg_confidence"] for r in results) / len(results)
        total_time = sum(r["processing_time_ms"] for r in results)
        
        print(f"Files processed: {len(results)}")
        print(f"Total blocks: {total_blocks}")
        print(f"Average confidence: {avg_conf:.1%}")
        print(f"Total processing time: {total_time:.0f}ms")


if __name__ == "__main__":
    main()
