"""
DID (Decentralized Identifier) verification service.

Validates that a wallet address has a valid business DID
associated with it on the XRPL.

Note: For hackathon MVP, DID verification is simplified.
Production would use full XLS-40d DID resolution.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import xrpl
import asyncio
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.models import AccountObjects, AccountObjectType

logger = logging.getLogger(__name__)


# JSON-RPC endpoints (more reliable, no SSL WebSocket issues)
NETWORK_URLS = {
    "mainnet": "https://xrplcluster.com",
    "testnet": "https://s.altnet.rippletest.net:51234",
    "devnet": "https://s.devnet.rippletest.net:51234",
}


class DIDStatus(Enum):
    """Status of DID verification."""
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INVALID = "invalid"
    PENDING = "pending"
    SKIPPED = "skipped"


@dataclass
class DIDDocument:
    """
    Parsed DID document from the ledger.
    """
    did: str
    controller: str
    created: datetime
    updated: datetime | None
    verification_methods: list[dict[str, Any]]
    services: list[dict[str, Any]]
    business_name: str | None = None
    registration_number: str | None = None
    country: str | None = None
    
    @property
    def is_business(self) -> bool:
        """Check if DID has required business claims."""
        return self.business_name is not None


@dataclass
class DIDVerificationResult:
    """Result of DID verification for a wallet."""
    wallet_address: str
    status: DIDStatus
    did_document: DIDDocument | None = None
    message: str = ""
    
    @property
    def is_verified(self) -> bool:
        """True if DID is valid for invoice factoring."""
        return self.status == DIDStatus.VERIFIED


class DIDVerifier:
    """
    Service for verifying DID ownership and business legitimacy.
    
    Uses AsyncJsonRpcClient to avoid asyncio.run() issues in FastAPI.
    """
    
    DID_METHOD = "did:xrpl"
    
    def __init__(
        self,
        network: str = "testnet",
        xrpl_url: str | None = None,
        cache_ttl_seconds: int = 300,
    ) -> None:
        """
        Initialize DID verifier.
        
        Args:
            network: XRPL network (testnet, mainnet, devnet)
            xrpl_url: Override URL (ignored, using JSON-RPC)
            cache_ttl_seconds: How long to cache verification results
        """
        self.network = network
        self.url = NETWORK_URLS.get(network, NETWORK_URLS["testnet"])
        self.cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[DIDVerificationResult, datetime]] = {}
        self._client: AsyncJsonRpcClient | None = None
    
    def _get_client(self) -> AsyncJsonRpcClient:
        """Get or create AsyncJsonRpcClient."""
        if self._client is None:
            self._client = AsyncJsonRpcClient(self.url)
        return self._client
    
    async def verify_wallet(
        self, 
        wallet_address: str, 
        bypass_cache: bool = False
    ) -> DIDVerificationResult:
        """
        Verify that a wallet has a valid business DID.
        
        Args:
            wallet_address: XRPL wallet address (r...)
            bypass_cache: If True, force fresh lookup
            
        Returns:
            DIDVerificationResult with status and document if found
        """
        # Check cache first (unless bypassed)
        if not bypass_cache:
            cached = self._get_cached(wallet_address)
            if cached:
                logger.info(f"Returning cached DID result for {wallet_address}: {cached.status}")
                return cached
        else:
            logger.info(f"Bypassing cache for DID check: {wallet_address}")
        
        try:
            client = self._get_client()
            
            # Query for ALL objects to debug
            request = AccountObjects(
                account=wallet_address,
                # type=AccountObjectType.DID, # Commented out to see all objects
            )
            logger.info(f"Querying XRPL for ALL objects: {wallet_address} on {self.url}")
            response = await client.request(request)
            
            if not response.is_successful():
                logger.warning(f"Failed to query objects for {wallet_address}: {response.result}")
                result = DIDVerificationResult(
                    wallet_address=wallet_address,
                    status=DIDStatus.NOT_FOUND,
                    message=f"XRPL Query Failed: {response.result.get('error_message', 'Unknown error')}",
                )
                self._cache_result(wallet_address, result)
                return result
            
            account_objects = response.result.get("account_objects", [])
            logger.info(f"Found {len(account_objects)} total account objects")
            for i, obj in enumerate(account_objects):
                logger.info(f"Object {i}: Type={obj.get('LedgerEntryType')}")
            
            # Find DID object
            did_object = None
            for obj in account_objects:
                if obj.get("LedgerEntryType") == "DID":
                    did_object = obj
                    break
            
            if not did_object:
                logger.info(f"No DID object found in account objects for {wallet_address}")
                result = DIDVerificationResult(
                    wallet_address=wallet_address,
                    status=DIDStatus.NOT_FOUND,
                    message="No DID found for this wallet",
                )
                self._cache_result(wallet_address, result)
                return result
            
            logger.info(f"Found DID object: {did_object}")

            # Parse DID document
            did_doc = self._parse_did_document(wallet_address, did_object)
            logger.info(f"Parsed DID Document: {did_doc}")
            
            # For MVP, just having a DID is enough
            # Production would validate specific business claims
            result = DIDVerificationResult(
                wallet_address=wallet_address,
                status=DIDStatus.VERIFIED,
                did_document=did_doc,
                message="DID found on ledger",
            )
            self._cache_result(wallet_address, result)
            return result
            
        except Exception as e:
            logger.exception(f"DID verification failed for {wallet_address}")
            # Return not_found instead of failing - allows testing without DID
            return DIDVerificationResult(
                wallet_address=wallet_address,
                status=DIDStatus.NOT_FOUND,
                message=f"Verification error: {str(e)}",
            )
    
    # Alias for compatibility
    async def verify_wallet_async(self, wallet_address: str) -> DIDVerificationResult:
        """Async wrapper around verify_wallet."""
        return await self.verify_wallet(wallet_address)
    
    def _parse_did_document(
        self,
        wallet_address: str,
        did_object: dict[str, Any],
    ) -> DIDDocument:
        """Parse XRPL DID object into DIDDocument."""
        uri = did_object.get("URI", "")
        data = did_object.get("Data", "")
        
        # Decode hex-encoded fields
        try:
            if uri:
                uri = bytes.fromhex(uri).decode("utf-8")
            if data:
                data = bytes.fromhex(data).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            pass
        
        did = f"{self.DID_METHOD}:{wallet_address}"
        
        # Parse business claims from data field
        business_name = None
        registration_number = None
        country = None
        
        if data:
            parts = data.split("|")
            if len(parts) >= 1:
                business_name = parts[0]
            if len(parts) >= 2:
                registration_number = parts[1]
            if len(parts) >= 3:
                country = parts[2]
        
        return DIDDocument(
            did=did,
            controller=wallet_address,
            created=datetime.now(timezone.utc),
            updated=None,
            verification_methods=[],
            services=[],
            business_name=business_name,
            registration_number=registration_number,
            country=country,
        )
    
    def _get_cached(self, wallet_address: str) -> DIDVerificationResult | None:
        """Get cached verification result if not expired."""
        if wallet_address not in self._cache:
            return None
        
        result, cached_at = self._cache[wallet_address]
        age_seconds = (datetime.now(timezone.utc) - cached_at).total_seconds()
        
        if age_seconds > self.cache_ttl:
            del self._cache[wallet_address]
            return None
        
        return result
    
    def _cache_result(
        self,
        wallet_address: str,
        result: DIDVerificationResult,
    ) -> None:
        """Cache a verification result."""
        self._cache[wallet_address] = (result, datetime.now(timezone.utc))
    
    def clear_cache(self) -> None:
        """Clear all cached verification results."""
        self._cache.clear()


def create_skipped_result(wallet_address: str) -> DIDVerificationResult:
    """Create a result for when DID check is skipped."""
    return DIDVerificationResult(
        wallet_address=wallet_address,
        status=DIDStatus.SKIPPED,
        message="DID verification skipped",
    )
