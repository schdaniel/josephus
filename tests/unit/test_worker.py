"""Unit tests for background worker module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from josephus.db.models import JobStatus
from josephus.worker.celery_app import celery_app, create_celery_app
from josephus.worker.tasks import (
    create_job,
    get_or_create_repository,
    run_async,
)


class TestCeleryApp:
    """Tests for Celery application configuration."""

    def test_create_celery_app(self) -> None:
        """Test Celery app creation."""
        with patch("josephus.worker.celery_app.get_settings") as mock_settings:
            mock_settings.return_value.redis_url = "redis://localhost:6379/0"
            app = create_celery_app()

            assert app.main == "josephus"
            assert app.conf.task_serializer == "json"
            assert app.conf.result_serializer == "json"
            assert app.conf.timezone == "UTC"

    def test_celery_app_singleton(self) -> None:
        """Test that celery_app is the singleton instance."""
        assert celery_app is not None
        assert celery_app.main == "josephus"


class TestRunAsync:
    """Tests for async helper function."""

    def test_run_async_executes_coroutine(self) -> None:
        """Test run_async executes async functions."""

        async def async_func() -> str:
            return "result"

        result = run_async(async_func())
        assert result == "result"

    def test_run_async_with_arguments(self) -> None:
        """Test run_async passes arguments correctly."""

        async def async_add(a: int, b: int) -> int:
            return a + b

        result = run_async(async_add(2, 3))
        assert result == 5


class TestCreateJob:
    """Tests for create_job function."""

    @pytest.mark.asyncio
    async def test_create_job(self) -> None:
        """Test creating a job record."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        async def mock_refresh(job: object) -> None:
            pass

        mock_session.refresh = mock_refresh

        job = await create_job(
            session=mock_session,
            repository_id=1,
            ref="main",
            trigger="push",
        )

        assert job.repository_id == 1
        assert job.ref == "main"
        assert job.trigger == "push"
        assert job.status == JobStatus.PENDING
        assert job.id is not None
        mock_session.add.assert_called_once_with(job)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_with_pr_number(self) -> None:
        """Test creating a job with PR number."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        async def mock_refresh(job: object) -> None:
            pass

        mock_session.refresh = mock_refresh

        job = await create_job(
            session=mock_session,
            repository_id=1,
            ref="feature-branch",
            trigger="pull_request",
            pr_number=42,
        )

        assert job.pr_number == 42
        assert job.trigger == "pull_request"


class TestGetOrCreateRepository:
    """Tests for get_or_create_repository function."""

    @pytest.mark.asyncio
    async def test_get_existing_repository(self) -> None:
        """Test getting an existing repository."""
        from josephus.db.models import Repository

        existing_repo = Repository(
            id=1,
            installation_id=12345,
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_repo
        mock_session.execute.return_value = mock_result

        repo = await get_or_create_repository(
            session=mock_session,
            installation_id=12345,
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )

        assert repo.id == 1
        assert repo.full_name == "schdaniel/josephus"
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_new_repository(self) -> None:
        """Test creating a new repository."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.add = MagicMock()

        async def mock_refresh(repo: object) -> None:
            pass

        mock_session.refresh = mock_refresh

        repo = await get_or_create_repository(
            session=mock_session,
            installation_id=12345,
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )

        assert repo.owner == "schdaniel"
        assert repo.name == "josephus"
        assert repo.installation_id == 12345
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_installation_id(self) -> None:
        """Test updating installation ID when it changes."""
        from josephus.db.models import Repository

        existing_repo = Repository(
            id=1,
            installation_id=11111,  # Old installation ID
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_repo
        mock_session.execute.return_value = mock_result

        repo = await get_or_create_repository(
            session=mock_session,
            installation_id=22222,  # New installation ID
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )

        assert repo.installation_id == 22222
        mock_session.commit.assert_called_once()
