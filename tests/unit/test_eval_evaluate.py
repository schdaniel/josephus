"""Unit tests for eval evaluate module."""

from pathlib import Path
from unittest.mock import patch

from josephus.eval.evaluate import (
    evaluate_all,
    evaluate_docs,
)


class TestEvaluateDocs:
    """Tests for evaluate_docs."""

    def test_evaluate_docs(self, tmp_path: Path) -> None:
        """Test evaluating docs for a single repo."""
        docs_dir = tmp_path / "test-repo"
        docs_dir.mkdir()
        (docs_dir / "docs").mkdir()

        # Create sample docs
        (docs_dir / "docs" / "index.md").write_text(
            """# Test Documentation

This is a test document with some content.

## Getting Started

Follow these steps to get started with the project.

1. Install dependencies
2. Run the application
3. Check the output

## API Reference

Here are the available functions:

```python
def hello():
    print("Hello, World!")
```
"""
        )

        result = evaluate_docs(docs_dir)

        assert "error" not in result
        assert "readability" in result
        assert "structure" in result
        assert "size" in result

        # Check readability metrics
        assert "flesch_kincaid_grade" in result["readability"]
        assert "flesch_reading_ease" in result["readability"]
        assert isinstance(result["readability"]["flesch_kincaid_grade"], float)

        # Check structure metrics
        assert "score" in result["structure"]
        assert "heading_count" in result["structure"]
        assert "code_block_count" in result["structure"]

        # Check size metrics
        assert result["size"]["word_count"] > 0
        assert result["size"]["char_count"] > 0

    def test_evaluate_docs_no_docs(self, tmp_path: Path) -> None:
        """Test evaluate_docs when no docs exist."""
        docs_dir = tmp_path / "empty-repo"
        docs_dir.mkdir()

        result = evaluate_docs(docs_dir)

        assert "error" in result

    def test_evaluate_docs_empty_docs(self, tmp_path: Path) -> None:
        """Test evaluate_docs with empty docs."""
        docs_dir = tmp_path / "test-repo"
        docs_dir.mkdir()
        (docs_dir / "docs").mkdir()
        (docs_dir / "docs" / "index.md").write_text("")

        result = evaluate_docs(docs_dir)

        assert "readability" in result
        assert result["size"]["word_count"] == 0


class TestEvaluateAll:
    """Tests for evaluate_all."""

    @patch("josephus.eval.evaluate.load_repos_config")
    @patch("josephus.eval.evaluate.get_output_dir")
    def test_evaluate_all(
        self,
        mock_get_output_dir,
        mock_load_config,
        tmp_path: Path,
    ) -> None:
        """Test evaluating all repos."""
        # Setup
        output_dir = tmp_path / "generated"
        output_dir.mkdir()

        # Create sample repo docs
        repo_dir = output_dir / "repo1"
        repo_dir.mkdir()
        (repo_dir / "docs").mkdir()
        (repo_dir / "docs" / "index.md").write_text("# Test\n\nContent here.")

        mock_get_output_dir.return_value = output_dir
        mock_load_config.return_value = {"repo1": {"url": "url1"}}

        # Execute
        results = evaluate_all()

        # Verify
        assert "repo1" in results
        assert "error" not in results["repo1"]
        assert "readability" in results["repo1"]

    @patch("josephus.eval.evaluate.load_repos_config")
    @patch("josephus.eval.evaluate.get_output_dir")
    def test_evaluate_all_missing_repo(
        self,
        mock_get_output_dir,
        mock_load_config,
        tmp_path: Path,
    ) -> None:
        """Test evaluate_all with missing repo."""
        output_dir = tmp_path / "generated"
        output_dir.mkdir()

        mock_get_output_dir.return_value = output_dir
        mock_load_config.return_value = {"repo1": {"url": "url1"}}

        results = evaluate_all()

        assert "repo1" in results
        assert "error" in results["repo1"]

    @patch("josephus.eval.evaluate.load_repos_config")
    @patch("josephus.eval.evaluate.get_output_dir")
    def test_evaluate_all_specific_repos(
        self,
        mock_get_output_dir,
        mock_load_config,
        tmp_path: Path,
    ) -> None:
        """Test evaluating specific repos only."""
        output_dir = tmp_path / "generated"
        output_dir.mkdir()

        # Create sample repo docs
        for name in ["repo1", "repo2"]:
            repo_dir = output_dir / name
            repo_dir.mkdir()
            (repo_dir / "docs").mkdir()
            (repo_dir / "docs" / "index.md").write_text(f"# {name}")

        mock_get_output_dir.return_value = output_dir
        mock_load_config.return_value = {
            "repo1": {"url": "url1"},
            "repo2": {"url": "url2"},
        }

        results = evaluate_all(repos=["repo1"])

        assert "repo1" in results
        assert "repo2" not in results
