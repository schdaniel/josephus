"""Evaluation metrics for documentation quality and PR detection."""

import re
import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JudgeScores:
    """Scores from LLM-as-judge evaluation."""

    accuracy: float  # 1-5: Are all claims supported by code?
    completeness: float  # 1-5: Are all features from ground truth covered?
    clarity: float  # 1-5: Would a non-technical user understand this?
    hallucination_free: float  # 1-5: No invented features or incorrect behavior?
    issues: list[str] = field(default_factory=list)

    @property
    def average_score(self) -> float:
        """Calculate average score across all dimensions."""
        scores = [self.accuracy, self.completeness, self.clarity, self.hallucination_free]
        return sum(scores) / len(scores)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "accuracy": self.accuracy,
            "completeness": self.completeness,
            "clarity": self.clarity,
            "hallucination_free": self.hallucination_free,
            "average": self.average_score,
            "issues": self.issues,
        }


@dataclass
class PRDetectionMetrics:
    """Metrics for PR relevance detection accuracy."""

    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    total_latency_ms: float = 0.0
    predictions: int = 0

    @property
    def precision(self) -> float:
        """Precision: TP / (TP + FP)."""
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)."""
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 0.0

    @property
    def f1_score(self) -> float:
        """F1 Score: harmonic mean of precision and recall."""
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def accuracy(self) -> float:
        """Overall accuracy: (TP + TN) / total."""
        total = (
            self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        )
        return (self.true_positives + self.true_negatives) / total if total > 0 else 0.0

    @property
    def average_latency_ms(self) -> float:
        """Average latency per prediction."""
        return self.total_latency_ms / self.predictions if self.predictions > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "accuracy": self.accuracy,
            "average_latency_ms": self.average_latency_ms,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


@dataclass
class DocumentationMetrics:
    """Metrics for documentation quality."""

    coverage_score: float = 0.0  # % of public APIs documented
    structure_score: float = 0.0  # Correct headings, code blocks, links
    readability_score: float = 0.0  # Flesch-Kincaid grade level
    judge_scores: JudgeScores | None = None
    files_evaluated: int = 0
    total_tokens_used: int = 0

    @property
    def accuracy_score(self) -> float:
        """Accuracy score from judge evaluation."""
        return self.judge_scores.accuracy if self.judge_scores else 0.0

    @property
    def hallucination_rate(self) -> float:
        """Hallucination rate (inverse of hallucination_free score)."""
        if self.judge_scores:
            # Convert 1-5 scale to 0-100% rate
            # 5 = 0% hallucinations, 1 = 100% hallucinations
            return (5 - self.judge_scores.hallucination_free) / 4 * 100
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "coverage_score": self.coverage_score,
            "structure_score": self.structure_score,
            "readability_score": self.readability_score,
            "accuracy_score": self.accuracy_score,
            "hallucination_rate": self.hallucination_rate,
            "files_evaluated": self.files_evaluated,
            "total_tokens_used": self.total_tokens_used,
            "judge_scores": self.judge_scores.to_dict() if self.judge_scores else None,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result."""

    doc_metrics: DocumentationMetrics
    pr_metrics: PRDetectionMetrics | None = None
    repo_name: str = ""
    baseline_comparison: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "repo_name": self.repo_name,
            "documentation": self.doc_metrics.to_dict(),
        }
        if self.pr_metrics:
            result["pr_detection"] = self.pr_metrics.to_dict()
        if self.baseline_comparison:
            result["baseline_comparison"] = self.baseline_comparison
        return result

    def passes_thresholds(
        self,
        coverage_min: float = 0.85,
        accuracy_min: float = 0.80,
        pr_f1_min: float = 0.88,
    ) -> tuple[bool, list[str]]:
        """Check if metrics pass minimum thresholds.

        Args:
            coverage_min: Minimum coverage score (0-1)
            accuracy_min: Minimum accuracy score (0-1)
            pr_f1_min: Minimum PR detection F1 score (0-1)

        Returns:
            Tuple of (passes, list of failure reasons)
        """
        failures: list[str] = []

        if self.doc_metrics.coverage_score < coverage_min:
            failures.append(f"Coverage {self.doc_metrics.coverage_score:.2%} < {coverage_min:.2%}")

        # Convert judge accuracy (1-5) to 0-1 scale
        normalized_accuracy = (self.doc_metrics.accuracy_score - 1) / 4
        if normalized_accuracy < accuracy_min:
            failures.append(f"Accuracy {normalized_accuracy:.2%} < {accuracy_min:.2%}")

        if self.pr_metrics and self.pr_metrics.f1_score < pr_f1_min:
            failures.append(f"PR F1 {self.pr_metrics.f1_score:.2%} < {pr_f1_min:.2%}")

        return len(failures) == 0, failures


def calculate_readability(text: str) -> float:
    """Calculate Flesch-Kincaid grade level.

    Lower scores are more readable:
    - 5-6: 5th-6th grade, very easy
    - 7-8: 7th-8th grade, easy
    - 9-10: 9th-10th grade, average
    - 11-12: 11th-12th grade, fairly difficult
    - 13+: College level, difficult

    Args:
        text: Text to analyze

    Returns:
        Flesch-Kincaid grade level
    """
    if not text.strip():
        return 0.0

    # Count sentences (approximate)
    sentences = len(re.findall(r"[.!?]+", text)) or 1

    # Count words
    words = len(re.findall(r"\b\w+\b", text)) or 1

    # Count syllables (approximate)
    syllables = _count_syllables(text)

    # Flesch-Kincaid Grade Level formula
    grade_level = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59

    return max(0, grade_level)


