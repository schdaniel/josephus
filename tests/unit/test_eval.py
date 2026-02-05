"""Unit tests for evaluation infrastructure."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from josephus.eval import (
    DocumentationMetrics,
    EvalDataset,
    EvaluationResult,
    EvaluationRunner,
    JudgeScores,
    PRDetectionMetrics,
    aggregate_metrics,
    calculate_coverage,
    calculate_readability,
    calculate_structure_score,
)
from josephus.eval.judge import DocumentationJudge


class TestJudgeScores:
    """Tests for JudgeScores dataclass."""

    def test_average_score(self) -> None:
        """Test average score calculation."""
        scores = JudgeScores(
            accuracy=4.0,
            completeness=3.0,
            clarity=5.0,
            hallucination_free=4.0,
        )

        assert scores.average_score == 4.0

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        scores = JudgeScores(
            accuracy=4.0,
            completeness=3.0,
            clarity=5.0,
            hallucination_free=4.0,
            issues=["Missing API reference"],
        )

        d = scores.to_dict()

        assert d["accuracy"] == 4.0
        assert d["completeness"] == 3.0
        assert d["clarity"] == 5.0
        assert d["hallucination_free"] == 4.0
        assert d["average"] == 4.0
        assert d["issues"] == ["Missing API reference"]


class TestPRDetectionMetrics:
    """Tests for PR detection metrics."""

    def test_precision(self) -> None:
        """Test precision calculation."""
        metrics = PRDetectionMetrics(
            true_positives=8,
            false_positives=2,
            true_negatives=5,
            false_negatives=1,
        )

        assert metrics.precision == 0.8  # 8 / (8 + 2)

    def test_recall(self) -> None:
        """Test recall calculation."""
        metrics = PRDetectionMetrics(
            true_positives=8,
            false_positives=2,
            true_negatives=5,
            false_negatives=2,
        )

        assert metrics.recall == 0.8  # 8 / (8 + 2)

    def test_f1_score(self) -> None:
        """Test F1 score calculation."""
        metrics = PRDetectionMetrics(
            true_positives=8,
            false_positives=2,
            true_negatives=5,
            false_negatives=2,
        )

        # precision = 0.8, recall = 0.8
        # F1 = 2 * 0.8 * 0.8 / (0.8 + 0.8) = 0.8
        assert metrics.f1_score == pytest.approx(0.8)

    def test_zero_division_handling(self) -> None:
        """Test handling of zero division cases."""
        metrics = PRDetectionMetrics()

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0
        assert metrics.accuracy == 0.0
        assert metrics.average_latency_ms == 0.0

    def test_average_latency(self) -> None:
        """Test average latency calculation."""
        metrics = PRDetectionMetrics(
            total_latency_ms=500.0,
            predictions=10,
        )

        assert metrics.average_latency_ms == 50.0


class TestDocumentationMetrics:
    """Tests for documentation metrics."""

    def test_accuracy_score_from_judge(self) -> None:
        """Test accuracy score extraction from judge scores."""
        metrics = DocumentationMetrics(
            judge_scores=JudgeScores(
                accuracy=4.5,
                completeness=3.0,
                clarity=4.0,
                hallucination_free=5.0,
            )
        )

        assert metrics.accuracy_score == 4.5

    def test_hallucination_rate(self) -> None:
        """Test hallucination rate calculation."""
        # hallucination_free = 5 (no hallucinations) -> 0% rate
        metrics = DocumentationMetrics(
            judge_scores=JudgeScores(
                accuracy=4.0,
                completeness=3.0,
                clarity=4.0,
                hallucination_free=5.0,
            )
        )
        assert metrics.hallucination_rate == 0.0

        # hallucination_free = 1 (many hallucinations) -> 100% rate
        metrics2 = DocumentationMetrics(
            judge_scores=JudgeScores(
                accuracy=4.0,
                completeness=3.0,
                clarity=4.0,
                hallucination_free=1.0,
            )
        )
        assert metrics2.hallucination_rate == 100.0


class TestEvaluationResult:
    """Tests for evaluation result."""

    def test_passes_thresholds_success(self) -> None:
        """Test threshold check when passing."""
        result = EvaluationResult(
            doc_metrics=DocumentationMetrics(
                coverage_score=0.90,
                judge_scores=JudgeScores(
                    accuracy=4.5,  # (4.5 - 1) / 4 = 0.875 normalized
                    completeness=4.0,
                    clarity=4.0,
                    hallucination_free=4.5,
                ),
            ),
            pr_metrics=PRDetectionMetrics(
                true_positives=9,
                false_positives=1,
                false_negatives=1,
                true_negatives=9,
            ),
        )

        passes, failures = result.passes_thresholds(
            coverage_min=0.85,
            accuracy_min=0.80,
            pr_f1_min=0.88,
        )

        assert passes is True
        assert failures == []

    def test_passes_thresholds_failure(self) -> None:
        """Test threshold check when failing."""
        result = EvaluationResult(
            doc_metrics=DocumentationMetrics(
                coverage_score=0.70,  # Below 0.85
                judge_scores=JudgeScores(
                    accuracy=2.0,  # (2.0 - 1) / 4 = 0.25 normalized, below 0.80
                    completeness=3.0,
                    clarity=3.0,
                    hallucination_free=3.0,
                ),
            ),
            pr_metrics=PRDetectionMetrics(
                true_positives=5,
                false_positives=5,  # 50% precision
                false_negatives=5,  # 50% recall
                true_negatives=5,
            ),
        )

        passes, failures = result.passes_thresholds()

        assert passes is False
        assert len(failures) == 3
        assert any("Coverage" in f for f in failures)
        assert any("Accuracy" in f for f in failures)
        assert any("PR F1" in f for f in failures)


class TestReadabilityCalculation:
    """Tests for readability score calculation."""

    def test_simple_text(self) -> None:
        """Test readability of simple text."""
        text = "The cat sat on the mat. It was a nice day."
        score = calculate_readability(text)

        # Simple text should have low grade level
        assert score < 8.0

    def test_complex_text(self) -> None:
        """Test readability of complex text."""
        text = """
        The implementation utilizes sophisticated algorithmic paradigms
        to facilitate the optimization of computational resource allocation
        through advanced heuristic methodologies.
        """
        score = calculate_readability(text)

        # Complex text should have higher grade level
        assert score > 10.0

    def test_empty_text(self) -> None:
        """Test readability of empty text."""
        assert calculate_readability("") == 0.0
        assert calculate_readability("   ") == 0.0


class TestStructureScoreCalculation:
    """Tests for structure score calculation."""

    def test_well_structured_markdown(self) -> None:
        """Test score for well-structured markdown."""
        markdown = """
