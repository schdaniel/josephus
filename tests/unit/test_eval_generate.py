"""Unit tests for eval generate module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from josephus.eval.generate import (
    generate_all,
    generate_docs_for_repo,
    get_output_dir,
)


class TestGetOutputDir:
    """Tests for get_output_dir."""

    def test_get_output_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test that get_output_dir creates the directory."""
        output_dir = tmp_path / "generated"

        result = get_output_dir(output_dir)

        assert result == output_dir
        assert output_dir.exists()

    def test_get_output_dir_existing(self, tmp_path: Path) -> None:
        """Test with existing directory."""
        output_dir = tmp_path / "generated"
        output_dir.mkdir()

        result = get_output_dir(output_dir)

        assert result == output_dir


class TestGenerateDocsForRepo:
    """Tests for generate_docs_for_repo."""

    @pytest.fixture
    def sample_repo(self, tmp_path: Path) -> Path:
        """Create a sample repository."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        (repo_path / "README.md").write_text("# Test Project\n\nA test project.")
        (repo_path / "main.py").write_text("def main():\n    print('hello')\n")

        return repo_path

    @pytest.fixture
    def mock_llm_provider(self) -> MagicMock:
        """Create a mock LLM provider."""
        provider = MagicMock()
        return provider

    @patch("josephus.eval.generate.DocGenerator")
    def test_generate_docs_for_repo(
        self,
        mock_generator_class: MagicMock,
        sample_repo: Path,
        mock_llm_provider: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generating docs for a repo."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock the generator
        mock_generator = MagicMock()
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"overview": "Test docs"}
        mock_result.overview = "Test overview"
        mock_result.sections = []
        mock_result.api_reference = None
        mock_generator.generate.return_value = mock_result
        mock_generator_class.return_value = mock_generator

        result = generate_docs_for_repo(
            repo_path=sample_repo,
            repo_name="test-repo",
            output_dir=output_dir,
            llm_provider=mock_llm_provider,
        )

        assert result["success"] is True
        assert result["repo_name"] == "test-repo"
        assert result["files_analyzed"] > 0

        # Check output files were created
        repo_output = output_dir / "test-repo"
        assert repo_output.exists()
        assert (repo_output / "docs.json").exists()
        assert (repo_output / "index.md").exists()


class TestGenerateAll:
    """Tests for generate_all."""

    @patch("josephus.eval.generate.LLMProvider")
    @patch("josephus.eval.generate.generate_docs_for_repo")
    @patch("josephus.eval.generate.load_repos_config")
    @patch("josephus.eval.generate.get_repos_dir")
    def test_generate_all(
        self,
        mock_get_repos_dir: MagicMock,
        mock_load_config: MagicMock,
        mock_generate: MagicMock,
        mock_llm_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generating docs for all repos."""
        # Setup
        repos_dir = tmp_path / "repos"
        repos_dir.mkdir()
        (repos_dir / "repo1").mkdir()

        output_dir = tmp_path / "output"

        mock_get_repos_dir.return_value = repos_dir
        mock_load_config.return_value = {"repo1": {"url": "url1"}}
        mock_generate.return_value = {
            "repo_name": "repo1",
            "success": True,
            "files_analyzed": 5,
        }
        mock_llm = MagicMock()
        mock_llm_class.return_value = mock_llm

        # Execute
        results = generate_all(
            repos_dir=repos_dir,
            output_dir=output_dir,
        )

        # Verify
        assert "repo1" in results
        assert results["repo1"]["success"] is True
        mock_llm.close.assert_called_once()

    @patch("josephus.eval.generate.load_repos_config")
    def test_generate_all_no_repos(
        self,
        mock_load_config: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generate_all with no repos available."""
        repos_dir = tmp_path / "repos"
        repos_dir.mkdir()

        mock_load_config.return_value = {"repo1": {"url": "url1"}}

        results = generate_all(repos_dir=repos_dir)

        assert results == {}

    @patch("josephus.eval.generate.LLMProvider")
    @patch("josephus.eval.generate.generate_docs_for_repo")
    @patch("josephus.eval.generate.load_repos_config")
    @patch("josephus.eval.generate.get_repos_dir")
    def test_generate_all_handles_errors(
        self,
        mock_get_repos_dir: MagicMock,
        mock_load_config: MagicMock,
        mock_generate: MagicMock,
        mock_llm_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that generate_all handles errors gracefully."""
        repos_dir = tmp_path / "repos"
        repos_dir.mkdir()
        (repos_dir / "repo1").mkdir()

        mock_get_repos_dir.return_value = repos_dir
        mock_load_config.return_value = {"repo1": {"url": "url1"}}
        mock_generate.side_effect = Exception("Generation failed")
        mock_llm = MagicMock()
        mock_llm_class.return_value = mock_llm

        results = generate_all(repos_dir=repos_dir)

        assert results["repo1"]["success"] is False
        assert "error" in results["repo1"]

    @patch("josephus.eval.generate.LLMProvider")
    @patch("josephus.eval.generate.generate_docs_for_repo")
    @patch("josephus.eval.generate.load_repos_config")
    @patch("josephus.eval.generate.get_repos_dir")
    def test_generate_all_specific_repos(
        self,
        mock_get_repos_dir: MagicMock,
        mock_load_config: MagicMock,
        mock_generate: MagicMock,
        mock_llm_class: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test generating docs for specific repos only."""
        repos_dir = tmp_path / "repos"
        repos_dir.mkdir()
        (repos_dir / "repo1").mkdir()
        (repos_dir / "repo2").mkdir()

        mock_get_repos_dir.return_value = repos_dir
        mock_load_config.return_value = {
            "repo1": {"url": "url1"},
            "repo2": {"url": "url2"},
        }
        mock_generate.return_value = {"repo_name": "repo1", "success": True}
        mock_llm = MagicMock()
        mock_llm_class.return_value = mock_llm

        results = generate_all(repos_dir=repos_dir, repos=["repo1"])

        assert "repo1" in results
        assert "repo2" not in results
