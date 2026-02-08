"""Tests for josephus.eval.crawl module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from josephus.eval.crawl import (
    get_ground_truth_dir,
    is_doc_file,
    load_repos_config,
    parse_repo_url,
)


class TestParseRepoUrl:
    """Tests for parse_repo_url function."""

    def test_parse_https_url(self):
        """Test parsing HTTPS GitHub URL."""
        owner, repo = parse_repo_url("https://github.com/backstage/backstage.git")
        assert owner == "backstage"
        assert repo == "backstage"

    def test_parse_https_url_no_git_suffix(self):
        """Test parsing HTTPS URL without .git suffix."""
        owner, repo = parse_repo_url("https://github.com/backstage/backstage")
        assert owner == "backstage"
        assert repo == "backstage"

    def test_parse_git_url(self):
        """Test parsing git@ URL."""
        owner, repo = parse_repo_url("git@github.com:backstage/backstage.git")
        assert owner == "backstage"
        assert repo == "backstage"


class TestIsDocFile:
    """Tests for is_doc_file function."""

    def test_markdown_files(self):
        """Test markdown file detection."""
        assert is_doc_file("README.md")
        assert is_doc_file("index.mdx")
        assert is_doc_file("docs.markdown")
        assert not is_doc_file("script.py")
        assert not is_doc_file("config.yaml")

    def test_asciidoc_files(self):
        """Test asciidoc file detection."""
        assert is_doc_file("api.adoc", docs_format="asciidoc")
        assert is_doc_file("guide.asciidoc", docs_format="asciidoc")
        assert not is_doc_file("README.md", docs_format="asciidoc")

    def test_lektor_files(self):
        """Test lektor file detection."""
        assert is_doc_file("contents.lr", docs_format="lektor")
        assert not is_doc_file("README.md", docs_format="lektor")
        assert not is_doc_file("other.lr", docs_format="lektor")  # Only contents.lr


class TestLoadReposConfig:
    """Tests for load_repos_config function."""

    def test_load_repos_config(self, tmp_path: Path):
        """Test loading valid repos config."""
        config_file = tmp_path / "repos.yaml"
        config_file.write_text("""
repos:
  test-repo:
    url: https://github.com/test/repo.git
    language: python
    size: small
    description: Test repository
    docs_path: docs
""")
        repos = load_repos_config(config_file)
        assert "test-repo" in repos
        assert repos["test-repo"]["language"] == "python"
        assert repos["test-repo"]["docs_path"] == "docs"

    def test_load_repos_config_not_found(self, tmp_path: Path):
        """Test loading non-existent config file."""
        config_file = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError):
            load_repos_config(config_file)


class TestGetGroundTruthDir:
    """Tests for get_ground_truth_dir function."""

    def test_creates_directory(self, tmp_path: Path):
        """Test that ground truth directory is created."""
        with patch("josephus.eval.crawl.get_project_root", return_value=tmp_path):
            ground_truth_dir = get_ground_truth_dir("test-repo")
            assert ground_truth_dir.exists()
            assert ground_truth_dir.name == "crawled_docs"
            assert ground_truth_dir.parent.name == "test-repo"


class TestIntegration:
    """Integration tests for the crawl module."""

    def test_repos_yaml_is_valid(self):
        """Test that the actual repos.yaml is valid."""
        repos = load_repos_config()
        assert len(repos) > 0

        # All repos should have required fields
        required_fields = ["url", "language", "size", "description"]
        for name, config in repos.items():
            for field in required_fields:
                assert field in config, f"Repo {name} missing field: {field}"
