"""FastAPI application setup."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from josephus import __version__
from josephus.api.routes import health, webhooks
from josephus.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Josephus",
        description="AI-powered documentation generator",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Instrument with Logfire
    logfire.instrument_fastapi(app)

    # Routes
    app.include_router(health.router, tags=["health"])
    app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

    return app


app = create_app()
