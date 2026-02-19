"""Unit tests for large repository handling (#109)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from josephus.analyzer.repo import (
    AnalyzedFile,
    RepoAnalysis,
    format_files_for_llm,
    format_for_llm,
    format_for_llm_compressed,
)
from josephus.generator.docs import DocGenerator, GenerationConfig
from josephus.generator.planning import (
    PlannedFile,
    parse_structure_plan,
)
from josephus.llm import LLMResponse


def _make_repo(name: str = "test-repo") -> MagicMock:
    """Create a mock Repository."""
    repo = MagicMock()
    repo.name = name
    repo.full_name = f"test/{name}"
    repo.description = "Test repo"
    repo.language = "Python"
    repo.default_branch = "main"
    repo.html_url = f"https://github.com/test/{name}"
    return repo


def _make_file(path: str, content: str, token_count: int = 100) -> AnalyzedFile:
    """Create an AnalyzedFile."""
    return AnalyzedFile(
        path=path,
        content=content,
        size=len(content),
        extension=path.rsplit(".", 1)[-1] if "." in path else "",
        token_count=token_count,
    )


def _make_analysis(files: list[AnalyzedFile] | None = None) -> RepoAnalysis:
    """Create a RepoAnalysis with sensible defaults."""
    if files is None:
        files = [
            _make_file("README.md", "# Test\nThis is a test project.\n"),
            _make_file(
                "src/main.py",
                "\n".join([f"# line {i}" for i in range(50)]),
            ),
            _make_file("src/utils.py", "def helper(): pass\n"),
        ]

    return RepoAnalysis(
        repository=_make_repo(),
        files=files,
        directory_structure="README.md\nsrc/\n  main.py\n  utils.py",
        total_tokens=sum(f.token_count for f in files),
    )


# --- format_for_llm_compressed tests ---


class TestFormatForLlmCompressed:
    """Tests for format_for_llm_compressed()."""

    def test_output_shorter_than_full(self) -> None:
        """Compressed format should be significantly shorter than full."""
        analysis = _make_analysis()
        full = format_for_llm(analysis)
        compressed = format_for_llm_compressed(analysis)

        assert len(compressed) < len(full)

    def test_includes_first_n_lines(self) -> None:
        """Should include the first preview_lines of each file."""
        lines = [f"line_{i}" for i in range(50)]
        content = "\n".join(lines)
        analysis = _make_analysis([_make_file("big.py", content)])

        result = format_for_llm_compressed(analysis, preview_lines=5)

        assert "line_0" in result
        assert "line_4" in result
        assert "line_5" not in result

    def test_includes_total_lines_attribute(self) -> None:
        """Should include total_lines and tokens attributes on file tags."""
        lines = [f"line_{i}" for i in range(30)]
        content = "\n".join(lines)
        analysis = _make_analysis([_make_file("big.py", content, token_count=500)])

        result = format_for_llm_compressed(analysis)

        assert 'total_lines="30"' in result
        assert 'tokens="500"' in result

    def test_truncation_indicator(self) -> None:
        """Should show '... (N more lines)' for truncated files."""
        lines = [f"line_{i}" for i in range(30)]
        content = "\n".join(lines)
        analysis = _make_analysis([_make_file("big.py", content)])

        result = format_for_llm_compressed(analysis, preview_lines=10)

        assert "20 more lines" in result

    def test_small_file_not_truncated(self) -> None:
        """Files shorter than preview_lines should not show truncation."""
        analysis = _make_analysis([_make_file("small.py", "x = 1\n")])

        result = format_for_llm_compressed(analysis, preview_lines=20)

        assert "more lines" not in result

    def test_includes_guidelines(self) -> None:
        """Guidelines should be included in compressed output."""
        analysis = _make_analysis()

        result = format_for_llm_compressed(analysis, guidelines="Write for beginners")

        assert "Write for beginners" in result

    def test_includes_repo_metadata(self) -> None:
        """Should include repo name, description, language."""
        analysis = _make_analysis()

        result = format_for_llm_compressed(analysis)

        assert "test-repo" in result
        assert "Python" in result


# --- format_files_for_llm tests ---


class TestFormatFilesForLlm:
    """Tests for format_files_for_llm()."""

    def test_includes_only_specified_files(self) -> None:
        """Should include only the requested file paths."""
        analysis = _make_analysis()

        result = format_files_for_llm(analysis, ["src/main.py"])

        assert "src/main.py" in result
        assert "README.md" not in result.split("<files>")[1]  # Not in files section

    def test_includes_full_content(self) -> None:
        """Should include full file content, not truncated."""
        lines = [f"line_{i}" for i in range(50)]
        content = "\n".join(lines)
        analysis = _make_analysis([_make_file("big.py", content)])

        result = format_files_for_llm(analysis, ["big.py"])

        assert "line_49" in result

    def test_skips_missing_files(self) -> None:
        """Should silently skip paths not in the analysis."""
        analysis = _make_analysis()

        result = format_files_for_llm(analysis, ["nonexistent.py"])

        assert "nonexistent.py" not in result

    def test_includes_directory_structure(self) -> None:
        """Should include the full directory structure for context."""
        analysis = _make_analysis()

        result = format_files_for_llm(analysis, ["src/main.py"])

        assert "directory_structure" in result

    def test_includes_guidelines(self) -> None:
        """Guidelines should be included."""
        analysis = _make_analysis()

        result = format_files_for_llm(analysis, ["src/main.py"], guidelines="API focus")

        assert "API focus" in result


# --- PlannedFile source_files tests ---


class TestPlannedFileSourceFiles:
    """Tests for source_files field on PlannedFile."""

    def test_parse_source_files(self) -> None:
        """parse_structure_plan should extract source_files."""
        content = """
        {
            "rationale": "Test",
            "files": [
                {
                    "path": "docs/api.md",
                    "title": "API Reference",
                    "description": "API docs",
                    "order": 1,
                    "source_files": ["src/api.py", "src/routes.py"],
                    "sections": []
                }
            ]
        }
        """

        plan = parse_structure_plan(content)

        assert plan.files[0].source_files == ["src/api.py", "src/routes.py"]

    def test_parse_missing_source_files_defaults_empty(self) -> None:
        """Missing source_files should default to empty list."""
        content = """
        {
            "files": [
                {
                    "path": "docs/index.md",
                    "title": "Index",
                    "description": "Main",
                    "order": 1
                }
            ]
        }
        """

        plan = parse_structure_plan(content)

        assert plan.files[0].source_files == []

    def test_source_files_in_prompt_context(self) -> None:
        """to_prompt_context() should include source_files when present."""
        from josephus.generator.planning import DocStructurePlan

        plan = DocStructurePlan(
            files=[
                PlannedFile(
                    path="docs/api.md",
                    title="API",
                    description="API docs",
                    source_files=["src/api.py", "src/routes.py"],
                    order=1,
                ),
            ]
        )

        context = plan.to_prompt_context()

        assert "src/api.py" in context
        assert "src/routes.py" in context


# --- Planner uses compressed context ---


class TestPlannerUsesCompressedContext:
    """Test that DocPlanner uses compressed format."""

    @pytest.mark.asyncio
    async def test_planner_uses_compressed_context(self) -> None:
        """DocPlanner.plan() should use format_for_llm_compressed."""
        from josephus.generator.planning import DocPlanner

        analysis = _make_analysis()

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            '{"files": [{"path": "docs/index.md", "title": "T", "description": "D", "order": 1}]}'
        )
        mock_llm.generate.return_value = mock_response

        planner = DocPlanner(mock_llm)

        with patch("josephus.generator.planning.format_for_llm_compressed") as mock_compressed:
            mock_compressed.return_value = "<compressed/>"
            await planner.plan(analysis)

            mock_compressed.assert_called_once()


# --- DocGenerator single-shot vs per-page tests ---


class TestDocGeneratorLargeRepos:
    """Tests for DocGenerator auto-budget and per-page generation."""

    @pytest.fixture
    def mock_llm(self) -> AsyncMock:
        """Create a mock LLM."""
        llm = AsyncMock()
        response = MagicMock(spec=LLMResponse)
        response.content = "<!-- FILE: docs/index.md -->\n# Index\nHello"
        response.input_tokens = 100
        response.output_tokens = 50
        response.model = "test"
        response.stop_reason = "end_turn"
        llm.generate.return_value = response
        return llm

    @pytest.mark.asyncio
    async def test_generate_small_repo_uses_single_shot(self, mock_llm: AsyncMock) -> None:
        """Small repos should use single-shot generation (one LLM call for content)."""
        analysis = _make_analysis()
        config = GenerationConfig(plan_structure=True)

        generator = DocGenerator(mock_llm)
        result = await generator.generate(analysis, config)

        assert result.total_files >= 1
        # 2 calls: one for planning, one for generation (single-shot)
        assert mock_llm.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_large_repo_uses_per_page(self, mock_llm: AsyncMock) -> None:
        """Large repos should trigger per-page generation (multiple LLM calls)."""
        # Create a large analysis that exceeds the context limit
        big_files = []
        for i in range(100):
            content = f"# Module {i}\n" + ("x = 1\n" * 500)
            big_files.append(_make_file(f"src/module_{i}.py", content, token_count=3000))

        analysis = _make_analysis(big_files)  # 300K tokens total

        # Plan response with source_files
        plan_response = MagicMock(spec=LLMResponse)
        plan_response.content = """
        {
            "rationale": "Large project",
            "files": [
                {"path": "docs/index.md", "title": "Index", "description": "Main", "order": 1, "source_files": ["src/module_0.py"], "sections": []},
                {"path": "docs/api.md", "title": "API", "description": "API ref", "order": 2, "source_files": ["src/module_1.py"], "sections": []}
            ]
        }
        """
        plan_response.input_tokens = 100
        plan_response.output_tokens = 200
        plan_response.model = "test"
        plan_response.stop_reason = "end_turn"

        page_response = MagicMock(spec=LLMResponse)
        page_response.content = "<!-- FILE: docs/index.md -->\n# Docs\nContent"
        page_response.input_tokens = 50
        page_response.output_tokens = 100
        page_response.model = "test"
        page_response.stop_reason = "end_turn"

        # First call = planning, remaining = per-page generation
        mock_llm.generate.side_effect = [plan_response, page_response, page_response]

        generator = DocGenerator(mock_llm)
        config = GenerationConfig(plan_structure=True)
        result = await generator.generate(analysis, config)

        # Should have made: 1 plan call + 2 page calls = 3 total
        assert mock_llm.generate.call_count == 3
        assert result.total_files >= 1

    @pytest.mark.asyncio
    async def test_dynamic_page_discovery(self, mock_llm: AsyncMock) -> None:
        """LLM suggesting new pages via SUGGEST_PAGE should trigger additional generation."""
        big_files = [
            _make_file(f"src/mod_{i}.py", "x = 1\n" * 500, token_count=3000) for i in range(100)
        ]
        analysis = _make_analysis(big_files)

        plan_response = MagicMock(spec=LLMResponse)
        plan_response.content = """
        {
            "rationale": "Test",
            "files": [
                {"path": "docs/index.md", "title": "Index", "description": "Main", "order": 1, "source_files": ["src/mod_0.py"], "sections": []}
            ]
        }
        """
        plan_response.input_tokens = 100
        plan_response.output_tokens = 200
        plan_response.model = "test"
        plan_response.stop_reason = "end_turn"

        # First page response includes a SUGGEST_PAGE marker
        page1_response = MagicMock(spec=LLMResponse)
        page1_response.content = (
            "<!-- FILE: docs/index.md -->\n# Index\nContent\n\n"
            "<!-- SUGGEST_PAGE: docs/advanced.md | Advanced Guide | Advanced topics | src/mod_1.py, src/mod_2.py -->"
        )
        page1_response.input_tokens = 50
        page1_response.output_tokens = 100
        page1_response.model = "test"
        page1_response.stop_reason = "end_turn"

        # Second page response (for discovered page)
        page2_response = MagicMock(spec=LLMResponse)
        page2_response.content = (
            "<!-- FILE: docs/advanced.md -->\n# Advanced Guide\nAdvanced content"
        )
        page2_response.input_tokens = 50
        page2_response.output_tokens = 100
        page2_response.model = "test"
        page2_response.stop_reason = "end_turn"

        mock_llm.generate.side_effect = [plan_response, page1_response, page2_response]

        generator = DocGenerator(mock_llm)
        config = GenerationConfig(plan_structure=True)
        result = await generator.generate(analysis, config)

        # Should have made 3 calls: plan + index page + discovered advanced page
        assert mock_llm.generate.call_count == 3
        assert result.total_files == 2


# --- _parse_page_suggestions tests ---


class TestParsePageSuggestions:
    """Tests for _parse_page_suggestions()."""

    @pytest.fixture
    def generator(self) -> DocGenerator:
        mock_llm = MagicMock()
        return DocGenerator(llm=mock_llm)

    def test_parse_single_suggestion(self, generator: DocGenerator) -> None:
        """Should parse a single SUGGEST_PAGE marker."""
        content = (
            "Some content\n"
            "<!-- SUGGEST_PAGE: docs/advanced.md | Advanced Guide | Deep dive into advanced features | src/advanced.py, src/core.py -->"
        )

        suggestions = generator._parse_page_suggestions(content)

        assert len(suggestions) == 1
        assert suggestions[0].path == "docs/advanced.md"
        assert suggestions[0].title == "Advanced Guide"
        assert suggestions[0].description == "Deep dive into advanced features"
        assert suggestions[0].source_files == ["src/advanced.py", "src/core.py"]

    def test_parse_multiple_suggestions(self, generator: DocGenerator) -> None:
        """Should parse multiple SUGGEST_PAGE markers."""
        content = (
            "<!-- SUGGEST_PAGE: docs/a.md | Page A | Desc A | src/a.py -->\n"
            "<!-- SUGGEST_PAGE: docs/b.md | Page B | Desc B | src/b.py, src/c.py -->"
        )

        suggestions = generator._parse_page_suggestions(content)

        assert len(suggestions) == 2
        assert suggestions[0].path == "docs/a.md"
        assert suggestions[1].path == "docs/b.md"

    def test_parse_no_suggestions(self, generator: DocGenerator) -> None:
        """Should return empty list when no markers present."""
        content = "Just regular content with <!-- FILE: docs/index.md --> markers"

        suggestions = generator._parse_page_suggestions(content)

        assert suggestions == []

    def test_suggestion_has_high_order(self, generator: DocGenerator) -> None:
        """Suggested pages should have high order to appear at end."""
        content = "<!-- SUGGEST_PAGE: docs/extra.md | Extra | More stuff | src/x.py -->"

        suggestions = generator._parse_page_suggestions(content)

        assert suggestions[0].order == 999
