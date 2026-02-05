"""Initial schema with repositories, jobs, and doc_generations.

Revision ID: 001
Revises:
Create Date: 2026-02-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=512), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("full_name"),
    )
    op.create_index(
        op.f("ix_repositories_installation_id"),
        "repositories",
        ["installation_id"],
        unique=False,
    )

    # Create job status enum
    job_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="jobstatus",
        create_type=True,
    )
    job_status.create(op.get_bind())

    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "completed",
                "failed",
                "cancelled",
                name="jobstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("ref", sa.String(length=255), nullable=False),
        sa.Column("trigger", sa.String(length=50), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_pr_url", sa.String(length=512), nullable=True),
        sa.Column("files_analyzed", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create doc_generations table
    op.create_table(
        "doc_generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("doc_generations")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_repositories_installation_id"), table_name="repositories")
    op.drop_table("repositories")

    # Drop enum type
    job_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
        name="jobstatus",
    )
    job_status.drop(op.get_bind())
