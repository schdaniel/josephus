"""Data models for the UI crawler."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


class ScreenshotFormat(StrEnum):
    """Supported screenshot image formats."""

    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class AuthStrategy(StrEnum):
    """Authentication strategy for the crawled deployment."""

    COOKIES = "cookies"
    TOKEN_HEADER = "token_header"


class PageType(StrEnum):
    """Classification of a crawled page."""

    CONTENT = "content"
    LOGIN = "login"
    ERROR = "error"
    REDIRECT = "redirect"
    EMPTY = "empty"


@dataclass
class ScreenshotConfig:
    """Configuration for screenshot capture."""

    format: ScreenshotFormat = ScreenshotFormat.PNG
    quality: int = 85  # Only applies to JPEG/WebP (1-100)
    max_width: int = 1280
    full_page: bool = True


@dataclass
class CookieConfig:
    """A single cookie for auth injection."""

    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = False
    http_only: bool = False


@dataclass
class AuthConfig:
    """Authentication configuration for the crawled deployment."""

    strategy: AuthStrategy = AuthStrategy.COOKIES
    cookies: list[CookieConfig] = field(default_factory=list)
    bearer_token: str | None = None
    custom_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class CrawlConfig:
    """Configuration for a site crawl."""

    base_url: str
    auth: AuthConfig = field(default_factory=AuthConfig)
    screenshot: ScreenshotConfig = field(default_factory=ScreenshotConfig)
    max_pages: int = 50
    max_depth: int = 4
    viewport_width: int = 1280
    viewport_height: int = 720
    wait_for_idle_ms: int = 2000
    navigation_timeout_ms: int = 30000
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass
class InteractiveElement:
    """An interactive element discovered on a page."""

    element_type: Literal[
        "button", "link", "select", "input", "tab", "modal_trigger", "checkbox", "radio"
    ]
    label: str
    selector: str
    action: str | None = None  # e.g., "click", "input"
    target_url: str | None = None  # For links
    aria_role: str | None = None


@dataclass
class FormField:
    """A form field discovered on a page."""

    field_type: str  # "text", "email", "password", "select", "textarea", etc.
    label: str | None = None
    name: str | None = None
    placeholder: str | None = None
    required: bool = False
    selector: str = ""


@dataclass
class Heading:
    """A heading element with its level."""

    level: int  # 1-6
    text: str


@dataclass
class NavLink:
    """A navigation link found on the page."""

    text: str
    href: str
    is_active: bool = False


@dataclass
class DOMData:
    """Structured data extracted from a page's DOM."""

    headings: list[Heading] = field(default_factory=list)
    nav_links: list[NavLink] = field(default_factory=list)
    interactive_elements: list[InteractiveElement] = field(default_factory=list)
    form_fields: list[FormField] = field(default_factory=list)
    visible_text: str = ""
    aria_landmarks: list[str] = field(default_factory=list)
    detected_tabs: list[str] = field(default_factory=list)
    detected_modals: list[str] = field(default_factory=list)


@dataclass
class CrawledPage:
    """A single crawled page with its data."""

    url: str
    title: str
    nav_path: list[str]  # Breadcrumb from root
    screenshot_path: str | None = None
    screenshot_bytes: bytes | None = None
    screenshot_format: ScreenshotFormat = ScreenshotFormat.PNG
    dom: DOMData = field(default_factory=DOMData)
    page_type: PageType = PageType.CONTENT
    parent_url: str | None = None
    depth: int = 0
    status_code: int | None = None

    @property
    def screenshot_base64(self) -> str | None:
        """Base64-encoded screenshot data, or None if no screenshot."""
        if self.screenshot_bytes is None:
            return None
        return base64.b64encode(self.screenshot_bytes).decode("ascii")

    @property
    def screenshot_media_type(self) -> str | None:
        """MIME type for the screenshot, or None if no screenshot."""
        if self.screenshot_bytes is None:
            return None
        media_types = {
            ScreenshotFormat.PNG: "image/png",
            ScreenshotFormat.JPEG: "image/jpeg",
            ScreenshotFormat.WEBP: "image/webp",
        }
        return media_types.get(self.screenshot_format, "image/png")


@dataclass
class SiteInventory:
    """Complete inventory of all crawled pages."""

    base_url: str
    pages: list[CrawledPage] = field(default_factory=list)
    total_pages: int = 0
    crawl_duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
