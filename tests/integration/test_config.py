"""Integration tests for configuration loading."""

from unittest.mock import AsyncMock

import pytest

from josephus.config import RepoConfig, load_repo_config


class TestConfigLoading:
    """Integration tests for loading config from repositories."""

    @pytest.mark.asyncio
    async def test_load_full_config(self) -> None:
        """Test loading a complete configuration."""
        mock_client = AsyncMock()

        files = {
            ".josephus/config.yml": """
output_dir: docs/api
output_format: markdown
create_pr: true
branch_prefix: docs/auto
""",
            ".josephus/guidelines.md": """
# Documentation Guidelines

## Target Audience
Software developers integrating with our API.

## Tone
Technical but approachable. Use clear language.

## Requirements
- Include code examples in Python and JavaScript
- Document all error codes
- Provide authentication examples
""",
            ".josephus/scope.md": """
# Scope

## Include
- All public REST API endpoints
- Authentication flows
- SDK usage examples
- Error handling patterns

## Exclude
- Internal microservice APIs
- Deprecated endpoints
- Admin-only endpoints
""",
            ".josephus/style.md": """
# Style Preferences

## Code Examples
Prefer TypeScript for frontend examples and Python for backend.

## Diagrams
Use Mermaid for sequence diagrams and flowcharts.

## Format
- Use tables for parameter documentation
- Include request/response examples
- Add links to related endpoints
""",
        }

        async def mock_get_file(**kwargs: object) -> str | None:
            path = kwargs.get("path")
            return files.get(str(path))

        mock_client.get_file_content.side_effect = mock_get_file

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="testuser",
            repo="testrepo",
        )

        # Verify deterministic config
        assert config.output_dir == "docs/api"
        assert config.output_format == "markdown"
        assert config.create_pr is True
        assert config.branch_prefix == "docs/auto"

        # Verify natural language content loaded
        assert "Software developers" in config.guidelines
        assert "public REST API" in config.scope
        assert "TypeScript" in config.style

    @pytest.mark.asyncio
    async def test_load_partial_config(self) -> None:
        """Test loading config with only some files present."""
        mock_client = AsyncMock()

        files = {
            ".josephus/guidelines.md": """
Write documentation for beginners.
Keep it simple and include lots of examples.
""",
        }

        async def mock_get_file(**kwargs: object) -> str | None:
            path = kwargs.get("path")
            return files.get(str(path))

        mock_client.get_file_content.side_effect = mock_get_file

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="testuser",
            repo="testrepo",
        )

        # Verify defaults used for missing config
        assert config.output_dir == "docs"  # Default
        assert config.create_pr is True  # Default

        # Verify guidelines loaded
        assert "beginners" in config.guidelines
        assert config.scope == ""
        assert config.style == ""

    @pytest.mark.asyncio
    async def test_load_no_config(self) -> None:
        """Test loading config when no files exist."""
        mock_client = AsyncMock()
        mock_client.get_file_content.return_value = None

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="testuser",
            repo="testrepo",
        )

        # All defaults
        assert config.output_dir == "docs"
        assert config.output_format == "markdown"
        assert config.guidelines == ""
        assert config.scope == ""
        assert config.style == ""

    @pytest.mark.asyncio
    async def test_config_to_prompt_context(self) -> None:
        """Test converting config to LLM prompt context."""
        config = RepoConfig(
            guidelines="Write for developers",
            scope="All public APIs",
            style="Use Python examples",
        )

        context = config.to_prompt_context()

        assert "## Documentation Guidelines" in context
        assert "Write for developers" in context
        assert "## Scope" in context
        assert "All public APIs" in context
        assert "## Style Preferences" in context
        assert "Use Python examples" in context

    @pytest.mark.asyncio
    async def test_config_handles_malformed_yaml(self) -> None:
        """Test that malformed YAML doesn't crash loading."""
        mock_client = AsyncMock()

        files = {
            ".josephus/config.yml": "{{not valid yaml",
            ".josephus/guidelines.md": "Valid guidelines content",
        }

        async def mock_get_file(**kwargs: object) -> str | None:
            path = kwargs.get("path")
            return files.get(str(path))

        mock_client.get_file_content.side_effect = mock_get_file

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="testuser",
            repo="testrepo",
        )

        # Should use defaults for config but still load guidelines
        assert config.output_dir == "docs"  # Default due to parse error
        assert "Valid guidelines content" in config.guidelines
