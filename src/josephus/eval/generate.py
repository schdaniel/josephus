"""Batch documentation generation for evaluation."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from josephus.analyzer import LocalRepoAnalyzer, format_for_llm
from josephus.eval.download import get_project_root, get_repos_dir, load_repos_config
from josephus.generator import DocGenerator, GenerationConfig
from josephus.llm import LLMProvider


def get_output_dir(output_dir: Path | None = None) -> Path:
    """Get the output directory for generated docs."""
    if output_dir is None:
        output_dir = get_project_root() / "eval" / "generated"

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def generate_docs_for_repo(
    repo_path: Path,
    repo_name: str,
    output_dir: Path,
    llm_provider: LLMProvider,
    config: GenerationConfig | None = None,
) -> dict:
    """Generate documentation for a single repository.

    Returns metadata about the generation.
    """
    print(f"  Analyzing {repo_name}...")

    # Analyze the repository
    analyzer = LocalRepoAnalyzer(max_tokens=80000)
    analysis = analyzer.analyze(repo_path, name=repo_name)

    print(f"    Files: {len(analysis.files)}, Tokens: {analysis.total_tokens}")

    # Format for LLM
    context = format_for_llm(analysis)

    # Generate documentation
    print(f"  Generating docs for {repo_name}...")
    generator = DocGenerator(llm_provider=llm_provider, config=config)
    result = generator.generate(context)

    # Save output
    repo_output_dir = output_dir / repo_name
    repo_output_dir.mkdir(parents=True, exist_ok=True)

    # Save the generated docs as JSON
    output_file = repo_output_dir / "docs.json"
    output_data = {
        "generated_at": datetime.now(UTC).isoformat(),
        "repo_name": repo_name,
        "files_analyzed": len(analysis.files),
        "tokens_analyzed": analysis.total_tokens,
        "docs": result.model_dump(),
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    # Also save as markdown for easy viewing
    md_file = repo_output_dir / "index.md"
    md_content = _format_docs_as_markdown(result)
    md_file.write_text(md_content)

    print(f"  {repo_name}: docs saved to {repo_output_dir}")

    return {
        "repo_name": repo_name,
        "files_analyzed": len(analysis.files),
        "tokens_analyzed": analysis.total_tokens,
        "output_dir": str(repo_output_dir),
        "success": True,
    }


def _format_docs_as_markdown(result) -> str:
    """Format documentation result as markdown."""
    lines = []

    # Main overview
    if hasattr(result, "overview") and result.overview:
        lines.append("# Overview\n")
        lines.append(result.overview)
        lines.append("\n")

    # Sections
    if hasattr(result, "sections") and result.sections:
        for section in result.sections:
            lines.append(f"## {section.title}\n")
            lines.append(section.content)
            lines.append("\n")

    # API reference
    if hasattr(result, "api_reference") and result.api_reference:
        lines.append("## API Reference\n")
        lines.append(result.api_reference)
        lines.append("\n")

    return "\n".join(lines)


def generate_all(
    repos_dir: Path | None = None,
    output_dir: Path | None = None,
    config_path: Path | None = None,
    repos: list[str] | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, dict]:
    """Generate documentation for all evaluation repositories.

    Args:
        repos_dir: Directory containing cloned repos
        output_dir: Directory for generated docs
        config_path: Path to repos.yaml
        repos: Specific repos to generate (None = all)
        model: LLM model to use

    Returns:
        Dict mapping repo name to generation metadata
    """
    repos_config = load_repos_config(config_path)
    repos_dir = get_repos_dir(repos_dir)
    output_dir = get_output_dir(output_dir)

    print(f"Generating docs to: {output_dir}")
    print(f"Using model: {model}")

    if repos:
        repos_config = {k: v for k, v in repos_config.items() if k in repos}
        if not repos_config:
            print(f"No matching repos found for: {repos}")
            return {}

    # Check which repos exist
    available_repos = {}
    for name in repos_config:
        repo_path = repos_dir / name
        if repo_path.exists():
            available_repos[name] = repo_path
        else:
            print(f"  {name}: not downloaded, skipping")

    if not available_repos:
        print("No repos available. Run 'download' command first.")
        return {}

    # Initialize LLM provider
    llm_provider = LLMProvider(model=model)

    # Generation config
    gen_config = GenerationConfig()

    results = {}
    try:
        for name, repo_path in available_repos.items():
            try:
                results[name] = generate_docs_for_repo(
                    repo_path=repo_path,
                    repo_name=name,
                    output_dir=output_dir,
                    llm_provider=llm_provider,
                    config=gen_config,
                )
            except Exception as e:
                print(f"  ERROR: Failed to generate docs for {name}: {e}")
                results[name] = {
                    "repo_name": name,
                    "success": False,
                    "error": str(e),
                }
    finally:
        llm_provider.close()

    # Summary
    successful = sum(1 for r in results.values() if r.get("success"))
    failed = sum(1 for r in results.values() if not r.get("success"))
    print(f"\nSummary: {successful} succeeded, {failed} failed")

    return results


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate documentation for evaluation repositories",
        prog="python -m josephus.eval.generate",
    )

    parser.add_argument("--repos", "-r", nargs="+", help="Specific repos to generate")
    parser.add_argument(
        "--model",
        "-m",
        default="claude-sonnet-4-20250514",
        help="LLM model to use",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        help="Output directory for generated docs",
    )

    args = parser.parse_args()

    generate_all(
        repos=args.repos,
        model=args.model,
        output_dir=args.output_dir,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
