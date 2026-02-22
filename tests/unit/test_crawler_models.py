"""Tests for crawler data models."""

from josephus.crawler.models import (
    AuthConfig,
    AuthStrategy,
    CookieConfig,
    CrawlConfig,
    CrawledPage,
    DOMData,
    FormField,
    Heading,
    InteractiveElement,
    NavLink,
    PageType,
    ScreenshotConfig,
    ScreenshotFormat,
    SiteInventory,
)


class TestScreenshotConfig:
    def test_defaults(self):
        config = ScreenshotConfig()
        assert config.format == ScreenshotFormat.PNG
        assert config.quality == 85
        assert config.max_width == 1280
        assert config.full_page is True

    def test_jpeg_format(self):
        config = ScreenshotConfig(format=ScreenshotFormat.JPEG, quality=70)
        assert config.format == ScreenshotFormat.JPEG
        assert config.quality == 70


class TestAuthConfig:
    def test_default_strategy(self):
        config = AuthConfig()
        assert config.strategy == AuthStrategy.COOKIES
        assert config.cookies == []
        assert config.bearer_token is None

    def test_cookie_auth(self):
        config = AuthConfig(
            strategy=AuthStrategy.COOKIES,
            cookies=[CookieConfig(name="session", value="abc", domain=".example.com")],
        )
        assert len(config.cookies) == 1
        assert config.cookies[0].name == "session"

    def test_token_auth(self):
        config = AuthConfig(
            strategy=AuthStrategy.TOKEN_HEADER,
            bearer_token="eyJtoken",
        )
        assert config.bearer_token == "eyJtoken"


class TestCrawlConfig:
    def test_defaults(self):
        config = CrawlConfig(base_url="https://example.com")
        assert config.max_pages == 50
        assert config.max_depth == 4
        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.include_patterns == []
        assert config.exclude_patterns == []

    def test_with_patterns(self):
        config = CrawlConfig(
            base_url="https://example.com",
            include_patterns=["/dashboard/*"],
            exclude_patterns=["/admin/*", "/api/*"],
        )
        assert len(config.include_patterns) == 1
        assert len(config.exclude_patterns) == 2


class TestDOMData:
    def test_empty_defaults(self):
        dom = DOMData()
        assert dom.headings == []
        assert dom.nav_links == []
        assert dom.interactive_elements == []
        assert dom.form_fields == []
        assert dom.visible_text == ""
        assert dom.aria_landmarks == []
        assert dom.detected_tabs == []
        assert dom.detected_modals == []

    def test_with_data(self):
        dom = DOMData(
            headings=[Heading(level=1, text="Title"), Heading(level=2, text="Section")],
            nav_links=[NavLink(text="Home", href="/", is_active=True)],
            interactive_elements=[
                InteractiveElement(element_type="button", label="Submit", selector="button.submit")
            ],
            form_fields=[FormField(field_type="text", label="Name", name="name")],
            detected_tabs=["Overview", "Details"],
            detected_modals=["Export"],
        )
        assert len(dom.headings) == 2
        assert dom.headings[0].level == 1
        assert dom.nav_links[0].is_active is True
        assert len(dom.detected_tabs) == 2


class TestCrawledPage:
    def test_defaults(self):
        page = CrawledPage(url="https://example.com", title="Home", nav_path=["Home"])
        assert page.page_type == PageType.CONTENT
        assert page.depth == 0
        assert page.parent_url is None
        assert page.screenshot_bytes is None

    def test_error_page(self):
        page = CrawledPage(
            url="https://example.com/404",
            title="Not Found",
            nav_path=["Home", "404"],
            page_type=PageType.ERROR,
            status_code=404,
        )
        assert page.page_type == PageType.ERROR
        assert page.status_code == 404


class TestSiteInventory:
    def test_empty(self):
        inventory = SiteInventory(base_url="https://example.com")
        assert inventory.total_pages == 0
        assert inventory.pages == []
        assert inventory.errors == []

    def test_with_pages(self):
        pages = [
            CrawledPage(url="https://example.com", title="Home", nav_path=["Home"]),
            CrawledPage(url="https://example.com/about", title="About", nav_path=["Home", "About"]),
        ]
        inventory = SiteInventory(
            base_url="https://example.com",
            pages=pages,
            total_pages=2,
            crawl_duration_seconds=3.5,
        )
        assert inventory.total_pages == 2
        assert inventory.crawl_duration_seconds == 3.5
