"""
Database configuration and session management with SQLAlchemy.

Uses async SQLAlchemy for non-blocking database operations.
All audit records are persisted for compliance and debugging.

Design Decisions:
- AsyncSession for non-blocking operations
- Connection pooling with sensible defaults
- Explicit transaction management
- Session-per-request pattern
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, Numeric, Boolean, ForeignKey, JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from eula.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class VerificationRecord(Base):
    """
    Audit record for document verification attempts.
    
    Persists all verification attempts for compliance,
    debugging, and analytics.
    """
    __tablename__ = "verification_records"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Wallet and identity
    wallet_address: Mapped[str] = mapped_column(String(64), index=True)
    did_status: Mapped[str | None] = mapped_column(String(32))
    business_name: Mapped[str | None] = mapped_column(String(256))
    
    # Document hashes (for duplicate detection)
    invoice_hash: Mapped[str] = mapped_column(String(128), index=True)
    po_hash: Mapped[str] = mapped_column(String(128))
    pod_hash: Mapped[str] = mapped_column(String(128))
    bundle_hash: Mapped[str] = mapped_column(String(128), index=True)
    
    # Verification results
    status: Mapped[str] = mapped_column(String(32))  # passed, failed, requires_review
    checks_json: Mapped[dict] = mapped_column(JSON, default=dict)
    anomalies_json: Mapped[dict] = mapped_column(JSON, default=dict)
    review_flags: Mapped[str | None] = mapped_column(Text)
    
    # Extracted data (for debugging)
    invoice_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    po_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    pod_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Minting (if successful)
    nft_token_id: Mapped[str | None] = mapped_column(String(128))
    minted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentStorage(Base):
    """
    Reference to stored document files.
    
    Actual files are stored on disk/S3, this tracks metadata.
    """
    __tablename__ = "document_storage"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    
    verification_id: Mapped[str] = mapped_column(String(36), ForeignKey("verification_records.id"))
    document_type: Mapped[str] = mapped_column(String(32))  # invoice, po, pod
    
    # File info
    original_filename: Mapped[str] = mapped_column(String(256))
    content_type: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column()
    
    # Storage location
    storage_path: Mapped[str] = mapped_column(String(512))
    document_hash: Mapped[str] = mapped_column(String(128))
    
    # Encryption (for sensitive documents)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=True)
    encryption_key_id: Mapped[str | None] = mapped_column(String(64))


# Engine and session factory (initialized lazily)
_engine = None
_session_factory = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            str(settings.database_url),
            echo=settings.debug,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
        )
        # Extract host from MultiHostUrl (Pydantic v2)
        hosts = settings.database_url.hosts()
        host_info = hosts[0]["host"] if hosts else "unknown"
        logger.info(f"Database engine created for {host_info}")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory for creating database sessions."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session for a request.
    
    Usage:
        async with get_session() as session:
            session.add(record)
            await session.commit()
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """
    Initialize database tables.
    
    Call this on application startup to ensure tables exist.
    In production, use Alembic migrations instead.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")


async def close_db() -> None:
    """Close database connections on shutdown."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    logger.info("Database connections closed")
