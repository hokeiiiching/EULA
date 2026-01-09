"""
XRPL integration service for NFT operations.

Based on official XRPL Python tutorial:
https://xrpl.org/docs/tutorials/python/nfts/mint-and-burn-nfts

Handles:
- NFTokenMint transaction creation and submission
- Account NFT queries
- Synchronous client for reliability
"""

import json
import logging
import ssl
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

import xrpl
from xrpl.clients import JsonRpcClient
from xrpl.models import NFTokenMint, AccountNFTs
from xrpl.transaction import sign_and_submit
from xrpl.wallet import Wallet

logger = logging.getLogger(__name__)


class XRPLNetwork(Enum):
    """Supported XRPL networks."""
    MAINNET = "mainnet"
    TESTNET = "testnet"
    DEVNET = "devnet"


# JSON-RPC endpoints (more reliable than WebSocket for quick operations)
NETWORK_URLS = {
    XRPLNetwork.MAINNET: "https://xrplcluster.com",
    XRPLNetwork.TESTNET: "https://s.altnet.rippletest.net:51234",
    XRPLNetwork.DEVNET: "https://s.devnet.rippletest.net:51234",
}


@dataclass
class NFTMetadata:
    """
    NFT metadata following EULA schema.
    
    This structure is stored in the NFT URI and provides
    tamper-evident document verification.
    """
    invoice_number: str
    face_value: Decimal
    currency: str
    due_date: date
    issuer_did: str
    invoice_hash: str
    po_hash: str
    pod_hash: str
    
    def to_json(self) -> str:
        """Serialize to JSON for NFT URI."""
        return json.dumps({
            "schema": "EULA_v1",
            "name": f"Verified Invoice: #{self.invoice_number}",
            "description": "3-Way Matched Supply Chain Asset",
            "properties": {
                "issuer_did": self.issuer_did,
                "face_value": str(self.face_value),
                "currency": self.currency,
                "due_date": self.due_date.isoformat(),
                "audit_status": "PASSED_AI_VERIFICATION",
                "document_hashes": {
                    "invoice_hash": self.invoice_hash,
                    "po_hash": self.po_hash,
                    "pod_hash": self.pod_hash,
                },
            },
        })
    
    def to_hex(self) -> str:
        """Convert to hex-encoded URI for XRPL."""
        return self.to_json().encode('utf-8').hex().upper()


@dataclass
class MintResult:
    """Result of NFT minting operation."""
    success: bool
    nft_id: str | None = None
    tx_hash: str | None = None
    error: str | None = None


@dataclass 
class DuplicateCheckResult:
    """Result of checking for duplicate invoice hashes."""
    is_duplicate: bool
    existing_nft_id: str | None = None
    existing_issuer: str | None = None
    message: str = ""


