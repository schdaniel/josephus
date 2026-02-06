"""API v1 routes for Josephus."""

from typing import Any

import logfire
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from josephus.api.auth import verify_api_key
from josephus.api.rate_limit import RATE_LIMITS, limiter
from josephus.db.session import get_session
from josephus.worker import celery_app
from josephus.worker.tasks import create_job, get_or_create_repository

router = APIRouter()


class GenerateRequest(BaseModel):
    """Request body for documentation generation."""

    installation_id: int = Field(..., description="GitHub App installation ID")
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    ref: str | None = Field(None, description="Git ref (branch/tag), defaults to default branch")
    guidelines: str = Field("", description="Documentation guidelines")
    output_dir: str = Field("docs", description="Output directory for generated docs")


class GenerateResponse(BaseModel):
    """Response body for documentation generation."""

    job_id: str = Field(..., description="Job ID for tracking")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Status message")


class JobStatusResponse(BaseModel):
    """Response body for job status."""

    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Job status")
    repository: str | None = Field(None, description="Repository full name")
    pr_url: str | None = Field(None, description="Pull request URL if created")
    error_message: str | None = Field(None, description="Error message if failed")
    files_analyzed: int | None = Field(None, description="Number of files analyzed")
    tokens_used: int | None = Field(None, description="Number of tokens used")


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit(RATE_LIMITS["generate"])
async def trigger_documentation_generation(
    http_request: Request,  # Required for rate limiting
    request: GenerateRequest,
    session: AsyncSession = Depends(get_session),
    _authenticated: bool = Depends(verify_api_key),
) -> dict[str, Any]:
    """Manually trigger documentation generation for a repository.

    This endpoint queues a background job to:
    1. Analyze the repository
    2. Generate documentation using LLM
    3. Create a PR with the generated docs

    Returns immediately with a job ID for status polling.

    Rate limited to 5 requests per minute per IP address.
    """
    logfire.info(
        "Manual documentation generation requested",
        installation_id=request.installation_id,
        repo=f"{request.owner}/{request.repo}",
        ref=request.ref,
    )

    # Get or create repository record
    full_name = f"{request.owner}/{request.repo}"
    repo = await get_or_create_repository(
        session=session,
        installation_id=request.installation_id,
        owner=request.owner,
        name=request.repo,
        full_name=full_name,
        default_branch=request.ref or "main",
    )

    # Determine ref to use
    ref = request.ref or repo.default_branch

    # Create job record
    job = await create_job(
        session=session,
        repository_id=repo.id,
        ref=ref,
        trigger="manual",
    )

    # Queue Celery task
    celery_app.send_task(
        "josephus.worker.tasks.generate_documentation",
        kwargs={
            "job_id": job.id,
            "installation_id": request.installation_id,
            "owner": request.owner,
            "repo": request.repo,
            "ref": ref,
            "guidelines": request.guidelines,
            "output_dir": request.output_dir,
        },
    )

    logfire.info(
        "Documentation generation job queued",
        job_id=job.id,
        repo=full_name,
    )

    return {
        "job_id": job.id,
        "status": "queued",
        "message": f"Documentation generation queued for {full_name}",
    }


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
@limiter.limit(RATE_LIMITS["job_status"])
async def get_job_status(
    request: Request,  # Required for rate limiting
    job_id: str,
    session: AsyncSession = Depends(get_session),
    _authenticated: bool = Depends(verify_api_key),
) -> dict[str, Any]:
    """Get the status of a documentation generation job.

    Poll this endpoint to track progress of queued jobs.

    Rate limited to 60 requests per minute per IP address.
    """

    from josephus.db.models import Job, Repository

    # Get job
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Get repository info
    repo = await session.get(Repository, job.repository_id)
    repo_name = repo.full_name if repo else None

    return {
        "job_id": job.id,
        "status": job.status.value,
        "repository": repo_name,
        "pr_url": job.result_pr_url,
        "error_message": job.error_message,
        "files_analyzed": job.files_analyzed,
        "tokens_used": job.tokens_used,
    }


@router.get("/jobs", response_model=list[JobStatusResponse])
@limiter.limit(RATE_LIMITS["jobs_list"])
async def list_jobs(
    request: Request,  # Required for rate limiting
    session: AsyncSession = Depends(get_session),
    installation_id: int | None = None,
    limit: int = 20,
    _authenticated: bool = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """List recent documentation generation jobs.

    Optionally filter by installation_id.

    Rate limited to 30 requests per minute per IP address.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from josephus.db.models import Job, Repository

    # Build query
    stmt = (
        select(Job)
        .options(selectinload(Job.repository))
        .order_by(Job.created_at.desc())
        .limit(limit)
    )

    if installation_id:
        stmt = stmt.join(Repository).where(Repository.installation_id == installation_id)

    result = await session.execute(stmt)
    jobs = result.scalars().all()

    return [
        {
            "job_id": job.id,
            "status": job.status.value,
            "repository": job.repository.full_name if job.repository else None,
            "pr_url": job.result_pr_url,
            "error_message": job.error_message,
            "files_analyzed": job.files_analyzed,
            "tokens_used": job.tokens_used,
        }
        for job in jobs
    ]
