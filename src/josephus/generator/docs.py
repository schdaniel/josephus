"""Documentation generator - creates docs from repository analysis."""

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import logfire
import tiktoken

from josephus.analyzer import (
    AudienceInference,
    RepoAnalysis,
    format_files_for_llm,
    format_for_llm,
    infer_audience,
)
from josephus.generator.planning import DocPlanner, DocStructurePlan, PlannedFile
from josephus.generator.prompts import (
    build_generation_prompt,
    build_page_generation_prompt,
    get_system_prompt,
)
from josephus.llm import LLMProvider, LLMResponse

# Budget constants
MODEL_CONTEXT_LIMIT = 200_000
OUTPUT_BUDGET = 16_384
SYSTEM_PROMPT_BUDGET = 2_000
SAFETY_MARGIN = 5_000


@dataclass
class GeneratedDocs:
    """Generated documentation result."""

    files: dict[str, str]  # path -> content
    llm_response: LLMResponse
    structure_plan: DocStructurePlan | None = None
    audience: AudienceInference | None = None
    total_files: int = 0
    total_chars: int = 0
    llm_responses: list[LLMResponse] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.total_files = len(self.files)
        self.total_chars = sum(len(content) for content in self.files.values())


@dataclass
class GenerationConfig:
    """Configuration for documentation generation."""

    # User guidelines (natural language)
    guidelines: str = ""

    # Output configuration
    output_dir: str = "docs"
    include_index: bool = True

    # Planning
    plan_structure: bool = True  # Whether to plan structure before generating

    # LLM parameters
    max_tokens: int = 16384
    temperature: float = 0.7


