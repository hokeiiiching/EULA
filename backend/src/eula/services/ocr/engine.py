"""
docTR OCR engine wrapper for document text extraction.

docTR provides layout-aware OCR with bounding boxes and confidence scores,
which is critical for accurate table column extraction and validation.

Design Decisions:
- Lazy model loading to avoid startup overhead
- Page-by-page processing for memory efficiency
- Confidence scores preserved for downstream review flagging
- Bounding boxes normalized to 0-1 range for consistency

Note: docTR requires PyTorch or TensorFlow backend. We use PyTorch.
"""

import io
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """
    A block of text extracted from a document with spatial information.
    
    Bounding box coordinates are normalized to 0-1 range relative to page size.
    """
    text: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    page: int
    
    @property
    def center_x(self) -> float:
        """Horizontal center of the text block."""
        return (self.x_min + self.x_max) / 2
    
    @property
    def center_y(self) -> float:
        """Vertical center of the text block."""
        return (self.y_min + self.y_max) / 2
    
    @property
    def width(self) -> float:
        """Width of the text block (normalized)."""
        return self.x_max - self.x_min
    
    @property
    def height(self) -> float:
        """Height of the text block (normalized)."""
        return self.y_max - self.y_min
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/debugging."""
        return {
            "text": self.text,
            "confidence": round(self.confidence, 3),
            "bbox": [
                round(self.x_min, 4),
                round(self.y_min, 4),
                round(self.x_max, 4),
                round(self.y_max, 4),
            ],
            "page": self.page,
        }


@dataclass
class OCRPage:
    """OCR results for a single page."""
    page_number: int
    width: int
    height: int
    blocks: list[TextBlock]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/debugging."""
        return {
            "page_number": self.page_number,
            "dimensions": {"width": self.width, "height": self.height},
            "block_count": len(self.blocks),
            "blocks": [b.to_dict() for b in self.blocks],
        }


