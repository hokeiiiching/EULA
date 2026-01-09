"""
Application configuration loaded from environment variables.

All configuration is validated at startup to fail fast on misconfiguration.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with validation.
    
    All settings are loaded from environment variables with the same name.
    Use .env file for local development.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Database
    database_url: PostgresDsn = Field(
        description="PostgreSQL connection string with asyncpg driver"
    )
    
    # XRPL Configuration
    xrpl_network: Literal["testnet", "mainnet", "devnet"] = Field(
        default="testnet",
        description="XRPL network to connect to"
    )
    xrpl_wallet_seed: str | None = Field(
        default=None,
        description="Wallet seed for backend signing operations (optional for read-only)"
    )
    
    # Storage
    storage_path: Path = Field(
        default=Path("./storage"),
        description="Local path for document storage"
    )
    
    # OCR Configuration
    ocr_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for OCR fields (0-1)"
    )
    
    # Server
    debug: bool = Field(
        default=False,
        description="Enable debug mode with detailed error messages"
    )
    
    @property
    def xrpl_url(self) -> str:
        """Return the WebSocket URL for the configured XRPL network."""
        urls = {
            "testnet": "wss://s.altnet.rippletest.net:51233",
            "mainnet": "wss://xrplcluster.com",
            "devnet": "wss://s.devnet.rippletest.net:51233",
        }
        return urls[self.xrpl_network]


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Settings are loaded once at startup and cached for subsequent calls.
    This ensures consistent configuration across the application lifecycle.
    """
    return Settings()
