"""Unit tests for documentation structure planning."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from josephus.generator.planning import (
    DocPlanner,
    DocStructurePlan,
    PlannedFile,
    PlannedSection,
    parse_structure_plan,
)


class TestPlannedSection:
    """Tests for PlannedSection."""

    def test_create_section(self) -> None:
        """Test creating a planned section."""
        section = PlannedSection(
            heading="Installation",
            description="How to install the package",
            order=1,
        )

        assert section.heading == "Installation"
        assert section.description == "How to install the package"
        assert section.order == 1

    def test_default_order(self) -> None:
        """Test default order value."""
        section = PlannedSection(heading="Test", description="Desc")
        assert section.order == 0


class TestPlannedFile:
    """Tests for PlannedFile."""

    def test_create_file(self) -> None:
        """Test creating a planned file."""
        file = PlannedFile(
            path="docs/index.md",
            title="Documentation",
            description="Main documentation page",
            order=1,
            sections=[
                PlannedSection("Overview", "Project overview", 1),
                PlannedSection("Features", "Key features", 2),
            ],
        )

        assert file.path == "docs/index.md"
        assert file.title == "Documentation"
        assert len(file.sections) == 2

    def test_empty_sections(self) -> None:
        """Test file with no sections."""
        file = PlannedFile(
            path="docs/readme.md",
            title="README",
            description="Basic readme",
        )

        assert file.sections == []


class TestDocStructurePlan:
    """Tests for DocStructurePlan."""

    def test_total_files(self) -> None:
        """Test total_files property."""
        plan = DocStructurePlan(
            files=[
                PlannedFile("docs/index.md", "Index", "Main page", order=1),
                PlannedFile("docs/getting-started.md", "Getting Started", "Setup", order=2),
            ]
        )

        assert plan.total_files == 2

    def test_file_paths(self) -> None:
        """Test file_paths property returns ordered paths."""
        plan = DocStructurePlan(
            files=[
                PlannedFile("docs/api.md", "API", "API docs", order=3),
                PlannedFile("docs/index.md", "Index", "Main page", order=1),
                PlannedFile("docs/getting-started.md", "Getting Started", "Setup", order=2),
            ]
        )

        assert plan.file_paths == [
            "docs/index.md",
            "docs/getting-started.md",
            "docs/api.md",
        ]

    def test_to_prompt_context(self) -> None:
        """Test conversion to prompt context."""
        plan = DocStructurePlan(
            files=[
                PlannedFile(
                    path="docs/index.md",
                    title="Documentation",
                    description="Main page",
                    order=1,
                    sections=[
                        PlannedSection("Overview", "Project overview", 1),
                    ],
                ),
            ],
            rationale="Simple structure",
        )

        context = plan.to_prompt_context()

        assert "docs/index.md" in context
        assert "Documentation" in context
        assert "Main page" in context
        assert "Overview" in context


class TestParseStructurePlan:
    """Tests for parse_structure_plan function."""

    def test_parse_valid_json(self) -> None:
        """Test parsing valid JSON structure plan."""
        content = """
        {
            "rationale": "Test project structure",
            "files": [
                {
                    "path": "docs/index.md",
                    "title": "Documentation",
                    "description": "Main page",
                    "order": 1,
                    "sections": [
                        {"heading": "Overview", "description": "Project overview", "order": 1}
                    ]
                }
            ]
        }
        """

        plan = parse_structure_plan(content)

        assert plan.rationale == "Test project structure"
        assert len(plan.files) == 1
        assert plan.files[0].path == "docs/index.md"
        assert len(plan.files[0].sections) == 1

    def test_parse_json_in_code_block(self) -> None:
        """Test parsing JSON wrapped in markdown code block."""
        content = """
Here's the plan:

```json
{
    "rationale": "Structure for CLI tool",
    "files": [
        {
            "path": "docs/index.md",
            "title": "CLI Docs",
            "description": "Main docs",
            "order": 1,
            "sections": []
        }
    ]
}
```
        """

        plan = parse_structure_plan(content)

        assert plan.rationale == "Structure for CLI tool"
        assert len(plan.files) == 1

    def test_parse_invalid_json_raises(self) -> None:
        """Test that invalid JSON raises ValueError."""
        content = "not valid json at all"

        with pytest.raises(ValueError, match="No JSON found"):
            parse_structure_plan(content)

    def test_parse_malformed_json_raises(self) -> None:
        """Test that malformed JSON raises ValueError."""
        content = '{"invalid": json without quotes}'

        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_structure_plan(content)

    def test_parse_missing_fields_uses_defaults(self) -> None:
        """Test that missing fields get default values."""
        content = """
        {
            "files": [
                {
                    "path": "docs/test.md"
                }
            ]
        }
        """

        plan = parse_structure_plan(content)

        assert plan.rationale == ""
        assert plan.files[0].title == "Untitled"
        assert plan.files[0].sections == []


class TestDocPlanner:
    """Tests for DocPlanner."""

    @pytest.fixture
    def mock_analysis(self) -> MagicMock:
        """Create a mock repository analysis."""
        analysis = MagicMock()
        analysis.repository.name = "test-repo"
        analysis.repository.full_name = "test/repo"
        analysis.repository.description = "Test repository"
        analysis.repository.language = "Python"
        analysis.repository.default_branch = "main"
        analysis.directory_structure = "src/\n  main.py"
        analysis.truncated = False
        analysis.skipped_files = []

        # Create a mock file
        mock_file = MagicMock()
        mock_file.path = "src/main.py"
        mock_file.content = "def main(): pass"
        analysis.files = [mock_file]

        return analysis

    @pytest.mark.asyncio
    async def test_plan_success(self, mock_analysis: MagicMock) -> None:
        """Test successful structure planning."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = """
        {
            "rationale": "Library documentation",
            "files": [
                {"path": "docs/index.md", "title": "Index", "description": "Main", "order": 1, "sections": []},
                {"path": "docs/api.md", "title": "API", "description": "API ref", "order": 2, "sections": []}
            ]
        }
        """
        mock_llm.generate.return_value = mock_response

        planner = DocPlanner(mock_llm)
        plan = await planner.plan(mock_analysis)

        assert plan.total_files == 2
        assert plan.rationale == "Library documentation"
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_plan_fallback_on_error(self, mock_analysis: MagicMock) -> None:
        """Test that planning falls back to default on parse error."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Not valid JSON response"
        mock_llm.generate.return_value = mock_response

        planner = DocPlanner(mock_llm)
        plan = await planner.plan(mock_analysis)

        # Should return default plan
        assert plan.total_files == 2
        assert "docs/index.md" in plan.file_paths
        assert "docs/getting-started.md" in plan.file_paths

    @pytest.mark.asyncio
    async def test_plan_with_guidelines(self, mock_analysis: MagicMock) -> None:
        """Test planning with guidelines."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            '{"files": [{"path": "docs/index.md", "title": "T", "description": "D", "order": 1}]}'
        )
        mock_llm.generate.return_value = mock_response

        planner = DocPlanner(mock_llm)
        await planner.plan(mock_analysis, guidelines="Focus on API docs")

        # Check that guidelines were passed
        call_args = mock_llm.generate.call_args
        assert "Focus on API docs" in call_args.kwargs["prompt"]