# Main Heading

## Section One

Some content here.

```python
def example():
    pass
```

## Section Two

- Item one
- Item two

[Link text](https://example.com)
"""
        score = calculate_structure_score(markdown)

        assert score >= 0.8

    def test_poorly_structured_markdown(self) -> None:
        """Test score for poorly structured markdown."""
        markdown = """
Some text without headings.

More text.

def example():
    pass
"""
        score = calculate_structure_score(markdown)

        assert score < 0.5

    def test_empty_markdown(self) -> None:
        """Test score for empty markdown."""
        assert calculate_structure_score("") == 0.0

    def test_heading_hierarchy(self) -> None:
        """Test detection of skipped heading levels."""
        # Bad: jumps from h1 to h3
        bad_markdown = """
# Main

### Skipped Level
"""
        bad_score = calculate_structure_score(bad_markdown)

        # Good: proper hierarchy
        good_markdown = """
# Main

## Level Two

### Level Three
"""
        good_score = calculate_structure_score(good_markdown)

        assert good_score > bad_score


class TestCoverageCalculation:
    """Tests for coverage calculation."""

    def test_full_coverage(self) -> None:
        """Test 100% coverage."""
        documented = {"func_a", "func_b", "func_c"}
        expected = {"func_a", "func_b", "func_c"}

        assert calculate_coverage(documented, expected) == 1.0

    def test_partial_coverage(self) -> None:
        """Test partial coverage."""
        documented = {"func_a", "func_b"}
        expected = {"func_a", "func_b", "func_c", "func_d"}

        assert calculate_coverage(documented, expected) == 0.5

    def test_no_coverage(self) -> None:
        """Test zero coverage."""
        documented = {"other_func"}
        expected = {"func_a", "func_b"}

        assert calculate_coverage(documented, expected) == 0.0

    def test_empty_expected(self) -> None:
        """Test with no expected items."""
        documented = {"func_a"}
        expected: set[str] = set()

        assert calculate_coverage(documented, expected) == 1.0


class TestAggregateMetrics:
    """Tests for metrics aggregation."""

    def test_aggregate_single_result(self) -> None:
        """Test aggregation of single result."""
        results = [
            EvaluationResult(
                doc_metrics=DocumentationMetrics(
                    coverage_score=0.90,
                    structure_score=0.85,
                    readability_score=8.5,
                ),
                repo_name="test-repo",
            )
        ]

        aggregated = aggregate_metrics(results)

        assert aggregated["repos_evaluated"] == 1
        assert aggregated["documentation"]["coverage"]["mean"] == 0.90
        assert aggregated["documentation"]["structure"]["mean"] == 0.85

    def test_aggregate_multiple_results(self) -> None:
        """Test aggregation of multiple results."""
        results = [
            EvaluationResult(
                doc_metrics=DocumentationMetrics(
                    coverage_score=0.80,
                    structure_score=0.70,
                    readability_score=8.0,
                ),
                repo_name="repo-1",
            ),
            EvaluationResult(
                doc_metrics=DocumentationMetrics(
                    coverage_score=1.00,
                    structure_score=0.90,
                    readability_score=10.0,
                ),
                repo_name="repo-2",
            ),
        ]

        aggregated = aggregate_metrics(results)

        assert aggregated["repos_evaluated"] == 2
        assert aggregated["documentation"]["coverage"]["mean"] == 0.90
        assert aggregated["documentation"]["structure"]["mean"] == 0.80

    def test_aggregate_empty_results(self) -> None:
        """Test aggregation of empty results."""
        assert aggregate_metrics([]) == {}


class TestDocumentationJudge:
    """Tests for LLM-as-judge."""

    def test_parse_valid_response(self) -> None:
        """Test parsing valid JSON response."""
        judge = DocumentationJudge()

        response = """
        Here is my evaluation:
        {"accuracy": 4, "completeness": 3, "clarity": 5, "hallucinations": 4, "issues": ["Minor issue"]}
        """

        scores = judge._parse_response(response)

        assert scores.accuracy == 4.0
        assert scores.completeness == 3.0
        assert scores.clarity == 5.0
        assert scores.hallucination_free == 4.0
        assert scores.issues == ["Minor issue"]

    def test_parse_invalid_response(self) -> None:
        """Test parsing invalid response returns defaults."""
        judge = DocumentationJudge()

        response = "This is not JSON at all"
        scores = judge._parse_response(response)

        # Should return default scores
        assert scores.accuracy == 3.0
        assert scores.completeness == 3.0
        assert len(scores.issues) > 0

    def test_validate_score_clamps_values(self) -> None:
        """Test score validation clamps to 1-5 range."""
        judge = DocumentationJudge()

        assert judge._validate_score(0) == 1.0
        assert judge._validate_score(10) == 5.0
        assert judge._validate_score(3.5) == 3.5
        assert judge._validate_score("invalid") == 3.0


class TestEvalDataset:
    """Tests for evaluation dataset."""

    def test_from_path(self, tmp_path: Path) -> None:
        """Test creating dataset from path."""
        # Create required directories
        (tmp_path / "repos").mkdir()
        (tmp_path / "ground_truth").mkdir()

        dataset = EvalDataset.from_path(tmp_path)

        assert dataset.repos_dir == tmp_path / "repos"
        assert dataset.ground_truth_dir == tmp_path / "ground_truth"
        assert dataset.pr_scenarios_dir is None

    def test_from_path_with_pr_scenarios(self, tmp_path: Path) -> None:
        """Test creating dataset with PR scenarios."""
        (tmp_path / "repos").mkdir()
        (tmp_path / "ground_truth").mkdir()
        (tmp_path / "pr_scenarios").mkdir()

        dataset = EvalDataset.from_path(tmp_path)

        assert dataset.pr_scenarios_dir == tmp_path / "pr_scenarios"

    def test_from_path_missing_repos(self, tmp_path: Path) -> None:
        """Test error when repos directory missing."""
        (tmp_path / "ground_truth").mkdir()

        with pytest.raises(ValueError, match="Repos directory not found"):
            EvalDataset.from_path(tmp_path)

    def test_list_repos(self, tmp_path: Path) -> None:
        """Test listing available repos."""
        repos_dir = tmp_path / "repos"
        repos_dir.mkdir()
        (repos_dir / "repo-1").mkdir()
        (repos_dir / "repo-2").mkdir()
        (tmp_path / "ground_truth").mkdir()

        dataset = EvalDataset.from_path(tmp_path)
        repos = dataset.list_repos()

        assert set(repos) == {"repo-1", "repo-2"}


class TestEvaluationRunner:
    """Tests for evaluation runner."""

    @pytest.fixture
    def eval_dataset(self, tmp_path: Path) -> EvalDataset:
        """Create a test dataset."""
        repos_dir = tmp_path / "repos"
        repos_dir.mkdir()
        (repos_dir / "test-repo").mkdir()

        # Create a simple source file
        (repos_dir / "test-repo" / "main.py").write_text("def hello(): pass")

        ground_truth_dir = tmp_path / "ground_truth"
        ground_truth_dir.mkdir()
        (ground_truth_dir / "test-repo").mkdir()
        (ground_truth_dir / "test-repo" / "expected_docs").mkdir()
        (ground_truth_dir / "test-repo" / "expected_docs" / "index.md").write_text(
            "# Test Documentation\n\n## hello()\n\nSays hello."
        )

        # Create annotations
        annotations = {"expected_items": ["hello"]}
        (ground_truth_dir / "test-repo" / "annotations.json").write_text(json.dumps(annotations))

        return EvalDataset.from_path(tmp_path)

    @pytest.mark.asyncio
    async def test_run_evaluation(self, eval_dataset: EvalDataset) -> None:
        """Test running evaluation."""
        runner = EvaluationRunner(eval_dataset, quick=True, verbose=False)

        # Mock the judge to avoid LLM calls
        with patch.object(runner, "_judge", MagicMock()):
            runner._judge = AsyncMock()
            runner._judge.evaluate = AsyncMock(
                return_value=JudgeScores(
                    accuracy=4.0,
                    completeness=4.0,
                    clarity=4.0,
                    hallucination_free=4.0,
                )
            )
            runner._judge.close = AsyncMock()

            results = await runner.run(repos=["test-repo"])

        assert len(results) == 1
        assert results[0].repo_name == "test-repo"

    def test_load_docs(self, eval_dataset: EvalDataset) -> None:
        """Test loading documentation files."""
        runner = EvaluationRunner(eval_dataset)

        docs = runner._load_docs(eval_dataset.ground_truth_dir / "test-repo" / "expected_docs")

        assert "index.md" in docs
        assert "# Test Documentation" in docs["index.md"]

    def test_extract_documented_items(self, eval_dataset: EvalDataset) -> None:
        """Test extracting documented items."""
        runner = EvaluationRunner(eval_dataset)

        docs = {
            "index.md": """
# API Reference

### hello()
Says hello.

### goodbye()
Says goodbye.

Uses class `MyClass` for operations.
"""
        }

        items = runner._extract_documented_items(docs)

        assert "hello" in items
        assert "goodbye" in items
        assert "MyClass" in items
