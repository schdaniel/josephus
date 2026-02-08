"""Unit tests for API v1 endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from josephus.api.errors import APIError, api_error_handler
from josephus.api.routes import api_v1
from josephus.db.models import Job, JobStatus, Repository


def create_test_app() -> FastAPI:
    """Create minimal test app without logfire instrumentation."""
    app = FastAPI()
    app.add_exception_handler(APIError, api_error_handler)
    app.include_router(api_v1.router, prefix="/api/v1")
    return app


class TestGenerateEndpoint:
    """Tests for POST /api/v1/generate endpoint."""

    def test_generate_request_validation(self) -> None:
        """Test request validation for missing fields."""
        app = create_test_app()

        async def mock_session_gen():
            yield AsyncMock()

        app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(app)

        response = client.post("/api/v1/generate", json={})
        assert response.status_code == 422

    def test_generate_requires_installation_id(self) -> None:
        """Test that installation_id is required."""
        app = create_test_app()

        async def mock_session_gen():
            yield AsyncMock()

        app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(app)

        response = client.post(
            "/api/v1/generate",
            json={"owner": "user", "repo": "test"},
        )
        assert response.status_code == 422
        assert "installation_id" in response.text

    def test_generate_success(self) -> None:
        """Test successful generation request."""
        app = create_test_app()

        mock_repo = Repository(
            id=1,
            installation_id=12345,
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )
        mock_job = Job(
            id="test-job-id",
            repository_id=1,
            status=JobStatus.PENDING,
            ref="main",
            trigger="manual",
        )

        async def mock_session_gen():
            yield AsyncMock()

        app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(app)

        with (
            patch.object(api_v1, "get_or_create_repository") as mock_get_repo,
            patch.object(api_v1, "create_job") as mock_create_job,
            patch.object(api_v1, "celery_app") as mock_celery,
        ):
            mock_get_repo.return_value = mock_repo
            mock_create_job.return_value = mock_job

            response = client.post(
                "/api/v1/generate",
                json={
                    "installation_id": 12345,
                    "owner": "schdaniel",
                    "repo": "josephus",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-id"
            assert data["status"] == "queued"
            assert "schdaniel/josephus" in data["message"]
            mock_celery.send_task.assert_called_once()


class TestJobStatusEndpoint:
    """Tests for GET /api/v1/jobs/{job_id} endpoint."""

    def test_job_not_found(self) -> None:
        """Test 404 for non-existent job."""
        app = create_test_app()

        mock_session = AsyncMock()
        mock_session.get.return_value = None

        async def mock_session_gen():
            yield mock_session

        app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(app)

        response = client.get("/api/v1/jobs/nonexistent-id")
        assert response.status_code == 404

    def test_job_status_success(self) -> None:
        """Test successful job status retrieval."""
        app = create_test_app()

        mock_repo = Repository(
            id=1,
            installation_id=12345,
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )
        mock_job = Job(
            id="test-job-id",
            repository_id=1,
            status=JobStatus.COMPLETED,
            ref="main",
            trigger="manual",
            result_pr_url="https://github.com/schdaniel/josephus/pull/1",
            files_analyzed=10,
            tokens_used=5000,
        )

        mock_session = AsyncMock()

        async def mock_get(model: type, _id: str) -> Job | Repository | None:
            if model == Job:
                return mock_job
            if model == Repository:
                return mock_repo
            return None

        mock_session.get = mock_get

        async def mock_session_gen():
            yield mock_session

        app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(app)

        response = client.get("/api/v1/jobs/test-job-id")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-id"
        assert data["status"] == "completed"
        assert data["repository"] == "schdaniel/josephus"
        assert data["pr_url"] == "https://github.com/schdaniel/josephus/pull/1"


class TestListJobsEndpoint:
    """Tests for GET /api/v1/jobs endpoint."""

    def test_list_jobs_empty(self) -> None:
        """Test listing jobs when none exist."""
        app = create_test_app()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        async def mock_session_gen():
            yield mock_session

        app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(app)

        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_jobs_with_results(self) -> None:
        """Test listing jobs with results."""
        app = create_test_app()

        mock_repo = Repository(
            id=1,
            installation_id=12345,
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )
        mock_job = Job(
            id="test-job-id",
            repository_id=1,
            status=JobStatus.PENDING,
            ref="main",
            trigger="manual",
        )
        mock_job.repository = mock_repo

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_job]
        mock_session.execute.return_value = mock_result

        async def mock_session_gen():
            yield mock_session

        app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(app)

        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["job_id"] == "test-job-id"
