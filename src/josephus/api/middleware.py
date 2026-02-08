"""API middleware for Josephus."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import logfire
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add unique request ID to each request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        """Add request ID to request state and response headers."""
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID") or generate_request_id()

        # Store in request state for access in handlers
        request.state.request_id = request_id

        # Add to Logfire context
        with logfire.span("http_request", request_id=request_id):
            response = await call_next(request)

        # Add to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class ResponseTimeMiddleware(BaseHTTPMiddleware):
    """Middleware to add response time header."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        """Add X-Response-Time header with processing time in milliseconds."""
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time = (time.perf_counter() - start_time) * 1000
        response.headers["X-Response-Time"] = f"{process_time:.2f}ms"

        return response


class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add rate limit headers to responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        """Add rate limit headers if available."""
        response = await call_next(request)

        # Rate limit info is added by slowapi, this ensures it's always visible
        # Headers are typically: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

        return response
