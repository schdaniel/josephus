"""Evaluation runner for running evaluations on datasets."""

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import logfire

from josephus.analyzer import LocalRepoAnalyzer
from josephus.eval.judge import DocumentationJudge
from josephus.eval.metrics import (
    DocumentationMetrics,
    EvaluationResult,
    PRDetectionMetrics,
    aggregate_metrics,
    calculate_coverage,
    calculate_readability,
    calculate_structure_score,
)
from josephus.generator import DocGenerator, GenerationConfig
from josephus.llm import LLMProvider, get_provider


@dataclass
class EvalDataset:
    """Evaluation dataset configuration."""

    path: Path
    repos_dir: Path
    ground_truth_dir: Path
    pr_scenarios_dir: Path | None

    @classmethod
    def from_path(cls, path: Path) -> "EvalDataset":
        """Create dataset from path.

        Expected structure:
            path/
            ├── repos/           # Repository snapshots
            ├── ground_truth/    # Expected documentation
            └── pr_scenarios/    # PR scenarios (optional)
        """
        repos_dir = path / "repos"
        ground_truth_dir = path / "ground_truth"
        pr_scenarios_dir = path / "pr_scenarios"

        if not repos_dir.exists():
            raise ValueError(f"Repos directory not found: {repos_dir}")
        if not ground_truth_dir.exists():
            raise ValueError(f"Ground truth directory not found: {ground_truth_dir}")

        return cls(
            path=path,
            repos_dir=repos_dir,
            ground_truth_dir=ground_truth_dir,
            pr_scenarios_dir=pr_scenarios_dir if pr_scenarios_dir.exists() else None,
        )

    def list_repos(self) -> list[str]:
        """List available repository names."""
        return [d.name for d in self.repos_dir.iterdir() if d.is_dir()]

    def get_repo_path(self, repo_name: str) -> Path:
        """Get path to repository."""
        return self.repos_dir / repo_name

    def get_ground_truth_path(self, repo_name: str) -> Path:
        """Get path to ground truth for repository."""
        return self.ground_truth_dir / repo_name

    def get_annotations_path(self, repo_name: str) -> Path | None:
        """Get path to annotations file if it exists."""
        path = self.ground_truth_dir / repo_name / "annotations.json"
        return path if path.exists() else None