class XRPLService:
    """
    Service for XRPL NFT operations following official tutorial pattern.
    
    Uses JSON-RPC client for reliability and follows the pattern from:
    https://xrpl.org/docs/tutorials/python/nfts/mint-and-burn-nfts
    
    Example:
        service = XRPLService(network=XRPLNetwork.TESTNET)
        
        # Mint NFT with wallet seed
        result = service.mint_nft(
            seed="sEdVW...",
            uri="ipfs://...",
            flags=8,
            transfer_fee=500,
            taxon=1
        )
        
        if result.success:
            print(f"Minted NFT: {result.nft_id}")
    """
    
    # NFT flags
    FLAG_TRANSFERABLE = 8  # tfTransferable
    
    # Default transfer fee: 0.5% (500 basis points, max 50000 = 50%)
    DEFAULT_TRANSFER_FEE = 500
    
    # Taxon for EULA invoice NFTs
    INVOICE_TAXON = 1
    
    def __init__(
        self,
        network: XRPLNetwork = XRPLNetwork.TESTNET,
        custom_url: str | None = None,
    ) -> None:
        """
        Initialize XRPL service.
        
        Args:
            network: XRPL network to connect to
            custom_url: Override network URL (for testing)
        """
        self.network = network
        self.url = custom_url or NETWORK_URLS[network]
        self._client: JsonRpcClient | None = None
    
    def _get_client(self) -> JsonRpcClient:
        """Get or create JSON-RPC client."""
        if self._client is None:
            self._client = JsonRpcClient(self.url)
        return self._client
    
    def mint_nft(
        self,
        seed: str,
        uri: str,
        flags: int = FLAG_TRANSFERABLE,
        transfer_fee: int = DEFAULT_TRANSFER_FEE,
        taxon: int = INVOICE_TAXON,
    ) -> MintResult:
        """
        Mint an NFT on the XRPL.
        
        This follows the official XRPL Python tutorial pattern:
        1. Create wallet from seed
        2. Build NFTokenMint transaction
        3. Sign and submit
        4. Extract NFT ID from metadata
        
        Args:
            seed: Wallet seed (secret)
            uri: NFT URI (will be hex-encoded)
            flags: NFT flags (default: transferable)
            transfer_fee: Transfer fee in basis points (0-50000)
            taxon: NFT taxon for grouping
            
        Returns:
            MintResult with success status and NFT ID
        """
        try:
            # Create wallet from seed
            wallet = Wallet.from_seed(seed)
            logger.info(f"Minting NFT for account: {wallet.classic_address}")
            
            # Hex-encode URI if not already
            if not uri.startswith(('ipfs://', 'http')):
                uri_hex = uri  # Already hex
            else:
                uri_hex = uri.encode('utf-8').hex().upper()
            
            # Build NFTokenMint transaction
            mint_tx = NFTokenMint(
                account=wallet.classic_address,
                uri=uri_hex,
                flags=flags,
                transfer_fee=transfer_fee,
                nftoken_taxon=taxon,
            )
            
            # Sign and submit
            client = self._get_client()
            response = sign_and_submit(mint_tx, client, wallet)
            
            # Check result
            result = response.result
            
            if result.get("meta", {}).get("TransactionResult") == "tesSUCCESS":
                # Extract NFT ID from affected nodes
                nft_id = self._extract_nft_id(result)
                tx_hash = result.get("hash")
                
                logger.info(f"NFT minted successfully: {nft_id}")
                return MintResult(
                    success=True,
                    nft_id=nft_id,
                    tx_hash=tx_hash,
                )
            else:
                error = result.get("meta", {}).get("TransactionResult", "Unknown error")
                logger.error(f"NFT mint failed: {error}")
                return MintResult(
                    success=False,
                    error=error,
                )
                
        except Exception as e:
            logger.exception("NFT minting failed")
            return MintResult(
                success=False,
                error=str(e),
            )
    
    def mint_invoice_nft(
        self,
        seed: str,
        metadata: NFTMetadata,
    ) -> MintResult:
        """
        Mint an invoice NFT with EULA metadata.
        
        Args:
            seed: Wallet seed
            metadata: NFT metadata with invoice details
            
        Returns:
            MintResult with NFT ID if successful
        """
        return self.mint_nft(
            seed=seed,
            uri=metadata.to_hex(),
            flags=self.FLAG_TRANSFERABLE,
            transfer_fee=self.DEFAULT_TRANSFER_FEE,
            taxon=self.INVOICE_TAXON,
        )
    
    def get_account_nfts(self, account: str) -> list[dict[str, Any]]:
        """
        Get all NFTs owned by an account.
        
        Args:
            account: XRPL wallet address (r...)
            
        Returns:
            List of NFT objects from the ledger
        """
        try:
            client = self._get_client()
            request = AccountNFTs(account=account)
            response = client.request(request)
            
            if response.is_successful():
                return response.result.get("account_nfts", [])
            
            logger.warning(f"Failed to get NFTs for {account}: {response.result}")
            return []
            
        except Exception as e:
            logger.exception(f"Failed to get NFTs for {account}")
            return []
    
    def check_duplicate(self, invoice_hash: str) -> DuplicateCheckResult:
        """
        Check if an invoice hash already exists on the ledger.
        
        Note: This is a simplified check. Production systems should
        maintain an off-chain index of NFT hashes for efficiency.
        
        Args:
            invoice_hash: SHA-256 hash of the invoice document
            
        Returns:
            DuplicateCheckResult indicating if hash exists
        """
        # For MVP, we just log a warning about the limitation
        # A full implementation would query an off-chain index
        logger.warning(
            "Duplicate check is limited. Production should use "
            "an off-chain index of NFT hashes for efficient lookup."
        )
        
        return DuplicateCheckResult(
            is_duplicate=False,
            message="Hash not found in local index (simplified check)",
        )
    
    def _extract_nft_id(self, tx_result: dict[str, Any]) -> str | None:
        """Extract NFT ID from transaction metadata."""
        try:
            affected_nodes = tx_result.get("meta", {}).get("AffectedNodes", [])
            
            for node in affected_nodes:
                # Look for created NFTokenPage
                created = node.get("CreatedNode", {})
                if created.get("LedgerEntryType") == "NFTokenPage":
                    nftokens = created.get("NewFields", {}).get("NFTokens", [])
                    if nftokens:
                        return nftokens[-1].get("NFToken", {}).get("NFTokenID")
                
                # Look for modified NFTokenPage
                modified = node.get("ModifiedNode", {})
                if modified.get("LedgerEntryType") == "NFTokenPage":
                    final_nftokens = modified.get("FinalFields", {}).get("NFTokens", [])
                    prev_nftokens = modified.get("PreviousFields", {}).get("NFTokens", [])
                    
                    # Find the new token (in final but not in previous)
                    if len(final_nftokens) > len(prev_nftokens):
                        return final_nftokens[-1].get("NFToken", {}).get("NFTokenID")
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not extract NFT ID: {e}")
            return None
    
    def prepare_mint_payload(
        self,
        account: str,
        metadata: NFTMetadata,
    ) -> dict[str, Any]:
        """
        Prepare an NFTokenMint transaction payload for client-side signing.
        
        Use this when the frontend has the wallet and will sign the transaction.
        
        Args:
            account: Wallet address of the issuer (SME)
            metadata: NFT metadata with document hashes
            
        Returns:
            Transaction payload ready for signing
        """
        return {
            "TransactionType": "NFTokenMint",
            "Account": account,
            "URI": metadata.to_hex(),
            "Flags": self.FLAG_TRANSFERABLE,
            "TransferFee": self.DEFAULT_TRANSFER_FEE,
            "NFTokenTaxon": self.INVOICE_TAXON,
        }
