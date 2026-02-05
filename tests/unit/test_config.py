"""Unit tests for repository configuration parsing."""

from unittest.mock import AsyncMock

import pytest

from josephus.config import (
    RepoConfig,
    ScopeConfig,
    StyleConfig,
    load_repo_config,
    parse_repo_config,
)


class TestRepoConfig:
    """Tests for RepoConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RepoConfig()

        assert config.guidelines == ""
        assert config.output_dir == "docs"
        assert isinstance(config.scope, ScopeConfig)
        assert isinstance(config.style, StyleConfig)

    def test_full_config(self) -> None:
        """Test configuration with all fields."""
        config = RepoConfig(
            guidelines="Write for developers",
            scope=ScopeConfig(
                include="All public APIs",
                exclude="Internal utilities",
            ),
            style=StyleConfig(
                code_examples="Python and TypeScript",
                diagram_style="Mermaid",
            ),
            output_dir="documentation",
        )

        assert config.guidelines == "Write for developers"
        assert config.scope.include == "All public APIs"
        assert config.scope.exclude == "Internal utilities"
        assert config.style.code_examples == "Python and TypeScript"
        assert config.output_dir == "documentation"

    def test_to_prompt_context_empty(self) -> None:
        """Test prompt context generation with empty config."""
        config = RepoConfig()
        context = config.to_prompt_context()
        assert context == ""

    def test_to_prompt_context_with_guidelines(self) -> None:
        """Test prompt context with guidelines only."""
        config = RepoConfig(guidelines="Write for beginners")
        context = config.to_prompt_context()

        assert "## Documentation Guidelines" in context
        assert "Write for beginners" in context

    def test_to_prompt_context_full(self) -> None:
        """Test prompt context with all fields."""
        config = RepoConfig(
            guidelines="Write for developers",
            scope=ScopeConfig(
                include="All public APIs",
                exclude="Internal utilities",
            ),
            style=StyleConfig(
                code_examples="Python",
                diagram_style="Mermaid",
            ),
        )
        context = config.to_prompt_context()

        assert "## Documentation Guidelines" in context
        assert "Write for developers" in context
        assert "## Scope" in context
        assert "**Include:** All public APIs" in context
        assert "**Exclude:** Internal utilities" in context
        assert "## Style Preferences" in context
        assert "**Code Examples:** Python" in context
        assert "**Diagrams:** Mermaid" in context


class TestParseRepoConfig:
    """Tests for parse_repo_config function."""

    def test_parse_empty_yaml(self) -> None:
        """Test parsing empty YAML."""
        config = parse_repo_config("")
        assert isinstance(config, RepoConfig)
        assert config.guidelines == ""

    def test_parse_simple_config(self) -> None:
        """Test parsing simple YAML config."""
        yaml_content = """
guidelines: |
  Target audience: Developers
  Tone: Technical
"""
        config = parse_repo_config(yaml_content)

        assert "Target audience: Developers" in config.guidelines
        assert "Tone: Technical" in config.guidelines

    def test_parse_full_config(self) -> None:
        """Test parsing full YAML config."""
        yaml_content = """
guidelines: |
  Write for non-technical readers.
  Use simple language.

scope:
  include: All REST API endpoints
  exclude: Internal microservices

style:
  code_examples: "TypeScript and Python"
  diagram_style: "Mermaid flowcharts"

output_dir: docs/api
"""
        config = parse_repo_config(yaml_content)

        assert "non-technical readers" in config.guidelines
        assert config.scope.include == "All REST API endpoints"
        assert config.scope.exclude == "Internal microservices"
        assert config.style.code_examples == "TypeScript and Python"
        assert config.style.diagram_style == "Mermaid flowcharts"
        assert config.output_dir == "docs/api"

    def test_parse_invalid_yaml(self) -> None:
        """Test parsing invalid YAML raises error."""
        invalid_yaml = "{{invalid: yaml"
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_repo_config(invalid_yaml)

    def test_parse_non_mapping_yaml(self) -> None:
        """Test parsing non-mapping YAML raises error."""
        non_mapping = "- item1\n- item2"
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            parse_repo_config(non_mapping)

    def test_parse_partial_config(self) -> None:
        """Test parsing config with missing fields uses defaults."""
        yaml_content = """
guidelines: Just some guidelines
"""
        config = parse_repo_config(yaml_content)

        assert config.guidelines == "Just some guidelines"
        assert config.output_dir == "docs"  # Default
        assert config.scope.include == ""  # Default


class TestLoadRepoConfig:
    """Tests for load_repo_config function."""

    @pytest.mark.asyncio
    async def test_load_config_first_filename(self) -> None:
        """Test loading config from .josephus.yml."""
        mock_client = AsyncMock()
        mock_client.get_file_content.return_value = "guidelines: Test guidelines"

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
        )

        assert config.guidelines == "Test guidelines"
        mock_client.get_file_content.assert_called_once_with(
            installation_id=12345,
            owner="user",
            repo="test-repo",
            path=".josephus.yml",
            ref=None,
        )

    @pytest.mark.asyncio
    async def test_load_config_fallback_filename(self) -> None:
        """Test loading config falls back to alternative filenames."""
        mock_client = AsyncMock()

        # First call (.josephus.yml) returns None
        # Second call (.josephus.yaml) returns config
        mock_client.get_file_content.side_effect = [
            None,
            "guidelines: From yaml file",
        ]

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
        )

        assert config.guidelines == "From yaml file"
        assert mock_client.get_file_content.call_count == 2

    @pytest.mark.asyncio
    async def test_load_config_no_file_found(self) -> None:
        """Test loading config returns defaults when no file found."""
        mock_client = AsyncMock()
        mock_client.get_file_content.return_value = None

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
        )

        assert isinstance(config, RepoConfig)
        assert config.guidelines == ""
        assert mock_client.get_file_content.call_count == 4  # Tried all filenames

    @pytest.mark.asyncio
    async def test_load_config_with_ref(self) -> None:
        """Test loading config from specific ref."""
        mock_client = AsyncMock()
        mock_client.get_file_content.return_value = "guidelines: Branch config"

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
            ref="feature-branch",
        )

        mock_client.get_file_content.assert_called_with(
            installation_id=12345,
            owner="user",
            repo="test-repo",
            path=".josephus.yml",
            ref="feature-branch",
        )
        assert config.guidelines == "Branch config"

    @pytest.mark.asyncio
    async def test_load_config_handles_exceptions(self) -> None:
        """Test loading config handles errors gracefully."""
        mock_client = AsyncMock()
        mock_client.get_file_content.side_effect = Exception("API Error")

        # Should not raise, returns defaults
        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
        )

        assert isinstance(config, RepoConfig)
        assert config.guidelines == ""
