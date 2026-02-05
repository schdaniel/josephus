"""Evaluate generated documentation quality."""

import json
import sys
from pathlib import Path

from josephus.eval.download import load_repos_config
from josephus.eval.generate import get_output_dir
from josephus.eval.metrics import (
    calculate_readability,
    calculate_structure_score,
)


def evaluate_docs(docs_dir: Path) -> dict:
    """Evaluate documentation quality for a single repo.

    Returns evaluation metrics.
    """
    # Find the docs
    docs_path = docs_dir / "docs" / "index.md"
    if not docs_path.exists():
        return {"error": "No docs found"}

    # Read the docs content
    content = docs_path.read_text()

    # Calculate metrics
    fk_grade = calculate_readability(content)
    structure = calculate_structure_score(content)

    # Calculate Flesch Reading Ease (related to grade level)
    # FRE = 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)
    # Approximate from FK grade: FRE ≈ 100 - (FK_grade * 5)
    fk_ease = max(0, min(100, 100 - (fk_grade * 5)))

    # Count sections and code blocks
    lines = content.split("\n")
    heading_count = sum(1 for line in lines if line.startswith("#"))
    code_block_count = content.count("```")
    word_count = len(content.split())
    char_count = len(content)

    return {
        "readability": {
            "flesch_kincaid_grade": fk_grade,
            "flesch_reading_ease": fk_ease,
        },
        "structure": {
            "score": structure,
            "heading_count": heading_count,
            "code_block_count": code_block_count // 2,  # Opening and closing
        },
        "size": {
            "word_count": word_count,
            "char_count": char_count,
        },
    }


def evaluate_all(
    output_dir: Path | None = None,
    config_path: Path | None = None,
    repos: list[str] | None = None,
) -> dict[str, dict]:
    """Evaluate all generated documentation.

    Returns dict mapping repo name to evaluation results.
    """
    repos_config = load_repos_config(config_path)
    output_dir = get_output_dir(output_dir)

    if repos:
        repos_config = {k: v for k, v in repos_config.items() if k in repos}

    results = {}
    for name in repos_config:
        docs_dir = output_dir / name
        if not docs_dir.exists():
            print(f"  {name}: no generated docs found")
            results[name] = {"error": "No generated docs"}
            continue

        print(f"  Evaluating {name}...")
        results[name] = evaluate_docs(docs_dir)

        # Load metadata if available
        metadata_file = docs_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                results[name]["generation_metadata"] = json.load(f)

    return results


def print_report(results: dict[str, dict]) -> None:
    """Print a formatted evaluation report."""
    print("\n" + "=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)

    for repo_name, metrics in results.items():
        print(f"\n{repo_name.upper()}")
        print("-" * 40)

        if "error" in metrics:
            print(f"  Error: {metrics['error']}")
            continue

        # Readability
        readability = metrics.get("readability", {})
        fk_grade = readability.get("flesch_kincaid_grade", "N/A")
        fk_ease = readability.get("flesch_reading_ease", "N/A")
        print("  Readability:")
        print(
            f"    Flesch-Kincaid Grade: {fk_grade:.1f}"
            if isinstance(fk_grade, (int, float))
            else f"    Flesch-Kincaid Grade: {fk_grade}"
        )
        print(
            f"    Flesch Reading Ease: {fk_ease:.1f}"
            if isinstance(fk_ease, (int, float))
            else f"    Flesch Reading Ease: {fk_ease}"
        )

        # Structure
        structure = metrics.get("structure", {})
        print("  Structure:")
        print(
            f"    Score: {structure.get('score', 'N/A'):.2f}"
            if isinstance(structure.get("score"), (int, float))
            else f"    Score: {structure.get('score', 'N/A')}"
        )
        print(f"    Headings: {structure.get('heading_count', 'N/A')}")
        print(f"    Code blocks: {structure.get('code_block_count', 'N/A')}")

        # Size
        size = metrics.get("size", {})
        print("  Size:")
        print(
            f"    Words: {size.get('word_count', 'N/A'):,}"
            if isinstance(size.get("word_count"), int)
            else f"    Words: {size.get('word_count', 'N/A')}"
        )
        print(
            f"    Characters: {size.get('char_count', 'N/A'):,}"
            if isinstance(size.get("char_count"), int)
            else f"    Characters: {size.get('char_count', 'N/A')}"
        )

        # Generation info
        gen_meta = metrics.get("generation_metadata", {})
        if gen_meta:
            print("  Generation:")
            print(f"    Files analyzed: {gen_meta.get('files_analyzed', 'N/A')}")
            print(
                f"    Tokens analyzed: {gen_meta.get('tokens_analyzed', 'N/A'):,}"
                if isinstance(gen_meta.get("tokens_analyzed"), int)
                else f"    Tokens analyzed: {gen_meta.get('tokens_analyzed', 'N/A')}"
            )
            print(
                f"    LLM input tokens: {gen_meta.get('llm_input_tokens', 'N/A'):,}"
                if isinstance(gen_meta.get("llm_input_tokens"), int)
                else f"    LLM input tokens: {gen_meta.get('llm_input_tokens', 'N/A')}"
            )
            print(
                f"    LLM output tokens: {gen_meta.get('llm_output_tokens', 'N/A'):,}"
                if isinstance(gen_meta.get("llm_output_tokens"), int)
                else f"    LLM output tokens: {gen_meta.get('llm_output_tokens', 'N/A')}"
            )

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    valid_results = {k: v for k, v in results.items() if "error" not in v}
    if valid_results:
        avg_fk_grade = sum(
            r["readability"]["flesch_kincaid_grade"] for r in valid_results.values()
        ) / len(valid_results)
        avg_fk_ease = sum(
            r["readability"]["flesch_reading_ease"] for r in valid_results.values()
        ) / len(valid_results)
        avg_structure = sum(r["structure"]["score"] for r in valid_results.values()) / len(
            valid_results
        )
        total_words = sum(r["size"]["word_count"] for r in valid_results.values())

        print(f"\n  Average Flesch-Kincaid Grade: {avg_fk_grade:.1f}")
        print(f"  Average Reading Ease: {avg_fk_ease:.1f}")
        print(f"  Average Structure Score: {avg_structure:.2f}")
        print(f"  Total Words Generated: {total_words:,}")
        print(f"  Repos Evaluated: {len(valid_results)}")

        # Interpretation
        print("\n  Interpretation:")
        if avg_fk_ease >= 60:
            print("    ✓ Good readability (accessible to general audience)")
        elif avg_fk_ease >= 30:
            print("    ~ Moderate readability (appropriate for technical docs)")
        else:
            print("    ✗ Low readability (may need simplification)")

        if avg_structure >= 0.7:
            print("    ✓ Good document structure")
        elif avg_structure >= 0.4:
            print("    ~ Moderate document structure")
        else:
            print("    ✗ Document structure needs improvement")


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate generated documentation quality",
        prog="python -m josephus.eval.evaluate",
    )

    parser.add_argument("--repos", "-r", nargs="+", help="Specific repos to evaluate")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        help="Directory containing generated docs",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    print("Evaluating generated documentation...")
    results = evaluate_all(
        output_dir=args.output_dir,
        repos=args.repos,
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
