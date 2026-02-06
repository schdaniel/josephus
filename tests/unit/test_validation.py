"""Unit tests for validation agent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from josephus.eval.metrics import GuidelinesAdherenceScores
from josephus.generator.validation import (
    ValidationAgent,
    ValidationReport,
    ValidationResult,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_needs_fix_below_threshold(self) -> None:
        """Test that content below threshold needs fix."""
        result = ValidationResult(
            file_path="docs/index.md",
            original_content="# Test",
            scores=GuidelinesAdherenceScores(
                tone_adherence=3.0,
                format_adherence=3.0,
                content_adherence=3.0,
                overall_adherence=3.0,
            ),
        )
        assert result.needs_fix is True

    def test_needs_fix_above_threshold(self) -> None:
        """Test that content above threshold doesn't need fix."""
        result = ValidationResult(
            file_path="docs/index.md",
            original_content="# Test",
            scores=GuidelinesAdherenceScores(
                tone_adherence=4.5,
                format_adherence=4.5,
                content_adherence=4.5,
                overall_adherence=4.5,
            ),
        )
        assert result.needs_fix is False

    def test_needs_fix_at_threshold(self) -> None:
        """Test that content exactly at threshold doesn't need fix."""
        result = ValidationResult(
            file_path="docs/index.md",
            original_content="# Test",
            scores=GuidelinesAdherenceScores(
                tone_adherence=4.0,
                format_adherence=4.0,
                content_adherence=4.0,
                overall_adherence=4.0,
            ),
        )
        assert result.needs_fix is False


class TestValidationReport:
    """Tests for ValidationReport dataclass."""

    def test_total_files(self) -> None:
        """Test total files count."""
        report = ValidationReport(
            file_results=[
                ValidationResult(
                    file_path="docs/a.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=4.0,
                        format_adherence=4.0,
                        content_adherence=4.0,
                        overall_adherence=4.0,
                    ),
                ),
                ValidationResult(
                    file_path="docs/b.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=4.0,
                        format_adherence=4.0,
                        content_adherence=4.0,
                        overall_adherence=4.0,
                    ),
                ),
            ]
        )
        assert report.total_files == 2

    def test_files_needing_fix(self) -> None:
        """Test files needing fix count."""
        report = ValidationReport(
            file_results=[
                ValidationResult(
                    file_path="docs/a.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=4.0,
                        format_adherence=4.0,
                        content_adherence=4.0,
                        overall_adherence=4.5,  # Above threshold
                    ),
                ),
                ValidationResult(
                    file_path="docs/b.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=3.0,
                        format_adherence=3.0,
                        content_adherence=3.0,
                        overall_adherence=3.0,  # Below threshold
                    ),
                ),
            ]
        )
        assert report.files_needing_fix == 1

    def test_files_fixed(self) -> None:
        """Test files fixed count."""
        report = ValidationReport(
            file_results=[
                ValidationResult(
                    file_path="docs/a.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=3.0,
                        format_adherence=3.0,
                        content_adherence=3.0,
                        overall_adherence=3.0,
                    ),
                    was_fixed=True,
                ),
                ValidationResult(
                    file_path="docs/b.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=3.0,
                        format_adherence=3.0,
                        content_adherence=3.0,
                        overall_adherence=3.0,
                    ),
                    was_fixed=False,
                ),
            ]
        )
        assert report.files_fixed == 1

    def test_average_adherence(self) -> None:
        """Test average adherence calculation."""
        report = ValidationReport(
            file_results=[
                ValidationResult(
                    file_path="docs/a.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=4.0,
                        format_adherence=4.0,
                        content_adherence=4.0,
                        overall_adherence=4.0,
                    ),
                ),
                ValidationResult(
                    file_path="docs/b.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=3.0,
                        format_adherence=3.0,
                        content_adherence=3.0,
                        overall_adherence=2.0,
                    ),
                ),
            ]
        )
        assert report.average_adherence == 3.0  # (4.0 + 2.0) / 2

    def test_all_deviations(self) -> None:
        """Test all deviations aggregation."""
        report = ValidationReport(
            file_results=[
                ValidationResult(
                    file_path="docs/a.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=3.0,
                        format_adherence=3.0,
                        content_adherence=3.0,
                        overall_adherence=3.0,
                        deviations=["Issue A1", "Issue A2"],
                    ),
                ),
                ValidationResult(
                    file_path="docs/b.md",
                    original_content="",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=3.0,
                        format_adherence=3.0,
                        content_adherence=3.0,
                        overall_adherence=3.0,
                        deviations=["Issue B1"],
                    ),
                ),
            ]
        )

        deviations = report.all_deviations
        assert len(deviations) == 3
        assert "docs/a.md: Issue A1" in deviations
        assert "docs/b.md: Issue B1" in deviations

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        report = ValidationReport(
            file_results=[
                ValidationResult(
                    file_path="docs/index.md",
                    original_content="# Test",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=4.0,
                        format_adherence=4.0,
                        content_adherence=4.0,
                        overall_adherence=4.0,
                    ),
                )
            ],
            guidelines="Write clearly",
            check_only=True,
        )

        d = report.to_dict()

        assert d["total_files"] == 1
        assert d["check_only"] is True
        assert len(d["file_results"]) == 1
        assert d["file_results"][0]["file_path"] == "docs/index.md"


