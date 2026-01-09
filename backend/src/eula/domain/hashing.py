"""
Cryptographic hashing utilities for document deduplication and tamper detection.

The hash-on-chain model stores document hashes in NFT metadata while keeping
the actual document content off-chain. This provides:
1. Privacy: Sensitive document content is not exposed on public ledger
2. Tamper detection: Any modification invalidates the original hash
3. Deduplication: Same document hash prevents double financing

Design Decisions:
- SHA-256 chosen for wide support and collision resistance
- Hash computed on raw bytes to avoid encoding issues
- Deterministic hashing requires consistent input handling
"""

import hashlib
from pathlib import Path


def compute_document_hash(content: bytes) -> str:
    """
    Compute SHA-256 hash of document content.
    
    Args:
        content: Raw bytes of the document file (PDF, image, etc.)
        
    Returns:
        Hex-encoded SHA-256 hash prefixed with 'sha256:'
        
    Example:
        >>> compute_document_hash(b"invoice content")
        'sha256:a1b2c3d4...'
    """
    if not content:
        raise ValueError("Cannot hash empty content")
    
    digest = hashlib.sha256(content).hexdigest()
    return f"sha256:{digest}"


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA-256 hash of a file on disk.
    
    Reads file in chunks to handle large documents efficiently.
    
    Args:
        file_path: Path to the document file
        
    Returns:
        Hex-encoded SHA-256 hash prefixed with 'sha256:'
        
    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    hasher = hashlib.sha256()
    chunk_size = 65536  # 64KB chunks
    
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    
    return f"sha256:{hasher.hexdigest()}"


def verify_hash(content: bytes, expected_hash: str) -> bool:
    """
    Verify that content matches an expected hash.
    
    Used for tamper detection when retrieving documents from storage.
    
    Args:
        content: Raw bytes of the document
        expected_hash: The hash to verify against (with 'sha256:' prefix)
        
    Returns:
        True if hash matches, False otherwise
    """
    if not expected_hash.startswith("sha256:"):
        raise ValueError(f"Invalid hash format, expected 'sha256:' prefix: {expected_hash}")
    
    actual_hash = compute_document_hash(content)
    return actual_hash == expected_hash


def compute_bundle_hash(
    invoice_hash: str,
    po_hash: str,
    pod_hash: str,
) -> str:
    """
    Compute a combined hash for a document bundle.
    
    This creates a single unique identifier for the entire 3-way match set.
    The combined hash is used for bundle-level deduplication on the ledger.
    
    Args:
        invoice_hash: Hash of the invoice document
        po_hash: Hash of the purchase order document  
        pod_hash: Hash of the proof of delivery document
        
    Returns:
        Hex-encoded SHA-256 hash of the combined hashes
        
    Note:
        Hashes are sorted before combining to ensure deterministic output
        regardless of argument order.
    """
    # Validate format
    for hash_val in [invoice_hash, po_hash, pod_hash]:
        if not hash_val.startswith("sha256:"):
            raise ValueError(f"Invalid hash format: {hash_val}")
    
    # Sort for deterministic combination
    sorted_hashes = sorted([invoice_hash, po_hash, pod_hash])
    combined = "|".join(sorted_hashes)
    
    digest = hashlib.sha256(combined.encode()).hexdigest()
    return f"sha256:{digest}"
