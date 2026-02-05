"""Evaluation infrastructure for documentation quality assessment."""

from josephus.eval.download import (
    download_all,
    download_repo,
    get_repos_dir,
    list_repos,
    load_repos_config,
    update_repos,
)
from josephus.eval.evaluate import evaluate_all, evaluate_docs
from josephus.eval.generate import generate_all, generate_docs_for_repo
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
    # Download
    "download_all",
    "download_repo",
    "get_repos_dir",
    "list_repos",
    "load_repos_config",
    "update_repos",
    # Evaluate
    "evaluate_all",
    "evaluate_docs",
    # Generate
    "generate_all",
    "generate_docs_for_repo",
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
