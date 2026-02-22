"""Screenshot manager — capture, save, compress, and encode screenshots."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from urllib.parse import urlparse

import logfire
from playwright.async_api import Page

from josephus.crawler.models import ScreenshotConfig, ScreenshotFormat


class ScreenshotManager:
    """Manages screenshot capture, storage, and encoding."""

    def __init__(
        self, config: ScreenshotConfig | None = None, output_dir: Path | None = None
    ) -> None:
        self._config = config or ScreenshotConfig()
        self._output_dir = output_dir
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

    async def capture(self, page: Page, url: str | None = None) -> bytes:
        """Capture a screenshot of the current page.

        Returns raw screenshot bytes in the configured format.
        """
        screenshot_kwargs: dict = {
            "full_page": self._config.full_page,
        }

        # Playwright supports png and jpeg natively
        if self._config.format == ScreenshotFormat.JPEG:
            screenshot_kwargs["type"] = "jpeg"
            screenshot_kwargs["quality"] = self._config.quality
        else:
            # PNG (default) — Playwright doesn't support WebP directly,
            # so we capture as PNG and could convert if needed
            screenshot_kwargs["type"] = "png"

        raw_bytes = await page.screenshot(**screenshot_kwargs)

        # Resize if wider than max_width
        raw_bytes = self._resize_if_needed(raw_bytes)

        logfire.info(
            "Screenshot captured",
            url=url or page.url,
            format=self._config.format.value,
            size_kb=len(raw_bytes) // 1024,
        )

        return raw_bytes

    async def capture_and_save(self, page: Page, url: str | None = None) -> tuple[bytes, str]:
        """Capture a screenshot and save to disk.

        Returns (screenshot_bytes, file_path).
        """
        raw_bytes = await self.capture(page, url)
        filename = self.url_to_filename(url or page.url)

        if self._output_dir:
            filepath = self._output_dir / filename
            filepath.write_bytes(raw_bytes)
            logfire.info("Screenshot saved", path=str(filepath))
            return raw_bytes, str(filepath)

        return raw_bytes, filename

    def url_to_filename(self, url: str) -> str:
        """Generate a clean filename from a URL.

        Examples:
            https://app.example.com/ → screen-home.png
            https://app.example.com/dashboard → screen-dashboard.png
            https://app.example.com/users/123 → screen-users-123.png
            https://app.example.com/settings/general → screen-settings-general.png
        """
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        if not path:
            slug = "home"
        else:
            # Replace path separators and non-alphanumeric chars with hyphens
            slug = re.sub(r"[^a-zA-Z0-9]+", "-", path)
            slug = slug.strip("-").lower()
            # Limit length
            if len(slug) > 80:
                slug = slug[:80].rstrip("-")

        ext = self._config.format.value
        if ext == "jpeg":
            ext = "jpg"

        return f"screen-{slug}.{ext}"

    def encode_base64(self, screenshot_bytes: bytes) -> str:
        """Encode screenshot bytes as base64 string."""
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    @property
    def media_type(self) -> str:
        """Get the MIME type for the configured format."""
        mime_map = {
            ScreenshotFormat.PNG: "image/png",
            ScreenshotFormat.JPEG: "image/jpeg",
            ScreenshotFormat.WEBP: "image/webp",
        }
        return mime_map[self._config.format]

    def _resize_if_needed(self, image_bytes: bytes) -> bytes:
        """Resize image if it exceeds max_width. Uses Playwright's native size."""
        # For now, we rely on Playwright's viewport setting to control width.
        # Full image processing (resize/compress/convert to webp) can be added
        # with Pillow if needed, but keeping dependencies minimal for now.
        return image_bytes
