"""Celery application configuration."""

from celery import Celery

from josephus.core.config import get_settings


def create_celery_app() -> Celery:
    """Create and configure Celery application."""
    settings = get_settings()

    app = Celery(
        "josephus",
        broker=str(settings.redis_url),
        backend=str(settings.redis_url),
        include=["josephus.worker.tasks"],
    )

    app.conf.update(
        # Task settings
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        # Retry settings
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        # Result settings
        result_expires=3600,  # 1 hour
        # Worker settings
        worker_prefetch_multiplier=1,  # One task at a time for long-running jobs
        worker_concurrency=2,  # 2 concurrent workers
        # Task routes (can be expanded later)
        task_routes={
            "josephus.worker.tasks.generate_documentation": {"queue": "docs"},
            "josephus.worker.tasks.analyze_pull_request": {"queue": "docs"},
        },
        # Default queue
        task_default_queue="default",
    )

    return app


# Create the app instance
celery_app = create_celery_app()
