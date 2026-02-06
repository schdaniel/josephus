"""Crawl documentation from GitHub repositories for evaluation ground truth."""

import base64
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent


def load_repos_config(config_path: Path | None = None) -> dict:
    """Load repositories configuration from YAML file."""
    if config_path is None:
        config_path = get_project_root() / "eval" / "repos.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Repos config not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config.get("repos", {})


def get_ground_truth_dir(repo_name: str) -> Path:
    """Get the ground truth directory for a repository."""
    ground_truth_dir = get_project_root() / "eval" / "ground_truth" / repo_name / "crawled_docs"
    ground_truth_dir.mkdir(parents=True, exist_ok=True)
    return ground_truth_dir


def parse_repo_url(url: str) -> tuple[str, str]:
    """Parse a GitHub URL to get owner and repo name."""
    # Handle both HTTPS and git URLs
    if url.startswith("git@"):
        # git@github.com:owner/repo.git
        path = url.split(":")[1]
    else:
        # https://github.com/owner/repo.git
        parsed = urlparse(url)
        path = parsed.path.lstrip("/")

    # Remove .git suffix
    path = path.removesuffix(".git")
    parts = path.split("/")
    return parts[0], parts[1]


def fetch_github_tree(owner: str, repo: str, path: str = "") -> list[dict]:
    """Fetch the file tree from a GitHub repository using gh CLI."""
    api_path = f"repos/{owner}/{repo}/contents/{path}".rstrip("/")

    result = subprocess.run(
        ["gh", "api", api_path, "-q", "."],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"    Error fetching tree: {result.stderr}")
        return []

    import json

    try:
        data = json.loads(result.stdout)
        # API returns a single object for files, list for directories
        if isinstance(data, dict):
            return [data]
        return data
    except json.JSONDecodeError:
        return []


