"""Tests for screenshot manager."""

from josephus.crawler.models import ScreenshotConfig, ScreenshotFormat
from josephus.crawler.screenshot import ScreenshotManager


class TestUrlToFilename:
    def setup_method(self):
        self.manager = ScreenshotManager(ScreenshotConfig())

    def test_root_url(self):
        assert self.manager.url_to_filename("https://example.com/") == "screen-home.png"

    def test_root_no_trailing_slash(self):
        assert self.manager.url_to_filename("https://example.com") == "screen-home.png"

    def test_simple_path(self):
        assert (
            self.manager.url_to_filename("https://example.com/dashboard") == "screen-dashboard.png"
        )

    def test_nested_path(self):
        result = self.manager.url_to_filename("https://example.com/settings/general")
        assert result == "screen-settings-general.png"

    def test_path_with_id(self):
        result = self.manager.url_to_filename("https://example.com/users/123")
        assert result == "screen-users-123.png"

    def test_special_characters(self):
        result = self.manager.url_to_filename("https://example.com/my page/test!")
        assert "screen-" in result
        assert ".png" in result
        # Should replace special chars with hyphens
        assert " " not in result

    def test_jpeg_extension(self):
        manager = ScreenshotManager(ScreenshotConfig(format=ScreenshotFormat.JPEG))
        result = manager.url_to_filename("https://example.com/dashboard")
        assert result == "screen-dashboard.jpg"

    def test_webp_extension(self):
        manager = ScreenshotManager(ScreenshotConfig(format=ScreenshotFormat.WEBP))
        result = manager.url_to_filename("https://example.com/dashboard")
        assert result == "screen-dashboard.webp"

    def test_long_path_truncated(self):
        long_path = "/".join(["segment"] * 30)
        result = self.manager.url_to_filename(f"https://example.com/{long_path}")
        # Slug should be at most 80 chars
        slug = result.replace("screen-", "").replace(".png", "")
        assert len(slug) <= 80


class TestEncodeBase64:
    def test_encode(self):
        manager = ScreenshotManager(ScreenshotConfig())
        data = b"fake png data"
        result = manager.encode_base64(data)
        assert isinstance(result, str)
        # Should be valid base64
        import base64

        decoded = base64.b64decode(result)
        assert decoded == data


class TestMediaType:
    def test_png(self):
        manager = ScreenshotManager(ScreenshotConfig(format=ScreenshotFormat.PNG))
        assert manager.media_type == "image/png"

    def test_jpeg(self):
        manager = ScreenshotManager(ScreenshotConfig(format=ScreenshotFormat.JPEG))
        assert manager.media_type == "image/jpeg"

    def test_webp(self):
        manager = ScreenshotManager(ScreenshotConfig(format=ScreenshotFormat.WEBP))
        assert manager.media_type == "image/webp"
