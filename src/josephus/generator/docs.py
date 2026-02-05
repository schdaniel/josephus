"""Documentation generator - creates docs from repository analysis."""

import json
import re
from dataclasses import dataclass

import logfire

from josephus.analyzer import RepoAnalysis, format_for_llm
from josephus.generator.planning import DocPlanner, DocStructurePlan
from josephus.generator.prompts import SYSTEM_PROMPT, build_generation_prompt
from josephus.llm import LLMProvider, LLMResponse


@dataclass
class GeneratedDocs:
    """Generated documentation result."""

    files: dict[str, str]  # path -> content
    llm_response: LLMResponse
    structure_plan: DocStructurePlan | None = None
    total_files: int = 0
    total_chars: int = 0

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

    async def generate(
        self,
        analysis: RepoAnalysis,
        config: GenerationConfig | None = None,
    ) -> GeneratedDocs:
        """Generate documentation for a repository.

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

        # Step 1: Optionally plan structure first
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

        # Step 2: Format repository for LLM
        repo_context = format_for_llm(analysis, config.guidelines)

        # Step 3: Build prompt (with or without structure plan)
        prompt = build_generation_prompt(
            repo_context=repo_context,
            guidelines=config.guidelines,
            structure_plan=structure_plan_context,
        )

        # Step 4: Generate documentation
        response = await self.llm.generate(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

        # Step 5: Parse response
        files = self._parse_response(response.content, config.output_dir)

        logfire.info(
            "Documentation generated",
            repo=analysis.repository.full_name,
            files_generated=len(files),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        return GeneratedDocs(
            files=files,
            llm_response=response,
            structure_plan=structure_plan,
        )

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
                path = match.group(1).strip()

                # Get content between this marker and next (or end)
                start = match.end()
                end = markers[i + 1].start() if i + 1 < len(markers) else len(content)
                doc_content = content[start:end].strip()

                # Normalize path
                if not path.startswith(output_dir):
                    path = f"{output_dir}/{path.lstrip('/')}"
                if not path.endswith(".md"):
                    path = f"{path}.md"

                files[path] = doc_content

            if files:
                logfire.info("Parsed docs using file markers", file_count=len(files))
                return files

        # Fallback to JSON format
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                data = json.loads(json_match.group())
                files = {}
                for path, doc_content in data.items():
                    if not path.startswith(output_dir):
                        path = f"{output_dir}/{path.lstrip('/')}"
                    if not path.endswith(".md"):
                        path = f"{path}.md"
                    files[path] = doc_content

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
