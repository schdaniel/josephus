"""Tests for UI documentation planning and terminology extraction."""

import json

from josephus.crawler.models import (
    CrawledPage,
    DOMData,
    FormField,
    Heading,
    InteractiveElement,
    NavLink,
    PageType,
    ScreenshotFormat,
    SiteInventory,
)
from josephus.generator.ui_planning import (
    PlannedScreen,
    SubPage,
    TermEntry,
    UIDocPlan,
    UITerminology,
    _build_screen_summary,
    _default_ui_plan,
    _extract_json,
    build_terminology_prompt,
    build_ui_planning_prompt,
    get_ui_planning_system_prompt,
    parse_terminology,
    parse_ui_structure_plan,
)


class TestTermEntry:
    def test_basic_term(self):
        entry = TermEntry(
            term="Dashboard",
            definition="Main overview screen",
            category="navigation",
        )
        assert entry.term == "Dashboard"
        assert entry.category == "navigation"
        assert entry.synonyms == []

    def test_term_with_synonyms(self):
        entry = TermEntry(
            term="Workspace",
            definition="A shared project area",
            category="concept",
            synonyms=["Project", "Space"],
        )
        assert entry.synonyms == ["Project", "Space"]


class TestUITerminology:
    def test_empty_terminology(self):
        t = UITerminology()
        assert t.terms == []
        assert t.app_name is None
        assert t.primary_navigation == []

    def test_to_prompt_context(self):
        t = UITerminology(
            terms=[
                TermEntry("Dashboard", "Main overview", "navigation"),
                TermEntry("Deploy", "Push changes live", "action", synonyms=["Publish"]),
            ],
            app_name="MyApp",
            primary_navigation=["Dashboard", "Settings", "Users"],
        )
        ctx = t.to_prompt_context()
        assert "Application: MyApp" in ctx
        assert "Dashboard, Settings, Users" in ctx
        assert "**Dashboard** (navigation): Main overview" in ctx
        assert "(also: Publish)" in ctx

    def test_to_prompt_context_empty(self):
        t = UITerminology()
        ctx = t.to_prompt_context()
        assert ctx == ""


class TestPlannedScreen:
    def test_basic(self):
        ps = PlannedScreen(screen_url="https://app.example.com/dashboard")
        assert ps.screen_url == "https://app.example.com/dashboard"
        assert ps.source_files == []
        assert ps.sub_pages == []

    def test_with_sub_pages(self):
        ps = PlannedScreen(
            screen_url="https://app.example.com/settings",
            sub_pages=[
                SubPage(path="docs/ui/settings-general.md", title="General", tab_name="General"),
                SubPage(path="docs/ui/settings-security.md", title="Security", tab_name="Security"),
            ],
        )
        assert len(ps.sub_pages) == 2
        assert ps.sub_pages[0].tab_name == "General"


class TestBuildScreenSummary:
    def test_with_dom_data(self):
        page = CrawledPage(
            url="https://app.example.com/dashboard",
            title="Dashboard",
            nav_path=["Home", "Dashboard"],
            dom=DOMData(
                headings=[Heading(level=1, text="Dashboard")],
                nav_links=[NavLink(text="Settings", href="/settings")],
                interactive_elements=[
                    InteractiveElement(
                        element_type="button", label="Save", selector="button.save", action="click"
                    ),
                ],
                form_fields=[
                    FormField(field_type="text", label="Name", name="name"),
                ],
                detected_tabs=["Overview", "Details"],
                detected_modals=["Delete Confirmation"],
            ),
        )
        summary = _build_screen_summary(page)
        assert summary["url"] == "https://app.example.com/dashboard"
        assert summary["title"] == "Dashboard"
        assert summary["nav_path"] == "Home > Dashboard"
        assert len(summary["headings"]) == 1
        assert summary["headings"][0]["text"] == "Dashboard"
        assert summary["tabs"] == ["Overview", "Details"]
        assert summary["modals"] == ["Delete Confirmation"]
        assert summary["buttons"] == ["Save"]
        assert len(summary["form_fields"]) == 1

    def test_without_dom(self):
        page = CrawledPage(
            url="https://app.example.com/page",
            title="Page",
            nav_path=[],
            dom=DOMData(),
        )
        summary = _build_screen_summary(page)
        assert summary["headings"] == []
        assert summary["tabs"] == []
        assert summary["nav_path"] == ""