def _count_syllables(text: str) -> int:
    """Count syllables in text (approximate).

    Uses a simple heuristic based on vowel patterns.
    """
    text = text.lower()
    words = re.findall(r"\b[a-z]+\b", text)
    total = 0

    for word in words:
        # Count vowel groups
        syllables = len(re.findall(r"[aeiouy]+", word))

        # Adjust for silent 'e'
        if word.endswith("e") and syllables > 1:
            syllables -= 1

        # Adjust for 'le' ending
        if word.endswith("le") and len(word) > 2 and word[-3] not in "aeiouy":
            syllables += 1

        # Minimum 1 syllable per word
        total += max(1, syllables)

    return total


def calculate_structure_score(markdown: str) -> float:
    """Calculate structure score for markdown documentation.

    Checks for:
    - Proper heading hierarchy
    - Code blocks with language specification
    - Valid links
    - Lists where appropriate

    Args:
        markdown: Markdown content to analyze

    Returns:
        Structure score from 0.0 to 1.0
    """
    if not markdown.strip():
        return 0.0

    checks: list[tuple[str, bool]] = []

    # Check for headings
    headings = re.findall(r"^#+\s+.+$", markdown, re.MULTILINE)
    checks.append(("has_headings", len(headings) >= 1))

    # Check for proper heading hierarchy (no skipping levels)
    heading_levels = [len(h.split()[0]) for h in headings]
    proper_hierarchy = True
    for i in range(1, len(heading_levels)):
        if heading_levels[i] > heading_levels[i - 1] + 1:
            proper_hierarchy = False
            break
    checks.append(("proper_heading_hierarchy", proper_hierarchy))

    # Check for code blocks
    code_blocks = re.findall(r"```(\w*)\n", markdown)
    has_code_blocks = len(code_blocks) > 0
    checks.append(("has_code_blocks", has_code_blocks))

    # Check code blocks have language specification
    if code_blocks:
        has_lang_spec = all(lang for lang in code_blocks)
        checks.append(("code_blocks_have_language", has_lang_spec))

    # Check for links
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", markdown)
    if links:
        # Check links have non-empty text
        valid_links = all(text.strip() for text, _ in links)
        checks.append(("valid_link_text", valid_links))

    # Calculate score
    passed = sum(1 for _, result in checks if result)
    return passed / len(checks) if checks else 0.0


def calculate_coverage(
    documented_items: set[str],
    expected_items: set[str],
) -> float:
    """Calculate documentation coverage.

    Args:
        documented_items: Set of documented API/feature names
        expected_items: Set of expected API/feature names

    Returns:
        Coverage score from 0.0 to 1.0
    """
    if not expected_items:
        return 1.0

    covered = documented_items & expected_items
    return len(covered) / len(expected_items)


def aggregate_metrics(results: list[EvaluationResult]) -> dict[str, Any]:
    """Aggregate metrics across multiple evaluation results.

    Args:
        results: List of evaluation results

    Returns:
        Aggregated metrics dictionary
    """
    if not results:
        return {}

    # Collect all metric values
    coverage_scores = [r.doc_metrics.coverage_score for r in results]
    structure_scores = [r.doc_metrics.structure_score for r in results]
    readability_scores = [r.doc_metrics.readability_score for r in results]
    accuracy_scores = [r.doc_metrics.accuracy_score for r in results if r.doc_metrics.judge_scores]

    # PR metrics
    pr_results = [r for r in results if r.pr_metrics]
    pr_f1_scores = [r.pr_metrics.f1_score for r in pr_results if r.pr_metrics]
    pr_precision = [r.pr_metrics.precision for r in pr_results if r.pr_metrics]
    pr_recall = [r.pr_metrics.recall for r in pr_results if r.pr_metrics]

    def safe_mean(values: list[float]) -> float:
        return statistics.mean(values) if values else 0.0

    def safe_stdev(values: list[float]) -> float:
        return statistics.stdev(values) if len(values) > 1 else 0.0

    aggregated = {
        "repos_evaluated": len(results),
        "documentation": {
            "coverage": {
                "mean": safe_mean(coverage_scores),
                "stdev": safe_stdev(coverage_scores),
            },
            "structure": {
                "mean": safe_mean(structure_scores),
                "stdev": safe_stdev(structure_scores),
            },
            "readability": {
                "mean": safe_mean(readability_scores),
                "stdev": safe_stdev(readability_scores),
            },
            "accuracy": {
                "mean": safe_mean(accuracy_scores),
                "stdev": safe_stdev(accuracy_scores),
            },
        },
    }

    if pr_f1_scores:
        aggregated["pr_detection"] = {
            "f1_score": {
                "mean": safe_mean(pr_f1_scores),
                "stdev": safe_stdev(pr_f1_scores),
            },
            "precision": {
                "mean": safe_mean(pr_precision),
                "stdev": safe_stdev(pr_precision),
            },
            "recall": {
                "mean": safe_mean(pr_recall),
                "stdev": safe_stdev(pr_recall),
            },
        }

    return aggregated
