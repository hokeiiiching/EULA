"""
FastAPI application entry point.

This is the main application that ties together all components:
- API routes for document verification and minting
- Database lifecycle management
- CORS configuration for frontend access
- Error handling and logging
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from eula import __version__
from eula.api.routes import debug, health, mint, verification
from eula.config import get_settings
from eula.infrastructure.database import close_db, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown tasks:
    - Initialize database tables
    - Create storage directories
    - Clean up on shutdown
    """
    settings = get_settings()
    
    logger.info(f"Starting EULA v{__version__}")
    logger.info(f"XRPL Network: {settings.xrpl_network}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Continue anyway for development without DB
    
    # Ensure storage directory exists
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Storage path: {settings.storage_path}")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down EULA")
    await close_db()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI instance ready to serve requests.
    """
    settings = get_settings()
    
    app = FastAPI(
        title="EULA API",
        description=(
            "RWA Tokenization & Invoice Factoring Platform.\n\n"
            "Provides automated document verification and NFT minting "
            "for supply chain assets on the XRP Ledger."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )
    
    # CORS configuration
    # In production, replace with specific allowed origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://eula.io"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routers
    app.include_router(health.router)
    app.include_router(verification.router, prefix="/api/v1")
    app.include_router(mint.router, prefix="/api/v1")
    
    # Debug router (only in debug mode)
    if settings.debug:
        app.include_router(debug.router, prefix="/api/v1")
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch-all exception handler for unhandled errors."""
        logger.exception(f"Unhandled error: {exc}")
        
        # Don't expose internal errors in production
        if settings.debug:
            detail = str(exc)
        else:
            detail = "An internal error occurred"
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": detail,
            },
        )
    
    return app


# Create the application instance
app = create_app()


# Development server entry point
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "eula.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