@dataclass
class OCRResult:
    """Complete OCR results for a document."""
    pages: list[OCRPage]
    processing_time_ms: float = 0
    
    @property
    def all_blocks(self) -> list[TextBlock]:
        """Flatten all text blocks across all pages."""
        return [block for page in self.pages for block in page.blocks]
    
    @property
    def full_text(self) -> str:
        """Concatenate all text in reading order."""
        return "\n".join(block.text for block in self.all_blocks)
    
    @property
    def total_blocks(self) -> int:
        """Total number of text blocks across all pages."""
        return sum(len(page.blocks) for page in self.pages)
    
    @property
    def avg_confidence(self) -> float:
        """Average confidence across all blocks."""
        blocks = self.all_blocks
        if not blocks:
            return 0.0
        return sum(b.confidence for b in blocks) / len(blocks)
    
    @property
    def low_confidence_blocks(self) -> list[TextBlock]:
        """Blocks with confidence below 0.7."""
        return [b for b in self.all_blocks if b.confidence < 0.7]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/debugging."""
        return {
            "page_count": len(self.pages),
            "total_blocks": self.total_blocks,
            "avg_confidence": round(self.avg_confidence, 3),
            "processing_time_ms": round(self.processing_time_ms, 1),
            "low_confidence_count": len(self.low_confidence_blocks),
            "pages": [p.to_dict() for p in self.pages],
        }
    
    def to_debug_json(self, indent: int = 2) -> str:
        """Export full results as pretty JSON for debugging."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    def print_summary(self) -> None:
        """Print a human-readable summary to console."""
        print("\n" + "=" * 60)
        print("OCR RESULT SUMMARY")
        print("=" * 60)
        print(f"Pages: {len(self.pages)}")
        print(f"Total blocks: {self.total_blocks}")
        print(f"Average confidence: {self.avg_confidence:.1%}")
        print(f"Processing time: {self.processing_time_ms:.0f}ms")
        print(f"Low confidence blocks: {len(self.low_confidence_blocks)}")
        print("-" * 60)
        
        for page in self.pages:
            print(f"\nPage {page.page_number + 1} ({page.width}x{page.height}):")
            print("-" * 40)
            for block in page.blocks[:20]:  # First 20 blocks
                conf_indicator = "✓" if block.confidence >= 0.7 else "⚠"
                print(f"  {conf_indicator} [{block.confidence:.0%}] {block.text[:50]}")
            if len(page.blocks) > 20:
                print(f"  ... and {len(page.blocks) - 20} more blocks")
        
        if self.low_confidence_blocks:
            print("\n" + "-" * 60)
            print("LOW CONFIDENCE BLOCKS (may need review):")
            for block in self.low_confidence_blocks[:10]:
                print(f"  ⚠ [{block.confidence:.0%}] '{block.text}' at ({block.x_min:.2f}, {block.y_min:.2f})")
        
        print("=" * 60 + "\n")
    
    def save_debug_output(self, output_path: Path) -> None:
        """Save detailed debug output to a file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            f.write(f"# OCR Debug Output\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            f.write(self.to_debug_json())
        
        logger.info(f"OCR debug output saved to: {output_path}")


class OCREngine:
    """
    Document OCR engine using docTR for layout-aware text extraction.
    
    The engine provides bounding boxes and confidence scores for each
    detected text block, enabling accurate table column extraction.
    
    Example:
        engine = OCREngine(debug=True)
        with open("invoice.pdf", "rb") as f:
            result = engine.process_document(f.read(), "pdf")
        
        # Print summary for debugging
        result.print_summary()
        
        # Save full debug output
        result.save_debug_output("debug/ocr_output.json")
    """
    
    def __init__(self, debug: bool = False) -> None:
        """
        Initialize OCR engine.
        
        Args:
            debug: If True, print detailed OCR results to console
        """
        self._model = None
        self.debug = debug
    
    def _get_model(self):
        """
        Lazy load the docTR model.
        
        Models are loaded on first use to avoid startup overhead.
        The pretrained models are cached by docTR after first download.
        """
        if self._model is None:
            try:
                from doctr.io import DocumentFile
                from doctr.models import ocr_predictor
                
                logger.info("Loading docTR OCR model...")
                self._model = ocr_predictor(
                    det_arch="db_resnet50",
                    reco_arch="crnn_vgg16_bn",
                    pretrained=True,
                )
                logger.info("docTR model loaded successfully")
            except ImportError as e:
                logger.error(f"docTR not installed: {e}")
                raise RuntimeError(
                    "docTR is required for OCR. Install with: pip install python-doctr[torch]"
                ) from e
        
        return self._model
    
    def process_document(
        self,
        content: bytes,
        file_type: str,
    ) -> OCRResult:
        """
        Process a document and extract text with spatial information.
        
        Args:
            content: Raw bytes of the document (PDF or image)
            file_type: File type - "pdf", "png", "jpg", "jpeg"
            
        Returns:
            OCRResult with all pages and text blocks
            
        Raises:
            ValueError: If file type is not supported
            RuntimeError: If OCR processing fails
        """
        import time
        from doctr.io import DocumentFile
        
        start_time = time.time()
        
        file_type = file_type.lower().lstrip(".")
        logger.info(f"Processing document: type={file_type}, size={len(content)} bytes")
        
        if file_type == "pdf":
            doc = DocumentFile.from_pdf(content)
            logger.debug(f"PDF loaded: {len(doc)} pages")
        elif file_type in ("png", "jpg", "jpeg"):
            doc = DocumentFile.from_images(content)
            logger.debug(f"Image loaded")
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        model = self._get_model()
        
        logger.info("Running OCR inference...")
        result = model(doc)
        
        ocr_result = self._convert_result(result, doc)
        ocr_result.processing_time_ms = (time.time() - start_time) * 1000
        
        # Log summary
        logger.info(
            f"OCR complete: {ocr_result.total_blocks} blocks extracted, "
            f"avg confidence: {ocr_result.avg_confidence:.1%}, "
            f"time: {ocr_result.processing_time_ms:.0f}ms"
        )
        
        # Log low confidence warnings
        low_conf = ocr_result.low_confidence_blocks
        if low_conf:
            logger.warning(
                f"{len(low_conf)} blocks have low confidence (<70%). "
                f"Examples: {[b.text[:20] for b in low_conf[:3]]}"
            )
        
        # Debug output
        if self.debug:
            ocr_result.print_summary()
        
        return ocr_result
    
    def process_file(self, file_path: Path, save_debug: bool = False) -> OCRResult:
        """
        Process a document file from disk.
        
        Args:
            file_path: Path to the document file
            save_debug: If True, save debug output next to the file
            
        Returns:
            OCRResult with all pages and text blocks
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower().lstrip(".")
        
        logger.info(f"Processing file: {file_path}")
        
        with open(file_path, "rb") as f:
            result = self.process_document(f.read(), suffix)
        
        if save_debug or self.debug:
            debug_path = file_path.with_suffix(".ocr_debug.json")
            result.save_debug_output(debug_path)
        
        return result
    
    def _convert_result(self, doctr_result, doc) -> OCRResult:
        """
        Convert docTR result to our OCRResult format.
        
        Normalizes bounding box coordinates to 0-1 range.
        """
        pages: list[OCRPage] = []
        
        for page_idx, page in enumerate(doctr_result.pages):
            # Get page dimensions for normalization
            page_height, page_width = page.dimensions
            
            blocks: list[TextBlock] = []
            
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        # docTR returns coordinates as (x_min, y_min, x_max, y_max)
                        # Already normalized to 0-1 range
                        geometry = word.geometry
                        
                        text_block = TextBlock(
                            text=word.value,
                            confidence=word.confidence,
                            x_min=geometry[0][0],
                            y_min=geometry[0][1],
                            x_max=geometry[1][0],
                            y_max=geometry[1][1],
                            page=page_idx,
                        )
                        blocks.append(text_block)
                        
                        # Log each block at DEBUG level
                        logger.debug(
                            f"Block: '{word.value}' conf={word.confidence:.2f} "
                            f"pos=({geometry[0][0]:.3f}, {geometry[0][1]:.3f})"
                        )
            
            pages.append(OCRPage(
                page_number=page_idx,
                width=page_width,
                height=page_height,
                blocks=blocks,
            ))
            
            logger.debug(f"Page {page_idx}: {len(blocks)} blocks extracted")
        
        return OCRResult(pages=pages)
    
    def extract_text_in_region(
        self,
        result: OCRResult,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
        page: int = 0,
    ) -> list[TextBlock]:
        """
        Extract text blocks within a specific region.
        
        Useful for extracting specific fields like "Total:" or table cells.
        
        Args:
            result: OCR result to search within
            x_min, y_min, x_max, y_max: Region bounds (0-1 normalized)
            page: Page number (0-indexed)
            
        Returns:
            List of text blocks whose centers fall within the region
        """
        if page >= len(result.pages):
            return []
        
        matching_blocks: list[TextBlock] = []
        
        for block in result.pages[page].blocks:
            # Check if block center is within region
            if (x_min <= block.center_x <= x_max and
                y_min <= block.center_y <= y_max):
                matching_blocks.append(block)
        
        # Sort by position (top to bottom, left to right)
        matching_blocks.sort(key=lambda b: (b.center_y, b.center_x))
        
        logger.debug(
            f"Region ({x_min:.2f}, {y_min:.2f}) - ({x_max:.2f}, {y_max:.2f}): "
            f"{len(matching_blocks)} blocks found"
        )
        
        return matching_blocks
