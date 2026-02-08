"""Documentation structure planning."""

import json
import re
from dataclasses import dataclass, field

import logfire

from josephus.analyzer import RepoAnalysis, format_for_llm
from josephus.llm import LLMProvider


@dataclass
class PlannedSection:
    """A planned section within a documentation file."""

    heading: str
    description: str
    order: int = 0


@dataclass
class PlannedFile:
    """A planned documentation file."""

    path: str
    title: str
    description: str
    sections: list[PlannedSection] = field(default_factory=list)
    order: int = 0


@dataclass
class DocStructurePlan:
    """Planned documentation structure."""

    files: list[PlannedFile]
    rationale: str = ""

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def file_paths(self) -> list[str]:
        return [f.path for f in sorted(self.files, key=lambda x: x.order)]

    def to_prompt_context(self) -> str:
        """Convert plan to context string for generation prompt."""
        lines = ["Follow this documentation structure plan:"]
        lines.append("")

        for f in sorted(self.files, key=lambda x: x.order):
            lines.append(f"## {f.path}")
            lines.append(f"Title: {f.title}")
            lines.append(f"Purpose: {f.description}")

            if f.sections:
                lines.append("Sections:")
                for section in sorted(f.sections, key=lambda x: x.order):
                    lines.append(f"  - {section.heading}: {section.description}")

            lines.append("")

        return "\n".join(lines)


PLANNING_SYSTEM_PROMPT = """You are Josephus, an expert technical writer planning documentation structure.

Your task is to analyze the codebase and plan the optimal documentation structure BEFORE writing any documentation. Consider:
- The type of project (library, CLI tool, web app, API, etc.)
- The target audience (developers, end-users, administrators)
- Standard documentation conventions for this type of project
- Logical information flow and navigation

Output a JSON structure plan with files and their sections. Each file should have a clear purpose."""


def build_planning_prompt(
    repo_context: str,
    guidelines: str = "",
) -> str:
    """Build the prompt for documentation structure planning.

    Args:
        repo_context: XML-formatted repository context
        guidelines: User's documentation guidelines

    Returns:
        Formatted prompt string
    """
    parts = [
        "Analyze this repository and plan the optimal documentation structure.",
        "",
        repo_context,
    ]

    if guidelines:
        parts.extend(
            [
                "",
                "<user_guidelines>",
                guidelines,
                "</user_guidelines>",
            ]
        )

    parts.extend(
        [
            "",
            "Plan the documentation structure by outputting a JSON object with this schema:",
            "",
            "```json",
            "{",
            '  "rationale": "Brief explanation of why this structure fits the project",',
            '  "files": [',
            "    {",
            '      "path": "docs/index.md",',
            '      "title": "Project Name Documentation",',
            '      "description": "Main landing page with overview and navigation",',
            '      "order": 1,',
            '      "sections": [',
            '        {"heading": "Overview", "description": "What the project does", "order": 1},',
            '        {"heading": "Quick Start", "description": "Fastest path to using it", "order": 2}',
            "      ]",
            "    }",
            "  ]",
            "}",
            "```",
            "",
            "Requirements:",
            "- Include at minimum: index.md (overview), getting-started.md (installation/setup)",
            "- Add appropriate files based on project type:",
            "  - Libraries: API reference, usage examples, configuration",
            "  - CLI tools: Commands reference, configuration, examples",
            "  - Web apps: Features, deployment, configuration",
            "  - APIs: Endpoints, authentication, request/response examples",
            "- Order files logically (index first, getting started second, etc.)",
            "- Each file should have 2-6 meaningful sections",
            "- Use descriptive section headings",
            "",
            "Output ONLY the JSON object, no additional text.",
        ]
    )

    return "\n".join(parts)


def parse_structure_plan(content: str) -> DocStructurePlan:
    """Parse LLM response to extract documentation structure plan.

    Args:
        content: Raw LLM response (expected JSON)

    Returns:
        Parsed DocStructurePlan

    Raises:
        ValueError: If content cannot be parsed
    """
    # Extract JSON from response (may be wrapped in markdown code blocks)
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try to find raw JSON
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise ValueError("No JSON found in response")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    # Parse files
    files = []
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

        files.append(
            PlannedFile(
                path=file_data.get("path", f"docs/file-{i + 1}.md"),
                title=file_data.get("title", "Untitled"),
                description=file_data.get("description", ""),
                sections=sections,
                order=file_data.get("order", i + 1),
            )
        )

    return DocStructurePlan(
        files=files,
        rationale=data.get("rationale", ""),
    )


class DocPlanner:
    """Plans documentation structure before generation."""

    def __init__(self, llm: LLMProvider) -> None:
        """Initialize the planner.

        Args:
            llm: LLM provider for planning
        """
        self.llm = llm

    async def plan(
        self,
        analysis: RepoAnalysis,
        guidelines: str = "",
        max_tokens: int = 4096,
    ) -> DocStructurePlan:
        """Plan documentation structure for a repository.

        Args:
            analysis: Repository analysis result
            guidelines: User's documentation guidelines
            max_tokens: Maximum tokens for response

        Returns:
            DocStructurePlan with planned files and sections
        """
        logfire.info(
            "Planning documentation structure",
            repo=analysis.repository.full_name,
            files_in_analysis=len(analysis.files),
        )

        # Format repository for LLM
        repo_context = format_for_llm(analysis, guidelines)

        # Build prompt
        prompt = build_planning_prompt(repo_context, guidelines)

        # Generate plan
        response = await self.llm.generate(
            prompt=prompt,
            system=PLANNING_SYSTEM_PROMPT,
            max_tokens=max_tokens,
            temperature=0.3,  # Lower temperature for more structured output
        )

        # Parse response
        try:
            plan = parse_structure_plan(response.content)
        except ValueError as e:
            logfire.warn(
                "Failed to parse structure plan, using default",
                error=str(e),
            )
            plan = _default_plan()

        logfire.info(
            "Documentation structure planned",
            repo=analysis.repository.full_name,
            files_planned=plan.total_files,
            rationale=plan.rationale[:100] if plan.rationale else "none",
        )

        return plan


def _default_plan() -> DocStructurePlan:
    """Return a default documentation structure plan."""
    return DocStructurePlan(
        files=[
            PlannedFile(
                path="docs/index.md",
                title="Documentation",
                description="Main documentation page with overview",
                order=1,
                sections=[
                    PlannedSection("Overview", "What the project does", 1),
                    PlannedSection("Features", "Key features and capabilities", 2),
                ],
            ),
            PlannedFile(
                path="docs/getting-started.md",
                title="Getting Started",
                description="Installation and quick start guide",
                order=2,
                sections=[
                    PlannedSection("Installation", "How to install", 1),
                    PlannedSection("Quick Start", "First steps", 2),
                    PlannedSection("Configuration", "Basic configuration", 3),
                ],
            ),
        ],
        rationale="Default structure for general projects",
    )
