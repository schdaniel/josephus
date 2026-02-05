"""Fixtures for integration tests."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from josephus.api.routes import api_v1, webhooks
from josephus.db.models import Job, JobStatus, Repository


@pytest.fixture
def mock_github_client() -> AsyncMock:
    """Create a mock GitHub client."""
    client = AsyncMock()

    # Mock repository info
    client.get_repository.return_value = {
        "id": 123456,
        "full_name": "testuser/testrepo",
        "name": "testrepo",
        "owner": {"login": "testuser"},
        "default_branch": "main",
        "html_url": "https://github.com/testuser/testrepo",
    }

    # Mock file tree
    client.get_tree.return_value = [
        {"path": "src/main.py", "type": "blob", "size": 500},
        {"path": "src/utils.py", "type": "blob", "size": 300},
        {"path": "README.md", "type": "blob", "size": 100},
    ]

    # Mock file content
    async def mock_get_content(
        _installation_id: int, _owner: str, _repo: str, path: str, _ref: str | None = None
    ) -> str:
        contents = {
            "src/main.py": 'def main():\n    print("Hello")\n',
            "src/utils.py": "def helper():\n    return 42\n",
            "README.md": "# Test Repo\n\nA test repository.",
        }
        return contents.get(path, "")

    client.get_file_content.side_effect = mock_get_content

    # Mock commit
    client.commit_files.return_value = {
        "sha": "abc123def456",
        "html_url": "https://github.com/testuser/testrepo/commit/abc123def456",
    }

    # Mock PR creation
    client.create_pull_request.return_value = {
        "number": 42,
        "html_url": "https://github.com/testuser/testrepo/pull/42",
    }

    return client


@pytest.fixture
def mock_llm_provider() -> AsyncMock:
    """Create a mock LLM provider."""
    provider = AsyncMock()

    # Mock generate response
    provider.generate.return_value = MagicMock(
        content="""# API Documentation

## Overview
This is the generated documentation.

## Functions

### main()
Entry point for the application.

### helper()
Returns the value 42.
""",
        model="claude-3-opus",
        input_tokens=1000,
        output_tokens=500,
    )

    return provider


@pytest.fixture
def mock_repository() -> Repository:
    """Create a mock repository model."""
    return Repository(
        id=1,
        installation_id=12345,
        owner="testuser",
        name="testrepo",
        full_name="testuser/testrepo",
        default_branch="main",
    )


@pytest.fixture
def mock_job(mock_repository: Repository) -> Job:
    """Create a mock job model."""
    job = Job(
        id="test-job-123",
        repository_id=mock_repository.id,
        status=JobStatus.PENDING,
        ref="main",
        trigger="manual",
    )
    job.repository = mock_repository
    return job


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app without logfire instrumentation."""
    app = FastAPI()
    app.include_router(api_v1.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/webhooks")
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(test_app)


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def webhook_push_payload() -> dict[str, Any]:
    """Sample GitHub push webhook payload."""
    return {
        "ref": "refs/heads/main",
        "repository": {
            "id": 123456,
            "name": "testrepo",
            "full_name": "testuser/testrepo",
            "owner": {"login": "testuser"},
            "default_branch": "main",
        },
        "installation": {"id": 12345},
        "pusher": {"name": "testuser"},
        "commits": [
            {
                "id": "abc123",
                "message": "Update code",
                "added": ["src/new.py"],
                "modified": ["src/main.py"],
            }
        ],
    }


@pytest.fixture
def webhook_pr_payload() -> dict[str, Any]:
    """Sample GitHub pull request webhook payload."""
    return {
        "action": "opened",
        "number": 1,
        "pull_request": {
            "number": 1,
            "title": "Add new feature",
            "head": {
                "ref": "feature-branch",
                "sha": "def456",
            },
            "base": {
                "ref": "main",
            },
        },
        "repository": {
            "id": 123456,
            "name": "testrepo",
            "full_name": "testuser/testrepo",
            "owner": {"login": "testuser"},
            "default_branch": "main",
        },
        "installation": {"id": 12345},
    }


@pytest.fixture
def webhook_installation_payload() -> dict[str, Any]:
    """Sample GitHub installation webhook payload."""
    return {
        "action": "created",
        "installation": {
            "id": 12345,
            "account": {"login": "testuser"},
        },
        "repositories": [
            {"id": 123456, "name": "testrepo", "full_name": "testuser/testrepo"},
            {"id": 123457, "name": "another-repo", "full_name": "testuser/another-repo"},
        ],
    }
