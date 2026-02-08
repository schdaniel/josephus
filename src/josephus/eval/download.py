"""Download and manage evaluation repositories."""

import re
import shutil
import subprocess  # nosec B404 - subprocess needed for git operations
import sys
from pathlib import Path

import yaml

# Pattern for valid git URLs (https or git@)
_VALID_GIT_URL_PATTERN = re.compile(r"^(https://[\w.-]+/[\w./-]+\.git|git@[\w.-]+:[\w./-]+\.git)$")


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


def get_repos_dir(repos_dir: Path | None = None) -> Path:
    """Get the eval repos directory."""
    if repos_dir is None:
        repos_dir = get_project_root() / "eval" / "repos"

    repos_dir.mkdir(parents=True, exist_ok=True)
    return repos_dir


def _validate_git_url(url: str) -> bool:
    """Validate that a URL is a safe git URL.

    Only allows https:// and git@ URLs to prevent command injection.
    """
    return bool(_VALID_GIT_URL_PATTERN.match(url))


def download_repo(
    name: str,
    url: str,
    repos_dir: Path,
    force: bool = False,
    depth: int = 1,
) -> bool:
    """Download a single repository."""
    # Validate URL to prevent command injection
    if not _validate_git_url(url):
        print(f"  ERROR: Invalid git URL for {name}: {url}")
        return False

    repo_path = repos_dir / name

    if repo_path.exists():
        if force:
            print(f"  Removing existing {name}...")
            shutil.rmtree(repo_path)
        else:
            print(f"  {name}: already exists (use --force to re-download)")
            return False

    print(f"  Cloning {name} from {url}...")
    cmd = ["git", "clone", "--depth", str(depth), url, str(repo_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603

    if result.returncode != 0:
        print(f"  ERROR: Failed to clone {name}: {result.stderr}")
        return False

    print(f"  {name}: downloaded successfully")
    return True


def download_all(
    repos_dir: Path | None = None,
    config_path: Path | None = None,
    force: bool = False,
    repos: list[str] | None = None,
) -> dict[str, bool]:
    """Download all evaluation repositories."""
    repos_config = load_repos_config(config_path)
    repos_dir = get_repos_dir(repos_dir)

    print(f"Downloading repos to: {repos_dir}")

    if repos:
        repos_config = {k: v for k, v in repos_config.items() if k in repos}
        if not repos_config:
            print(f"No matching repos found for: {repos}")
            return {}

    results = {}
    for name, config in repos_config.items():
        results[name] = download_repo(
            name=name,
            url=config["url"],
            repos_dir=repos_dir,
            force=force,
        )

    downloaded = sum(1 for v in results.values() if v)
    skipped = sum(1 for v in results.values() if not v)
    print(f"\nSummary: {downloaded} downloaded, {skipped} skipped")
    return results


def list_repos(config_path: Path | None = None) -> None:
    """List available evaluation repositories."""
    repos_config = load_repos_config(config_path)
    repos_dir = get_repos_dir()

    print("Evaluation Repositories:")
    print("-" * 70)
    print(f"{'Name':<15} {'Language':<12} {'Size':<8} {'Status':<20}")
    print("-" * 70)

    for name, config in repos_config.items():
        repo_path = repos_dir / name
        status = "✓ downloaded" if repo_path.exists() else "✗ not downloaded"
        print(f"{name:<15} {config['language']:<12} {config['size']:<8} {status}")

    print("-" * 70)


def update_repos(
    repos_dir: Path | None = None,
    config_path: Path | None = None,
    repos: list[str] | None = None,
) -> dict[str, bool]:
    """Update (git pull) existing repositories."""
    repos_config = load_repos_config(config_path)
    repos_dir = get_repos_dir(repos_dir)

    if repos:
        repos_config = {k: v for k, v in repos_config.items() if k in repos}

    results = {}
    for name in repos_config:
        repo_path = repos_dir / name

        if not repo_path.exists():
            print(f"  {name}: not downloaded, skipping")
            results[name] = False
            continue

        print(f"  Updating {name}...")
        cmd = ["git", "-C", str(repo_path), "pull", "--ff-only"]
        result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603

        if result.returncode != 0:
            print(f"  ERROR: Failed to update {name}")
            results[name] = False
        else:
            print(f"  {name}: updated")
            results[name] = True

    return results


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and manage evaluation repositories",
        prog="python -m josephus.eval.download",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Download command
    dl = subparsers.add_parser("download", help="Download repositories")
    dl.add_argument("--force", "-f", action="store_true", help="Force re-download")
    dl.add_argument("--repos", "-r", nargs="+", help="Specific repos")

    # List command
    subparsers.add_parser("list", help="List available repositories")

    # Update command
    up = subparsers.add_parser("update", help="Update existing repositories")
    up.add_argument("--repos", "-r", nargs="+", help="Specific repos")

    args = parser.parse_args()

    if args.command == "download":
        download_all(force=args.force, repos=args.repos)
    elif args.command == "list":
        list_repos()
    elif args.command == "update":
        update_repos(repos=args.repos)
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
