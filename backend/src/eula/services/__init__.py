"""
Services package - Business logic and external integrations.

Includes OCR, DID verification, XRPL integration, and forensic audit.
"""

from .ocr import OCREngine, FieldNormalizer, TableDetector

__all__ = ["OCREngine", "TableDetector", "FieldNormalizer"]

