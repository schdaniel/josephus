"""Unit tests for database models."""

from josephus.db.models import DocGeneration, Job, JobStatus, Repository


class TestRepository:
    """Tests for Repository model."""

    def test_create_repository(self) -> None:
        """Test creating a repository instance."""
        repo = Repository(
            id=1,
            installation_id=12345,
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )

        assert repo.owner == "schdaniel"
        assert repo.name == "josephus"
        assert repo.full_name == "schdaniel/josephus"
        assert repo.installation_id == 12345

    def test_repository_repr(self) -> None:
        """Test repository string representation."""
        repo = Repository(
            id=1,
            installation_id=12345,
            owner="schdaniel",
            name="josephus",
            full_name="schdaniel/josephus",
            default_branch="main",
        )

        assert repr(repo) == "<Repository schdaniel/josephus>"


class TestJob:
    """Tests for Job model."""

    def test_create_job(self) -> None:
        """Test creating a job instance."""
        job = Job(
            id="test-uuid",
            repository_id=1,
            status=JobStatus.PENDING,
            ref="main",
            trigger="manual",
        )

        assert job.id == "test-uuid"
        assert job.status == JobStatus.PENDING
        assert job.trigger == "manual"

    def test_job_status_enum(self) -> None:
        """Test job status enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_job_repr(self) -> None:
        """Test job string representation."""
        job = Job(
            id="test-uuid",
            repository_id=1,
            status=JobStatus.RUNNING,
            ref="main",
            trigger="manual",
        )

        assert repr(job) == "<Job test-uuid (running)>"


class TestDocGeneration:
    """Tests for DocGeneration model."""

    def test_create_doc_generation(self) -> None:
        """Test creating a doc generation instance."""
        doc = DocGeneration(
            id=1,
            job_id="test-uuid",
            file_path="docs/index.md",
            content="# Welcome",
            content_hash="abc123",
        )

        assert doc.file_path == "docs/index.md"
        assert doc.content == "# Welcome"

    def test_doc_generation_repr(self) -> None:
        """Test doc generation string representation."""
        doc = DocGeneration(
            id=1,
            job_id="test-uuid",
            file_path="docs/index.md",
            content="# Welcome",
            content_hash="abc123",
        )

        assert repr(doc) == "<DocGeneration docs/index.md>"
