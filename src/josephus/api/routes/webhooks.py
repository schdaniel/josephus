"""GitHub webhook handlers."""

import hashlib
import hmac
from typing import Any

import logfire
from fastapi import APIRouter, Header, HTTPException, Request, status

from josephus.api.rate_limit import RATE_LIMITS, limiter
from josephus.core.config import get_settings

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
@limiter.limit(RATE_LIMITS["webhooks"])
async def handle_github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
) -> dict[str, str]:
    """Handle incoming GitHub webhooks.

    Verifies signature, then queues appropriate job based on event type.
    Returns immediately - actual processing happens async in Celery workers.

    Rate limited to 60 requests per minute per IP address.
    """
    settings = get_settings()

    # Get raw body for signature verification
    body = await request.body()

    # Verify webhook signature (CRITICAL for security)
    if not settings.github_webhook_secret:
        if settings.environment != "development":
            logfire.error(
                "Webhook secret not configured in production environment",
                environment=settings.environment,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook verification not configured",
            )
        logfire.warn(
            "Webhook signature verification disabled in development mode",
            delivery_id=x_github_delivery,
        )
    elif not verify_webhook_signature(body, x_hub_signature_256, settings.github_webhook_secret):
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
            await handle_installation(payload)
        case "pull_request":
            await handle_pull_request(payload)
        case "push":
            await handle_push(payload)
        case "ping":
            # GitHub sends ping on webhook setup
            return {"status": "pong"}
        case _:
            logfire.debug("Unhandled webhook event", event=x_github_event)

    return {"status": "queued"}


async def handle_installation(payload: dict[str, Any]) -> None:
    """Handle GitHub App installation/uninstallation."""
    action = payload.get("action")
    installation_id = payload.get("installation", {}).get("id")

    logfire.info(
        "Installation event",
        action=action,
        installation_id=installation_id,
    )

    match action:
        case "created":
            # TODO: Queue job to set up new installation
            # - Store installation info in database
            # - Send welcome message/email
            pass
        case "deleted":
            # TODO: Queue job to clean up installation
            # - Mark installation as inactive
            # - Clean up any cached data
            pass
        case "suspend" | "unsuspend":
            # TODO: Update installation status
            pass


async def handle_pull_request(payload: dict[str, Any]) -> None:
    """Handle pull request events - main entry point for doc updates."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    logfire.info(
        "Pull request event",
        action=action,
        pr_number=pr.get("number"),
        repo=repo.get("full_name"),
    )

    # Only process on open/synchronize (new commits)
    if action not in ("opened", "synchronize"):
        return

    # TODO: Queue Celery job for PR analysis
    # celery_app.send_task(
    #     "josephus.tasks.analyze_pr",
    #     kwargs={
    #         "installation_id": payload["installation"]["id"],
    #         "repo_full_name": repo["full_name"],
    #         "pr_number": pr["number"],
    #         "head_sha": pr["head"]["sha"],
    #     },
    # )


async def handle_push(payload: dict[str, Any]) -> None:
    """Handle push events - triggers full doc rebuild on main branch."""
    ref = payload.get("ref", "")
    repo = payload.get("repository", {})
    default_branch = repo.get("default_branch", "main")

    # Only process pushes to default branch
    if ref != f"refs/heads/{default_branch}":
        return

    logfire.info(
        "Push to default branch",
        repo=repo.get("full_name"),
        ref=ref,
    )

    # TODO: Queue full doc regeneration job
    # This runs when PRs are merged to main
