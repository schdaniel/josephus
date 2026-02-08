"""Unit tests for eval download module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from josephus.eval.download import (
    download_all,
    download_repo,
    get_repos_dir,
    list_repos,
    load_repos_config,
    update_repos,
)


class TestLoadReposConfig:
    """Tests for load_repos_config."""

    def test_load_repos_config(self, tmp_path: Path) -> None:
        """Test loading repos config from YAML."""
        config_path = tmp_path / "repos.yaml"
        config_path.write_text(
            """
repos:
  test-repo:
    url: https://github.com/test/repo.git
    language: python
    size: small
"""
        )

        repos = load_repos_config(config_path)

        assert "test-repo" in repos
        assert repos["test-repo"]["url"] == "https://github.com/test/repo.git"
        assert repos["test-repo"]["language"] == "python"

    def test_load_repos_config_not_found(self, tmp_path: Path) -> None:
        """Test error when config file not found."""
        with pytest.raises(FileNotFoundError):
            load_repos_config(tmp_path / "nonexistent.yaml")

    def test_load_repos_config_empty(self, tmp_path: Path) -> None:
        """Test loading empty config."""
        config_path = tmp_path / "repos.yaml"
        config_path.write_text("repos:")

        repos = load_repos_config(config_path)

        assert repos is None or repos == {}


class TestGetReposDir:
    """Tests for get_repos_dir."""

    def test_get_repos_dir_creates_directory(self, tmp_path: Path) -> None:
        """Test that get_repos_dir creates the directory."""
        repos_dir = tmp_path / "repos"

        result = get_repos_dir(repos_dir)

        assert result == repos_dir
        assert repos_dir.exists()

    def test_get_repos_dir_existing(self, tmp_path: Path) -> None:
        """Test with existing directory."""
        repos_dir = tmp_path / "repos"
        repos_dir.mkdir()

        result = get_repos_dir(repos_dir)

        assert result == repos_dir


class TestDownloadRepo:
    """Tests for download_repo."""

    @patch("josephus.eval.download.subprocess.run")
    def test_download_repo_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful repo download."""
        mock_run.return_value = MagicMock(returncode=0)

        result = download_repo(
            name="test-repo",
            url="https://github.com/test/repo.git",
            repos_dir=tmp_path,
        )

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert "clone" in call_args

    @patch("josephus.eval.download.subprocess.run")
    def test_download_repo_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test failed repo download."""
        mock_run.return_value = MagicMock(returncode=1, stderr="error")

        result = download_repo(
            name="test-repo",
            url="https://github.com/test/repo.git",
            repos_dir=tmp_path,
        )

        assert result is False

    def test_download_repo_already_exists(self, tmp_path: Path) -> None:
        """Test download when repo already exists."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()

        result = download_repo(
            name="test-repo",
            url="https://github.com/test/repo.git",
            repos_dir=tmp_path,
            force=False,
        )

        assert result is False

    @patch("josephus.eval.download.subprocess.run")
    @patch("josephus.eval.download.shutil.rmtree")
    def test_download_repo_force(
        self, mock_rmtree: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test force re-download."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        mock_run.return_value = MagicMock(returncode=0)

        result = download_repo(
            name="test-repo",
            url="https://github.com/test/repo.git",
            repos_dir=tmp_path,
            force=True,
        )

        assert result is True
        mock_rmtree.assert_called_once()


class TestDownloadAll:
    """Tests for download_all."""

    @patch("josephus.eval.download.download_repo")
    @patch("josephus.eval.download.load_repos_config")
    def test_download_all(
        self,
        mock_load_config: MagicMock,
        mock_download: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test downloading all repos."""
        mock_load_config.return_value = {
            "repo1": {"url": "url1"},
            "repo2": {"url": "url2"},
        }
        mock_download.return_value = True

        results = download_all(repos_dir=tmp_path)

        assert len(results) == 2
        assert results["repo1"] is True
        assert results["repo2"] is True

    @patch("josephus.eval.download.download_repo")
    @patch("josephus.eval.download.load_repos_config")
    def test_download_all_specific_repos(
        self,
        mock_load_config: MagicMock,
        mock_download: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test downloading specific repos."""
        mock_load_config.return_value = {
            "repo1": {"url": "url1"},
            "repo2": {"url": "url2"},
        }
        mock_download.return_value = True

        results = download_all(repos_dir=tmp_path, repos=["repo1"])

        assert len(results) == 1
        assert "repo1" in results


class TestUpdateRepos:
    """Tests for update_repos."""

    @patch("josephus.eval.download.subprocess.run")
    @patch("josephus.eval.download.load_repos_config")
    def test_update_repos(
        self,
        mock_load_config: MagicMock,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test updating repos."""
        mock_load_config.return_value = {"repo1": {"url": "url1"}}
        mock_run.return_value = MagicMock(returncode=0)

        # Create repo directory
        (tmp_path / "repo1").mkdir()

        results = update_repos(repos_dir=tmp_path)

        assert results["repo1"] is True
        mock_run.assert_called_once()

    @patch("josephus.eval.download.load_repos_config")
    def test_update_repos_not_downloaded(
        self,
        mock_load_config: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test update when repo not downloaded."""
        mock_load_config.return_value = {"repo1": {"url": "url1"}}

        results = update_repos(repos_dir=tmp_path)

        assert results["repo1"] is False


class TestListRepos:
    """Tests for list_repos."""

    @patch("josephus.eval.download.load_repos_config")
    @patch("josephus.eval.download.get_repos_dir")
    def test_list_repos(
        self,
        mock_get_dir: MagicMock,
        mock_load_config: MagicMock,
        tmp_path: Path,
        capsys,
    ) -> None:
        """Test listing repos."""
        mock_load_config.return_value = {
            "repo1": {"language": "python", "size": "small"},
        }
        mock_get_dir.return_value = tmp_path

        list_repos()

        captured = capsys.readouterr()
        assert "repo1" in captured.out
        assert "python" in captured.out
