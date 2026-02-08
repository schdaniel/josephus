"""Josephus CLI for documentation generation."""

from __future__ import annotations

import typer
from rich.console import Console

from josephus.cli.commands import generate, status

app = typer.Typer(
    name="josephus",
    help="AI-powered documentation generator",
    no_args_is_help=True,
)
console = Console()

# Add command groups
app.add_typer(generate.app, name="generate", help="Generate documentation")
app.add_typer(status.app, name="status", help="Check job status")


@app.command()
def version() -> None:
    """Show the CLI version."""
    console.print("josephus version 0.1.0")


def main() -> None:
    """Main entry point for the CLI."""
    app()


__all__ = ["app", "main"]
