"""UI documentation generator — per-screen multimodal generation."""

from __future__ import annotations

from dataclasses import dataclass, field

import logfire

from josephus.crawler.models import CrawledPage, SiteInventory
from josephus.crawler.screenshot import ScreenshotManager
from josephus.generator.planning import PlannedFile
from josephus.generator.ui_planning import UIDocPlan
from josephus.llm.provider import ImageBlock, LLMProvider, Message, TextBlock
from josephus.templates import render_template


@dataclass
class UIGeneratedDocs:
    """Result of UI documentation generation."""

    files: dict[str, str] = field(default_factory=dict)  # path → markdown content
    screenshots: dict[str, bytes] = field(default_factory=dict)  # path → image bytes
    total_input_tokens: int = 0
    total_output_tokens: int = 0


def get_ui_system_prompt() -> str:
    """Get the system prompt for UI doc writing."""
    return render_template("ui_system.xml.j2")


def build_ui_page_prompt(
    screen_url: str,
    screen_title: str,
    nav_path: str,
    screenshot_ref: str,
    headings: list[dict] | None = None,
    nav_links: list[dict] | None = None,
    interactive_elements: list[dict] | None = None,
    form_fields: list[dict] | None = None,
    tabs: list[str] | None = None,
    modals: list[str] | None = None,
    visible_text: str = "",
    terminology: str = "",
    source_code: str = "",
    plan_context: str = "",
    guidelines: str = "",
) -> str:
    """Build the per-screen generation prompt."""
    return render_template(
        "ui_page.xml.j2",
        screen_url=screen_url,
        screen_title=screen_title,
        nav_path=nav_path,
        screenshot_ref=screenshot_ref,
        headings=headings or [],
        nav_links=nav_links or [],
        interactive_elements=interactive_elements or [],
        form_fields=form_fields or [],
        tabs=tabs or [],
        modals=modals or [],
        visible_text=visible_text,
        terminology=terminology,
        source_code=source_code,
        plan_context=plan_context,
        guidelines=guidelines,
    )


