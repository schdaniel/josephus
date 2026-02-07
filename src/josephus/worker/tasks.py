"""Celery tasks for background job processing."""

import asyncio
import uuid
from datetime import datetime
from typing import Any

import logfire
from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from josephus.core.config import get_settings
from josephus.core.service import JosephusService
from josephus.db.models import Job, JobStatus, Repository
from josephus.security import sanitize_error_message
from josephus.worker.celery_app import celery_app


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create async session factory for tasks."""
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), echo=settings.debug)
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class AsyncTask(Task):
    """Base class for async Celery tasks."""

    _session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Lazy-loaded session factory."""
        if self._session_factory is None:
            self._session_factory = get_async_session_factory()
        return self._session_factory


def run_async(coro: Any) -> Any:
    """Run an async function in a sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, base=AsyncTask, max_retries=3)
def generate_documentation(
    self: AsyncTask,
    job_id: str,
    installation_id: int,
    owner: str,
    repo: str,
    ref: str,
    guidelines: str = "",
    output_dir: str = "docs",
) -> dict[str, Any]:
    """Generate documentation for a repository.

    Args:
        job_id: Job ID for tracking
        installation_id: GitHub App installation ID
        owner: Repository owner
        repo: Repository name
        ref: Git ref (branch/tag)
        guidelines: Documentation guidelines
        output_dir: Output directory for docs

    Returns:
        Dict with job result information
    """
    return run_async(
        _generate_documentation_async(
            self,
            job_id=job_id,
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            ref=ref,
            guidelines=guidelines,
            output_dir=output_dir,
        )
    )


async def _generate_documentation_async(
    task: AsyncTask,
    job_id: str,
    installation_id: int,
    owner: str,
    repo: str,
    ref: str,
    guidelines: str = "",
    output_dir: str = "docs",
) -> dict[str, Any]:
    """Async implementation of documentation generation."""
    logfire.info(
        "Starting documentation generation task",
        job_id=job_id,
        repo=f"{owner}/{repo}",
        ref=ref,
    )

    async with task.session_factory() as session:
        # Update job status to running
        job = await session.get(Job, job_id)
        if job:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            await session.commit()

        try:
            # Run the documentation generation
            service = JosephusService()
            result = await service.generate_documentation(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                guidelines=guidelines,
                output_dir=output_dir,
                create_pr=True,
            )

            # Update job with success
            if job:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                job.result_pr_url = result.pr_url
                job.files_analyzed = result.files_analyzed
                job.tokens_used = result.total_tokens
                await session.commit()

            await service.close()

            logfire.info(
                "Documentation generation completed",
                job_id=job_id,
                pr_url=result.pr_url,
                files_analyzed=result.files_analyzed,
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "pr_url": result.pr_url,
                "pr_number": result.pr_number,
                "files_analyzed": result.files_analyzed,
                "docs_generated": result.docs_generated,
            }

        except Exception as e:
            # Log full error details internally for debugging
            logfire.error(
                "Documentation generation failed",
                job_id=job_id,
                error=str(e),
                exc_info=True,
            )

            # Update job with sanitized error message (no sensitive info)
            if job:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = sanitize_error_message(e)
                await session.commit()

            # Retry on transient errors
            raise task.retry(exc=e, countdown=60) from None


@celery_app.task(bind=True, base=AsyncTask, max_retries=3)
def analyze_pull_request(
    self: AsyncTask,
    job_id: str,
    installation_id: int,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
) -> dict[str, Any]:
    """Analyze a pull request and suggest documentation updates.

    Args:
        job_id: Job ID for tracking
        installation_id: GitHub App installation ID
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        head_sha: Head commit SHA

    Returns:
        Dict with analysis result information
    """
    return run_async(
        _analyze_pull_request_async(
            self,
            job_id=job_id,
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            head_sha=head_sha,
        )
    )


async def _analyze_pull_request_async(
    task: AsyncTask,
    job_id: str,
    installation_id: int,
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
) -> dict[str, Any]:
    """Async implementation of PR analysis."""
    logfire.info(
        "Starting PR analysis task",
        job_id=job_id,
        repo=f"{owner}/{repo}",
        pr_number=pr_number,
        installation_id=installation_id,
        head_sha=head_sha,
    )

    async with task.session_factory() as session:
        # Update job status to running
        job = await session.get(Job, job_id)
        if job:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            await session.commit()

        try:
            # TODO: Implement PR-specific analysis
            # - Get PR diff
            # - Analyze changed files
            # - Generate doc updates only for changed areas
            # - Comment on PR with suggestions

            # For now, placeholder implementation
            logfire.info(
                "PR analysis completed (placeholder)",
                job_id=job_id,
                pr_number=pr_number,
            )

            if job:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                await session.commit()

            return {
                "status": "completed",
                "job_id": job_id,
                "pr_number": pr_number,
                "message": "PR analysis not yet implemented",
            }

        except Exception as e:
            # Log full error details internally for debugging
            logfire.error(
                "PR analysis failed",
                job_id=job_id,
                error=str(e),
                exc_info=True,
            )

            # Update job with sanitized error message (no sensitive info)
            if job:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = sanitize_error_message(e)
                await session.commit()

            raise task.retry(exc=e, countdown=60) from None


async def create_job(
    session: AsyncSession,
    repository_id: int,
    ref: str,
    trigger: str,
    pr_number: int | None = None,
) -> Job:
    """Create a new job record in the database.

    Args:
        session: Database session
        repository_id: Repository ID
        ref: Git ref
        trigger: Trigger type (webhook, manual, etc.)
        pr_number: PR number if triggered from PR

    Returns:
        Created Job instance
    """
    job = Job(
        id=str(uuid.uuid4()),
        repository_id=repository_id,
        status=JobStatus.PENDING,
        ref=ref,
        trigger=trigger,
        pr_number=pr_number,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_or_create_repository(
    session: AsyncSession,
    installation_id: int,
    owner: str,
    name: str,
    full_name: str,
    default_branch: str,
) -> Repository:
    """Get existing repository or create new one.

    Args:
        session: Database session
        installation_id: GitHub App installation ID
        owner: Repository owner
        name: Repository name
        full_name: Full repository name (owner/repo)
        default_branch: Default branch name

    Returns:
        Repository instance
    """
    stmt = select(Repository).where(Repository.full_name == full_name)
    result = await session.execute(stmt)
    repo = result.scalar_one_or_none()

    if repo:
        # Update installation ID if changed
        if repo.installation_id != installation_id:
            repo.installation_id = installation_id
            await session.commit()
        return repo

    # Create new repository
    repo = Repository(
        installation_id=installation_id,
        owner=owner,
        name=name,
        full_name=full_name,
        default_branch=default_branch,
    )
    session.add(repo)
    await session.commit()
    await session.refresh(repo)
    return repo
