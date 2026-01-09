"""
OCR subpackage - Layout-aware document text recognition.
"""

from .engine import OCREngine
from .extractor import SmartFieldExtractor
from .normalize import FieldNormalizer
from .table import TableDetector

__all__ = ["OCREngine", "TableDetector", "FieldNormalizer", "SmartFieldExtractor"]

