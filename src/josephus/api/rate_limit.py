"""Rate limiting configuration for API endpoints."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from josephus.core.config import get_settings


def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key based on client identity.

    Uses IP address as the default key. Can be extended to use
    API key or installation ID for more granular rate limiting.
    """
    return get_remote_address(request)


def get_rate_limit_key_installation(request: Request) -> str:
    """Get rate limit key based on installation ID from request body.

    Falls back to IP address if installation_id is not available.
    """
    # Try to get installation_id from cached body (set by middleware)
    if hasattr(request.state, "body_json"):
        installation_id = request.state.body_json.get("installation_id")
        if installation_id:
            return f"installation:{installation_id}"

    return get_remote_address(request)


# Create limiter instance
# Uses in-memory storage by default, can be configured to use Redis
settings = get_settings()
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["100/minute"],  # Default rate limit for all endpoints
    storage_uri=str(settings.redis_url) if settings.environment != "development" else None,
    strategy="fixed-window",
)

# Rate limit configurations for different endpoints
# Format: "requests/period" where period can be second, minute, hour, day
RATE_LIMITS = {
    # Expensive operations - strict limits
    "generate": "5/minute",  # Documentation generation is expensive (LLM calls)
    "webhooks": "60/minute",  # GitHub may send bursts of webhooks

    # Read operations - more lenient
    "jobs_list": "30/minute",
    "job_status": "60/minute",
}
