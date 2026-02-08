"""Status command for Josephus CLI."""

from __future__ import annotations

import time

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from josephus.cli.api_client import get_api_client
from josephus.cli.config import get_api_key

app = typer.Typer()
console = Console()


def create_status_table(jobs: list[dict]) -> Table:
    """Create a table displaying job statuses."""
    table = Table(title="Documentation Generation Jobs")
    table.add_column("Job ID", style="cyan", no_wrap=True)
    table.add_column("Repository", style="blue")
    table.add_column("Status", style="bold")
    table.add_column("PR URL")
    table.add_column("Error")

    status_colors = {
        "queued": "yellow",
        "analyzing": "blue",
        "generating": "blue",
        "creating_pr": "blue",
        "completed": "green",
        "failed": "red",
    }

    for job in jobs:
        status = job.get("status", "unknown")
        color = status_colors.get(status, "white")

        table.add_row(
            job.get("job_id", "")[:12] + "...",
            job.get("repository", ""),
            f"[{color}]{status}[/{color}]",
            job.get("pr_url", "") or "-",
            job.get("error_message", "") or "-",
        )

    return table


@app.callback(invoke_without_command=True)
def status(
    job_id: str | None = typer.Argument(
        None,
        help="Job ID to check. If not provided, lists recent jobs.",
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        "-w",
        help="Watch job progress with live updates.",
    ),
    list_jobs: bool = typer.Option(  # noqa: ARG001
        False,
        "--list",
        "-l",
        help="List recent jobs.",
    ),
    repo: str | None = typer.Option(  # noqa: ARG001
        None,
        "--repo",
        "-r",
        help="Filter jobs by repository (owner/repo).",
    ),
    state: str | None = typer.Option(  # noqa: ARG001
        None,
        "--state",
        "-s",
        help="Filter jobs by status (queued, generating, completed, failed).",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Maximum number of jobs to show.",
    ),
    format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: text or json.",
    ),
) -> None:
    """Check status of documentation generation jobs.

    If a job ID is provided, shows details for that specific job.
    Otherwise, lists recent jobs.

    Examples:

        josephus status

        josephus status <job-id>

        josephus status <job-id> --watch

        josephus status --list --repo owner/repo
    """
    # Check authentication
    api_key = get_api_key()
    if not api_key:
        console.print(
            "[red]Error:[/red] Not authenticated. Run [blue]josephus auth login[/blue] first."
        )
        raise typer.Exit(1)

    client = get_api_client(api_key)

    try:
        if job_id:
            # Show specific job status
            show_job_status(client, job_id, watch, format)
        else:
            # List jobs
            list_recent_jobs(client, limit, format)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None


def show_job_status(
    client,
    job_id: str,
    watch: bool,
    format: str,
) -> None:
    """Show status for a specific job."""
    if watch:
        # Watch mode with live updates
        with Live(console=console, refresh_per_second=0.5) as live:
            while True:
                result = client.get_job_status(job_id)
                status = result.get("status", "unknown")

                panel = create_job_panel(result)
                live.update(panel)

                if status in ("completed", "failed"):
                    break

                time.sleep(3)
    else:
        # Single status check
        result = client.get_job_status(job_id)

        if format == "json":
            import json

            console.print(json.dumps(result, indent=2))
        else:
            panel = create_job_panel(result)
            console.print(panel)


def create_job_panel(job: dict) -> Panel:
    """Create a panel displaying job details."""
    status = job.get("status", "unknown")
    status_colors = {
        "queued": "yellow",
        "analyzing": "blue",
        "generating": "blue",
        "creating_pr": "blue",
        "completed": "green",
        "failed": "red",
    }
    color = status_colors.get(status, "white")

    lines = [
        f"Status: [{color}]{status}[/{color}]",
        f"Repository: [blue]{job.get('repository', 'N/A')}[/blue]",
    ]

    if job.get("files_analyzed"):
        lines.append(f"Files Analyzed: {job['files_analyzed']}")

    if job.get("tokens_used"):
        lines.append(f"Tokens Used: {job['tokens_used']:,}")

    if job.get("pr_url"):
        lines.append(f"PR URL: [link={job['pr_url']}]{job['pr_url']}[/link]")

    if job.get("error_message"):
        lines.append(f"[red]Error: {job['error_message']}[/red]")

    return Panel(
        "\n".join(lines),
        title=f"Job {job.get('job_id', 'Unknown')[:16]}...",
        border_style=color,
    )


def list_recent_jobs(
    client,
    limit: int,
    format: str,
) -> None:
    """List recent jobs."""
    jobs = client.list_jobs(limit=limit)

    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    if format == "json":
        import json

        console.print(json.dumps(jobs, indent=2))
    else:
        table = create_status_table(jobs)
        console.print(table)