class UIDocGenerator:
    """Generates per-screen UI documentation using multimodal LLM.

    For each screen, sends a high-detail screenshot alongside DOM data
    and source code context to produce a markdown article.
    """

    def __init__(
        self,
        llm: LLMProvider,
        screenshot_manager: ScreenshotManager | None = None,
    ) -> None:
        self.llm = llm
        self.screenshot_manager = screenshot_manager or ScreenshotManager()

    async def generate_all(
        self,
        inventory: SiteInventory,
        plan: UIDocPlan,
        code_context: dict[str, str] | None = None,
        guidelines: str = "",
        max_tokens: int = 8192,
    ) -> UIGeneratedDocs:
        """Generate documentation for all planned screens.

        Args:
            inventory: Crawled site inventory
            plan: UI documentation plan with terminology and structure
            code_context: Map of screen URL → relevant source code
            guidelines: User guidelines
            max_tokens: Max response tokens per screen

        Returns:
            UIGeneratedDocs with markdown files and screenshot references
        """
        result = UIGeneratedDocs()
        code_context = code_context or {}
        system_prompt = get_ui_system_prompt()
        terminology_context = plan.terminology.to_prompt_context()

        # Build a lookup from URL to crawled page
        page_by_url = {p.url: p for p in inventory.pages}

        logfire.info(
            "Starting UI doc generation",
            planned_files=plan.structure.total_files,
            screens=len(page_by_url),
        )

        for planned_file in sorted(plan.structure.files, key=lambda f: f.order):
            # Find the screen URL(s) for this file
            screen_urls = self._get_screen_urls_for_file(planned_file, plan)

            if not screen_urls:
                # Index page or non-screen file — generate from plan context only
                content = self._generate_index_content(planned_file, plan)
                result.files[planned_file.path] = content
                continue

            # Use the first matching page for the primary screenshot
            page = None
            for url in screen_urls:
                if url in page_by_url:
                    page = page_by_url[url]
                    break

            if page is None:
                logfire.warn(
                    "No crawled page found for planned file",
                    path=planned_file.path,
                    urls=screen_urls,
                )
                continue

            # Generate doc for this screen
            doc_content, input_tokens, output_tokens = await self._generate_screen_doc(
                page=page,
                planned_file=planned_file,
                terminology=terminology_context,
                source_code=code_context.get(page.url, ""),
                plan_context=planned_file.description,
                guidelines=guidelines,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )

            result.files[planned_file.path] = doc_content
            result.total_input_tokens += input_tokens
            result.total_output_tokens += output_tokens

            # Collect screenshot
            if page.screenshot_bytes:
                screenshot_filename = self.screenshot_manager.url_to_filename(page.url)
                screenshot_path = f"docs/ui/screenshots/{screenshot_filename}"
                result.screenshots[screenshot_path] = page.screenshot_bytes

        logfire.info(
            "UI doc generation complete",
            files=len(result.files),
            screenshots=len(result.screenshots),
            total_input_tokens=result.total_input_tokens,
            total_output_tokens=result.total_output_tokens,
        )

        return result

    async def generate_screen(
        self,
        page: CrawledPage,
        terminology: str = "",
        source_code: str = "",
        guidelines: str = "",
        max_tokens: int = 8192,
    ) -> str:
        """Generate documentation for a single screen.

        Args:
            page: Crawled page with screenshot and DOM data
            terminology: Terminology context string
            source_code: Relevant source code
            guidelines: User guidelines
            max_tokens: Max response tokens

        Returns:
            Markdown documentation for this screen
        """
        planned_file = PlannedFile(
            path="",
            title=page.title,
            description=f"Documentation for {page.url}",
        )

        content, _, _ = await self._generate_screen_doc(
            page=page,
            planned_file=planned_file,
            terminology=terminology,
            source_code=source_code,
            plan_context="",
            guidelines=guidelines,
            system_prompt=get_ui_system_prompt(),
            max_tokens=max_tokens,
        )
        return content

    async def _generate_screen_doc(
        self,
        page: CrawledPage,
        planned_file: PlannedFile,
        terminology: str,
        source_code: str,
        plan_context: str,
        guidelines: str,
        system_prompt: str,
        max_tokens: int,
    ) -> tuple[str, int, int]:
        """Generate documentation for a single screen.

        Returns:
            Tuple of (markdown_content, input_tokens, output_tokens)
        """
        logfire.info(
            "Generating doc for screen",
            url=page.url,
            title=page.title,
        )

        # Build screenshot reference
        screenshot_filename = self.screenshot_manager.url_to_filename(page.url)
        screenshot_ref = f"screenshots/{screenshot_filename}"

        # Build DOM data for the prompt
        dom_data = self._extract_dom_for_prompt(page)

        # Build text prompt
        text_prompt = build_ui_page_prompt(
            screen_url=page.url,
            screen_title=planned_file.title or page.title,
            nav_path=" > ".join(page.nav_path) if page.nav_path else "",
            screenshot_ref=screenshot_ref,
            terminology=terminology,
            source_code=source_code,
            plan_context=plan_context,
            guidelines=guidelines,
            **dom_data,
        )

        # Build multimodal message
        content_blocks: list[TextBlock | ImageBlock] = []

        if page.screenshot_base64:
            content_blocks.append(
                ImageBlock(
                    data=page.screenshot_base64,
                    media_type=page.screenshot_media_type or "image/png",
                    detail="high",
                )
            )

        content_blocks.append(TextBlock(text=text_prompt))
        messages = [Message(role="user", content=content_blocks)]

        response = await self.llm.generate_messages(
            messages=messages,
            system=system_prompt,
            max_tokens=max_tokens,
            temperature=0.5,
        )

        return response.content, response.input_tokens, response.output_tokens

    def _get_screen_urls_for_file(
        self,
        planned_file: PlannedFile,
        plan: UIDocPlan,
    ) -> list[str]:
        """Get screen URLs associated with a planned file.

        Matches by checking which screen_mapping entries correspond to
        this planned file's path. Falls back to slug matching from
        the file path against screen URLs.
        """
        # The screen_mapping is keyed by URL; the plan structure stores
        # screen_urls per file. Reverse-lookup: find URLs whose planned
        # screen maps to this file path by checking the structure plan.
        urls = []

        # Direct: check if any screen_mapping entry's URL slug matches the file
        file_slug = planned_file.path.rsplit("/", 1)[-1].replace(".md", "")
        for url in plan.screen_mapping:
            # Extract last path segment from URL
            url_slug = url.rstrip("/").rsplit("/", 1)[-1] or "index"
            if url_slug.lower() == file_slug.lower():
                urls.append(url)

        # Fallback: if file is "index", it's an overview page — skip
        if not urls and file_slug == "index":
            return []

        # Fallback: return all mapped URLs (caller will pick the first match)
        if not urls:
            urls = list(plan.screen_mapping.keys())

        return urls

    def _extract_dom_for_prompt(self, page: CrawledPage) -> dict:
        """Extract DOM data into a dict suitable for the prompt template."""
        if not page.dom:
            return {}

        return {
            "headings": [{"level": h.level, "text": h.text} for h in page.dom.headings],
            "nav_links": [
                {"text": n.text, "href": n.href, "is_active": n.is_active}
                for n in page.dom.nav_links
            ],
            "interactive_elements": [
                {
                    "element_type": el.element_type,
                    "label": el.label,
                    "action": el.action,
                }
                for el in page.dom.interactive_elements
            ],
            "form_fields": [
                {
                    "field_type": f.field_type,
                    "name": f.name,
                    "label": f.label,
                    "placeholder": f.placeholder,
                    "required": f.required,
                }
                for f in page.dom.form_fields
            ],
            "tabs": page.dom.detected_tabs,
            "modals": page.dom.detected_modals,
            "visible_text": page.dom.visible_text,
        }

    def _generate_index_content(
        self,
        planned_file: PlannedFile,
        plan: UIDocPlan,
    ) -> str:
        """Generate a simple index page from the plan."""
        lines = [
            f"# {planned_file.title}",
            "",
        ]

        if planned_file.description:
            lines.extend([planned_file.description, ""])

        if plan.terminology.app_name:
            lines.extend(
                [
                    f"Welcome to the {plan.terminology.app_name} documentation.",
                    "",
                ]
            )

        # Add navigation section
        lines.extend(["## Pages", ""])
        for f in sorted(plan.structure.files, key=lambda x: x.order):
            if f.path != planned_file.path:
                rel_path = f.path.replace("docs/ui/", "")
                lines.append(f"- [{f.title}]({rel_path})")

        lines.append("")
        return "\n".join(lines)
