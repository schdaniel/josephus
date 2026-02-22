"""UI documentation planning — terminology extraction and structure planning."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import logfire

from josephus.crawler.models import CrawledPage, PageType, SiteInventory
from josephus.generator.planning import DocStructurePlan, PlannedFile, PlannedSection
from josephus.llm.provider import ImageBlock, LLMProvider, Message, TextBlock
from josephus.templates import render_template


@dataclass
class TermEntry:
    """A single term in the UI terminology glossary."""

    term: str
    definition: str
    category: str  # navigation, action, concept, data, status
    synonyms: list[str] = field(default_factory=list)


@dataclass
class UITerminology:
    """Extracted UI terminology glossary."""

    terms: list[TermEntry] = field(default_factory=list)
    app_name: str | None = None
    primary_navigation: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format terminology as context for downstream prompts."""
        lines = []
        if self.app_name:
            lines.append(f"Application: {self.app_name}")
        if self.primary_navigation:
            lines.append(f"Primary navigation: {', '.join(self.primary_navigation)}")
        if self.terms:
            lines.append("")
            lines.append("Glossary:")
            for entry in self.terms:
                line = f"- **{entry.term}** ({entry.category}): {entry.definition}"
                if entry.synonyms:
                    line += f" (also: {', '.join(entry.synonyms)})"
                lines.append(line)
        return "\n".join(lines)


@dataclass
class PlannedScreen:
    """A screen entry in the UI documentation plan."""

    screen_url: str
    screenshot_path: str | None = None
    source_files: list[str] = field(default_factory=list)
    sub_pages: list[SubPage] = field(default_factory=list)


@dataclass
class SubPage:
    """A sub-page for a complex screen (e.g., a tab)."""

    path: str
    title: str
    tab_name: str


@dataclass
class UIDocPlan:
    """Complete UI documentation plan with terminology and structure."""

    terminology: UITerminology
    structure: DocStructurePlan
    screen_mapping: dict[str, PlannedScreen] = field(default_factory=dict)


def _build_screen_summary(page: CrawledPage) -> dict:
    """Build a summary dict for a crawled page, suitable for templates."""
    summary: dict = {
        "url": page.url,
        "title": page.title,
        "depth": page.depth,
        "nav_path": " > ".join(page.nav_path) if page.nav_path else "",
    }

    if page.dom:
        summary["headings"] = [{"level": h.level, "text": h.text} for h in page.dom.headings]
        summary["nav_links"] = [
            {"text": link.text, "href": link.href} for link in page.dom.nav_links
        ]
        summary["buttons"] = [
            el.label for el in page.dom.interactive_elements if el.element_type == "button"
        ]
        summary["tabs"] = page.dom.detected_tabs
        summary["modals"] = page.dom.detected_modals
        summary["interactive_elements"] = [
            {"type": el.element_type, "label": el.label} for el in page.dom.interactive_elements
        ]
        summary["form_fields"] = [
            {"type": f.field_type, "label": f.label, "name": f.name} for f in page.dom.form_fields
        ]
    else:
        summary["headings"] = []
        summary["nav_links"] = []
        summary["buttons"] = []
        summary["tabs"] = []
        summary["modals"] = []
        summary["interactive_elements"] = []
        summary["form_fields"] = []

    return summary


def get_ui_planning_system_prompt() -> str:
    """Get the system prompt for UI documentation planning."""
    return render_template("ui_planning_system.xml.j2")


def build_terminology_prompt(screens: list[dict]) -> str:
    """Build the terminology extraction prompt."""
    return render_template("ui_terminology.xml.j2", screens=screens)


def build_ui_planning_prompt(
    base_url: str,
    screens: list[dict],
    terminology: str = "",
    code_context: str = "",
    guidelines: str = "",
) -> str:
    """Build the UI documentation planning prompt."""
    return render_template(
        "ui_planning.xml.j2",
        base_url=base_url,
        total_screens=len(screens),
        screens=screens,
        terminology=terminology,
        code_context=code_context,
        guidelines=guidelines,
    )


