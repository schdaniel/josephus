"""GitHub webhook handlers."""

import hashlib
import hmac
from typing import Any

import logfire
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from josephus.core.config import get_settings
from josephus.db.session import get_session
from josephus.worker import celery_app
from josephus.worker.tasks import create_job, get_or_create_repository

router = APIRouter()


def verify_webhook_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """Verify GitHub webhook signature using HMAC.

    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret configured in GitHub App

    Returns:
        True if signature is valid, False otherwise
    """
    if not signature:
        return False

    expected = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(expected, signature)


@router.post("/github")
async def handle_github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
) -> dict[str, str]:
    """Handle incoming GitHub webhooks.

    Verifies signature, then queues appropriate job based on event type.
    Returns immediately - actual processing happens async in Celery workers.
    """
    settings = get_settings()

    # Get raw body for signature verification
    body = await request.body()

    # Verify webhook signature (CRITICAL for security)
    if settings.github_webhook_secret and not verify_webhook_signature(
        body, x_hub_signature_256, settings.github_webhook_secret
    ):
        logfire.warn("Invalid webhook signature", delivery_id=x_github_delivery)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse payload
    payload: dict[str, Any] = await request.json()

    # Log webhook receipt
    logfire.info(
        "Received GitHub webhook",
        event=x_github_event,
        delivery_id=x_github_delivery,
        action=payload.get("action"),
    )

    # Route to appropriate handler
    match x_github_event:
        case "installation":
            await handle_installation(payload, session)
        case "pull_request":
            await handle_pull_request(payload, session)
        case "push":
            await handle_push(payload, session)
        case "ping":
            # GitHub sends ping on webhook setup
            return {"status": "pong"}
        case _:
            logfire.debug("Unhandled webhook event", event=x_github_event)

    return {"status": "queued"}


async def handle_installation(payload: dict[str, Any], session: AsyncSession) -> None:
    """Handle GitHub App installation/uninstallation."""
    action = payload.get("action")
    installation = payload.get("installation", {})
    installation_id = installation.get("id")

    logfire.info(
        "Installation event",
        action=action,
        installation_id=installation_id,
    )

    match action:
        case "created":
            # Store repository info for each repo in the installation
            repos = payload.get("repositories", [])
            for repo_data in repos:
                await get_or_create_repository(
                    session=session,
                    installation_id=installation_id,
                    owner=repo_data["full_name"].split("/")[0],
                    name=repo_data["name"],
                    full_name=repo_data["full_name"],
                    default_branch="main",  # Will be updated on first push
                )
            logfire.info(
                "Installation created",
                installation_id=installation_id,
                repos_count=len(repos),
            )
        case "deleted":
            # Mark repositories as inactive (soft delete)
            # For now, just log - repos stay in DB for history
            logfire.info(
                "Installation deleted",
                installation_id=installation_id,
            )
        case "suspend" | "unsuspend":
            logfire.info(
                "Installation status changed",
                action=action,
                installation_id=installation_id,
            )


async def handle_pull_request(payload: dict[str, Any], session: AsyncSession) -> None:
    """Handle pull request events - main entry point for doc updates."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    installation_id = payload.get("installation", {}).get("id")

    logfire.info(
        "Pull request event",
        action=action,
        pr_number=pr.get("number"),
        repo=repo_data.get("full_name"),
    )

    # Only process on open/synchronize (new commits)
    if action not in ("opened", "synchronize"):
        return

    # Get or create repository
    repo = await get_or_create_repository(
        session=session,
        installation_id=installation_id,
        owner=repo_data["owner"]["login"],
        name=repo_data["name"],
        full_name=repo_data["full_name"],
        default_branch=repo_data.get("default_branch", "main"),
    )

    # Create job record
    job = await create_job(
        session=session,
        repository_id=repo.id,
        ref=pr["head"]["ref"],
        trigger="pull_request",
        pr_number=pr["number"],
    )

    # Queue Celery task for PR analysis
    celery_app.send_task(
        "josephus.worker.tasks.analyze_pull_request",
        kwargs={
            "job_id": job.id,
            "installation_id": installation_id,
            "owner": repo_data["owner"]["login"],
            "repo": repo_data["name"],
            "pr_number": pr["number"],
            "head_sha": pr["head"]["sha"],
        },
    )

    logfire.info(
        "PR analysis job queued",
        job_id=job.id,
        pr_number=pr["number"],
    )


async def handle_push(payload: dict[str, Any], session: AsyncSession) -> None:
    """Handle push events - triggers full doc rebuild on main branch."""
    ref = payload.get("ref", "")
    repo_data = payload.get("repository", {})
    installation_id = payload.get("installation", {}).get("id")
    default_branch = repo_data.get("default_branch", "main")

    # Only process pushes to default branch
    if ref != f"refs/heads/{default_branch}":
        return

    logfire.info(
        "Push to default branch",
        repo=repo_data.get("full_name"),
        ref=ref,
    )

    # Get or create repository
    repo = await get_or_create_repository(
        session=session,
        installation_id=installation_id,
        owner=repo_data["owner"]["login"],
        name=repo_data["name"],
        full_name=repo_data["full_name"],
        default_branch=default_branch,
    )

    # Create job record
    job = await create_job(
        session=session,
        repository_id=repo.id,
        ref=default_branch,
        trigger="push",
    )

    # Queue full documentation regeneration
    celery_app.send_task(
        "josephus.worker.tasks.generate_documentation",
        kwargs={
            "job_id": job.id,
            "installation_id": installation_id,
            "owner": repo_data["owner"]["login"],
            "repo": repo_data["name"],
            "ref": default_branch,
        },
    )

    logfire.info(
        "Documentation generation job queued",
        job_id=job.id,
        repo=repo_data["full_name"],
    )
