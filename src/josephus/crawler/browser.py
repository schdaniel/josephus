"""Browser manager — Playwright lifecycle and context creation."""

from __future__ import annotations

import logfire
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from josephus.crawler.models import AuthStrategy, CookieConfig, CrawlConfig


class BrowserManager:
    """Manages Playwright browser lifecycle and context creation."""

    def __init__(self, config: CrawlConfig, headless: bool = True) -> None:
        self._config = config
        self._headless = headless
        self._playwright: object | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> BrowserContext:
        """Launch browser and create context with auth."""
        logfire.info("Starting Playwright browser", headless=self._headless)

        pw = await async_playwright().start()
        self._playwright = pw

        self._browser = await pw.chromium.launch(headless=self._headless)

        context_kwargs: dict = {
            "viewport": {
                "width": self._config.viewport_width,
                "height": self._config.viewport_height,
            },
        }

        # Add extra HTTP headers for bearer token auth
        if (
            self._config.auth.strategy == AuthStrategy.TOKEN_HEADER
            and self._config.auth.bearer_token
        ):
            context_kwargs["extra_http_headers"] = {
                "Authorization": f"Bearer {self._config.auth.bearer_token}",
                **self._config.auth.custom_headers,
            }
        elif self._config.auth.custom_headers:
            context_kwargs["extra_http_headers"] = self._config.auth.custom_headers

        self._context = await self._browser.new_context(**context_kwargs)

        # Inject cookies
        if self._config.auth.strategy == AuthStrategy.COOKIES and self._config.auth.cookies:
            await self._inject_cookies(self._config.auth.cookies)

        # Set default navigation timeout
        self._context.set_default_navigation_timeout(self._config.navigation_timeout_ms)

        logfire.info("Browser context created")
        return self._context

    async def _inject_cookies(self, cookies: list[CookieConfig]) -> None:
        """Inject cookies into the browser context."""
        if not self._context:
            raise RuntimeError("Browser context not initialized")

        playwright_cookies = []
        for cookie in cookies:
            playwright_cookies.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "secure": cookie.secure,
                    "httpOnly": cookie.http_only,
                }
            )

        await self._context.add_cookies(playwright_cookies)
        logfire.info("Injected cookies", count=len(cookies))

    async def new_page(self) -> Page:
        """Create a new page in the current context."""
        if not self._context:
            raise RuntimeError("Browser context not initialized. Call start() first.")
        return await self._context.new_page()

    @property
    def context(self) -> BrowserContext | None:
        return self._context

    async def close(self) -> None:
        """Close browser and cleanup."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()  # type: ignore[union-attr]
            self._playwright = None
        logfire.info("Browser closed")

    async def __aenter__(self) -> BrowserManager:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
