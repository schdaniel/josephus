"""Repository configuration parsing for .josephus.yml files."""

import yaml
from pydantic import BaseModel, Field

from josephus.github import GitHubClient

# Default config file names to look for
CONFIG_FILE_NAMES = [".josephus.yml", ".josephus.yaml", "josephus.yml", "josephus.yaml"]


class ScopeConfig(BaseModel):
    """Configuration for documentation scope."""

    include: str = Field(
        default="",
        description="Natural language description of what to include in documentation",
    )
    exclude: str = Field(
        default="",
        description="Natural language description of what to exclude from documentation",
    )


class StyleConfig(BaseModel):
    """Configuration for documentation style."""

    code_examples: str = Field(
        default="",
        description="Preferred languages for code examples",
    )
    diagram_style: str = Field(
        default="",
        description="Preferred diagram format (e.g., Mermaid, PlantUML)",
    )
    output_format: str = Field(
        default="markdown",
        description="Output format for documentation",
    )


class RepoConfig(BaseModel):
    """Repository-level configuration for documentation generation.

    This is parsed from .josephus.yml files in user repositories.
    All fields accept natural language descriptions that are passed
    to the LLM for interpretation.
    """

    guidelines: str = Field(
        default="",
        description="Natural language guidelines for documentation style and content",
    )
    scope: ScopeConfig = Field(
        default_factory=ScopeConfig,
        description="Scope of documentation (what to include/exclude)",
    )
    style: StyleConfig = Field(
        default_factory=StyleConfig,
        description="Style preferences for documentation",
    )
    output_dir: str = Field(
        default="docs",
        description="Output directory for generated documentation",
    )

    def to_prompt_context(self) -> str:
        """Convert config to context string for LLM prompt.

        Returns:
            Formatted string containing all configuration for LLM context.
        """
        sections = []

        if self.guidelines:
            sections.append(f"## Documentation Guidelines\n{self.guidelines}")

        if self.scope.include or self.scope.exclude:
            scope_parts = []
            if self.scope.include:
                scope_parts.append(f"**Include:** {self.scope.include}")
            if self.scope.exclude:
                scope_parts.append(f"**Exclude:** {self.scope.exclude}")
            sections.append("## Scope\n" + "\n".join(scope_parts))

        if self.style.code_examples or self.style.diagram_style:
            style_parts = []
            if self.style.code_examples:
                style_parts.append(f"**Code Examples:** {self.style.code_examples}")
            if self.style.diagram_style:
                style_parts.append(f"**Diagrams:** {self.style.diagram_style}")
            sections.append("## Style Preferences\n" + "\n".join(style_parts))

        return "\n\n".join(sections) if sections else ""


def parse_repo_config(yaml_content: str) -> RepoConfig:
    """Parse repository configuration from YAML content.

    Args:
        yaml_content: Raw YAML string from .josephus.yml file.

    Returns:
        Parsed RepoConfig object with defaults for missing fields.

    Raises:
        ValueError: If YAML is invalid.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}") from e

    if data is None:
        return RepoConfig()

    if not isinstance(data, dict):
        raise ValueError("Config must be a YAML mapping")

    return RepoConfig.model_validate(data)


async def load_repo_config(
    github_client: GitHubClient,
    installation_id: int,
    owner: str,
    repo: str,
    ref: str | None = None,
) -> RepoConfig:
    """Load repository configuration from GitHub.

    Looks for config files in the following order:
    1. .josephus.yml
    2. .josephus.yaml
    3. josephus.yml
    4. josephus.yaml

    Args:
        github_client: GitHub API client.
        installation_id: GitHub App installation ID.
        owner: Repository owner.
        repo: Repository name.
        ref: Git ref (branch/tag), defaults to default branch.

    Returns:
        Parsed RepoConfig, or default config if no file found.
    """
    for filename in CONFIG_FILE_NAMES:
        try:
            content = await github_client.get_file_content(
                installation_id=installation_id,
                owner=owner,
                repo=repo,
                path=filename,
                ref=ref,
            )
            if content:
                return parse_repo_config(content)
        except Exception:
            # File not found or other error, try next filename
            continue

    # No config file found, return defaults
    return RepoConfig()
