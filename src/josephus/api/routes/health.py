"""Health check endpoints."""

from fastapi import APIRouter

from josephus import __version__

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "version": __version__}


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check - verifies all dependencies are available."""
    # TODO: Check database connection
    # TODO: Check Redis connection
    # TODO: Check LLM provider availability
    return {"status": "ready"}
