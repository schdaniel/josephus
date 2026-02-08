"""Unit tests for repository configuration parsing."""

from unittest.mock import AsyncMock

import pytest

from josephus.config import (
    DeterministicConfig,
    RepoConfig,
    load_repo_config,
    parse_deterministic_config,
)


class TestDeterministicConfig:
    """Tests for DeterministicConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = DeterministicConfig()

        assert config.output_dir == "docs"
        assert config.output_format == "markdown"
        assert config.create_pr is True
        assert config.branch_prefix == "josephus/docs"

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = DeterministicConfig(
            output_dir="documentation",
            output_format="html",
            create_pr=False,
            branch_prefix="docs/auto",
        )

        assert config.output_dir == "documentation"
        assert config.output_format == "html"
        assert config.create_pr is False
        assert config.branch_prefix == "docs/auto"


class TestRepoConfig:
    """Tests for RepoConfig model."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RepoConfig()

        assert config.guidelines == ""
        assert config.output_dir == "docs"
        assert config.create_pr is True

    def test_full_config(self) -> None:
        """Test configuration with all fields."""
        config = RepoConfig(
            config=DeterministicConfig(output_dir="api-docs"),
            guidelines="Write for developers\n\n## Scope\nAll public APIs\n\n## Style\nUse TypeScript examples",
        )

        assert "Write for developers" in config.guidelines
        assert "All public APIs" in config.guidelines
        assert "Use TypeScript examples" in config.guidelines
        assert config.output_dir == "api-docs"

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
        """Test prompt context with comprehensive guidelines."""
        config = RepoConfig(
            guidelines="""Write for developers

## Scope
All public APIs
Exclude internal utilities

## Style
Use Python examples
Include Mermaid diagrams""",
        )
        context = config.to_prompt_context()

        assert "## Documentation Guidelines" in context
        assert "Write for developers" in context
        assert "## Scope" in context
        assert "All public APIs" in context
        assert "## Style" in context
        assert "Use Python examples" in context

    def test_convenience_accessors(self) -> None:
        """Test convenience property accessors."""
        config = RepoConfig(
            config=DeterministicConfig(
                output_dir="custom-docs",
                output_format="html",
                create_pr=False,
                branch_prefix="auto/docs",
            )
        )

        assert config.output_dir == "custom-docs"
        assert config.output_format == "html"
        assert config.create_pr is False
        assert config.branch_prefix == "auto/docs"


class TestParseDeterministicConfig:
    """Tests for parse_deterministic_config function."""

    def test_parse_empty_yaml(self) -> None:
        """Test parsing empty YAML."""
        config = parse_deterministic_config("")
        assert isinstance(config, DeterministicConfig)
        assert config.output_dir == "docs"

    def test_parse_simple_config(self) -> None:
        """Test parsing simple YAML config."""
        yaml_content = """
output_dir: api-docs
output_format: markdown
"""
        config = parse_deterministic_config(yaml_content)

        assert config.output_dir == "api-docs"
        assert config.output_format == "markdown"

    def test_parse_full_config(self) -> None:
        """Test parsing full YAML config."""
        yaml_content = """
output_dir: docs/api
output_format: html
create_pr: false
branch_prefix: documentation/auto
"""
        config = parse_deterministic_config(yaml_content)

        assert config.output_dir == "docs/api"
        assert config.output_format == "html"
        assert config.create_pr is False
        assert config.branch_prefix == "documentation/auto"

    def test_parse_invalid_yaml(self) -> None:
        """Test parsing invalid YAML raises error."""
        invalid_yaml = "{{invalid: yaml"
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_deterministic_config(invalid_yaml)

    def test_parse_non_mapping_yaml(self) -> None:
        """Test parsing non-mapping YAML raises error."""
        non_mapping = "- item1\n- item2"
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            parse_deterministic_config(non_mapping)

    def test_parse_partial_config(self) -> None:
        """Test parsing config with missing fields uses defaults."""
        yaml_content = """
output_dir: custom
"""
        config = parse_deterministic_config(yaml_content)

        assert config.output_dir == "custom"
        assert config.output_format == "markdown"  # Default
        assert config.create_pr is True  # Default


class TestLoadRepoConfig:
    """Tests for load_repo_config function."""

    @pytest.mark.asyncio
    async def test_load_config_all_files(self) -> None:
        """Test loading config with all files present."""
        mock_client = AsyncMock()

        files = {
            ".josephus/config.yml": "output_dir: api-docs",
            ".josephus/guidelines.xml": """# Guidelines
Write for developers

## Scope
All public APIs

## Style
Use TypeScript""",
        }

        async def mock_get_file(**kwargs: object) -> str | None:
            path = kwargs.get("path")
            return files.get(str(path))

        mock_client.get_file_content.side_effect = mock_get_file

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
        )

        assert config.output_dir == "api-docs"
        assert "Write for developers" in config.guidelines
        assert "All public APIs" in config.guidelines
        assert "Use TypeScript" in config.guidelines

    @pytest.mark.asyncio
    async def test_load_config_partial_files(self) -> None:
        """Test loading config with only guidelines present."""
        mock_client = AsyncMock()

        files = {
            ".josephus/guidelines.xml": "Just some guidelines",
        }

        async def mock_get_file(**kwargs: object) -> str | None:
            path = kwargs.get("path")
            return files.get(str(path))

        mock_client.get_file_content.side_effect = mock_get_file

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
        )

        assert config.output_dir == "docs"  # Default
        assert config.guidelines == "Just some guidelines"

    @pytest.mark.asyncio
    async def test_load_config_no_files(self) -> None:
        """Test loading config returns defaults when no files found."""
        mock_client = AsyncMock()
        mock_client.get_file_content.return_value = None

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
        )

        assert isinstance(config, RepoConfig)
        assert config.output_dir == "docs"
        assert config.guidelines == ""

    @pytest.mark.asyncio
    async def test_load_config_with_ref(self) -> None:
        """Test loading config from specific ref."""
        mock_client = AsyncMock()
        mock_client.get_file_content.return_value = "Branch specific content"

        await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
            ref="feature-branch",
        )

        # Check that ref was passed to all file fetches
        calls = mock_client.get_file_content.call_args_list
        for call in calls:
            assert (
                call.kwargs.get("ref") == "feature-branch" or call[1].get("ref") == "feature-branch"
            )

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

    @pytest.mark.asyncio
    async def test_load_config_invalid_yaml_uses_defaults(self) -> None:
        """Test loading config with invalid YAML uses defaults."""
        mock_client = AsyncMock()

        async def mock_get_file(**kwargs: object) -> str | None:
            path = kwargs.get("path")
            if path == ".josephus/config.yml":
                return "{{invalid yaml"
            return None

        mock_client.get_file_content.side_effect = mock_get_file

        config = await load_repo_config(
            github_client=mock_client,
            installation_id=12345,
            owner="user",
            repo="test-repo",
        )

        # Should use defaults instead of raising
        assert config.output_dir == "docs"
