"""
Debug endpoints for development and testing.

These endpoints are only available when DEBUG=true.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from eula.config import get_settings
from eula.services.ocr import OCREngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/ocr")
async def debug_ocr(
    file: Annotated[UploadFile, File(description="Document to OCR (PDF/image)")],
):
    """
    Debug endpoint to test OCR extraction directly.
    
    Returns full OCR output with all text blocks, positions, and confidences.
    Only available in debug mode.
    """
    settings = get_settings()
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug endpoints are disabled in production",
        )
    
    # Validate file type
    allowed_types = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Allowed: PDF, PNG, JPG",
        )
    
    # Read file
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )
    
    # Get file extension
    filename = file.filename or "document.pdf"
    file_ext = filename.split(".")[-1].lower()
    
    # Run OCR
    ocr = OCREngine(debug=True)
    
    try:
        result = ocr.process_document(content, file_ext)
    except Exception as e:
        logger.exception("OCR failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR error: {str(e)}",
        )
    
    # Return detailed result
    return {
        "filename": filename,
        "file_size": len(content),
        "file_type": file_ext,
        "ocr_result": result.to_dict(),
        "full_text": result.full_text,
        "summary": {
            "pages": len(result.pages),
            "total_blocks": result.total_blocks,
            "avg_confidence": round(result.avg_confidence, 3),
            "processing_time_ms": round(result.processing_time_ms, 1),
            "low_confidence_blocks": [
                {
                    "text": b.text,
                    "confidence": round(b.confidence, 3),
                    "position": {
                        "x": round(b.center_x, 3),
                        "y": round(b.center_y, 3),
                    },
                }
                for b in result.low_confidence_blocks[:10]
            ],
        },
    }


@router.get("/ocr/config")
async def get_ocr_config():
    """Get current OCR configuration."""
    settings = get_settings()
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug endpoints are disabled in production",
        )
    
    return {
        "confidence_threshold": settings.ocr_confidence_threshold,
        "debug_mode": settings.debug,
    }
