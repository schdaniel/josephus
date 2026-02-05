"""Batch documentation generation for evaluation."""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from josephus.analyzer import LocalRepoAnalyzer
from josephus.eval.download import get_project_root, get_repos_dir, load_repos_config
from josephus.generator import DocGenerator, GeneratedDocs, GenerationConfig
from josephus.llm import ClaudeProvider, LLMProvider


def get_output_dir(output_dir: Path | None = None) -> Path:
    """Get the output directory for generated docs."""
    if output_dir is None:
        output_dir = get_project_root() / "eval" / "generated"

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def generate_docs_for_repo(
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

    # Generate documentation
    print(f"  Generating docs for {repo_name}...")
    generator = DocGenerator(llm_provider)
    result = await generator.generate(analysis, config)

    # Save output
    repo_output_dir = output_dir / repo_name
    repo_output_dir.mkdir(parents=True, exist_ok=True)

    # Save each generated doc file
    for file_path, content in result.files.items():
        output_file = repo_output_dir / file_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content)

    # Save metadata
    metadata_file = repo_output_dir / "metadata.json"
    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "repo_name": repo_name,
        "files_analyzed": len(analysis.files),
        "tokens_analyzed": analysis.total_tokens,
        "docs_generated": result.total_files,
        "total_chars": result.total_chars,
        "llm_input_tokens": result.llm_response.input_tokens,
        "llm_output_tokens": result.llm_response.output_tokens,
    }

    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"  {repo_name}: {result.total_files} docs saved to {repo_output_dir}")

    return {
        "repo_name": repo_name,
        "files_analyzed": len(analysis.files),
        "tokens_analyzed": analysis.total_tokens,
        "docs_generated": result.total_files,
        "output_dir": str(repo_output_dir),
        "success": True,
    }


def _format_docs_as_markdown(result: GeneratedDocs) -> str:
    """Format documentation result as markdown."""
    lines = []

    for file_path, content in result.files.items():
        lines.append(f"# {file_path}\n")
        lines.append(content)
        lines.append("\n---\n")

    return "\n".join(lines)


async def generate_all_async(
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
    llm_provider = ClaudeProvider(model=model)

    # Generation config
    gen_config = GenerationConfig()

    results = {}
    try:
        for name, repo_path in available_repos.items():
            try:
                results[name] = await generate_docs_for_repo(
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
        await llm_provider.close()

    # Summary
    successful = sum(1 for r in results.values() if r.get("success"))
    failed = sum(1 for r in results.values() if not r.get("success"))
    print(f"\nSummary: {successful} succeeded, {failed} failed")

    return results


def generate_all(
    repos_dir: Path | None = None,
    output_dir: Path | None = None,
    config_path: Path | None = None,
    repos: list[str] | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, dict]:
    """Sync wrapper for generate_all_async."""
    return asyncio.run(
        generate_all_async(
            repos_dir=repos_dir,
            output_dir=output_dir,
            config_path=config_path,
            repos=repos,
            model=model,
        )
    )


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