class DocGenerator:
    """Generates documentation from repository analysis.

    Takes analyzed repository content and uses an LLM to generate
    comprehensive, user-friendly documentation.
    """

    def __init__(self, llm: LLMProvider) -> None:
        """Initialize the generator.

        Args:
            llm: LLM provider for generation
        """
        self.llm = llm
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self._tokenizer.encode(text))

    def _estimate_available_context(self, config: GenerationConfig) -> int:
        """Calculate how many tokens are available for input context.

        Returns:
            Number of tokens available for repo context in the prompt
        """
        return MODEL_CONTEXT_LIMIT - config.max_tokens - SYSTEM_PROMPT_BUDGET - SAFETY_MARGIN

    async def generate(
        self,
        analysis: RepoAnalysis,
        config: GenerationConfig | None = None,
    ) -> GeneratedDocs:
        """Generate documentation for a repository.

        Automatically chooses single-shot or per-page generation based on
        whether the full repo context fits within the model's context limit.

        Args:
            analysis: Repository analysis result
            config: Generation configuration

        Returns:
            GeneratedDocs with generated files
        """
        config = config or GenerationConfig()

        logfire.info(
            "Starting documentation generation",
            repo=analysis.repository.full_name,
            files_in_analysis=len(analysis.files),
            guidelines_length=len(config.guidelines),
            plan_structure=config.plan_structure,
        )

        # Step 1: Infer target audience
        audience = infer_audience(analysis, config.guidelines)
        audience_context = audience.to_prompt_context()
        logfire.info(
            "Target audience inferred",
            audience=audience.audience.value,
            confidence=audience.confidence,
            signals=audience.signals,
        )

        # Step 2: Optionally plan structure first
        structure_plan: DocStructurePlan | None = None
        structure_plan_context = ""

        if config.plan_structure:
            planner = DocPlanner(self.llm)
            structure_plan = await planner.plan(
                analysis=analysis,
                guidelines=config.guidelines,
            )
            structure_plan_context = structure_plan.to_prompt_context()
            logfire.info(
                "Structure plan created",
                files_planned=structure_plan.total_files,
                file_paths=structure_plan.file_paths,
            )

        # Step 3: Decide single-shot vs per-page based on token math
        repo_context = format_for_llm(analysis, config.guidelines)
        repo_tokens = self._count_tokens(repo_context)
        available = self._estimate_available_context(config)

        if repo_tokens <= available:
            logfire.info(
                "Using single-shot generation",
                repo_tokens=repo_tokens,
                available_tokens=available,
            )
            return await self._generate_single_shot(
                analysis=analysis,
                config=config,
                repo_context=repo_context,
                structure_plan=structure_plan,
                structure_plan_context=structure_plan_context,
                audience=audience,
                audience_context=audience_context,
            )
        else:
            logfire.info(
                "Using per-page generation (repo too large for single-shot)",
                repo_tokens=repo_tokens,
                available_tokens=available,
            )
            if structure_plan is None:
                # Per-page requires a structure plan
                planner = DocPlanner(self.llm)
                structure_plan = await planner.plan(
                    analysis=analysis,
                    guidelines=config.guidelines,
                )
                structure_plan_context = structure_plan.to_prompt_context()

            return await self._generate_per_page(
                analysis=analysis,
                config=config,
                structure_plan=structure_plan,
                structure_plan_context=structure_plan_context,
                audience=audience,
                audience_context=audience_context,
            )

    async def _generate_single_shot(
        self,
        analysis: RepoAnalysis,
        config: GenerationConfig,
        repo_context: str,
        structure_plan: DocStructurePlan | None,
        structure_plan_context: str,
        audience: AudienceInference,
        audience_context: str,
    ) -> GeneratedDocs:
        """Generate all documentation in a single LLM call.

        Used when the full repo context fits within the model's context limit.
        """
        prompt = build_generation_prompt(
            repo_context=repo_context,
            guidelines=config.guidelines,
            structure_plan=structure_plan_context,
            audience_context=audience_context,
        )

        response = await self.llm.generate(
            prompt=prompt,
            system=get_system_prompt(),
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

        files = self._parse_response(response.content, config.output_dir)

        logfire.info(
            "Documentation generated (single-shot)",
            repo=analysis.repository.full_name,
            files_generated=len(files),
            audience=audience.audience.value,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        return GeneratedDocs(
            files=files,
            llm_response=response,
            structure_plan=structure_plan,
            audience=audience,
        )

    async def _generate_per_page(
        self,
        analysis: RepoAnalysis,
        config: GenerationConfig,
        structure_plan: DocStructurePlan,
        structure_plan_context: str,
        audience: AudienceInference,
        audience_context: str,
    ) -> GeneratedDocs:
        """Generate documentation one page at a time.

        Used when the full repo context exceeds the model's context limit.
        Each page is generated with only its relevant source files.
        """
        all_files: dict[str, str] = {}
        all_responses: list[LLMResponse] = []
        generated_manifest: dict[str, str] = {}  # path -> title

        # Use a deque so dynamically discovered pages can be appended
        page_queue: deque[PlannedFile] = deque(sorted(structure_plan.files, key=lambda x: x.order))

        # Fallback: highest-priority source files if source_files is empty
        fallback_source_paths = [f.path for f in analysis.files[:10]]

        while page_queue:
            planned_file = page_queue.popleft()

            # Select source files for this page
            source_paths = planned_file.source_files or fallback_source_paths
            repo_context = format_files_for_llm(analysis, source_paths, config.guidelines)

            prompt = build_page_generation_prompt(
                repo_context=repo_context,
                planned_file=planned_file,
                structure_plan=structure_plan_context,
                audience_context=audience_context,
                guidelines=config.guidelines,
                generated_manifest=generated_manifest,
            )

            response = await self.llm.generate(
                prompt=prompt,
                system=get_system_prompt(),
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )

            all_responses.append(response)

            # Parse the single page from response
            page_files = self._parse_response(response.content, config.output_dir)
            all_files.update(page_files)

            # Track in manifest for cross-referencing
            for path in page_files:
                generated_manifest[path] = planned_file.title

            # Check for SUGGEST_PAGE markers
            suggested = self._parse_page_suggestions(response.content)
            for suggested_file in suggested:
                # Avoid duplicates
                existing_paths = {f.path for f in structure_plan.files}
                existing_paths.update(sf.path for sf in page_queue)
                if suggested_file.path not in existing_paths:
                    page_queue.append(suggested_file)
                    structure_plan.files.append(suggested_file)
                    logfire.info(
                        "Discovered new page from LLM suggestion",
                        path=suggested_file.path,
                        title=suggested_file.title,
                    )

            logfire.info(
                "Generated page",
                path=planned_file.path,
                title=planned_file.title,
                files_remaining=len(page_queue),
            )

        # Use the first response as the primary (for backward compat)
        primary_response = (
            all_responses[0]
            if all_responses
            else LLMResponse(content="", model="unknown", input_tokens=0, output_tokens=0)
        )

        logfire.info(
            "Documentation generated (per-page)",
            repo=analysis.repository.full_name,
            files_generated=len(all_files),
            llm_calls=len(all_responses),
            audience=audience.audience.value,
        )

        return GeneratedDocs(
            files=all_files,
            llm_response=primary_response,
            structure_plan=structure_plan,
            audience=audience,
            llm_responses=all_responses,
        )

    def _parse_page_suggestions(self, content: str) -> list[PlannedFile]:
        """Extract SUGGEST_PAGE markers from LLM output.

        Format: <!-- SUGGEST_PAGE: path | title | description | source_file1, source_file2 -->

        Args:
            content: Raw LLM response content

        Returns:
            List of PlannedFile entries for suggested pages
        """
        pattern = r"<!--\s*SUGGEST_PAGE:\s*([^|]+)\|([^|]+)\|([^|]+)\|([^>]+?)-->"
        suggestions = []

        for match in re.finditer(pattern, content):
            path = match.group(1).strip()
            title = match.group(2).strip()
            description = match.group(3).strip()
            source_files_str = match.group(4).strip()
            source_files = [s.strip() for s in source_files_str.split(",") if s.strip()]

            suggestions.append(
                PlannedFile(
                    path=path,
                    title=title,
                    description=description,
                    source_files=source_files,
                    order=999,  # Append at end
                )
            )

        return suggestions

    def _safe_path(self, path: str, output_dir: str) -> str | None:
        """Safely normalize a file path within the output directory.

        Prevents path traversal attacks by ensuring the resulting path
        is always within the output directory.

        Args:
            path: Raw path from LLM response
            output_dir: Base output directory

        Returns:
            Safe normalized path, or None if path is invalid/malicious
        """
        try:
            # Remove any leading/trailing whitespace
            path = path.strip()

            # Reject paths with null bytes or other suspicious characters
            if "\x00" in path or "\n" in path or "\r" in path:
                logfire.warn("Path contains suspicious characters", path=repr(path))
                return None

            # Parse the path and extract just the filename parts
            # This prevents ../ attacks by only using path components
            parts = PurePosixPath(path).parts

            # Filter out any dangerous path components
            safe_parts = [
                part
                for part in parts
                if part not in (".", "..", "", "/")
                and not part.startswith("~")
                and not part.startswith(".")  # Reject hidden files/dirs
            ]

            # Reject paths that are only dots (like "...")
            safe_parts = [part for part in safe_parts if not all(c == "." for c in part)]

            if not safe_parts:
                logfire.warn("Path has no valid components", path=path)
                return None

            # Reconstruct safe path
            safe_path = "/".join(safe_parts)

            # Ensure it ends with .md
            if not safe_path.endswith(".md"):
                safe_path = f"{safe_path}.md"

            # Build final path within output_dir
            base = Path(output_dir).resolve()
            target = (base / safe_path).resolve()

            # Final safety check: ensure target is within base
            try:
                target.relative_to(base)
            except ValueError:
                logfire.warn(
                    "Path traversal attempt blocked",
                    original_path=path,
                    resolved_target=str(target),
                    base=str(base),
                )
                return None

            # Return relative path (output_dir/safe_path)
            return f"{output_dir}/{safe_path}"

        except Exception as e:
            logfire.warn("Invalid path", path=path, error=str(e))
            return None

    def _parse_response(self, content: str, output_dir: str) -> dict[str, str]:
        """Parse LLM response to extract documentation files.

        Supports two formats:
        1. File markers: <!-- FILE: path/to/file.md --> followed by content
        2. JSON fallback: {"path": "content"} format

        Args:
            content: Raw LLM response
            output_dir: Output directory prefix

        Returns:
            Dict of path -> content
        """
        # Try file marker format first (preferred)
        file_pattern = r"<!--\s*FILE:\s*([^\s>]+)\s*-->"
        markers = list(re.finditer(file_pattern, content))

        if markers:
            files = {}
            for i, match in enumerate(markers):
                raw_path = match.group(1).strip()

                # Get content between this marker and next (or end)
                start = match.end()
                end = markers[i + 1].start() if i + 1 < len(markers) else len(content)
                doc_content = content[start:end].strip()

                # Strip any SUGGEST_PAGE markers from the content
                doc_content = re.sub(r"<!--\s*SUGGEST_PAGE:.*?-->", "", doc_content).strip()

                # Safely normalize path
                safe_path = self._safe_path(raw_path, output_dir)
                if safe_path is None:
                    logfire.warn("Skipping file with unsafe path", raw_path=raw_path)
                    continue

                files[safe_path] = doc_content

            if files:
                logfire.info("Parsed docs using file markers", file_count=len(files))
                return files

        # Fallback to JSON format
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                data = json.loads(json_match.group())
                files = {}
                for raw_path, doc_content in data.items():
                    # Safely normalize path
                    safe_path = self._safe_path(raw_path, output_dir)
                    if safe_path is None:
                        logfire.warn("Skipping file with unsafe path", raw_path=raw_path)
                        continue
                    files[safe_path] = doc_content

                logfire.info("Parsed docs using JSON format", file_count=len(files))
                return files
            except json.JSONDecodeError as e:
                logfire.warn("Failed to parse JSON from response", error=str(e))

        # Final fallback
        logfire.warn("No structured format found, using fallback")
        return self._fallback_parse(content, output_dir)

    def _fallback_parse(self, content: str, output_dir: str) -> dict[str, str]:
        """Fallback parsing when JSON extraction fails.

        Treats entire response as a single README.
        """
        return {
            f"{output_dir}/index.md": content,
        }


async def generate_docs(
    analysis: RepoAnalysis,
    llm: LLMProvider,
    guidelines: str = "",
    output_dir: str = "docs",
) -> GeneratedDocs:
    """Convenience function to generate documentation.

    Args:
        analysis: Repository analysis
        llm: LLM provider
        guidelines: Documentation guidelines
        output_dir: Output directory for docs

    Returns:
        GeneratedDocs result
    """
    generator = DocGenerator(llm)
    config = GenerationConfig(guidelines=guidelines, output_dir=output_dir)
    return await generator.generate(analysis, config)
