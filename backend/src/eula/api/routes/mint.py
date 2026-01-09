"""
NFT minting endpoints.

Prepares transactions for client-side signing and submission.
"""

import logging
import traceback
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status

from eula.api.schemas import MintTransactionResponse, PrepareMinRequest
from eula.config import get_settings
from eula.services.xrpl import NFTMetadata, XRPLNetwork, XRPLService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mint", tags=["minting"])


@router.post(
    "/prepare",
    response_model=MintTransactionResponse,
    responses={
        400: {"description": "Invalid verification or not eligible for minting"},
        404: {"description": "Verification not found"},
        500: {"description": "Internal server error during mint preparation"},
    },
)
async def prepare_mint_transaction(
    request: PrepareMinRequest,
) -> MintTransactionResponse:
    """
    Prepare an NFTokenMint transaction for client signing.
    
    Given a successful verification ID, prepares the transaction
    payload that the user signs with their wallet.
    
    **Note:** This endpoint does not submit the transaction.
    The frontend must have the user sign it with Xumm/Crossmark.
    """
    logger.info("=" * 60)
    logger.info("MINT PREPARE REQUEST")
    logger.info("=" * 60)
    logger.info(f"  verification_id: {request.verification_id}")
    logger.info(f"  wallet_address: {request.wallet_address}")
    logger.info(f"  discount_percent: {request.discount_percent}")
    
    try:
        # Get settings
        logger.info("Loading settings...")
        settings = get_settings()
        logger.info(f"  XRPL network: {settings.xrpl_network}")
        
        # Initialize XRPL service
        logger.info("Initializing XRPL service...")
        try:
            network = XRPLNetwork(settings.xrpl_network)
            logger.info(f"  Network enum: {network}")
        except Exception as e:
            logger.error(f"Failed to parse XRPL network: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Invalid XRPL network config: {settings.xrpl_network}",
            )
        
        try:
            xrpl = XRPLService(network=network)
            logger.info("  XRPLService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize XRPLService: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize XRPL service: {str(e)}",
            )
        
        # Calculate pricing
        # In production, we'd look up the verification record from database
        # For now, use sample data for demonstration
        face_value = Decimal("8000.00")  # Would come from verification record
        discount = Decimal(str(request.discount_percent)) / 100
        sale_price = face_value * (1 - discount)
        
        logger.info("Pricing calculated:")
        logger.info(f"  face_value: {face_value}")
        logger.info(f"  discount: {discount} ({request.discount_percent}%)")
        logger.info(f"  sale_price: {sale_price}")
        
        # Build metadata
        logger.info("Building NFT metadata...")
        metadata = NFTMetadata(
            invoice_number="INV-2024-001",
            face_value=face_value,
            currency="RLUSD",
            due_date=date.today(),
            issuer_did=f"did:xrpl:{request.wallet_address}",
            invoice_hash="sha256:a1b2c3d4e5f6...",
            po_hash="sha256:b2c3d4e5f6g7...",
            pod_hash="sha256:c3d4e5f6g7h8...",
        )
        logger.info(f"  metadata: {metadata}")
        
        # Prepare transaction
        logger.info("Preparing mint transaction...")
        try:
            payload = xrpl.prepare_mint_payload(
                account=request.wallet_address,
                metadata=metadata,
            )
            logger.info(f"  Transaction payload prepared successfully")
            logger.info(f"    Account: {payload['Account']}")
            logger.info(f"    URI length: {len(payload['URI'])} chars")
            logger.info(f"    Flags: {payload['Flags']}")
            logger.info(f"    TransferFee: {payload['TransferFee']}")
            logger.info(f"    NFTokenTaxon: {payload['NFTokenTaxon']}")
        except Exception as e:
            logger.error(f"Failed to prepare mint transaction: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to prepare mint transaction: {str(e)}",
            )
        
        # Build response
        logger.info("Building response...")
        response = MintTransactionResponse(
            transaction_type=payload["TransactionType"],
            account=payload["Account"],
            uri_hex=payload["URI"],
            flags=payload["Flags"],
            transfer_fee=payload["TransferFee"],
            nftoken_taxon=payload["NFTokenTaxon"],
            memos=[],
            face_value=str(face_value),
            sale_price=str(sale_price),
            currency="RLUSD",
        )
        
        logger.info("=" * 60)
        logger.info("MINT PREPARE SUCCESS")
        logger.info("=" * 60)
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
        
    except Exception as e:
        # Catch any unexpected errors
        logger.error("=" * 60)
        logger.error("MINT PREPARE FAILED - UNEXPECTED ERROR")
        logger.error("=" * 60)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(traceback.format_exc())
        
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {type(e).__name__}: {str(e)}",
        )