class TestExtractJson:
    def test_code_block(self):
        content = '```json\n{"key": "value"}\n```'
        result = _extract_json(content)
        assert result == {"key": "value"}

    def test_raw_json(self):
        content = 'Here is the result: {"key": "value"}'
        result = _extract_json(content)
        assert result == {"key": "value"}

    def test_no_json_raises(self):
        import pytest

        with pytest.raises(ValueError, match="No JSON found"):
            _extract_json("no json here")

    def test_invalid_json_raises(self):
        import pytest

        with pytest.raises(ValueError, match="Invalid JSON"):
            _extract_json("```json\n{invalid}\n```")


class TestParseTerminology:
    def test_basic_parsing(self):
        content = json.dumps(
            {
                "terms": [
                    {
                        "term": "Dashboard",
                        "definition": "Main overview screen",
                        "category": "navigation",
                        "synonyms": [],
                    },
                    {
                        "term": "Deploy",
                        "definition": "Push changes",
                        "category": "action",
                        "synonyms": ["Publish", "Ship"],
                    },
                ],
                "app_name": "TestApp",
                "primary_navigation": ["Dashboard", "Settings"],
            }
        )
        result = parse_terminology(content)
        assert result.app_name == "TestApp"
        assert len(result.terms) == 2
        assert result.terms[0].term == "Dashboard"
        assert result.terms[1].synonyms == ["Publish", "Ship"]
        assert result.primary_navigation == ["Dashboard", "Settings"]

    def test_empty_response(self):
        content = json.dumps({"terms": []})
        result = parse_terminology(content)
        assert result.terms == []
        assert result.app_name is None

    def test_wrapped_in_code_block(self):
        content = (
            '```json\n{"terms": [{"term": "X", "definition": "Y", "category": "concept"}]}\n```'
        )
        result = parse_terminology(content)
        assert len(result.terms) == 1
        assert result.terms[0].term == "X"


class TestParseUIStructurePlan:
    def test_basic_plan(self):
        content = json.dumps(
            {
                "rationale": "Simple app structure",
                "files": [
                    {
                        "path": "docs/ui/index.md",
                        "title": "Overview",
                        "description": "App overview",
                        "screen_urls": ["https://app.example.com/"],
                        "order": 1,
                        "sections": [
                            {"heading": "Welcome", "description": "Welcome section", "order": 1}
                        ],
                        "sub_pages": [],
                    },
                    {
                        "path": "docs/ui/dashboard.md",
                        "title": "Dashboard",
                        "description": "Dashboard docs",
                        "screen_urls": ["https://app.example.com/dashboard"],
                        "order": 2,
                        "sections": [],
                        "sub_pages": [],
                    },
                ],
            }
        )
        plan, mapping = parse_ui_structure_plan(content)
        assert plan.rationale == "Simple app structure"
        assert plan.total_files == 2
        assert plan.files[0].path == "docs/ui/index.md"
        assert "https://app.example.com/" in mapping
        assert "https://app.example.com/dashboard" in mapping

    def test_plan_with_sub_pages(self):
        content = json.dumps(
            {
                "rationale": "Complex screen",
                "files": [
                    {
                        "path": "docs/ui/settings.md",
                        "title": "Settings",
                        "description": "Settings page",
                        "screen_urls": ["https://app.example.com/settings"],
                        "order": 1,
                        "sections": [],
                        "sub_pages": [
                            {
                                "path": "docs/ui/settings-general.md",
                                "title": "General Settings",
                                "tab_name": "General",
                            },
                            {
                                "path": "docs/ui/settings-security.md",
                                "title": "Security Settings",
                                "tab_name": "Security",
                            },
                        ],
                    }
                ],
            }
        )
        plan, mapping = parse_ui_structure_plan(content)
        assert plan.total_files == 1
        screen = mapping["https://app.example.com/settings"]
        assert len(screen.sub_pages) == 2
        assert screen.sub_pages[0].tab_name == "General"


class TestDefaultUIPlan:
    def test_generates_plan_from_inventory(self):
        inventory = SiteInventory(
            base_url="https://app.example.com",
            pages=[
                CrawledPage(
                    url="https://app.example.com/",
                    title="Home",
                    nav_path=["Home"],
                    page_type=PageType.CONTENT,
                ),
                CrawledPage(
                    url="https://app.example.com/dashboard",
                    title="Dashboard",
                    nav_path=["Home", "Dashboard"],
                    page_type=PageType.CONTENT,
                ),
                CrawledPage(
                    url="https://app.example.com/login",
                    title="Login",
                    nav_path=[],
                    page_type=PageType.LOGIN,
                ),
            ],
        )
        plan = _default_ui_plan(inventory)
        # Should have index + 2 content pages (login excluded)
        assert plan.total_files == 3
        assert plan.files[0].path == "docs/ui/index.md"
        assert plan.rationale.startswith("Default structure")

    def test_empty_inventory(self):
        inventory = SiteInventory(base_url="https://app.example.com", pages=[])
        plan = _default_ui_plan(inventory)
        assert plan.total_files == 1  # Just the index


