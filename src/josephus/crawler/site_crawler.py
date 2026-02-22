"""Site crawler — BFS multi-page orchestration with SPA support and URL deduplication."""

from __future__ import annotations

import fnmatch
import re
import time
from collections import deque
from urllib.parse import urlparse

import logfire

from josephus.crawler.auth import AuthValidator
from josephus.crawler.browser import BrowserManager
from josephus.crawler.dom_extractor import DOMExtractor
from josephus.crawler.models import CrawlConfig, CrawledPage, PageType, SiteInventory
from josephus.crawler.page_crawler import PageCrawler
from josephus.crawler.screenshot import ScreenshotManager


class SiteCrawler:
    """BFS site crawler with SPA support and URL template deduplication."""

    def __init__(self, config: CrawlConfig) -> None:
        self._config = config
        self._visited: set[str] = set()
        self._url_templates: dict[str, str] = {}  # template → first URL

    async def crawl(self, headless: bool = True) -> SiteInventory:
        """Crawl the site starting from base_url.

        Returns SiteInventory with all discovered pages.
        """
        start_time = time.monotonic()
        pages: list[CrawledPage] = []
        errors: list[str] = []

        async with BrowserManager(self._config, headless=headless) as browser:
            page = await browser.new_page()

            # Validate auth before full crawl
            validator = AuthValidator()
            try:
                await validator.validate(page, self._config.base_url)
            except Exception as e:
                logfire.error("Auth validation failed", error=str(e))
                return SiteInventory(
                    base_url=self._config.base_url,
                    errors=[str(e)],
                )

            # Set up page crawler
            dom_extractor = DOMExtractor()
            screenshot_manager = ScreenshotManager(
                config=self._config.screenshot,
            )
            page_crawler = PageCrawler(
                dom_extractor=dom_extractor,
                screenshot_manager=screenshot_manager,
                wait_for_idle_ms=self._config.wait_for_idle_ms,
            )

            # BFS queue: (url, parent_url, depth)
            queue: deque[tuple[str, str | None, int]] = deque()
            queue.append((self._config.base_url, None, 0))
            self._visited.add(self._normalize_url(self._config.base_url))

            while queue and len(pages) < self._config.max_pages:
                url, parent_url, depth = queue.popleft()

                if depth > self._config.max_depth:
                    continue

                if not self._should_crawl(url):
                    continue

                try:
                    crawled_page, discovered_links = await page_crawler.crawl_page(
                        page, url, parent_url, depth
                    )
                    if crawled_page.page_type == PageType.CONTENT:
                        # Check for URL template deduplication
                        if not self._is_duplicate_template(crawled_page):
                            pages.append(crawled_page)
                        else:
                            logfire.info(
                                "Skipping duplicate template page",
                                url=url,
                                template=self._get_url_template(url),
                            )
                    elif crawled_page.page_type == PageType.ERROR:
                        errors.append(f"Error crawling {url}: HTTP {crawled_page.status_code}")

                    # Enqueue discovered links
                    for link in discovered_links:
                        normalized = self._normalize_url(link)
                        if normalized not in self._visited:
                            self._visited.add(normalized)
                            queue.append((link, url, depth + 1))

                except Exception as e:
                    error_msg = f"Failed to crawl {url}: {e}"
                    logfire.error(error_msg)
                    errors.append(error_msg)

        duration = time.monotonic() - start_time

        logfire.info(
            "Site crawl complete",
            total_pages=len(pages),
            total_visited=len(self._visited),
            duration_seconds=round(duration, 1),
            errors=len(errors),
        )

        return SiteInventory(
            base_url=self._config.base_url,
            pages=pages,
            total_pages=len(pages),
            crawl_duration_seconds=round(duration, 1),
            errors=errors,
        )

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication (strip fragment, trailing slash)."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized

    def _should_crawl(self, url: str) -> bool:
        """Check if URL matches include/exclude patterns."""
        parsed = urlparse(url)
        path = parsed.path

        # Check base URL origin matches
        base_parsed = urlparse(self._config.base_url)
        if parsed.netloc != base_parsed.netloc:
            return False

        # Check exclude patterns
        for pattern in self._config.exclude_patterns:
            if fnmatch.fnmatch(path, pattern):
                return False

        # Check include patterns (if any specified, URL must match at least one)
        if self._config.include_patterns:
            return any(fnmatch.fnmatch(path, p) for p in self._config.include_patterns)

        return True

    def _get_url_template(self, url: str) -> str:
        """Convert a URL to a template by replacing numeric path segments.

        /users/123/posts/456 → /users/:id/posts/:id
        /items/abc-def-123 → /items/:id  (UUIDs)
        """
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        template_parts = []

        for part in parts:
            if re.match(r"^\d+$", part):
                # Pure numeric ID
                template_parts.append(":id")
            elif re.match(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", part, re.I
            ):
                # UUID
                template_parts.append(":uuid")
            elif re.match(r"^[0-9a-f]{24,}$", part, re.I):
                # MongoDB-style ObjectId or long hex
                template_parts.append(":id")
            else:
                template_parts.append(part)

        return "/" + "/".join(template_parts)

    def _is_duplicate_template(self, crawled_page: CrawledPage) -> bool:
        """Check if this page's URL template is already represented."""
        template = self._get_url_template(crawled_page.url)

        if template in self._url_templates:
            return True

        self._url_templates[template] = crawled_page.url
        return False
