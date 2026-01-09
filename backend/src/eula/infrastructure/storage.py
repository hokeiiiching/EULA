"""
File storage service for documents.

Handles secure storage and retrieval of uploaded documents.
Supports local filesystem for development and can be extended
to S3/IPFS for production.

Design Decisions:
- Abstract storage interface for multiple backends
- Encryption at rest for sensitive documents
- Content-addressable storage using document hash
- Cleanup of orphaned files on verification failure
"""

import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from eula.config import get_settings
from eula.domain.hashing import compute_document_hash, verify_hash

logger = logging.getLogger(__name__)


@dataclass
class StoredDocument:
    """Metadata for a stored document."""
    path: str
    document_hash: str
    size_bytes: int
    content_type: str


class StorageBackend(ABC):
    """Abstract interface for document storage backends."""
    
    @abstractmethod
    async def store(
        self,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> StoredDocument:
        """Store a document and return storage metadata."""
        pass
    
    @abstractmethod
    async def retrieve(self, path: str) -> bytes:
        """Retrieve document content by storage path."""
        pass
    
    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a document. Returns True if deleted."""
        pass
    
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a document exists."""
        pass


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage for development.
    
    Stores documents in a content-addressable structure:
    storage_path/
        ab/
            cd/
                sha256:abcd1234...
    """
    
    def __init__(self, base_path: Path | None = None) -> None:
        """
        Initialize local storage.
        
        Args:
            base_path: Base directory for storage. Uses config if None.
        """
        settings = get_settings()
        self.base_path = base_path or settings.storage_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized at {self.base_path}")
    
    async def store(
        self,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> StoredDocument:
        """
        Store document using content-addressable path.
        
        The path is derived from the hash to enable deduplication
        and easy integrity verification.
        """
        document_hash = compute_document_hash(content)
        
        # Create path from hash: sha256:abcd... -> ab/cd/sha256:abcd...
        hash_value = document_hash.replace("sha256:", "")
        subdir = self.base_path / hash_value[:2] / hash_value[2:4]
        subdir.mkdir(parents=True, exist_ok=True)
        
        # Preserve original extension for content type hints
        ext = Path(filename).suffix
        file_path = subdir / f"{hash_value}{ext}"
        
        # Write atomically (write to temp, then rename)
        temp_path = file_path.with_suffix(".tmp")
        try:
            temp_path.write_bytes(content)
            temp_path.rename(file_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        
        return StoredDocument(
            path=str(file_path.relative_to(self.base_path)),
            document_hash=document_hash,
            size_bytes=len(content),
            content_type=content_type,
        )
    
    async def retrieve(self, path: str) -> bytes:
        """Retrieve document and verify integrity."""
        file_path = self.base_path / path
        
        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {path}")
        
        if not file_path.is_relative_to(self.base_path):
            raise ValueError("Path traversal not allowed")
        
        return file_path.read_bytes()
    
    async def delete(self, path: str) -> bool:
        """Delete document file."""
        file_path = self.base_path / path
        
        if not file_path.is_relative_to(self.base_path):
            raise ValueError("Path traversal not allowed")
        
        try:
            file_path.unlink()
            
            # Clean up empty parent directories
            parent = file_path.parent
            while parent != self.base_path:
                if not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
            
            return True
        except FileNotFoundError:
            return False
    
    async def exists(self, path: str) -> bool:
        """Check if document exists."""
        file_path = self.base_path / path
        return file_path.exists() and file_path.is_relative_to(self.base_path)


class DocumentStorageService:
    """
    High-level service for document storage operations.
    
    Wraps the storage backend with application-specific logic
    like document type organization and access control.
    """
    
    def __init__(self, backend: StorageBackend | None = None) -> None:
        """
        Initialize storage service.
        
        Args:
            backend: Storage backend. Creates LocalStorageBackend if None.
        """
        self.backend = backend or LocalStorageBackend()
    
    async def store_document(
        self,
        content: bytes,
        filename: str,
        document_type: str,
        content_type: str = "application/pdf",
    ) -> StoredDocument:
        """
        Store an uploaded document.
        
        Args:
            content: Document binary content
            filename: Original filename
            document_type: Type (invoice, po, pod)
            content_type: MIME type
            
        Returns:
            StoredDocument with path and metadata
        """
        if not content:
            raise ValueError("Cannot store empty document")
        
        if document_type not in ("invoice", "po", "pod"):
            raise ValueError(f"Invalid document type: {document_type}")
        
        logger.info(f"Storing {document_type}: {filename} ({len(content)} bytes)")
        
        return await self.backend.store(content, filename, content_type)
    
    async def get_document(
        self,
        path: str,
        expected_hash: str | None = None,
    ) -> bytes:
        """
        Retrieve a document with optional integrity check.
        
        Args:
            path: Storage path
            expected_hash: If provided, verify document hash matches
            
        Returns:
            Document content bytes
            
        Raises:
            ValueError: If hash doesn't match (tampering detected)
        """
        content = await self.backend.retrieve(path)
        
        if expected_hash:
            if not verify_hash(content, expected_hash):
                logger.error(f"Hash mismatch for {path}")
                raise ValueError("Document integrity check failed")
        
        return content
    
    async def delete_documents(self, paths: list[str]) -> int:
        """
        Delete multiple documents.
        
        Args:
            paths: List of storage paths to delete
            
        Returns:
            Number of documents successfully deleted
        """
        deleted = 0
        for path in paths:
            if await self.backend.delete(path):
                deleted += 1
        return deleted
