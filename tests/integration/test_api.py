"""Integration tests for API endpoints."""

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from josephus.api.routes import api_v1, webhooks
from josephus.db.models import Job, JobStatus, Repository


class TestGenerateEndpoint:
    """Integration tests for POST /api/v1/generate."""

    def test_generate_queues_job(
        self,
        test_app: FastAPI,
        mock_repository: Repository,
    ) -> None:
        """Test that generate endpoint queues a Celery job."""
        mock_job = Job(
            id="test-job-id",
            repository_id=1,
            status=JobStatus.PENDING,
            ref="main",
            trigger="manual",
        )

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(test_app)

        with (
            patch.object(api_v1, "get_or_create_repository") as mock_get_repo,
            patch.object(api_v1, "create_job") as mock_create_job,
            patch.object(api_v1, "celery_app") as mock_celery,
        ):
            mock_get_repo.return_value = mock_repository
            mock_create_job.return_value = mock_job

            response = client.post(
                "/api/v1/generate",
                json={
                    "installation_id": 12345,
                    "owner": "testuser",
                    "repo": "testrepo",
                    "ref": "main",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-id"
            assert data["status"] == "queued"

            # Verify Celery task was queued
            mock_celery.send_task.assert_called_once()
            call_kwargs = mock_celery.send_task.call_args[1]["kwargs"]
            assert call_kwargs["job_id"] == "test-job-id"
            assert call_kwargs["installation_id"] == 12345
            assert call_kwargs["owner"] == "testuser"
            assert call_kwargs["repo"] == "testrepo"

    def test_generate_with_custom_options(
        self,
        test_app: FastAPI,
        mock_repository: Repository,
    ) -> None:
        """Test generate endpoint with custom guidelines and output_dir."""
        mock_job = Job(
            id="test-job-id",
            repository_id=1,
            status=JobStatus.PENDING,
            ref="develop",
            trigger="manual",
        )

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(test_app)

        with (
            patch.object(api_v1, "get_or_create_repository") as mock_get_repo,
            patch.object(api_v1, "create_job") as mock_create_job,
            patch.object(api_v1, "celery_app") as mock_celery,
        ):
            mock_get_repo.return_value = mock_repository
            mock_create_job.return_value = mock_job

            response = client.post(
                "/api/v1/generate",
                json={
                    "installation_id": 12345,
                    "owner": "testuser",
                    "repo": "testrepo",
                    "ref": "develop",
                    "guidelines": "Write for beginners",
                    "output_dir": "documentation",
                },
            )

            assert response.status_code == 200

            # Verify custom options were passed
            call_kwargs = mock_celery.send_task.call_args[1]["kwargs"]
            assert call_kwargs["ref"] == "develop"
            assert call_kwargs["guidelines"] == "Write for beginners"
            assert call_kwargs["output_dir"] == "documentation"


class TestJobStatusEndpoint:
    """Integration tests for GET /api/v1/jobs/{job_id}."""

    def test_get_completed_job(
        self,
        test_app: FastAPI,
        mock_repository: Repository,
    ) -> None:
        """Test getting status of a completed job."""
        mock_job = Job(
            id="completed-job",
            repository_id=1,
            status=JobStatus.COMPLETED,
            ref="main",
            trigger="manual",
            result_pr_url="https://github.com/testuser/testrepo/pull/42",
            files_analyzed=10,
            tokens_used=5000,
        )

        mock_session = AsyncMock()

        async def mock_get(model: type, _id: str) -> Job | Repository | None:
            if model == Job:
                return mock_job
            if model == Repository:
                return mock_repository
            return None

        mock_session.get = mock_get

        async def mock_session_gen():
            yield mock_session

        test_app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(test_app)

        response = client.get("/api/v1/jobs/completed-job")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "completed-job"
        assert data["status"] == "completed"
        assert data["pr_url"] == "https://github.com/testuser/testrepo/pull/42"
        assert data["files_analyzed"] == 10
        assert data["tokens_used"] == 5000

    def test_get_failed_job(
        self,
        test_app: FastAPI,
        mock_repository: Repository,
    ) -> None:
        """Test getting status of a failed job."""
        mock_job = Job(
            id="failed-job",
            repository_id=1,
            status=JobStatus.FAILED,
            ref="main",
            trigger="webhook",
            error_message="Rate limit exceeded",
        )

        mock_session = AsyncMock()

        async def mock_get(model: type, _id: str) -> Job | Repository | None:
            if model == Job:
                return mock_job
            if model == Repository:
                return mock_repository
            return None

        mock_session.get = mock_get

        async def mock_session_gen():
            yield mock_session

        test_app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(test_app)

        response = client.get("/api/v1/jobs/failed-job")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Rate limit exceeded"


class TestListJobsEndpoint:
    """Integration tests for GET /api/v1/jobs."""

    def test_list_jobs_with_filter(
        self,
        test_app: FastAPI,
        mock_repository: Repository,
    ) -> None:
        """Test listing jobs with installation_id filter."""
        mock_job = Job(
            id="job-1",
            repository_id=1,
            status=JobStatus.COMPLETED,
            ref="main",
            trigger="manual",
        )
        mock_job.repository = mock_repository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_job]
        mock_session.execute.return_value = mock_result

        async def mock_session_gen():
            yield mock_session

        test_app.dependency_overrides[api_v1.get_session] = mock_session_gen
        client = TestClient(test_app)

        response = client.get("/api/v1/jobs?installation_id=12345&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["job_id"] == "job-1"


class TestWebhookEndpoint:
    """Integration tests for webhook endpoints."""

    def _sign_payload(self, payload: dict[str, Any], secret: str) -> str:
        """Generate webhook signature."""
        body = json.dumps(payload).encode()
        signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"

    def test_webhook_push_to_main(
        self,
        test_app: FastAPI,
        webhook_push_payload: dict[str, Any],
        mock_repository: Repository,
    ) -> None:
        """Test push webhook triggers doc generation."""
        mock_job = Job(
            id="push-job",
            repository_id=1,
            status=JobStatus.PENDING,
            ref="main",
            trigger="push",
        )

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[webhooks.get_session] = mock_session_gen
        client = TestClient(test_app)

        with (
            patch.object(webhooks, "get_or_create_repository") as mock_get_repo,
            patch.object(webhooks, "create_job") as mock_create_job,
            patch.object(webhooks, "celery_app") as mock_celery,
            patch("josephus.api.routes.webhooks.get_settings") as mock_settings,
        ):
            mock_settings.return_value.github_webhook_secret = None
            mock_get_repo.return_value = mock_repository
            mock_create_job.return_value = mock_job

            response = client.post(
                "/webhooks/github",
                json=webhook_push_payload,
                headers={
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "test-delivery-123",
                },
            )

            assert response.status_code == 200
            assert response.json()["status"] == "queued"

            # Verify doc generation was queued
            mock_celery.send_task.assert_called_once()
            assert "generate_documentation" in mock_celery.send_task.call_args[0][0]

    def test_webhook_push_to_non_default_branch_ignored(
        self,
        test_app: FastAPI,
    ) -> None:
        """Test push to non-default branch is ignored."""
        payload = {
            "ref": "refs/heads/feature-branch",
            "repository": {
                "name": "testrepo",
                "full_name": "testuser/testrepo",
                "owner": {"login": "testuser"},
                "default_branch": "main",
            },
            "installation": {"id": 12345},
        }

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[webhooks.get_session] = mock_session_gen
        client = TestClient(test_app)

        with (
            patch.object(webhooks, "celery_app") as mock_celery,
            patch("josephus.api.routes.webhooks.get_settings") as mock_settings,
        ):
            mock_settings.return_value.github_webhook_secret = None

            response = client.post(
                "/webhooks/github",
                json=payload,
                headers={
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "test-delivery-123",
                },
            )

            assert response.status_code == 200
            # Should not queue any jobs for non-default branch
            mock_celery.send_task.assert_not_called()

    def test_webhook_pr_opened(
        self,
        test_app: FastAPI,
        webhook_pr_payload: dict[str, Any],
        mock_repository: Repository,
    ) -> None:
        """Test PR opened webhook triggers analysis."""
        mock_job = Job(
            id="pr-job",
            repository_id=1,
            status=JobStatus.PENDING,
            ref="feature-branch",
            trigger="pull_request",
            pr_number=1,
        )

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[webhooks.get_session] = mock_session_gen
        client = TestClient(test_app)

        with (
            patch.object(webhooks, "get_or_create_repository") as mock_get_repo,
            patch.object(webhooks, "create_job") as mock_create_job,
            patch.object(webhooks, "celery_app") as mock_celery,
            patch("josephus.api.routes.webhooks.get_settings") as mock_settings,
        ):
            mock_settings.return_value.github_webhook_secret = None
            mock_get_repo.return_value = mock_repository
            mock_create_job.return_value = mock_job

            response = client.post(
                "/webhooks/github",
                json=webhook_pr_payload,
                headers={
                    "X-GitHub-Event": "pull_request",
                    "X-GitHub-Delivery": "test-delivery-123",
                },
            )

            assert response.status_code == 200

            # Verify PR analysis was queued
            mock_celery.send_task.assert_called_once()
            assert "analyze_pull_request" in mock_celery.send_task.call_args[0][0]

    def test_webhook_ping(self, test_app: FastAPI) -> None:
        """Test ping webhook returns pong."""

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[webhooks.get_session] = mock_session_gen
        client = TestClient(test_app)

        with patch("josephus.api.routes.webhooks.get_settings") as mock_settings:
            mock_settings.return_value.github_webhook_secret = None

            response = client.post(
                "/webhooks/github",
                json={"zen": "Keep it simple"},
                headers={
                    "X-GitHub-Event": "ping",
                    "X-GitHub-Delivery": "test-delivery-123",
                },
            )

            assert response.status_code == 200
            assert response.json()["status"] == "pong"

    def test_webhook_invalid_signature(self, test_app: FastAPI) -> None:
        """Test webhook with invalid signature is rejected."""

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[webhooks.get_session] = mock_session_gen
        client = TestClient(test_app)

        with patch("josephus.api.routes.webhooks.get_settings") as mock_settings:
            mock_settings.return_value.github_webhook_secret = "test-secret"

            response = client.post(
                "/webhooks/github",
                json={"test": "data"},
                headers={
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": "test-delivery-123",
                    "X-Hub-Signature-256": "sha256=invalid",
                },
            )

            assert response.status_code == 401

    def test_webhook_valid_signature(
        self,
        test_app: FastAPI,
    ) -> None:
        """Test webhook with valid signature is accepted."""
        # Use exact bytes for signature calculation
        payload_bytes = b'{"zen": "Keep it simple"}'
        secret = "test-webhook-secret"
        signature = "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[webhooks.get_session] = mock_session_gen
        client = TestClient(test_app)

        with patch("josephus.api.routes.webhooks.get_settings") as mock_settings:
            mock_settings.return_value.github_webhook_secret = secret

            response = client.post(
                "/webhooks/github",
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "ping",
                    "X-GitHub-Delivery": "test-delivery-123",
                    "X-Hub-Signature-256": signature,
                },
            )

            assert response.status_code == 200

    def test_webhook_installation_created(
        self,
        test_app: FastAPI,
        webhook_installation_payload: dict[str, Any],
    ) -> None:
        """Test installation webhook stores repositories."""

        async def mock_session_gen():
            yield AsyncMock()

        test_app.dependency_overrides[webhooks.get_session] = mock_session_gen
        client = TestClient(test_app)

        with (
            patch.object(webhooks, "get_or_create_repository") as mock_get_repo,
            patch("josephus.api.routes.webhooks.get_settings") as mock_settings,
        ):
            mock_settings.return_value.github_webhook_secret = None
            mock_get_repo.return_value = MagicMock()

            response = client.post(
                "/webhooks/github",
                json=webhook_installation_payload,
                headers={
                    "X-GitHub-Event": "installation",
                    "X-GitHub-Delivery": "test-delivery-123",
                },
            )

            assert response.status_code == 200

            # Should create repository records for each repo
            assert mock_get_repo.call_count == 2