def fetch_github_file(owner: str, repo: str, path: str) -> str | None:
    """Fetch file content from GitHub using gh CLI."""
    api_path = f"repos/{owner}/{repo}/contents/{path}"

    result = subprocess.run(
        ["gh", "api", api_path, "-q", ".content"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    # Content is base64 encoded
    try:
        content = base64.b64decode(result.stdout.strip()).decode("utf-8")
        return content
    except Exception:
        return None


def is_doc_file(name: str, docs_format: str = "markdown") -> bool:
    """Check if a file is a documentation file."""
    name_lower = name.lower()

    if docs_format == "asciidoc":
        return name_lower.endswith((".adoc", ".asciidoc", ".asc"))
    elif docs_format == "lektor":
        # Lektor uses contents.lr files for content
        return name_lower == "contents.lr"

    # Markdown and related formats
    return name_lower.endswith((".md", ".mdx", ".markdown"))


def crawl_github_docs(
    owner: str,
    repo: str,
    docs_path: str,
    output_dir: Path,
    docs_format: str = "markdown",
    max_files: int = 200,
    exclude_dirs: list[str] | None = None,
) -> dict[str, str]:
    """Crawl documentation from a GitHub repository.

    Args:
        owner: GitHub repository owner
        repo: GitHub repository name
        docs_path: Path to documentation directory in the repo
        output_dir: Directory to save documentation files
        docs_format: Format of documentation (markdown, asciidoc)
        max_files: Maximum number of files to fetch
        exclude_dirs: List of directory names to exclude

    Returns:
        Dictionary mapping file paths to saved file paths
    """
    results: dict[str, str] = {}
    files_fetched = 0
    exclude_set = set(exclude_dirs or [])

    def crawl_directory(path: str, depth: int = 0) -> None:
        nonlocal files_fetched

        if files_fetched >= max_files:
            return

        if depth > 10:  # Prevent infinite recursion
            return

        items = fetch_github_tree(owner, repo, path)

        for item in items:
            if files_fetched >= max_files:
                break

            item_name = item.get("name", "")
            item_path = item.get("path", "")
            item_type = item.get("type", "")

            if item_type == "dir":
                # Skip hidden directories and common non-doc directories
                if item_name.startswith(".") or item_name in (
                    "node_modules",
                    "__pycache__",
                    "vendor",
                    "dist",
                    "build",
                    "assets",
                    "imgs",
                    "images",
                    "static",
                ):
                    continue
                # Skip user-specified exclude directories
                if item_name in exclude_set:
                    continue
                crawl_directory(item_path, depth + 1)

            elif item_type == "file" and is_doc_file(item_name, docs_format):
                # Fetch the file content
                content = fetch_github_file(owner, repo, item_path)

                if content:
                    # Create relative path from docs_path
                    rel_path = item_path
                    if docs_path and docs_path != ".":
                        rel_path = item_path[len(docs_path) :].lstrip("/")

                    # Save file preserving directory structure
                    output_path = output_dir / rel_path
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(content)

                    results[item_path] = str(output_path)
                    files_fetched += 1
                    print(f"    [{files_fetched}/{max_files}] {rel_path}")

    print(f"  Fetching docs from: {owner}/{repo}/{docs_path}")
    crawl_directory(docs_path)
    print(f"  Crawl complete: {len(results)} files saved")

    return results


def crawl_repo_docs(
    repo_name: str,
    config: dict,
    force: bool = False,
    max_files: int = 200,
) -> bool:
    """Crawl documentation for a single repository from GitHub."""
    # Determine the source repository for docs
    if "docs_repo" in config:
        owner, repo = config["docs_repo"].split("/")
    else:
        owner, repo = parse_repo_url(config["url"])

    docs_path = config.get("docs_path", "docs")
    docs_format = config.get("docs_format", "markdown")
    exclude_dirs = config.get("exclude_dirs", [])

    output_dir = get_ground_truth_dir(repo_name)

    # Check if already crawled
    if not force and list(output_dir.glob("**/*.md")) + list(output_dir.glob("**/*.adoc")):
        print(f"  {repo_name}: Already crawled (use --force to re-crawl)")
        return False

    # Clear existing files if force
    if force:
        import shutil

        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nCrawling documentation for: {repo_name}")
    if exclude_dirs:
        print(f"  Excluding directories: {', '.join(exclude_dirs)}")
    results = crawl_github_docs(
        owner=owner,
        repo=repo,
        docs_path=docs_path,
        output_dir=output_dir,
        docs_format=docs_format,
        max_files=max_files,
        exclude_dirs=exclude_dirs,
    )
    return len(results) > 0


def crawl_all(
    repos: list[str] | None = None,
    force: bool = False,
    max_files: int = 200,
) -> dict[str, bool]:
    """Crawl documentation for all configured repositories."""
    repos_config = load_repos_config()

    if repos:
        repos_config = {k: v for k, v in repos_config.items() if k in repos}
        if not repos_config:
            print(f"No matching repos found for: {repos}")
            return {}

    results = {}
    for name, config in repos_config.items():
        results[name] = crawl_repo_docs(name, config, force=force, max_files=max_files)

    crawled = sum(1 for v in results.values() if v)
    skipped = sum(1 for v in results.values() if not v)
    print(f"\nSummary: {crawled} crawled, {skipped} skipped")
    return results


def list_repos(config_path: Path | None = None) -> None:
    """List available evaluation repositories with their doc sources."""
    repos_config = load_repos_config(config_path)
    ground_truth_root = get_project_root() / "eval" / "ground_truth"

    print("Evaluation Repositories:")
    print("-" * 90)
    print(f"{'Name':<12} {'Language':<10} {'Size':<8} {'Docs Source':<40} {'Status':<15}")
    print("-" * 90)

    for name, config in repos_config.items():
        # Determine docs source
        if "docs_repo" in config:
            docs_source = config["docs_repo"]
        else:
            owner, repo = parse_repo_url(config["url"])
            docs_source = f"{owner}/{repo}"

        docs_path = config.get("docs_path", "docs")
        docs_source = f"{docs_source}/{docs_path}"

        # Check status
        crawled_dir = ground_truth_root / name / "crawled_docs"
        if crawled_dir.exists():
            file_count = (
                len(list(crawled_dir.glob("**/*.md")))
                + len(list(crawled_dir.glob("**/*.adoc")))
                + len(list(crawled_dir.glob("**/*.lr")))
            )
            status = f"crawled ({file_count} files)"
        else:
            status = "not crawled"

        print(f"{name:<12} {config['language']:<10} {config['size']:<8} {docs_source:<40} {status}")

    print("-" * 90)


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Crawl documentation from GitHub repositories for evaluation",
        prog="python -m josephus.eval.crawl",
    )

    parser.add_argument("--repos", "-r", nargs="+", help="Specific repos to crawl")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-crawl")
    parser.add_argument(
        "--max-files", "-m", type=int, default=200, help="Max files per repo (default: 200)"
    )
    parser.add_argument("--list", "-l", action="store_true", help="List repos with doc sources")

    args = parser.parse_args()

    if args.list:
        list_repos()
        return 0

    crawl_all(repos=args.repos, force=args.force, max_files=args.max_files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
