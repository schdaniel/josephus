"""UI crawler module — Playwright-based browser automation for UI documentation."""

from josephus.crawler.models import (
    AuthConfig,
    CrawlConfig,
    CrawledPage,
    DOMData,
    InteractiveElement,
    ScreenshotConfig,
    SiteInventory,
)

__all__ = [
    "AuthConfig",
    "CrawlConfig",
    "CrawledPage",
    "DOMData",
    "InteractiveElement",
    "ScreenshotConfig",
    "SiteInventory",
]
