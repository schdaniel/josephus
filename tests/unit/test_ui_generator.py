"""Tests for UI documentation generator."""

from josephus.crawler.models import (
    CrawledPage,
    DOMData,
    FormField,
    Heading,
    InteractiveElement,
    NavLink,
)
from josephus.generator.planning import DocStructurePlan, PlannedFile
from josephus.generator.ui_docs import (
    UIDocGenerator,
    UIGeneratedDocs,
    build_ui_page_prompt,
    get_ui_system_prompt,
)
from josephus.generator.ui_planning import (
    PlannedScreen,
    UIDocPlan,
    UITerminology,
)


class TestUIGeneratedDocs:
    def test_empty(self):
        docs = UIGeneratedDocs()
        assert docs.files == {}
        assert docs.screenshots == {}
        assert docs.total_input_tokens == 0
        assert docs.total_output_tokens == 0

    def test_with_data(self):
        docs = UIGeneratedDocs(
            files={"docs/ui/dashboard.md": "# Dashboard\n\nContent here"},
            screenshots={"docs/ui/screenshots/screen-dashboard.png": b"png-data"},
            total_input_tokens=1000,
            total_output_tokens=500,
        )
        assert len(docs.files) == 1
        assert len(docs.screenshots) == 1


class TestPromptTemplates:
    def test_ui_system_prompt_renders(self):
        prompt = get_ui_system_prompt()
        assert "Josephus" in prompt
        assert "UI documentation" in prompt
        assert "screenshot" in prompt.lower()

    def test_ui_page_prompt_renders(self):
        prompt = build_ui_page_prompt(
            screen_url="https://app.example.com/dashboard",
            screen_title="Dashboard",
            nav_path="Home > Dashboard",
            screenshot_ref="screenshots/screen-dashboard.png",
            headings=[{"level": 1, "text": "Dashboard"}],
            nav_links=[{"text": "Settings", "href": "/settings", "is_active": False}],
            interactive_elements=[{"element_type": "button", "label": "Export", "action": "click"}],
            form_fields=[
                {
                    "field_type": "text",
                    "name": "search",
                    "label": "Search",
                    "placeholder": "Search...",
                    "required": False,
                }
            ],
            tabs=["Overview", "Analytics"],
            modals=["Confirm Export"],
            visible_text="Welcome to your dashboard",
            terminology="Dashboard = main overview",
            guidelines="Write for beginners",
        )
        assert "https://app.example.com/dashboard" in prompt
        assert "Dashboard" in prompt
        assert "Export" in prompt
        assert "Overview" in prompt
        assert "Analytics" in prompt
        assert "Confirm Export" in prompt
        assert "Search" in prompt
        assert "Write for beginners" in prompt

    def test_ui_page_prompt_minimal(self):
        prompt = build_ui_page_prompt(
            screen_url="https://app.example.com/",
            screen_title="Home",
            nav_path="",
            screenshot_ref="screenshots/screen-home.png",
        )
        assert "https://app.example.com/" in prompt
        assert "Home" in prompt


class TestUIDocGenerator:
    def test_extract_dom_for_prompt(self):
        page = CrawledPage(
            url="https://app.example.com/dashboard",
            title="Dashboard",
            nav_path=["Home", "Dashboard"],
            dom=DOMData(
                headings=[Heading(level=1, text="Dashboard")],
                nav_links=[NavLink(text="Settings", href="/settings")],
                interactive_elements=[
                    InteractiveElement(
                        element_type="button",
                        label="Save",
                        selector="button.save",
                        action="click",
                    ),
                ],
                form_fields=[
                    FormField(
                        field_type="email",
                        label="Email",
                        name="email",
                        required=True,
                    ),
                ],
                detected_tabs=["General", "Advanced"],
                detected_modals=["Delete"],
                visible_text="Some visible text",
            ),
        )
        gen = UIDocGenerator.__new__(UIDocGenerator)
        result = gen._extract_dom_for_prompt(page)

        assert len(result["headings"]) == 1
        assert result["headings"][0]["text"] == "Dashboard"
        assert len(result["nav_links"]) == 1
        assert result["tabs"] == ["General", "Advanced"]
        assert result["modals"] == ["Delete"]
        assert result["form_fields"][0]["field_type"] == "email"
        assert result["form_fields"][0]["required"] is True
        assert result["visible_text"] == "Some visible text"

    def test_extract_dom_empty(self):
        page = CrawledPage(
            url="https://app.example.com/",
            title="Home",
            nav_path=[],
        )
        gen = UIDocGenerator.__new__(UIDocGenerator)
        result = gen._extract_dom_for_prompt(page)
        # Default DOMData is all empty lists/strings
        assert result["headings"] == []
        assert result["tabs"] == []
        assert result["form_fields"] == []

    def test_generate_index_content(self):
        gen = UIDocGenerator.__new__(UIDocGenerator)
        planned_file = PlannedFile(
            path="docs/ui/index.md",
            title="App Guide",
            description="Guide to the application",
            order=1,
        )
        plan = UIDocPlan(
            terminology=UITerminology(app_name="TestApp"),
            structure=DocStructurePlan(
                files=[
                    planned_file,
                    PlannedFile(
                        path="docs/ui/dashboard.md",
                        title="Dashboard",
                        description="Dashboard docs",
                        order=2,
                    ),
                    PlannedFile(
                        path="docs/ui/settings.md",
                        title="Settings",
                        description="Settings docs",
                        order=3,
                    ),
                ],
            ),
        )
        content = gen._generate_index_content(planned_file, plan)
        assert "# App Guide" in content
        assert "TestApp" in content
        assert "[Dashboard](dashboard.md)" in content
        assert "[Settings](settings.md)" in content
        # Index should not link to itself
        assert "[App Guide]" not in content

    def test_get_screen_urls_for_file(self):
        gen = UIDocGenerator.__new__(UIDocGenerator)
        planned_file = PlannedFile(
            path="docs/ui/dashboard.md",
            title="Dashboard",
            description="",
        )
        plan = UIDocPlan(
            terminology=UITerminology(),
            structure=DocStructurePlan(files=[planned_file]),
            screen_mapping={
                "https://app.example.com/dashboard": PlannedScreen(
                    screen_url="https://app.example.com/dashboard"
                ),
                "https://app.example.com/settings": PlannedScreen(
                    screen_url="https://app.example.com/settings"
                ),
            },
        )
        urls = gen._get_screen_urls_for_file(planned_file, plan)
        assert len(urls) >= 1


class TestConfigSettings:
    def test_crawler_settings_exist(self):
        """Verify crawler settings are defined in config."""
        from josephus.core.config import Settings

        # Check fields exist (don't instantiate — requires env setup)
        field_names = {f.alias or name for name, f in Settings.model_fields.items()}
        assert (
            "playwright_headless" in field_names or "playwright_headless" in Settings.model_fields
        )
        assert "crawler_max_pages" in Settings.model_fields
        assert "screenshot_format" in Settings.model_fields
        assert "screenshot_quality" in Settings.model_fields
