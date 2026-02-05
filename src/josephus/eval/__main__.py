"""CLI entry point for evaluation.

Usage:
    python -m josephus.eval --dataset eval/repos --quick
    python -m josephus.eval --dataset eval/repos --compare-baseline
    python -m josephus.eval.check --coverage-min 0.85 --accuracy-min 0.80
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from josephus.eval.runner import (
    EvalDataset,
    EvaluationRunner,
    aggregate_metrics,
    compare_to_baseline,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run evaluation on documentation generation quality",
        prog="python -m josephus.eval",
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("eval"),
        help="Path to evaluation dataset directory (default: eval/)",
    )

    parser.add_argument(
        "--repos",
        type=str,
        nargs="+",
        help="Specific repositories to evaluate (default: all)",
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick evaluation (fewer samples)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output results to JSON file",
    )

    parser.add_argument(
        "--compare-baseline",
        type=Path,
        metavar="BASELINE_FILE",
        help="Compare results to baseline JSON file",
    )

    parser.add_argument(
        "--save-baseline",
        type=Path,
        metavar="BASELINE_FILE",
        help="Save results as baseline to JSON file",
    )

    parser.add_argument(
        "--no-pr-detection",
        action="store_true",
        help="Skip PR detection evaluation",
    )

    # Threshold checking arguments
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if metrics pass thresholds",
    )

    parser.add_argument(
        "--coverage-min",
        type=float,
        default=0.85,
        help="Minimum coverage score (0-1, default: 0.85)",
    )

    parser.add_argument(
        "--accuracy-min",
        type=float,
        default=0.80,
        help="Minimum accuracy score (0-1, default: 0.80)",
    )

    parser.add_argument(
        "--pr-f1-min",
        type=float,
        default=0.88,
        help="Minimum PR detection F1 score (0-1, default: 0.88)",
    )

    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Validate dataset path
    if not args.dataset.exists():
        print(f"Error: Dataset path not found: {args.dataset}", file=sys.stderr)
        return 1

    try:
        dataset = EvalDataset.from_path(args.dataset)
    except ValueError as e:
        print(f"Error: Invalid dataset: {e}", file=sys.stderr)
        return 1

    print(f"Evaluation dataset: {args.dataset}")
    print(f"Available repos: {', '.join(dataset.list_repos())}")

    if args.quick:
        print("Running in QUICK mode (limited samples)")

    # Run evaluation
    runner = EvaluationRunner(
        dataset=dataset,
        quick=args.quick,
        verbose=args.verbose,
    )

    results = await runner.run(
        repos=args.repos,
        include_pr_detection=not args.no_pr_detection,
    )

    if not results:
        print("No results generated", file=sys.stderr)
        return 1

    # Aggregate metrics
    aggregated = aggregate_metrics(results)

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Repos evaluated: {aggregated.get('repos_evaluated', 0)}")

    if "documentation" in aggregated:
        doc = aggregated["documentation"]
        print("\nDocumentation Metrics (mean ± stdev):")
        print(f"  Coverage:    {doc['coverage']['mean']:.1%} ± {doc['coverage']['stdev']:.1%}")
        print(f"  Structure:   {doc['structure']['mean']:.1%} ± {doc['structure']['stdev']:.1%}")
        print(
            f"  Readability: {doc['readability']['mean']:.1f} ± {doc['readability']['stdev']:.1f} grade level"
        )
        if doc["accuracy"]["mean"] > 0:
            print(
                f"  Accuracy:    {doc['accuracy']['mean']:.1f}/5 ± {doc['accuracy']['stdev']:.1f}"
            )

    if "pr_detection" in aggregated:
        pr = aggregated["pr_detection"]
        print("\nPR Detection Metrics (mean ± stdev):")
        print(f"  F1 Score:    {pr['f1_score']['mean']:.1%} ± {pr['f1_score']['stdev']:.1%}")
        print(f"  Precision:   {pr['precision']['mean']:.1%} ± {pr['precision']['stdev']:.1%}")
        print(f"  Recall:      {pr['recall']['mean']:.1%} ± {pr['recall']['stdev']:.1%}")

    # Compare to baseline if requested
    if args.compare_baseline:
        if not args.compare_baseline.exists():
            print(f"\nWarning: Baseline file not found: {args.compare_baseline}", file=sys.stderr)
        else:
            with open(args.compare_baseline) as f:
                baseline_data = json.load(f)

            # Reconstruct baseline results (simplified)
            baseline_results = baseline_data.get("results", [])
            if baseline_results:
                comparison = compare_to_baseline(
                    [r.to_dict() for r in results],  # type: ignore
                    baseline_results,
                )

                print("\n" + "-" * 40)
                print("BASELINE COMPARISON")
                print("-" * 40)

                if comparison.get("improved"):
                    print(f"  Improved: {', '.join(comparison['improved'])}")
                if comparison.get("regressed"):
                    print(f"  Regressed: {', '.join(comparison['regressed'])}")
                if comparison.get("unchanged"):
                    print(f"  Unchanged: {', '.join(comparison['unchanged'])}")

    # Save results if requested
    if args.output or args.save_baseline:
        output_data = {
            "aggregated": aggregated,
            "results": [r.to_dict() for r in results],
        }

        output_path = args.output or args.save_baseline
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {output_path}")

    # Check thresholds if requested
    if args.check:
        print("\n" + "-" * 40)
        print("THRESHOLD CHECK")
        print("-" * 40)

        all_passed = True
        all_failures: list[str] = []

        for result in results:
            passed, failures = result.passes_thresholds(
                coverage_min=args.coverage_min,
                accuracy_min=args.accuracy_min,
                pr_f1_min=args.pr_f1_min,
            )
            if not passed:
                all_passed = False
                all_failures.extend([f"{result.repo_name}: {f}" for f in failures])

        if all_passed:
            print("✓ All metrics pass thresholds")
            return 0
        else:
            print("✗ Some metrics below thresholds:")
            for failure in all_failures:
                print(f"  - {failure}")
            return 1

    return 0


def run() -> None:
    """Entry point for console script."""
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    run()
