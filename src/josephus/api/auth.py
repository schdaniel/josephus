"""API authentication utilities."""

import secrets

import logfire
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from josephus.core.config import get_settings

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> bool:
    """Verify API key for protected endpoints.

    In development mode, allows requests without API key (with warning).
    In production, requires valid API key.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        True if authentication succeeds

    Raises:
        HTTPException: If authentication fails
    """
    settings = get_settings()

    # Check if API key is configured
    if not settings.api_key:
        if settings.environment != "development":
            logfire.error(
                "API key not configured in production environment",
                environment=settings.environment,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API authentication not configured",
            )
        logfire.warn("API key authentication disabled in development mode")
        return True

    # Verify API key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, settings.api_key):
        logfire.warn("Invalid API key provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return True
