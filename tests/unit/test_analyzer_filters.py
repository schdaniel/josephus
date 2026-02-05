"""Unit tests for repository file filtering."""

import pytest

from josephus.analyzer.filters import FileFilter, filter_tree


class TestFileFilter:
    """Tests for FileFilter class."""

    def test_includes_python_files(self) -> None:
        """Test that Python files are included by default."""
        f = FileFilter()
        assert f.should_include("src/main.py", size=100)
        assert f.should_include("tests/test_foo.py", size=100)

    def test_includes_common_source_files(self) -> None:
        """Test that common source files are included."""
        f = FileFilter()
        assert f.should_include("index.ts", size=100)
        assert f.should_include("app.js", size=100)
        assert f.should_include("main.go", size=100)
        assert f.should_include("lib.rs", size=100)

    def test_excludes_node_modules(self) -> None:
        """Test that node_modules is excluded."""
        f = FileFilter()
        assert not f.should_include("node_modules/lodash/index.js", size=100)
        assert not f.should_include("node_modules/react/package.json", size=100)

    def test_excludes_git_directory(self) -> None:
        """Test that .git directory is excluded."""
        f = FileFilter()
        assert not f.should_include(".git/config", size=100)
        assert not f.should_include(".git/hooks/pre-commit", size=100)

    def test_excludes_binary_files(self) -> None:
        """Test that binary files are excluded."""
        f = FileFilter()
        assert not f.should_include("logo.png", size=100)
        assert not f.should_include("font.woff2", size=100)
        assert not f.should_include("archive.zip", size=100)

    def test_excludes_large_files(self) -> None:
        """Test that files over size limit are excluded."""
        f = FileFilter(max_file_size_bytes=1000)
        assert f.should_include("small.py", size=500)
        assert not f.should_include("large.py", size=2000)

    def test_excludes_lock_files(self) -> None:
        """Test that lock files are excluded."""
        f = FileFilter()
        assert not f.should_include("package-lock.json", size=100)
        assert not f.should_include("yarn.lock", size=100)
        assert not f.should_include("poetry.lock", size=100)

    def test_includes_config_files(self) -> None:
        """Test that config files are included."""
        f = FileFilter()
        assert f.should_include("pyproject.toml", size=100)
        assert f.should_include("package.json", size=100)
        assert f.should_include("tsconfig.json", size=100)

    def test_includes_markdown(self) -> None:
        """Test that markdown files are included."""
        f = FileFilter()
        assert f.should_include("README.md", size=100)
        assert f.should_include("docs/guide.md", size=100)

    def test_custom_exclude_patterns(self) -> None:
        """Test custom exclude patterns."""
        f = FileFilter(exclude_patterns=["**/generated/**"])
        assert f.should_include("src/main.py", size=100)
        assert not f.should_include("src/generated/types.py", size=100)

    def test_custom_include_patterns(self) -> None:
        """Test custom include patterns (whitelist mode)."""
        f = FileFilter(include_patterns=["src/**/*.py"])
        assert f.should_include("src/main.py", size=100)
        assert not f.should_include("tests/test_main.py", size=100)

    def test_includes_special_files(self) -> None:
        """Test that special extensionless files are included."""
        f = FileFilter()
        assert f.should_include("Makefile", size=100)
        assert f.should_include("Dockerfile", size=100)


class TestFilterTree:
    """Tests for filter_tree function."""

    def test_filters_github_tree(self) -> None:
        """Test filtering a GitHub tree response."""
        tree = [
            {"path": "README.md", "type": "blob", "size": 500},
            {"path": "src", "type": "tree"},  # Directory, should be skipped
            {"path": "src/main.py", "type": "blob", "size": 1000},
            {"path": "node_modules/lodash/index.js", "type": "blob", "size": 200},
            {"path": "logo.png", "type": "blob", "size": 50000},
        ]

        result = filter_tree(tree)

        paths = [f.path for f in result]
        assert "README.md" in paths
        assert "src/main.py" in paths
        assert "node_modules/lodash/index.js" not in paths
        assert "logo.png" not in paths

    def test_returns_filtered_file_objects(self) -> None:
        """Test that filter_tree returns FilteredFile objects."""
        tree = [
            {"path": "main.py", "type": "blob", "size": 100},
        ]

        result = filter_tree(tree)

        assert len(result) == 1
        assert result[0].path == "main.py"
        assert result[0].size == 100
        assert result[0].extension == ".py"