class EvaluationRunner:
    """Runner for executing evaluations on datasets."""

    def __init__(
        self,
        dataset: EvalDataset,
        quick: bool = False,
        verbose: bool = False,
        llm_provider: LLMProvider | None = None,
        guidelines: str = "",
        output_dir: str = "docs",
    ) -> None:
        """Initialize the runner.

        Args:
            dataset: Evaluation dataset
            quick: If True, run quick evaluation (fewer samples)
            verbose: If True, print detailed progress
            llm_provider: LLM provider for doc generation (uses default if not provided)
            guidelines: Documentation guidelines to use
            output_dir: Output directory for generated docs
        """
        self.dataset = dataset
        self.quick = quick
        self.verbose = verbose
        self.guidelines = guidelines
        self.output_dir = output_dir
        self._llm_provider = llm_provider
        self._owns_llm = llm_provider is None
        self._judge: DocumentationJudge | None = None
        self._analyzer = LocalRepoAnalyzer()

    async def run(
        self,
        repos: list[str] | None = None,
        include_pr_detection: bool = True,
    ) -> list[EvaluationResult]:
        """Run evaluation on specified or all repos.

        Args:
            repos: List of repo names to evaluate. None = all.
            include_pr_detection: Whether to evaluate PR detection.

        Returns:
            List of evaluation results
        """
        if repos is None:
            repos = self.dataset.list_repos()

        if self.quick:
            # Limit to first 3 repos for quick evaluation
            repos = repos[:3]

        logfire.info(
            "Starting evaluation",
            repos=repos,
            quick=self.quick,
            include_pr=include_pr_detection,
        )

        results: list[EvaluationResult] = []

        self._judge = DocumentationJudge()
        try:
            for repo_name in repos:
                if self.verbose:
                    print(f"Evaluating: {repo_name}")

                result = await self._evaluate_repo(repo_name)

                if include_pr_detection and self.dataset.pr_scenarios_dir:
                    pr_metrics = await self._evaluate_pr_detection(repo_name)
                    result.pr_metrics = pr_metrics

                results.append(result)

                if self.verbose:
                    self._print_result(result)
        finally:
            await self._judge.close()
            self._judge = None
            # Close LLM provider if we created it
            if self._owns_llm and self._llm_provider is not None:
                await self._llm_provider.close()
                self._llm_provider = None

        return results

    async def _evaluate_repo(self, repo_name: str) -> EvaluationResult:
        """Evaluate a single repository.

        Args:
            repo_name: Name of repository to evaluate

        Returns:
            Evaluation result for the repository
        """
        repo_path = self.dataset.get_repo_path(repo_name)
        ground_truth_path = self.dataset.get_ground_truth_path(repo_name)

        if not repo_path.exists():
            logfire.warn(f"Repository not found: {repo_path}")
            return EvaluationResult(
                doc_metrics=DocumentationMetrics(),
                repo_name=repo_name,
            )

        # Load expected documentation
        expected_docs = self._load_docs(ground_truth_path / "expected_docs")

        # Load annotations (expected items to document)
        annotations_path = self.dataset.get_annotations_path(repo_name)
        expected_items = self._load_annotations(annotations_path)

        # Generate documentation (placeholder - would use real generator)
        generated_docs = await self._generate_docs(repo_path)

        # Calculate metrics
        doc_metrics = await self._calculate_doc_metrics(
            generated_docs=generated_docs,
            expected_docs=expected_docs,
            repo_path=repo_path,
            expected_items=expected_items,
        )

        return EvaluationResult(
            doc_metrics=doc_metrics,
            repo_name=repo_name,
        )

    async def _generate_docs(self, repo_path: Path) -> dict[str, str]:
        """Generate documentation for a repository.

        Uses the actual doc generator with local repo analysis.

        Args:
            repo_path: Path to repository

        Returns:
            Dict mapping file paths to generated content
        """
        logfire.info("Generating documentation", repo_path=str(repo_path))

        # Get or create LLM provider
        if self._llm_provider is None:
            self._llm_provider = get_provider()

        # Analyze repository locally
        analysis = self._analyzer.analyze(repo_path)

        if self.verbose:
            print(f"  Analyzed {len(analysis.files)} files ({analysis.total_tokens:,} tokens)")

        # Generate documentation
        generator = DocGenerator(self._llm_provider)
        config = GenerationConfig(
            guidelines=self.guidelines,
            output_dir=self.output_dir,
        )

        generated = await generator.generate(analysis, config)

        if self.verbose:
            print(f"  Generated {len(generated.files)} doc files")

        return generated.files

    async def _calculate_doc_metrics(
        self,
        generated_docs: dict[str, str],
        expected_docs: dict[str, str],
        repo_path: Path,
        expected_items: set[str],
    ) -> DocumentationMetrics:
        """Calculate documentation metrics.

        Args:
            generated_docs: Generated documentation
            expected_docs: Expected documentation
            repo_path: Path to source repository
            expected_items: Expected items to be documented

        Returns:
            Documentation metrics
        """
        metrics = DocumentationMetrics()
        metrics.files_evaluated = len(generated_docs)

        if not generated_docs:
            return metrics

        # Calculate structure score (average across files)
        structure_scores = [
            calculate_structure_score(content) for content in generated_docs.values()
        ]
        metrics.structure_score = (
            sum(structure_scores) / len(structure_scores) if structure_scores else 0.0
        )

        # Calculate readability (average across files)
        readability_scores = [calculate_readability(content) for content in generated_docs.values()]
        metrics.readability_score = (
            sum(readability_scores) / len(readability_scores) if readability_scores else 0.0
        )

        # Calculate coverage
        documented_items = self._extract_documented_items(generated_docs)
        metrics.coverage_score = calculate_coverage(documented_items, expected_items)

        # Run LLM judge if we have both generated and expected docs
        if generated_docs and expected_docs and self._judge:
            combined_generated = "\n\n".join(generated_docs.values())
            combined_expected = "\n\n".join(expected_docs.values())
            code_context = self._load_code_context(repo_path)

            metrics.judge_scores = await self._judge.evaluate(
                generated=combined_generated,
                expected=combined_expected,
                code_context=code_context,
            )

        return metrics

    async def _evaluate_pr_detection(self, repo_name: str) -> PRDetectionMetrics | None:
        """Evaluate PR detection accuracy for a repository.

        Args:
            repo_name: Repository name

        Returns:
            PR detection metrics or None if no scenarios exist
        """
        if not self.dataset.pr_scenarios_dir:
            return None

        labels_path = self.dataset.pr_scenarios_dir / "labels.json"
        if not labels_path.exists():
            return None

        # Load ground truth labels
        with open(labels_path) as f:
            labels: dict[str, Any] = json.load(f)

        scenarios = labels.get(repo_name, {})
        if not scenarios:
            return None

        metrics = PRDetectionMetrics()

        for scenario_id, expected_relevant in scenarios.items():
            start_time = time.time()

            # Load scenario diff and run classification
            # Placeholder: would call actual PR analysis
            predicted_relevant = await self._classify_pr_relevance(repo_name, scenario_id)

            elapsed_ms = (time.time() - start_time) * 1000
            metrics.total_latency_ms += elapsed_ms
            metrics.predictions += 1

            # Update confusion matrix
            if expected_relevant and predicted_relevant:
                metrics.true_positives += 1
            elif not expected_relevant and not predicted_relevant:
                metrics.true_negatives += 1
            elif predicted_relevant and not expected_relevant:
                metrics.false_positives += 1
            else:
                metrics.false_negatives += 1

        return metrics

    async def _classify_pr_relevance(self, repo_name: str, scenario_id: str) -> bool:
        """Classify whether a PR requires documentation updates.

        Placeholder - would call actual PR analysis service.

        Args:
            repo_name: Repository name
            scenario_id: Scenario identifier

        Returns:
            True if PR is relevant for documentation
        """
        # Placeholder: In real implementation, would analyze PR diff
        logfire.info(
            "Classifying PR relevance",
            repo=repo_name,
            scenario=scenario_id,
        )
        return True

    def _load_docs(self, path: Path) -> dict[str, str]:
        """Load documentation files from path.

        Args:
            path: Path to documentation directory

        Returns:
            Dict mapping relative paths to content
        """
        if not path.exists():
            return {}

        docs: dict[str, str] = {}
        for file_path in path.rglob("*.md"):
            rel_path = file_path.relative_to(path)
            docs[str(rel_path)] = file_path.read_text()

        return docs

    def _load_annotations(self, path: Path | None) -> set[str]:
        """Load annotations (expected documented items).

        Args:
            path: Path to annotations.json

        Returns:
            Set of expected item names
        """
        if not path or not path.exists():
            return set()

        with open(path) as f:
            data = json.load(f)

        return set(data.get("expected_items", []))

    def _load_code_context(self, repo_path: Path, max_size: int = 100000) -> str:
        """Load code context from repository.

        Args:
            repo_path: Path to repository
            max_size: Maximum context size in characters

        Returns:
            Combined code context
        """
        context_parts: list[str] = []
        total_size = 0

        # Common source file extensions
        extensions = {".py", ".ts", ".js", ".go", ".rs", ".java"}

        for ext in extensions:
            for file_path in repo_path.rglob(f"*{ext}"):
                if total_size >= max_size:
                    break

                # Skip common non-source directories
                if any(
                    part in file_path.parts
                    for part in ["node_modules", ".git", "__pycache__", "venv"]
                ):
                    continue

                try:
                    content = file_path.read_text()
                    rel_path = file_path.relative_to(repo_path)
                    part = f"--- {rel_path} ---\n{content}\n"

                    if total_size + len(part) <= max_size:
                        context_parts.append(part)
                        total_size += len(part)
                except (OSError, UnicodeDecodeError):
                    continue

        return "\n".join(context_parts)

    def _extract_documented_items(self, docs: dict[str, str]) -> set[str]:
        """Extract documented item names from documentation.

        Looks for function names, class names, etc. in documentation.

        Args:
            docs: Documentation content

        Returns:
            Set of documented item names
        """
        items: set[str] = set()

        for content in docs.values():
            # Find function/method references
            items.update(re.findall(r"`(\w+)\(`", content))
            items.update(re.findall(r"### (\w+)", content))

            # Find class references
            items.update(re.findall(r"class `(\w+)`", content))

        return items

    def _print_result(self, result: EvaluationResult) -> None:
        """Print evaluation result to console."""
        print(f"\n{'=' * 50}")
        print(f"Repository: {result.repo_name}")
        print(f"{'=' * 50}")

        dm = result.doc_metrics
        print(f"Coverage:    {dm.coverage_score:.1%}")
        print(f"Structure:   {dm.structure_score:.1%}")
        print(f"Readability: {dm.readability_score:.1f} grade level")

        if dm.judge_scores:
            js = dm.judge_scores
            print("\nLLM Judge Scores (1-5):")
            print(f"  Accuracy:      {js.accuracy:.1f}")
            print(f"  Completeness:  {js.completeness:.1f}")
            print(f"  Clarity:       {js.clarity:.1f}")
            print(f"  No hallucin.:  {js.hallucination_free:.1f}")
            if js.issues:
                print(f"  Issues: {len(js.issues)}")

        if result.pr_metrics:
            pm = result.pr_metrics
            print("\nPR Detection:")
            print(f"  Precision: {pm.precision:.1%}")
            print(f"  Recall:    {pm.recall:.1%}")
            print(f"  F1 Score:  {pm.f1_score:.1%}")
            print(f"  Latency:   {pm.average_latency_ms:.0f}ms avg")


