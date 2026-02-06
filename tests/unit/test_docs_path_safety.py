"""Unit tests for path safety in documentation generator."""

import pytest

from josephus.generator.docs import DocGenerator
from unittest.mock import MagicMock


class TestSafePath:
    """Tests for _safe_path method to prevent path traversal."""

    @pytest.fixture
    def generator(self) -> DocGenerator:
        """Create a DocGenerator with mock LLM."""
        mock_llm = MagicMock()
        return DocGenerator(llm=mock_llm)

    def test_safe_simple_path(self, generator: DocGenerator) -> None:
        """Test that simple paths work correctly."""
        result = generator._safe_path("readme.md", "docs")
        assert result == "docs/readme.md"

    def test_safe_nested_path(self, generator: DocGenerator) -> None:
        """Test that nested paths work correctly."""
        result = generator._safe_path("api/endpoints.md", "docs")
        assert result == "docs/api/endpoints.md"

    def test_adds_md_extension(self, generator: DocGenerator) -> None:
        """Test that .md extension is added if missing."""
        result = generator._safe_path("readme", "docs")
        assert result == "docs/readme.md"

    def test_blocks_parent_traversal(self, generator: DocGenerator) -> None:
        """Test that ../ components are filtered out safely."""
        result = generator._safe_path("../../../etc/passwd", "docs")
        # After filtering ../ we get just etc/passwd which is within docs
        assert result == "docs/etc/passwd.md"

    def test_blocks_absolute_path(self, generator: DocGenerator) -> None:
        """Test that absolute paths are sanitized by removing leading /."""
        result = generator._safe_path("/etc/passwd.md", "docs")
        # Leading / is filtered, should extract etc/passwd.md
        assert result == "docs/etc/passwd.md"

    def test_blocks_mixed_traversal(self, generator: DocGenerator) -> None:
        """Test that ../ in middle of path is filtered out."""
        result = generator._safe_path("docs/foo/../../../etc/passwd", "docs")
        # After filtering ../ we get docs/foo/etc/passwd which is safe within output dir
        assert result == "docs/docs/foo/etc/passwd.md"

    def test_blocks_dot_in_middle(self, generator: DocGenerator) -> None:
        """Test that single dots are handled."""
        result = generator._safe_path("./readme.md", "docs")
        assert result == "docs/readme.md"

    def test_blocks_tilde_expansion(self, generator: DocGenerator) -> None:
        """Test that tilde paths are blocked."""
        result = generator._safe_path("~/.ssh/id_rsa", "docs")
        # Tilde components should be filtered
        assert result is None or "~" not in result

    def test_blocks_null_bytes(self, generator: DocGenerator) -> None:
        """Test that null bytes are rejected."""
        result = generator._safe_path("readme\x00.md", "docs")
        assert result is None

    def test_blocks_newlines(self, generator: DocGenerator) -> None:
        """Test that newlines are rejected."""
        result = generator._safe_path("readme\n.md", "docs")
        assert result is None

    def test_handles_empty_path(self, generator: DocGenerator) -> None:
        """Test that empty paths are rejected."""
        result = generator._safe_path("", "docs")
        assert result is None

    def test_handles_only_dots(self, generator: DocGenerator) -> None:
        """Test that paths with only dots are rejected."""
        result = generator._safe_path("...", "docs")
        assert result is None

    def test_handles_deeply_nested(self, generator: DocGenerator) -> None:
        """Test that deeply nested paths work."""
        result = generator._safe_path("a/b/c/d/e/readme.md", "docs")
        assert result == "docs/a/b/c/d/e/readme.md"

    def test_strips_whitespace(self, generator: DocGenerator) -> None:
        """Test that whitespace is stripped."""
        result = generator._safe_path("  readme.md  ", "docs")
        assert result == "docs/readme.md"

    def test_handles_leading_slash(self, generator: DocGenerator) -> None:
        """Test that leading slashes are handled."""
        result = generator._safe_path("/readme.md", "docs")
        assert result == "docs/readme.md"

    def test_different_output_dir(self, generator: DocGenerator) -> None:
        """Test with different output directory."""
        result = generator._safe_path("guide.md", "documentation/api")
        assert result == "documentation/api/guide.md"
