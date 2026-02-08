"""API client for Josephus CLI."""

from __future__ import annotations

from typing import Any

import httpx


class APIError(Exception):
    """Error from the Josephus API."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id


class APIClient:
    """HTTP client for the Josephus API."""

    DEFAULT_BASE_URL = "https://api.josephus.dev"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the API client.

        Args:
            api_key: API key for authentication
            base_url: Base URL for the API. Defaults to production API.
            timeout: Request timeout in seconds
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "josephus-cli/1.0",
            },
            timeout=timeout,
        )

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response and raise errors if needed."""
        request_id = response.headers.get("X-Request-ID")

        if response.status_code >= 400:
            try:
                data = response.json()
                error_code = data.get("error", "UNKNOWN_ERROR")
                message = data.get("message", "An error occurred")
            except Exception:
                error_code = "UNKNOWN_ERROR"
                message = response.text or f"HTTP {response.status_code}"

            raise APIError(
                message=message,
                status_code=response.status_code,
                error_code=error_code,
                request_id=request_id,
            )

        try:
            return response.json()
        except Exception:
            return {"status": "ok"}

    def generate(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str | None = None,
        guidelines: str = "",
        output_dir: str = "docs",
    ) -> dict[str, Any]:
        """Trigger documentation generation.

        Args:
            installation_id: GitHub App installation ID
            owner: Repository owner
            repo: Repository name
            ref: Git ref (branch/tag)
            guidelines: Documentation guidelines
            output_dir: Output directory

        Returns:
            Job information including job_id
        """
        response = self._client.post(
            "/api/v1/generate",
            json={
                "installation_id": installation_id,
                "owner": owner,
                "repo": repo,
                "ref": ref,
                "guidelines": guidelines,
                "output_dir": output_dir,
            },
        )
        return self._handle_response(response)

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get the status of a job.

        Args:
            job_id: Job ID to check

        Returns:
            Job status information
        """
        response = self._client.get(f"/api/v1/jobs/{job_id}")
        return self._handle_response(response)

    def list_jobs(
        self,
        installation_id: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List recent jobs.

        Args:
            installation_id: Filter by installation ID
            limit: Maximum number of jobs to return

        Returns:
            List of job information
        """
        params: dict[str, Any] = {"limit": limit}
        if installation_id:
            params["installation_id"] = installation_id

        response = self._client.get("/api/v1/jobs", params=params)
        return self._handle_response(response)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> APIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def get_api_client(
    api_key: str,
    base_url: str | None = None,
) -> APIClient:
    """Get an API client instance.

    Args:
        api_key: API key for authentication
        base_url: Optional base URL override

    Returns:
        Configured API client
    """
    import os

    # Allow overriding base URL via environment
    base_url = base_url or os.environ.get("JOSEPHUS_API_URL")

    return APIClient(api_key=api_key, base_url=base_url)