def parse_terminology(content: str) -> UITerminology:
    """Parse LLM response into a UITerminology glossary.

    Args:
        content: Raw LLM response (expected JSON)

    Returns:
        Parsed UITerminology
    """
    data = _extract_json(content)

    terms = []
    for term_data in data.get("terms", []):
        terms.append(
            TermEntry(
                term=term_data.get("term", ""),
                definition=term_data.get("definition", ""),
                category=term_data.get("category", "concept"),
                synonyms=term_data.get("synonyms", []),
            )
        )

    return UITerminology(
        terms=terms,
        app_name=data.get("app_name"),
        primary_navigation=data.get("primary_navigation", []),
    )


def parse_ui_structure_plan(content: str) -> tuple[DocStructurePlan, dict[str, PlannedScreen]]:
    """Parse LLM response into a UI doc structure plan.

    Returns:
        Tuple of (DocStructurePlan, screen_mapping dict)
    """
    data = _extract_json(content)

    files = []
    screen_mapping: dict[str, PlannedScreen] = {}

    for i, file_data in enumerate(data.get("files", [])):
        sections = []
        for j, section_data in enumerate(file_data.get("sections", [])):
            sections.append(
                PlannedSection(
                    heading=section_data.get("heading", f"Section {j + 1}"),
                    description=section_data.get("description", ""),
                    order=section_data.get("order", j + 1),
                )
            )

        # Parse sub-pages for complex screens
        sub_pages = []
        for sp_data in file_data.get("sub_pages", []):
            sub_pages.append(
                SubPage(
                    path=sp_data.get("path", ""),
                    title=sp_data.get("title", ""),
                    tab_name=sp_data.get("tab_name", ""),
                )
            )

        path = file_data.get("path", f"docs/ui/screen-{i + 1}.md")
        files.append(
            PlannedFile(
                path=path,
                title=file_data.get("title", "Untitled"),
                description=file_data.get("description", ""),
                sections=sections,
                order=file_data.get("order", i + 1),
            )
        )

        # Map screen URLs to this planned file
        screen_urls = file_data.get("screen_urls", [])
        for url in screen_urls:
            screen_mapping[url] = PlannedScreen(
                screen_url=url,
                sub_pages=sub_pages,
            )

    plan = DocStructurePlan(
        files=files,
        rationale=data.get("rationale", ""),
    )

    return plan, screen_mapping


def _extract_json(content: str) -> dict:
    """Extract JSON from LLM response text."""
    # Try markdown code block first
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try raw JSON
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise ValueError("No JSON found in response")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e


