"""Evaluation infrastructure for documentation quality assessment."""

from josephus.eval.judge import DocumentationJudge, evaluate_documentation
from josephus.eval.metrics import (
    DocumentationMetrics,
    EvaluationResult,
    JudgeScores,
    PRDetectionMetrics,
    aggregate_metrics,
    calculate_coverage,
    calculate_readability,
    calculate_structure_score,
)
from josephus.eval.runner import (
    EvalDataset,
    EvaluationRunner,
    compare_to_baseline,
    run_evaluation,
)

__all__ = [
    # Metrics
    "JudgeScores",
    "PRDetectionMetrics",
    "DocumentationMetrics",
    "EvaluationResult",
    "calculate_readability",
    "calculate_structure_score",
    "calculate_coverage",
    "aggregate_metrics",
    # Judge
    "DocumentationJudge",
    "evaluate_documentation",
    # Runner
    "EvalDataset",
    "EvaluationRunner",
    "run_evaluation",
    "compare_to_baseline",
]