async def run_evaluation(
    dataset_path: Path | str,
    repos: list[str] | None = None,
    quick: bool = False,
    verbose: bool = False,
) -> list[EvaluationResult]:
    """Run evaluation on a dataset.

    Args:
        dataset_path: Path to evaluation dataset
        repos: Specific repos to evaluate (None = all)
        quick: Quick evaluation mode
        verbose: Verbose output

    Returns:
        List of evaluation results
    """
    dataset = EvalDataset.from_path(Path(dataset_path))
    runner = EvaluationRunner(dataset, quick=quick, verbose=verbose)
    return await runner.run(repos=repos)


def compare_to_baseline(
    current: list[EvaluationResult],
    baseline: list[EvaluationResult],
) -> dict[str, Any]:
    """Compare current results to baseline.

    Args:
        current: Current evaluation results
        baseline: Baseline evaluation results

    Returns:
        Comparison dictionary with deltas
    """
    current_agg = aggregate_metrics(current)
    baseline_agg = aggregate_metrics(baseline)

    def calc_delta(current_val: float, baseline_val: float) -> dict[str, float]:
        delta = current_val - baseline_val
        pct_change = (delta / baseline_val * 100) if baseline_val != 0 else 0
        return {
            "current": current_val,
            "baseline": baseline_val,
            "delta": delta,
            "pct_change": pct_change,
        }

    comparison: dict[str, Any] = {"improved": [], "regressed": [], "unchanged": []}

    # Compare documentation metrics
    if "documentation" in current_agg and "documentation" in baseline_agg:
        for metric in ["coverage", "structure", "accuracy"]:
            if metric in current_agg["documentation"] and metric in baseline_agg["documentation"]:
                curr = current_agg["documentation"][metric]["mean"]
                base = baseline_agg["documentation"][metric]["mean"]
                delta_info = calc_delta(curr, base)
                comparison[f"doc_{metric}"] = delta_info

                if delta_info["delta"] > 0.01:
                    comparison["improved"].append(f"doc_{metric}")
                elif delta_info["delta"] < -0.01:
                    comparison["regressed"].append(f"doc_{metric}")
                else:
                    comparison["unchanged"].append(f"doc_{metric}")

    # Compare PR detection metrics
    if "pr_detection" in current_agg and "pr_detection" in baseline_agg:
        for metric in ["f1_score", "precision", "recall"]:
            if metric in current_agg["pr_detection"] and metric in baseline_agg["pr_detection"]:
                curr = current_agg["pr_detection"][metric]["mean"]
                base = baseline_agg["pr_detection"][metric]["mean"]
                delta_info = calc_delta(curr, base)
                comparison[f"pr_{metric}"] = delta_info

                if delta_info["delta"] > 0.01:
                    comparison["improved"].append(f"pr_{metric}")
                elif delta_info["delta"] < -0.01:
                    comparison["regressed"].append(f"pr_{metric}")
                else:
                    comparison["unchanged"].append(f"pr_{metric}")

    return comparison