class TestPromptTemplates:
    def test_ui_planning_system_prompt_renders(self):
        prompt = get_ui_planning_system_prompt()
        assert "Josephus" in prompt
        assert "UI documentation" in prompt

    def test_terminology_prompt_renders(self):
        screens = [
            {
                "url": "https://app.example.com/",
                "title": "Home",
                "headings": [{"level": 1, "text": "Welcome"}],
                "nav_links": [{"text": "Dashboard", "href": "/dashboard"}],
                "buttons": ["Get Started"],
                "tabs": [],
            }
        ]
        prompt = build_terminology_prompt(screens)
        assert "https://app.example.com/" in prompt
        assert "Welcome" in prompt
        assert "Dashboard" in prompt
        assert "Get Started" in prompt

    def test_ui_planning_prompt_renders(self):
        screens = [
            {
                "url": "https://app.example.com/dashboard",
                "title": "Dashboard",
                "depth": 1,
                "nav_path": "Home > Dashboard",
                "headings": [{"level": 1, "text": "Dashboard"}],
                "tabs": ["Overview", "Analytics"],
                "interactive_elements": [{"type": "button", "label": "Export"}],
                "form_fields": [],
                "modals": ["Confirm Export"],
            }
        ]
        prompt = build_ui_planning_prompt(
            base_url="https://app.example.com",
            screens=screens,
            terminology="Glossary: Dashboard = main view",
            guidelines="Write for non-technical users",
        )
        assert "https://app.example.com" in prompt
        assert "Dashboard" in prompt
        assert "Overview" in prompt
        assert "Analytics" in prompt
        assert "Confirm Export" in prompt
        assert "Glossary: Dashboard = main view" in prompt
        assert "non-technical users" in prompt

    def test_ui_planning_prompt_without_optional_context(self):
        prompt = build_ui_planning_prompt(
            base_url="https://app.example.com",
            screens=[],
        )
        assert "https://app.example.com" in prompt
        # Optional sections should not appear
        assert "terminology" not in prompt.lower() or "terminology" in prompt.lower()


class TestCrawledPageScreenshotProperties:
    def test_screenshot_base64(self):
        page = CrawledPage(
            url="https://example.com",
            title="Test",
            nav_path=[],
            screenshot_bytes=b"fake-png-data",
        )
        assert page.screenshot_base64 is not None
        import base64

        assert base64.b64decode(page.screenshot_base64) == b"fake-png-data"

    def test_screenshot_base64_none(self):
        page = CrawledPage(
            url="https://example.com",
            title="Test",
            nav_path=[],
        )
        assert page.screenshot_base64 is None

    def test_screenshot_media_type_png(self):
        page = CrawledPage(
            url="https://example.com",
            title="Test",
            nav_path=[],
            screenshot_bytes=b"data",
            screenshot_format=ScreenshotFormat.PNG,
        )
        assert page.screenshot_media_type == "image/png"

    def test_screenshot_media_type_jpeg(self):
        page = CrawledPage(
            url="https://example.com",
            title="Test",
            nav_path=[],
            screenshot_bytes=b"data",
            screenshot_format=ScreenshotFormat.JPEG,
        )
        assert page.screenshot_media_type == "image/jpeg"

    def test_screenshot_media_type_webp(self):
        page = CrawledPage(
            url="https://example.com",
            title="Test",
            nav_path=[],
            screenshot_bytes=b"data",
            screenshot_format=ScreenshotFormat.WEBP,
        )
        assert page.screenshot_media_type == "image/webp"

    def test_screenshot_media_type_none_without_bytes(self):
        page = CrawledPage(
            url="https://example.com",
            title="Test",
            nav_path=[],
        )
        assert page.screenshot_media_type is None


class TestUIDocPlan:
    def test_basic_plan(self):
        from josephus.generator.planning import DocStructurePlan, PlannedFile

        plan = UIDocPlan(
            terminology=UITerminology(
                terms=[TermEntry("Dashboard", "Main view", "navigation")],
                app_name="TestApp",
            ),
            structure=DocStructurePlan(
                files=[
                    PlannedFile(
                        path="docs/ui/index.md",
                        title="Overview",
                        description="App overview",
                    )
                ],
                rationale="Simple structure",
            ),
            screen_mapping={
                "https://app.example.com/": PlannedScreen(screen_url="https://app.example.com/")
            },
        )
        assert plan.terminology.app_name == "TestApp"
        assert plan.structure.total_files == 1
        assert len(plan.screen_mapping) == 1
