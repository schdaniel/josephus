"""SQLAlchemy models for Josephus."""

import enum
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class JobStatus(enum.Enum):
    """Status of a documentation generation job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Repository(Base):
    """A GitHub repository configured for documentation generation."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    installation_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")

    # Configuration (from .josephus.yml)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="repository")

    def __repr__(self) -> str:
        return f"<Repository {self.full_name}>"


class Job(Base):
    """A documentation generation job."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING, nullable=False
    )

    # Job details
    ref: Mapped[str] = mapped_column(String(255), nullable=False)  # Branch or commit
    trigger: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "manual", "push", "pull_request"
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Results
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_pr_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Metrics
    files_analyzed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    repository: Mapped[Repository] = relationship("Repository", back_populates="jobs")
    doc_generations: Mapped[list["DocGeneration"]] = relationship(
        "DocGeneration", back_populates="job"
    )

    def __repr__(self) -> str:
        return f"<Job {self.id} ({self.status.value})>"


class DocGeneration(Base):
    """A generated documentation file."""

    __tablename__ = "doc_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)

    # File info
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    job: Mapped[Job] = relationship("Job", back_populates="doc_generations")

    def __repr__(self) -> str:
        return f"<DocGeneration {self.file_path}>"
