"""UI Documentation service — orchestrates crawl → analyze → plan → generate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import logfire

from josephus.analyzer.frontend import (
    RouteMap,
    detect_framework,
    extract_route_map,
    match_screens_to_code,
    prioritize_frontend_files,
)
from josephus.crawler.models import CrawlConfig, SiteInventory
from josephus.crawler.site_crawler import SiteCrawler
from josephus.generator.planning import DocStructurePlan
from josephus.generator.ui_docs import UIDocGenerator, UIGeneratedDocs
from josephus.generator.ui_planning import UIDocPlan, UIDocPlanner, UITerminology
from josephus.llm.provider import LLMProvider, get_provider


@dataclass
class UIDocResult:
    """Result of UI documentation generation."""

    # Site info
    base_url: str
    pages_crawled: int

    # Plan
    plan: UIDocPlan

    # Generated docs
    generated_docs: UIGeneratedDocs

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Errors
    errors: list[str] = field(default_factory=list)


class UIDocService:
    """Orchestrates UI documentation generation.

    Pipeline:
    1. Crawl deployment with Playwright
    2. Analyze repository for route→code mapping (optional)
    3. Plan documentation structure (terminology + structure)
    4. Generate per-screen documentation
    5. Collect results (markdown + screenshots)
    """

    def __init__(
        self,
        llm: LLMProvider | None = None,
    ) -> None:
        self.llm = llm or get_provider()

    async def generate(
        self,
        crawl_config: CrawlConfig,
        repo_files: list[str] | None = None,
        file_contents: dict[str, str] | None = None,
        guidelines: str = "",
    ) -> UIDocResult:
        """Generate UI documentation for a deployment.

        Args:
            crawl_config: Configuration for the site crawler
            repo_files: Optional list of repository file paths for code analysis
            file_contents: Optional file contents for route extraction
            guidelines: User documentation guidelines

        Returns:
            UIDocResult with all generated docs and screenshots
        """
        started_at = datetime.utcnow()
        errors: list[str] = []

        logfire.info(
            "Starting UI documentation generation",
            base_url=crawl_config.base_url,
        )

        # Step 1: Crawl the deployment
        inventory = await self._crawl(crawl_config)

        if not inventory.pages:
            return UIDocResult(
                base_url=crawl_config.base_url,
                pages_crawled=0,
                plan=UIDocPlan(
                    terminology=UITerminology(),
                    structure=DocStructurePlan(files=[]),
                ),
                generated_docs=UIGeneratedDocs(),
                started_at=started_at,
                completed_at=datetime.utcnow(),
                errors=["No pages were crawled. Check the deployment URL and auth configuration."],
            )

        errors.extend(inventory.errors)

        # Step 2: Code analysis (optional)
        code_context = {}
        if repo_files and file_contents:
            code_context = self._analyze_code(
                inventory=inventory,
                repo_files=repo_files,
                file_contents=file_contents,
            )

        # Step 3: Plan documentation
        planner = UIDocPlanner(self.llm)
        plan = await planner.plan(
            inventory=inventory,
            code_context=self._format_code_context(code_context),
            guidelines=guidelines,
        )

        # Step 4: Generate per-screen docs
        generator = UIDocGenerator(self.llm)
        generated_docs = await generator.generate_all(
            inventory=inventory,
            plan=plan,
            code_context={
                url: self._format_code_context(files) for url, files in code_context.items()
            }
            if code_context
            else None,
            guidelines=guidelines,
        )

        completed_at = datetime.utcnow()

        logfire.info(
            "UI documentation generation complete",
            files=len(generated_docs.files),
            screenshots=len(generated_docs.screenshots),
            duration_seconds=(completed_at - started_at).total_seconds(),
        )

        return UIDocResult(
            base_url=crawl_config.base_url,
            pages_crawled=len(inventory.pages),
            plan=plan,
            generated_docs=generated_docs,
            started_at=started_at,
            completed_at=completed_at,
            errors=errors,
        )

    async def _crawl(self, config: CrawlConfig) -> SiteInventory:
        """Crawl the deployment."""
        logfire.info("Crawling deployment", base_url=config.base_url)
        crawler = SiteCrawler(config)
        return await crawler.crawl()

    def _analyze_code(
        self,
        inventory: SiteInventory,
        repo_files: list[str],
        file_contents: dict[str, str],
    ) -> dict[str, list[str]]:
        """Analyze code to match screens to source files.

        Returns:
            Dict mapping screen URL → list of relevant source files
        """
        logfire.info("Analyzing code for screen-to-code mapping")

        # Prioritize frontend files
        prioritized = prioritize_frontend_files(repo_files)

        # Detect framework and extract routes
        framework = detect_framework(prioritized, file_contents)
        route_map: RouteMap = extract_route_map(prioritized, file_contents, framework)

        # Match screens to code
        screen_urls = [p.url for p in inventory.pages]
        return match_screens_to_code(screen_urls, prioritized, route_map)

    def _format_code_context(self, context: dict | list | str) -> str:
        """Format code context for LLM prompt."""
        if isinstance(context, str):
            return context
        if isinstance(context, list):
            return "\n".join(context)
        if isinstance(context, dict):
            parts = []
            for key, value in context.items():
                if isinstance(value, list):
                    parts.append(f"Files for {key}: {', '.join(value)}")
                else:
                    parts.append(f"{key}: {value}")
            return "\n".join(parts)
        return ""

    async def close(self) -> None:
        """Close all connections."""
        await self.llm.close()
