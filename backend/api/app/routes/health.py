"""
Health check endpoints for monitoring and readiness probes.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.metrics import get_metrics_response

router = APIRouter()


@router.get("/")
async def health():
    """Basic health check."""
    return {"status": "healthy", "service": "wdfwatch-api"}


@router.get("/ready")
async def readiness():
    """Readiness probe - checks if service can accept requests."""
    # Check if episodes directory is accessible
    episodes_accessible = settings.EPISODES_DIR.exists() and settings.EPISODES_DIR.is_dir()
    
    # Check if orchestrator exists
    orchestrator_exists = settings.ORCHESTRATOR_PATH.exists()
    
    if not episodes_accessible or not orchestrator_exists:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not ready",
                "checks": {
                    "episodes_dir": episodes_accessible,
                    "orchestrator": orchestrator_exists,
                },
            },
        )
    
    return {
        "status": "ready",
        "checks": {
            "episodes_dir": True,
            "orchestrator": True,
        },
    }


@router.get("/live")
async def liveness():
    """Liveness probe - checks if service is running."""
    return {"status": "alive"}


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics_response()

