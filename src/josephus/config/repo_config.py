"""Repository configuration parsing for .josephus/ directory.

Configuration structure:
    .josephus/
        config.yml       # Deterministic settings (output_dir, format, etc.)
        guidelines.md    # Natural language documentation guidelines (includes scope, structure, style)
"""

import contextlib

import yaml
from pydantic import BaseModel, Field

from josephus.github import GitHubClient

# Config directory and file names
CONFIG_DIR = ".josephus"
CONFIG_FILE = "config.yml"
GUIDELINES_FILE = "guidelines.md"


class DeterministicConfig(BaseModel):
    """Deterministic configuration settings from config.yml."""

    output_dir: str = Field(
        default="docs",
        description="Output directory for generated documentation",
    )
    output_format: str = Field(
        default="markdown",
        description="Output format (markdown, html, etc.)",
    )
    create_pr: bool = Field(
        default=True,
        description="Whether to create a PR with generated docs",
    )
    branch_prefix: str = Field(
        default="josephus/docs",
        description="Prefix for generated branch names",
    )


class RepoConfig(BaseModel):
    """Repository-level configuration for documentation generation.

    Combines deterministic settings from config.yml with natural language
    content from guidelines.md.
    """

    # Deterministic settings
    config: DeterministicConfig = Field(
        default_factory=DeterministicConfig,
        description="Deterministic configuration settings",
    )

    # Natural language content from guidelines.md
    guidelines: str = Field(
        default="",
        description="Documentation guidelines from guidelines.md (includes scope, structure, style)",
    )

    def to_prompt_context(self) -> str:
        """Convert config to context string for LLM prompt.

        Returns:
            Formatted string containing all configuration for LLM context.
        """
        if self.guidelines:
            return f"## Documentation Guidelines\n\n{self.guidelines}"
        return ""

    @property
    def output_dir(self) -> str:
        """Convenience accessor for output directory."""
        return self.config.output_dir

    @property
    def output_format(self) -> str:
        """Convenience accessor for output format."""
        return self.config.output_format

    @property
    def create_pr(self) -> bool:
        """Convenience accessor for create_pr setting."""
        return self.config.create_pr

    @property
    def branch_prefix(self) -> str:
        """Convenience accessor for branch prefix."""
        return self.config.branch_prefix


def parse_deterministic_config(yaml_content: str) -> DeterministicConfig:
    """Parse deterministic configuration from YAML content.

    Args:
        yaml_content: Raw YAML string from config.yml.

    Returns:
        Parsed DeterministicConfig object with defaults for missing fields.

    Raises:
        ValueError: If YAML is invalid.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}") from e

    if data is None:
        return DeterministicConfig()

    if not isinstance(data, dict):
        raise ValueError("Config must be a YAML mapping")

    return DeterministicConfig.model_validate(data)


async def load_repo_config(
    github_client: GitHubClient,
    installation_id: int,
    owner: str,
    repo: str,
    ref: str | None = None,
) -> RepoConfig:
    """Load repository configuration from GitHub.

    Looks for configuration in .josephus/ directory:
    - config.yml for deterministic settings
    - guidelines.md for documentation guidelines (includes scope, structure, style)

    Args:
        github_client: GitHub API client.
        installation_id: GitHub App installation ID.
        owner: Repository owner.
        repo: Repository name.
        ref: Git ref (branch/tag), defaults to default branch.

    Returns:
        Parsed RepoConfig with all available configuration.
    """
    # Load deterministic config
    config = DeterministicConfig()
    config_content = await _get_file_content(
        github_client, installation_id, owner, repo, f"{CONFIG_DIR}/{CONFIG_FILE}", ref
    )
    if config_content:
        with contextlib.suppress(ValueError):
            config = parse_deterministic_config(config_content)

    # Load guidelines
    guidelines = await _get_file_content(
        github_client, installation_id, owner, repo, f"{CONFIG_DIR}/{GUIDELINES_FILE}", ref
    )

    return RepoConfig(
        config=config,
        guidelines=guidelines or "",
    )


async def _get_file_content(
    github_client: GitHubClient,
    installation_id: int,
    owner: str,
    repo: str,
    path: str,
    ref: str | None,
) -> str | None:
    """Get file content from GitHub, returning None if not found."""
    try:
        return await github_client.get_file_content(
            installation_id=installation_id,
            owner=owner,
            repo=repo,
            path=path,
            ref=ref,
        )
    except Exception:
        return None
