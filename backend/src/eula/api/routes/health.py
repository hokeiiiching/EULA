"""
Health check endpoint.

Provides system health status for monitoring and load balancers.
"""

from fastapi import APIRouter, Depends

from eula import __version__
from eula.api.schemas import HealthResponse
from eula.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Check system health.
    
    Returns status of core components for monitoring dashboards
    and load balancer health checks.
    """
    settings = get_settings()
    
    return HealthResponse(
        status="healthy",
        version=__version__,
        database="connected",  # Would check actual connection in production
        xrpl_network=settings.xrpl_network,
    )
