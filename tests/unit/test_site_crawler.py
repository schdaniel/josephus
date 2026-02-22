"""Tests for site crawler URL handling and deduplication."""

from josephus.crawler.models import CrawlConfig, CrawledPage
from josephus.crawler.site_crawler import SiteCrawler


class TestUrlNormalization:
    def setup_method(self):
        self.crawler = SiteCrawler(CrawlConfig(base_url="https://example.com"))

    def test_strips_trailing_slash(self):
        assert (
            self.crawler._normalize_url("https://example.com/dashboard/")
            == "https://example.com/dashboard"
        )

    def test_strips_fragment(self):
        assert (
            self.crawler._normalize_url("https://example.com/page#section")
            == "https://example.com/page"
        )

    def test_preserves_query(self):
        assert (
            self.crawler._normalize_url("https://example.com/search?q=test")
            == "https://example.com/search?q=test"
        )

    def test_root_path(self):
        assert self.crawler._normalize_url("https://example.com") == "https://example.com/"

    def test_root_with_slash(self):
        assert self.crawler._normalize_url("https://example.com/") == "https://example.com/"


class TestUrlTemplateDeduplication:
    def setup_method(self):
        self.crawler = SiteCrawler(CrawlConfig(base_url="https://example.com"))

    def test_numeric_id_detection(self):
        template = self.crawler._get_url_template("https://example.com/users/123")
        assert template == "/users/:id"

    def test_uuid_detection(self):
        template = self.crawler._get_url_template(
            "https://example.com/items/550e8400-e29b-41d4-a716-446655440000"
        )
        assert template == "/items/:uuid"

    def test_non_id_path_preserved(self):
        template = self.crawler._get_url_template("https://example.com/dashboard/analytics")
        assert template == "/dashboard/analytics"

    def test_mixed_path(self):
        template = self.crawler._get_url_template("https://example.com/users/123/posts/456")
        assert template == "/users/:id/posts/:id"

    def test_duplicate_detection(self):
        page1 = CrawledPage(
            url="https://example.com/users/1",
            title="User 1",
            nav_path=["Home", "Users", "1"],
        )
        page2 = CrawledPage(
            url="https://example.com/users/2",
            title="User 2",
            nav_path=["Home", "Users", "2"],
        )

        # First page should not be a duplicate
        assert self.crawler._is_duplicate_template(page1) is False

        # Second page with same template should be a duplicate
        assert self.crawler._is_duplicate_template(page2) is True

    def test_different_templates_not_duplicated(self):
        page1 = CrawledPage(
            url="https://example.com/users/1",
            title="User 1",
            nav_path=["Home", "Users", "1"],
        )
        page2 = CrawledPage(
            url="https://example.com/dashboard",
            title="Dashboard",
            nav_path=["Home", "Dashboard"],
        )

        assert self.crawler._is_duplicate_template(page1) is False
        assert self.crawler._is_duplicate_template(page2) is False


class TestShouldCrawl:
    def test_same_origin(self):
        crawler = SiteCrawler(CrawlConfig(base_url="https://example.com"))
        assert crawler._should_crawl("https://example.com/page") is True

    def test_different_origin(self):
        crawler = SiteCrawler(CrawlConfig(base_url="https://example.com"))
        assert crawler._should_crawl("https://other.com/page") is False

    def test_exclude_pattern(self):
        crawler = SiteCrawler(
            CrawlConfig(
                base_url="https://example.com",
                exclude_patterns=["/admin/*", "/api/*"],
            )
        )
        assert crawler._should_crawl("https://example.com/admin/users") is False
        assert crawler._should_crawl("https://example.com/api/v1/data") is False
        assert crawler._should_crawl("https://example.com/dashboard") is True

    def test_include_pattern(self):
        crawler = SiteCrawler(
            CrawlConfig(
                base_url="https://example.com",
                include_patterns=["/dashboard/*", "/settings/*"],
            )
        )
        assert crawler._should_crawl("https://example.com/dashboard/analytics") is True
        assert crawler._should_crawl("https://example.com/settings/general") is True
        assert crawler._should_crawl("https://example.com/other") is False

    def test_no_patterns_allows_all(self):
        crawler = SiteCrawler(CrawlConfig(base_url="https://example.com"))
        assert crawler._should_crawl("https://example.com/anything/at/all") is True