class UIDocPlanner:
    """Plans UI documentation structure from crawled screens.

    Two-pass approach:
    1. Terminology extraction — batch low-detail screenshots → glossary
    2. Structure planning — screen inventory + code context + glossary → plan
    """

    # Maximum screens to include screenshots for in terminology pass
    MAX_TERMINOLOGY_SCREENS = 20

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    async def extract_terminology(
        self,
        inventory: SiteInventory,
        max_tokens: int = 4096,
    ) -> UITerminology:
        """Extract UI terminology from crawled screens.

        Uses low-detail screenshots (~85 tokens each) to keep costs down.

        Args:
            inventory: Crawled site inventory with screenshots
            max_tokens: Max response tokens

        Returns:
            UITerminology glossary
        """
        content_pages = [p for p in inventory.pages if p.page_type == PageType.CONTENT]
        pages_to_use = content_pages[: self.MAX_TERMINOLOGY_SCREENS]

        logfire.info(
            "Extracting UI terminology",
            base_url=inventory.base_url,
            screens=len(pages_to_use),
        )

        # Build screen summaries for the text prompt
        screen_summaries = [_build_screen_summary(p) for p in pages_to_use]
        text_prompt = build_terminology_prompt(screen_summaries)

        # Build multimodal message with low-detail screenshots
        content_blocks: list[TextBlock | ImageBlock] = []

        for page in pages_to_use:
            if page.screenshot_base64:
                content_blocks.append(
                    ImageBlock(
                        data=page.screenshot_base64,
                        media_type=page.screenshot_media_type or "image/png",
                        detail="low",
                    )
                )

        content_blocks.append(TextBlock(text=text_prompt))

        messages = [Message(role="user", content=content_blocks)]

        response = await self.llm.generate_messages(
            messages=messages,
            system=get_ui_planning_system_prompt(),
            max_tokens=max_tokens,
            temperature=0.3,
        )

        try:
            terminology = parse_terminology(response.content)
        except ValueError as e:
            logfire.warn("Failed to parse terminology, using empty glossary", error=str(e))
            terminology = UITerminology()

        logfire.info(
            "UI terminology extracted",
            terms=len(terminology.terms),
            app_name=terminology.app_name,
        )

        return terminology

    async def plan(
        self,
        inventory: SiteInventory,
        terminology: UITerminology | None = None,
        code_context: str = "",
        guidelines: str = "",
        max_tokens: int = 4096,
    ) -> UIDocPlan:
        """Plan UI documentation structure.

        Args:
            inventory: Crawled site inventory
            terminology: Pre-extracted terminology (if None, extracts first)
            code_context: Formatted source code context
            guidelines: User documentation guidelines
            max_tokens: Max response tokens

        Returns:
            UIDocPlan with terminology, structure, and screen mapping
        """
        # Step 1: Extract terminology if not provided
        if terminology is None:
            terminology = await self.extract_terminology(inventory)

        logfire.info(
            "Planning UI documentation structure",
            base_url=inventory.base_url,
            screens=len(inventory.pages),
        )

        # Step 2: Build screen summaries
        content_pages = [p for p in inventory.pages if p.page_type == PageType.CONTENT]
        screen_summaries = [_build_screen_summary(p) for p in content_pages]

        # Step 3: Build planning prompt with terminology context
        terminology_context = terminology.to_prompt_context()

        text_prompt = build_ui_planning_prompt(
            base_url=inventory.base_url,
            screens=screen_summaries,
            terminology=terminology_context,
            code_context=code_context,
            guidelines=guidelines,
        )

        # Step 4: Build multimodal message with low-detail screenshots
        content_blocks: list[TextBlock | ImageBlock] = []

        for page in content_pages[: self.MAX_TERMINOLOGY_SCREENS]:
            if page.screenshot_base64:
                content_blocks.append(
                    ImageBlock(
                        data=page.screenshot_base64,
                        media_type=page.screenshot_media_type or "image/png",
                        detail="low",
                    )
                )

        content_blocks.append(TextBlock(text=text_prompt))

        messages = [Message(role="user", content=content_blocks)]

        response = await self.llm.generate_messages(
            messages=messages,
            system=get_ui_planning_system_prompt(),
            max_tokens=max_tokens,
            temperature=0.3,
        )

        # Step 5: Parse response
        try:
            structure, screen_mapping = parse_ui_structure_plan(response.content)
        except ValueError as e:
            logfire.warn("Failed to parse UI plan, using default", error=str(e))
            structure = _default_ui_plan(inventory)
            screen_mapping = {}

        logfire.info(
            "UI documentation planned",
            files=structure.total_files,
            screens_mapped=len(screen_mapping),
        )

        return UIDocPlan(
            terminology=terminology,
            structure=structure,
            screen_mapping=screen_mapping,
        )


def _default_ui_plan(inventory: SiteInventory) -> DocStructurePlan:
    """Return a default UI documentation plan based on crawled screens."""
    files = [
        PlannedFile(
            path="docs/ui/index.md",
            title="Application Guide",
            description="Overview of the application and its main screens",
            order=1,
            sections=[
                PlannedSection("Overview", "Application overview", 1),
                PlannedSection("Navigation", "How to navigate the application", 2),
            ],
        ),
    ]

    content_pages = [p for p in inventory.pages if p.page_type == PageType.CONTENT]
    for i, page in enumerate(content_pages):
        # Generate a reasonable filename from the URL path
        path_parts = page.url.rstrip("/").split("/")
        slug = path_parts[-1] if len(path_parts) > 3 else "home"
        slug = re.sub(r"[^a-z0-9-]", "-", slug.lower()).strip("-") or "screen"

        files.append(
            PlannedFile(
                path=f"docs/ui/{slug}.md",
                title=page.title or slug.replace("-", " ").title(),
                description=f"Documentation for {page.url}",
                order=i + 2,
            )
        )

    return DocStructurePlan(
        files=files,
        rationale="Default structure — one article per crawled screen",
    )