class TestValidationAgent:
    """Tests for ValidationAgent."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock = AsyncMock()
        mock.generate = AsyncMock(
            return_value=MagicMock(content="# Fixed Content\n\nThis is the fixed documentation.")
        )
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def mock_judge_good_scores(self) -> MagicMock:
        """Create mock GuidelinesJudge with good scores."""
        mock = MagicMock()
        mock.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=4.5,
                format_adherence=4.5,
                content_adherence=4.5,
                overall_adherence=4.5,
                deviations=[],
            )
        )
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def mock_judge_bad_scores(self) -> MagicMock:
        """Create mock GuidelinesJudge with bad scores."""
        mock = MagicMock()
        mock.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=2.5,
                format_adherence=3.0,
                content_adherence=2.0,
                overall_adherence=2.5,
                deviations=["Tone too informal", "Missing code examples"],
            )
        )
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_validate_no_fixes_needed(
        self, mock_llm: MagicMock, mock_judge_good_scores: MagicMock
    ) -> None:
        """Test validation when no fixes are needed."""
        agent = ValidationAgent(mock_llm)
        agent._judge = mock_judge_good_scores

        docs = {"docs/index.md": "# Good Content"}
        guidelines = "Write clearly and professionally."

        report = await agent.validate(docs, guidelines)

        assert report.total_files == 1
        assert report.files_needing_fix == 0
        assert report.files_fixed == 0
        assert report.file_results[0].needs_fix is False

    @pytest.mark.asyncio
    async def test_validate_with_fixes(
        self, mock_llm: MagicMock, mock_judge_bad_scores: MagicMock
    ) -> None:
        """Test validation with automatic fixes."""
        agent = ValidationAgent(mock_llm)
        agent._judge = mock_judge_bad_scores

        docs = {"docs/index.md": "# Bad Content"}
        guidelines = "Write clearly and professionally."

        report = await agent.validate(docs, guidelines, check_only=False)

        assert report.total_files == 1
        assert report.files_needing_fix == 1
        assert report.files_fixed == 1
        assert report.file_results[0].was_fixed is True
        assert report.file_results[0].fixed_content is not None

    @pytest.mark.asyncio
    async def test_validate_check_only_mode(
        self, mock_llm: MagicMock, mock_judge_bad_scores: MagicMock
    ) -> None:
        """Test validation in check-only mode."""
        agent = ValidationAgent(mock_llm)
        agent._judge = mock_judge_bad_scores

        docs = {"docs/index.md": "# Bad Content"}
        guidelines = "Write clearly and professionally."

        report = await agent.validate(docs, guidelines, check_only=True)

        assert report.total_files == 1
        assert report.files_needing_fix == 1
        assert report.files_fixed == 0  # No fixes in check-only mode
        assert report.file_results[0].was_fixed is False
        assert report.check_only is True

    @pytest.mark.asyncio
    async def test_validate_empty_guidelines(self, mock_llm: MagicMock) -> None:
        """Test validation with empty guidelines."""
        agent = ValidationAgent(mock_llm)

        docs = {"docs/index.md": "# Content"}
        guidelines = ""

        report = await agent.validate(docs, guidelines)

        assert report.total_files == 0

    def test_get_fixed_docs(self, mock_llm: MagicMock) -> None:
        """Test getting fixed docs from report."""
        agent = ValidationAgent(mock_llm)

        report = ValidationReport(
            file_results=[
                ValidationResult(
                    file_path="docs/a.md",
                    original_content="# Original A",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=3.0,
                        format_adherence=3.0,
                        content_adherence=3.0,
                        overall_adherence=3.0,
                    ),
                    fixed_content="# Fixed A",
                    was_fixed=True,
                ),
                ValidationResult(
                    file_path="docs/b.md",
                    original_content="# Original B",
                    scores=GuidelinesAdherenceScores(
                        tone_adherence=4.5,
                        format_adherence=4.5,
                        content_adherence=4.5,
                        overall_adherence=4.5,
                    ),
                    was_fixed=False,
                ),
            ]
        )

        fixed_docs = agent.get_fixed_docs(report)

        assert fixed_docs["docs/a.md"] == "# Fixed A"  # Fixed
        assert fixed_docs["docs/b.md"] == "# Original B"  # Not fixed

    def test_generate_fix_summary(self, mock_llm: MagicMock) -> None:
        """Test fix summary generation."""
        agent = ValidationAgent(mock_llm)

        # No deviations
        assert "No specific fixes" in agent._generate_fix_summary([])

        # Single deviation
        summary = agent._generate_fix_summary(["Tone issue"])
        assert "Tone issue" in summary

        # Multiple deviations
        summary = agent._generate_fix_summary(["A", "B", "C", "D", "E"])
        assert "Fixed 5 issues" in summary
        assert "+2 more" in summary
