"""Page crawler — single page processing: navigate, extract DOM, screenshot, discover links."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import logfire
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeout

from josephus.crawler.dom_extractor import DOMExtractor
from josephus.crawler.models import CrawledPage, DOMData, PageType
from josephus.crawler.screenshot import ScreenshotManager


class PageCrawler:
    """Processes a single page: navigate, extract DOM, take screenshot, discover links."""

    def __init__(
        self,
        dom_extractor: DOMExtractor,
        screenshot_manager: ScreenshotManager,
        wait_for_idle_ms: int = 2000,
    ) -> None:
        self._dom_extractor = dom_extractor
        self._screenshot_manager = screenshot_manager
        self._wait_ms = wait_for_idle_ms

    async def crawl_page(
        self,
        page: Page,
        url: str,
        parent_url: str | None = None,
        depth: int = 0,
    ) -> tuple[CrawledPage, list[str]]:
        """Crawl a single page and return its data + discovered links.

        Returns:
            Tuple of (CrawledPage, list of discovered link URLs)
        """
        logfire.info("Crawling page", url=url, depth=depth)

        # Navigate
        try:
            response = await page.goto(url, wait_until="networkidle")
        except PlaywrightTimeout:
            logfire.warn("Page load timeout", url=url)
            return (
                CrawledPage(
                    url=url,
                    title="",
                    nav_path=self._build_nav_path(url),
                    page_type=PageType.ERROR,
                    parent_url=parent_url,
                    depth=depth,
                ),
                [],
            )

        status_code = response.status if response else None

        # Classify page type
        page_type = self._classify_page(status_code, page.url)

        # Extract title
        title = await page.title() or ""

        # Extract DOM
        dom = DOMData()
        if page_type == PageType.CONTENT:
            try:
                dom = await self._dom_extractor.extract(page)
            except Exception as e:
                logfire.warn("DOM extraction failed", url=url, error=str(e))

        # Take screenshot
        screenshot_bytes = None
        screenshot_path = None
        if page_type == PageType.CONTENT:
            try:
                screenshot_bytes, screenshot_path = await self._screenshot_manager.capture_and_save(
                    page, url
                )
            except Exception as e:
                logfire.warn("Screenshot capture failed", url=url, error=str(e))

        # Discover links
        discovered_links: list[str] = []
        if page_type == PageType.CONTENT:
            discovered_links = await self._discover_links(page, url)

        crawled = CrawledPage(
            url=page.url,  # Use final URL (after redirects)
            title=title,
            nav_path=self._build_nav_path(page.url),
            screenshot_path=screenshot_path,
            screenshot_bytes=screenshot_bytes,
            dom=dom,
            page_type=page_type,
            parent_url=parent_url,
            depth=depth,
            status_code=status_code,
        )

        logfire.info(
            "Page crawled",
            url=page.url,
            title=title,
            links_found=len(discovered_links),
            page_type=page_type.value,
        )

        return crawled, discovered_links

    async def _discover_links(self, page: Page, base_url: str) -> list[str]:
        """Discover outbound links on the page."""
        links: list[str] = []
        base_parsed = urlparse(base_url)

        # Extract href from all <a> elements
        raw_hrefs = await page.evaluate("""
            () => {
                const links = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.href;
                    if (href && !href.startsWith('javascript:') && !href.startsWith('mailto:')
                        && !href.startsWith('tel:') && !href.startsWith('#')) {
                        links.push(href);
                    }
                });
                return [...new Set(links)];
            }
        """)

        for href in raw_hrefs:
            # Resolve relative URLs
            resolved = urljoin(base_url, href)
            parsed = urlparse(resolved)

            # Only follow same-origin links
            if parsed.netloc == base_parsed.netloc:
                # Normalize: strip fragment, keep path + query
                clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean += f"?{parsed.query}"
                links.append(clean)

        return list(set(links))

    def _classify_page(self, status_code: int | None, url: str) -> PageType:
        """Classify the page type from status code and URL."""
        if status_code and status_code >= 400:
            return PageType.ERROR

        path = urlparse(url).path.lower()
        if any(p in path for p in ["/login", "/signin", "/sign-in", "/auth"]):
            return PageType.LOGIN

        return PageType.CONTENT

    def _build_nav_path(self, url: str) -> list[str]:
        """Build a navigation breadcrumb from the URL path."""
        path = urlparse(url).path.strip("/")
        if not path:
            return ["Home"]
        parts = path.split("/")
        return ["Home", *[p.replace("-", " ").replace("_", " ").title() for p in parts]]
