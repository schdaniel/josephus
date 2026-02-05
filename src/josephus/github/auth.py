"""GitHub App authentication and token management."""

import time
from dataclasses import dataclass

import httpx
import jwt

from josephus.core.config import get_settings


@dataclass
class InstallationToken:
    """GitHub App installation access token."""

    token: str
    expires_at: str
    permissions: dict[str, str]
    repository_selection: str


class GitHubAuth:
    """Handles GitHub App authentication.

    GitHub Apps authenticate in two steps:
    1. Generate a JWT signed with the app's private key
    2. Exchange the JWT for an installation access token

    Installation tokens are short-lived (1 hour) and scoped to specific installations.
    """

    def __init__(
        self,
        app_id: int | None = None,
        private_key: str | None = None,
    ) -> None:
        settings = get_settings()
        self.app_id = app_id or settings.github_app_id
        self.private_key = private_key or settings.github_app_private_key

        if not self.app_id or not self.private_key:
            raise ValueError(
                "GitHub App credentials not configured. "
                "Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY environment variables."
            )

        # Cache for installation tokens
        self._token_cache: dict[int, tuple[InstallationToken, float]] = {}

    def _generate_jwt(self) -> str:
        """Generate a JWT for GitHub App authentication.

        JWTs are valid for up to 10 minutes. We use 9 minutes to be safe.
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds ago (clock drift tolerance)
            "exp": now + (9 * 60),  # Expires in 9 minutes
            "iss": str(self.app_id),  # GitHub expects app_id as string in JWT
        }

        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_installation_token(
        self,
        installation_id: int,
        http_client: httpx.AsyncClient | None = None,
    ) -> InstallationToken:
        """Get an installation access token.

        Tokens are cached until 5 minutes before expiration.

        Args:
            installation_id: The GitHub App installation ID
            http_client: Optional HTTP client (for testing)

        Returns:
            InstallationToken with the access token and metadata
        """
        # Check cache
        if installation_id in self._token_cache:
            token, expires_at = self._token_cache[installation_id]
            # Return cached token if it has more than 5 minutes left
            if expires_at - time.time() > 300:
                return token

        # Generate new token
        app_jwt = self._generate_jwt()

        client = http_client or httpx.AsyncClient()
        try:
            response = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            data = response.json()

            token = InstallationToken(
                token=data["token"],
                expires_at=data["expires_at"],
                permissions=data.get("permissions", {}),
                repository_selection=data.get("repository_selection", "all"),
            )

            # Cache with expiration timestamp (parse ISO format)
            from datetime import datetime

            expires_at = datetime.fromisoformat(
                data["expires_at"].replace("Z", "+00:00")
            ).timestamp()
            self._token_cache[installation_id] = (token, expires_at)

            return token

        finally:
            if http_client is None:
                await client.aclose()

    async def get_app_installations(
        self,
        http_client: httpx.AsyncClient | None = None,
    ) -> list[dict]:
        """List all installations of this GitHub App.

        Returns:
            List of installation objects with id, account, permissions, etc.
        """
        app_jwt = self._generate_jwt()

        client = http_client or httpx.AsyncClient()
        try:
            response = await client.get(
                "https://api.github.com/app/installations",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            return response.json()

        finally:
            if http_client is None:
                await client.aclose()
