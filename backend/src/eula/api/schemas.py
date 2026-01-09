"""
Pydantic schemas for API request/response validation.

These schemas define the contract between frontend and backend.
All monetary values use strings to avoid floating point issues.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VerificationStatusEnum(str, Enum):
    """Verification status for API responses."""
    PENDING = "pending"
    PROCESSING = "processing"
    PASSED = "passed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


class DIDStatusEnum(str, Enum):
    """DID verification status."""
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INVALID = "invalid"
    PENDING = "pending"
    SKIPPED = "skipped"


# =============================================================================
# Request Schemas
# =============================================================================

class VerifyDocumentsRequest(BaseModel):
    """Request to start document verification."""
    wallet_address: str = Field(
        ...,
        description="XRPL wallet address of the SME",
        pattern=r"^r[a-zA-Z0-9]{24,34}$",
    )
    skip_did_check: bool = Field(
        default=False,
        description="Skip DID verification (for testing only)",
    )


class PrepareMinRequest(BaseModel):
    """Request to prepare NFT minting transaction."""
    verification_id: str = Field(
        ...,
        description="ID of a successful verification",
    )
    wallet_address: str = Field(
        ...,
        description="XRPL wallet address to mint the NFT to",
    )
    discount_percent: float = Field(
        default=4.0,
        ge=0,
        le=50,
        description="Discount percentage from face value (0-50%)",
    )


# =============================================================================
# Response Schemas
# =============================================================================

class ValidationCheckResponse(BaseModel):
    """Single validation check result."""
    rule_name: str
    passed: bool
    message: str
    details: dict[str, Any] = {}


class AnomalyResponse(BaseModel):
    """Detected anomaly in documents."""
    code: str
    message: str
    severity: str
    field_path: str


class ExtractedDataResponse(BaseModel):
    """Extracted document data for user confirmation."""
    invoice_number: str | None = None
    total_amount: str | None = None
    currency: str = "USD"
    invoice_date: date | None = None
    due_date: date | None = None
    payee_name: str | None = None
    payer_name: str | None = None
    po_number: str | None = None
    pod_reference: str | None = None


class VerificationResponse(BaseModel):
    """Response from document verification."""
    verification_id: str
    status: VerificationStatusEnum
    checks: list[ValidationCheckResponse]
    anomalies: list[AnomalyResponse]
    review_flags: list[str] = []
    extracted_data: ExtractedDataResponse
    
    # Hashes for reference
    invoice_hash: str | None = None
    po_hash: str | None = None
    pod_hash: str | None = None
    bundle_hash: str | None = None
    
    # Timestamps
    created_at: datetime


class DIDVerificationResponse(BaseModel):
    """Response from DID verification."""
    wallet_address: str
    status: DIDStatusEnum
    business_name: str | None = None
    registration_number: str | None = None
    country: str | None = None
    message: str = ""


class MintTransactionResponse(BaseModel):
    """Prepared mint transaction for client signing."""
    transaction_type: str = "NFTokenMint"
    account: str
    uri_hex: str
    flags: int
    transfer_fee: int
    nftoken_taxon: int
    memos: list[dict[str, Any]]
    
    # For display
    face_value: str
    sale_price: str
    currency: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    database: str = "connected"
    xrpl_network: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: str | None = None
    code: str | None = None
