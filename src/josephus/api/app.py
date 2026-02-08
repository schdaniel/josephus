"""FastAPI application setup."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi.errors import RateLimitExceeded

from josephus import __version__
from josephus.api.errors import (
    APIError,
    ErrorCode,
    ErrorResponse,
    api_error_handler,
    get_request_id,
    http_exception_handler,
    validation_exception_handler,
)
from josephus.api.middleware import RequestIDMiddleware, ResponseTimeMiddleware
from josephus.api.rate_limit import limiter
from josephus.api.routes import api_v1, health, webhooks
from josephus.core.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    settings = get_settings()

    # Initialize Logfire
    logfire.configure(
        service_name="josephus",
        environment=settings.environment,
    )

    # TODO: Initialize database connection pool
    # TODO: Initialize Redis connection
    # TODO: Initialize Celery

    yield

    # Cleanup
    # TODO: Close connections


def custom_openapi(app: FastAPI) -> dict:
    """Generate custom OpenAPI schema with additional documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Josephus API",
        version=__version__,
        description="""
## AI-Powered Documentation Generator

Josephus automatically generates customer-facing documentation from your codebase using AI.

### Features
- **Automatic Analysis**: Scans your repository to understand code structure
- **AI Generation**: Uses LLM to create comprehensive documentation
- **GitHub Integration**: Creates PRs with generated documentation
- **Customizable**: Configure guidelines and output formats

### Authentication
All API endpoints require authentication using an API key. Include your API key in the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

### Rate Limiting
API endpoints are rate limited to ensure fair usage:
- `/api/v1/generate`: 5 requests per minute
- `/api/v1/jobs/{id}`: 60 requests per minute
- `/api/v1/jobs`: 30 requests per minute

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Unix timestamp when the limit resets

### Error Handling
All errors return a consistent JSON format with:
- `error`: Error code for programmatic handling
- `message`: Human-readable description
- `request_id`: Unique ID for support reference
- `timestamp`: When the error occurred

### Request Tracking
Every response includes an `X-Request-ID` header for debugging and support.
        """,
        routes=app.routes,
        tags=[
            {"name": "api", "description": "Core API endpoints for documentation generation"},
            {"name": "health", "description": "Health check endpoints"},
            {"name": "webhooks", "description": "GitHub webhook endpoints"},
        ],
    )

    # Add error response schemas
    openapi_schema["components"]["schemas"]["ErrorResponse"] = ErrorResponse.model_json_schema()

    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": "API key for authentication",
        }
    }

    # Apply security to all API routes
    for path in openapi_schema["paths"]:
        if path.startswith("/api/"):
            for method in openapi_schema["paths"][path]:
                if method != "options":
                    openapi_schema["paths"][path][method]["security"] = [{"ApiKeyAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:  # noqa: ARG001
    """Custom rate limit exceeded handler with consistent error format."""
    request_id = get_request_id(request)

    # Parse retry_after from the exception message if available
    retry_after = 60  # Default to 60 seconds

    response = ErrorResponse(
        error=ErrorCode.RATE_LIMIT_EXCEEDED.value,
        message="Rate limit exceeded. Please slow down your requests.",
        request_id=request_id,
        details={"retry_after_seconds": retry_after},
        suggestion=f"Wait {retry_after} seconds before retrying",
    )

    return JSONResponse(
        status_code=429,
        content=response.model_dump(mode="json", exclude_none=True),
        headers={
            "X-Request-ID": request_id,
            "Retry-After": str(retry_after),
        },
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Josephus API",
        description="AI-powered documentation generator",
        version=__version__,
        lifespan=lifespan,
        # Always enable docs for better developer experience
        docs_url=None,  # We'll add custom docs endpoint
        redoc_url=None,  # We'll add custom redoc endpoint
        openapi_url="/api/openapi.json",
    )

    # Custom OpenAPI schema
    app.openapi = lambda: custom_openapi(app)

    # Add custom docs endpoints
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html() -> HTMLResponse:
        return get_redoc_html(
            openapi_url="/api/openapi.json",
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js",
        )

    # Middleware (order matters - first added is outermost)
    app.add_middleware(ResponseTimeMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Instrument with Logfire
    logfire.instrument_fastapi(app)

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # Error handlers
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Routes
    app.include_router(health.router, tags=["health"])
    app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
    app.include_router(api_v1.router, prefix="/api/v1", tags=["api"])

    return app


app = create_app()
