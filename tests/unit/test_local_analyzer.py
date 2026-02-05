"""Unit tests for local repository analyzer."""

from pathlib import Path

import pytest

from josephus.analyzer import LocalRepoAnalyzer
from josephus.analyzer.local import LocalRepository


class TestLocalRepository:
    """Tests for LocalRepository dataclass."""

    def test_to_repository(self, tmp_path: Path) -> None:
        """Test conversion to Repository."""
        local_repo = LocalRepository(
            path=tmp_path,
            name="test-repo",
            description="Test description",
            language="Python",
        )

        repo = local_repo.to_repository()

        assert repo.name == "test-repo"
        assert repo.full_name == "test-repo"
        assert repo.description == "Test description"
        assert repo.language == "Python"
        assert repo.default_branch == "main"
        assert f"file://{tmp_path}" in repo.html_url


class TestLocalRepoAnalyzer:
    """Tests for LocalRepoAnalyzer."""

    @pytest.fixture
    def sample_repo(self, tmp_path: Path) -> Path:
        """Create a sample repository structure."""
        # Create directory structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create README
        (tmp_path / "README.md").write_text("# Test Project\n\nA test project.")

        # Create pyproject.toml
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-project"\nversion = "0.1.0"'
        )

        # Create Python files
        (src_dir / "__init__.py").write_text('"""Test package."""')
        (src_dir / "main.py").write_text(
            'def main():\n    """Main entry point."""\n    print("Hello")\n'
        )
        (src_dir / "utils.py").write_text(
            'def helper(x: int) -> int:\n    """Helper function."""\n    return x * 2\n'
        )

        # Create a test file (should be lower priority)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("def test_main():\n    assert True\n")

        return tmp_path

    def test_analyze_basic(self, sample_repo: Path) -> None:
        """Test basic analysis of a repository."""
        analyzer = LocalRepoAnalyzer()
        analysis = analyzer.analyze(sample_repo)

        assert analysis.repository.name == sample_repo.name
        assert len(analysis.files) > 0
        assert analysis.total_tokens > 0

    def test_analyze_respects_max_tokens(self, sample_repo: Path) -> None:
        """Test that analysis respects max_tokens limit."""
        # Very small token limit
        analyzer = LocalRepoAnalyzer(max_tokens=50)
        analysis = analyzer.analyze(sample_repo)

        assert analysis.truncated is True
        assert len(analysis.skipped_files) > 0
        assert analysis.total_tokens <= 50

    def test_analyze_prioritizes_readme(self, sample_repo: Path) -> None:
        """Test that README is prioritized."""
        analyzer = LocalRepoAnalyzer()
        analysis = analyzer.analyze(sample_repo)

        # README should be first file
        assert analysis.files[0].path == "README.md"

    def test_analyze_prioritizes_config(self, sample_repo: Path) -> None:
        """Test that config files are prioritized."""
        analyzer = LocalRepoAnalyzer()
        analysis = analyzer.analyze(sample_repo)

        # pyproject.toml should be early (after README)
        paths = [f.path for f in analysis.files]
        readme_idx = paths.index("README.md")
        pyproject_idx = paths.index("pyproject.toml")

        # pyproject.toml should be right after README
        assert pyproject_idx == readme_idx + 1

    def test_analyze_detects_language(self, sample_repo: Path) -> None:
        """Test language detection from files."""
        analyzer = LocalRepoAnalyzer()
        analysis = analyzer.analyze(sample_repo)

        assert analysis.repository.language == "Python"

    def test_analyze_builds_directory_structure(self, sample_repo: Path) -> None:
        """Test directory structure generation."""
        analyzer = LocalRepoAnalyzer()
        analysis = analyzer.analyze(sample_repo)

        assert "src/" in analysis.directory_structure
        assert "main.py" in analysis.directory_structure

    def test_analyze_with_custom_name(self, sample_repo: Path) -> None:
        """Test analysis with custom repo name."""
        analyzer = LocalRepoAnalyzer()
        analysis = analyzer.analyze(sample_repo, name="custom-name")

        assert analysis.repository.name == "custom-name"
        assert analysis.repository.full_name == "custom-name"

    def test_analyze_nonexistent_path(self, tmp_path: Path) -> None:
        """Test error handling for nonexistent path."""
        analyzer = LocalRepoAnalyzer()

        with pytest.raises(ValueError, match="does not exist"):
            analyzer.analyze(tmp_path / "nonexistent")

    def test_analyze_file_instead_of_dir(self, tmp_path: Path) -> None:
        """Test error handling when path is a file."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        analyzer = LocalRepoAnalyzer()

        with pytest.raises(ValueError, match="not a directory"):
            analyzer.analyze(file_path)

    def test_analyze_skips_hidden_directories(self, tmp_path: Path) -> None:
        """Test that hidden directories are skipped."""
        # Create a hidden directory with files
        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "secret.py").write_text("SECRET = 'value'")

        # Create a normal file
        (tmp_path / "main.py").write_text("print('hello')")

        analyzer = LocalRepoAnalyzer()
        analysis = analyzer.analyze(tmp_path)

        paths = [f.path for f in analysis.files]
        assert "main.py" in paths
        assert ".hidden/secret.py" not in paths

    def test_analyze_filters_binary_files(self, tmp_path: Path) -> None:
        """Test that binary files are filtered out."""
        # Create a text file
        (tmp_path / "main.py").write_text("print('hello')")

        # Create a "binary" file (by extension)
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        analyzer = LocalRepoAnalyzer()
        analysis = analyzer.analyze(tmp_path)

        paths = [f.path for f in analysis.files]
        assert "main.py" in paths
        assert "image.png" not in paths


class TestAnalyzeLocalRepoFunction:
    """Tests for the convenience function."""

    def test_analyze_local_repo(self, tmp_path: Path) -> None:
        """Test the convenience function."""
        from josephus.analyzer import analyze_local_repo

        (tmp_path / "main.py").write_text("print('hello')")

        analysis = analyze_local_repo(tmp_path)

        assert analysis.repository.name == tmp_path.name
        assert len(analysis.files) == 1
