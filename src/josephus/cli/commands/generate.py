"""Generate command for Josephus CLI."""

from __future__ import annotations

import subprocess
import time

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from josephus.cli.api_client import get_api_client
from josephus.cli.config import get_api_key, load_project_config

app = typer.Typer()
console = Console()


def get_repo_from_git() -> tuple[str, str] | None:
    """Get owner/repo from git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()

        # Parse GitHub URL
        # https://github.com/owner/repo.git
        # git@github.com:owner/repo.git
        if "github.com" in url:
            # git@github.com:owner/repo.git or https://github.com/owner/repo.git
            path = url.split(":")[-1] if url.startswith("git@") else url.split("github.com/")[-1]
            path = path.rstrip(".git")
            parts = path.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
    except subprocess.CalledProcessError:
        pass

    return None


def get_current_branch() -> str | None:
    """Get the current git branch."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


@app.callback(invoke_without_command=True)
def generate(
    repo: str | None = typer.Option(
        None,
        "--repo",
        "-r",
        help="Repository in 'owner/repo' format. Auto-detected from git remote if not provided.",
    ),
    ref: str | None = typer.Option(
        None,
        "--ref",
        "-b",
        help="Git ref (branch/tag) to generate docs for. Defaults to current branch.",
    ),
    guidelines: str | None = typer.Option(
        None,
        "--guidelines",
        "-g",
        help="Documentation guidelines. Overrides project config.",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for generated docs.",
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        "-w",
        help="Wait for generation to complete (blocking).",
    ),
    format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: text, json, or quiet.",
    ),
    installation_id: int | None = typer.Option(
        None,
        "--installation-id",
        help="GitHub App installation ID. Required for API.",
    ),
    mode: str = typer.Option(
        "code",
        "--mode",
        "-m",
        help="Generation mode: 'code' for code-based docs, 'ui' for UI docs from deployment.",
    ),
    deployment_url: str | None = typer.Option(
        None,
        "--deployment-url",
        help="Deployment URL to crawl for UI docs (requires --mode ui).",
    ),
    auth_cookie: list[str] | None = typer.Option(
        None,
        "--auth-cookie",
        help="Auth cookie in 'name=value;domain=.example.com' format. Can be repeated.",
    ),
    auth_header: str | None = typer.Option(
        None,
        "--auth-header",
        help="Bearer token for auth header injection.",
    ),
) -> None:
    """Generate documentation for a repository.

    If no repository is specified, attempts to detect it from the git remote.

    Examples:

        josephus generate

        josephus generate --repo owner/repo

        josephus generate --repo owner/repo --ref feature-branch --wait

        josephus generate --mode ui --deployment-url https://app.example.com --auth-cookie "session=abc;domain=.example.com"
    """
    # Check authentication
    api_key = get_api_key()
    if not api_key:
        console.print(
            "[red]Error:[/red] Not authenticated. Run [blue]josephus auth login[/blue] first."
        )
        raise typer.Exit(1)

    # Detect repository
    if not repo:
        repo_info = get_repo_from_git()
        if repo_info:
            owner, repo_name = repo_info
            repo = f"{owner}/{repo_name}"
            if format != "quiet":
                console.print(f"[dim]Detected repository:[/dim] {repo}")
        else:
            console.print("[red]Error:[/red] Could not detect repository. Use --repo to specify.")
            raise typer.Exit(1)
    else:
        parts = repo.split("/")
        if len(parts) != 2:
            console.print("[red]Error:[/red] Invalid repository format. Use 'owner/repo' format.")
            raise typer.Exit(1)
        owner, repo_name = parts

    # Detect branch
    if not ref:
        ref = get_current_branch()
        if ref and format != "quiet":
            console.print(f"[dim]Using branch:[/dim] {ref}")

    # Load project config
    project_config = load_project_config()

    # Use guidelines from config if not provided
    if not guidelines:
        guidelines = project_config.guidelines

    # Use output dir from config if not provided
    if not output_dir:
        output_dir = project_config.output_directory

    # UI mode validation
    if mode == "ui":
        if not deployment_url:
            console.print("[red]Error:[/red] --deployment-url is required when using --mode ui.")
            raise typer.Exit(1)

        auth_info = ""
        if auth_cookie:
            auth_info += f"\nAuth cookies: {len(auth_cookie)} configured"
        if auth_header:
            auth_info += "\nAuth header: configured"

        console.print(
            Panel(
                f"Mode: [blue]UI Documentation[/blue]\n"
                f"Deployment: [blue]{deployment_url}[/blue]\n"
                f"Repository: [blue]{repo}[/blue]{auth_info}",
                title="UI Documentation Generation",
                border_style="blue",
            )
        )
        console.print(
            "[yellow]Note:[/yellow] UI documentation generation requires a running deployment "
            "and Playwright browser automation. This feature is in preview."
        )
        # TODO: Implement local UI doc generation pipeline
        # For now, this would go through the API
        console.print("[dim]UI mode will be available in a future release.[/dim]")
        raise typer.Exit(0)

    # Create API client
    client = get_api_client(api_key)

    # Trigger generation
    if format != "quiet":
        console.print()
        console.print(
            Panel(
                f"Repository: [blue]{repo}[/blue]\n"
                f"Branch: [blue]{ref or 'default'}[/blue]\n"
                f"Output: [blue]{output_dir}[/blue]",
                title="Starting Documentation Generation",
                border_style="blue",
            )
        )

    try:
        result = client.generate(
            installation_id=installation_id or 0,  # TODO: Need installation ID
            owner=owner,
            repo=repo_name,
            ref=ref,
            guidelines=guidelines,
            output_dir=output_dir,
        )

        job_id = result["job_id"]

        if format == "json":
            import json

            console.print(json.dumps(result, indent=2))
        elif format != "quiet":
            console.print(f"\n[green]✓[/green] Job queued: [blue]{job_id}[/blue]")

        # Wait for completion if requested
        if wait:
            if format != "quiet":
                console.print()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Waiting for generation...", total=None)

                while True:
                    status_result = client.get_job_status(job_id)
                    status = status_result["status"]

                    if status in ("completed", "failed"):
                        break

                    progress.update(task, description=f"Status: {status}...")
                    time.sleep(5)

            if status == "completed":
                pr_url = status_result.get("pr_url")
                if format == "json":
                    import json

                    console.print(json.dumps(status_result, indent=2))
                elif format != "quiet":
                    console.print(
                        Panel(
                            f"[green]Documentation generated successfully![/green]\n\n"
                            f"PR URL: [blue]{pr_url}[/blue]"
                            if pr_url
                            else "",
                            title="Generation Complete",
                            border_style="green",
                        )
                    )
            else:
                error = status_result.get("error_message", "Unknown error")
                if format != "quiet":
                    console.print(f"[red]Error:[/red] Generation failed: {error}")
                raise typer.Exit(1)
        else:
            if format != "quiet":
                console.print(f"\nRun [blue]josephus status {job_id}[/blue] to check progress.")

    except Exception as e:
        if format != "quiet":
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
