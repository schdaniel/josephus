"""Auth injection and pre-crawl validation."""

from __future__ import annotations

from urllib.parse import urlparse

import logfire
from playwright.async_api import Page


class AuthError(Exception):
    """Raised when authentication validation fails."""


class AuthValidator:
    """Validates that authentication is working before a full crawl."""

    # Common login page indicators
    LOGIN_INDICATORS = [
        'input[type="password"]',
        'form[action*="login"]',
        'form[action*="signin"]',
        'form[action*="sign-in"]',
        '[data-testid="login"]',
        "#login-form",
        ".login-form",
    ]

    async def validate(self, page: Page, base_url: str) -> None:
        """Navigate to base_url and verify auth is working.

        Raises AuthError if:
        - Response is 401/403
        - Page redirects to a login page on a different path
        - Page contains login form indicators
        """
        logfire.info("Validating authentication", url=base_url)

        response = await page.goto(base_url, wait_until="networkidle")

        if response is None:
            raise AuthError(f"No response received from {base_url}")

        # Check HTTP status
        if response.status in (401, 403):
            raise AuthError(
                f"Authentication failed: HTTP {response.status} from {base_url}. "
                "Check your auth cookies or bearer token."
            )

        # Check for redirect to login page
        if self._is_login_redirect(base_url, page.url):
            raise AuthError(
                f"Redirected to login page: {page.url}. "
                "The provided auth credentials may be expired or invalid."
            )

        # Check for login form on the page
        if await self._has_login_form(page):
            # Only flag as error if we also redirected
            final_path = urlparse(page.url).path
            base_path = urlparse(base_url).path or "/"
            if final_path != base_path:
                raise AuthError(
                    f"Page at {page.url} appears to be a login page. "
                    "The provided auth credentials may be expired or invalid."
                )

        logfire.info("Authentication validated successfully", final_url=page.url)

    def _is_login_redirect(self, original_url: str, final_url: str) -> bool:
        """Check if we were redirected to a login page."""
        original_parsed = urlparse(original_url)
        final_parsed = urlparse(final_url)

        # Different host = likely OAuth redirect
        if original_parsed.netloc != final_parsed.netloc:
            return True

        # Same host but path contains login/signin
        final_path = final_parsed.path.lower()
        login_paths = ["/login", "/signin", "/sign-in", "/auth", "/sso"]
        return any(login_path in final_path for login_path in login_paths)

    async def _has_login_form(self, page: Page) -> bool:
        """Check if the current page contains a login form."""
        for selector in self.LOGIN_INDICATORS:
            try:
                element = await page.query_selector(selector)
                if element:
                    return True
            except Exception:
                continue
        return False
