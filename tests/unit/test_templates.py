"""Unit tests for the template system."""

import pytest

from josephus.templates import get_template_loader, render_template
from josephus.templates.loader import get_template_loader as _get_template_loader


@pytest.fixture(autouse=True)
def clear_template_cache() -> None:
    """Clear the template loader cache before each test."""
    _get_template_loader.cache_clear()


class TestTemplateLoader:
    """Tests for TemplateLoader."""

    def test_list_templates(self) -> None:
        """Test listing available templates."""
        loader = get_template_loader()
        templates = loader.list_templates()

        # Should have at least the core templates
        assert "system.xml.j2" in templates
        assert "generation.xml.j2" in templates
        assert "refinement.xml.j2" in templates

    def test_render_system_template(self) -> None:
        """Test rendering the system prompt template."""
        result = render_template("system.xml.j2")

        # Should contain key elements
        assert "<system>" in result
        assert "Josephus" in result
        assert "technical writer" in result

    def test_render_generation_template_minimal(self) -> None:
        """Test rendering generation template with minimal context."""
        result = render_template(
            "generation.xml.j2",
            repo_context="<repo>test-repo</repo>",
        )

        assert "<prompt>" in result
        assert "<repo>test-repo</repo>" in result
        assert "repository_context" in result

    def test_render_generation_template_full(self) -> None:
        """Test rendering generation template with all optional fields."""
        result = render_template(
            "generation.xml.j2",
            repo_context="<repo>test-repo</repo>",
            guidelines="Be concise",
            existing_docs="# Existing",
            structure_plan="docs/index.md",
            audience_context="Developers",
        )

        assert "<user_guidelines>" in result
        assert "Be concise" in result
        assert "<existing_documentation>" in result
        assert "<documentation_structure_plan>" in result
        assert "<target_audience>" in result

    def test_render_refinement_template(self) -> None:
        """Test rendering refinement template."""
        result = render_template(
            "refinement.xml.j2",
            generated_docs={"docs/index.md": "# Welcome"},
            feedback="Add more examples",
        )

        assert "docs/index.md" in result
        assert "# Welcome" in result
        assert "Add more examples" in result

    def test_render_planning_templates(self) -> None:
        """Test rendering planning templates."""
        system = render_template("planning_system.xml.j2")
        assert "<system>" in system
        assert "documentation structure" in system

        prompt = render_template(
            "planning.xml.j2",
            repo_context="<repo>test</repo>",
            guidelines="Focus on API docs",
        )
        assert "<prompt>" in prompt
        assert "Focus on API docs" in prompt

    def test_render_fix_templates(self) -> None:
        """Test rendering fix templates."""
        system = render_template("fix_system.xml.j2")
        assert "<system>" in system
        assert "revise" in system.lower()

        prompt = render_template(
            "fix.xml.j2",
            content="# Test content",
            guidelines="Be formal",
            deviations=["Too informal", "Missing examples"],
        )
        assert "# Test content" in prompt
        assert "Be formal" in prompt
        assert "Too informal" in prompt
        assert "Missing examples" in prompt

    def test_render_judge_templates(self) -> None:
        """Test rendering judge templates."""
        system = render_template("judge_system.xml.j2")
        assert "<system>" in system
        assert "evaluator" in system

        prompt = render_template(
            "judge.xml.j2",
            generated="# Generated doc",
            expected="# Expected doc",
            code_context="def main(): pass",
        )
        assert "# Generated doc" in prompt
        assert "# Expected doc" in prompt
        assert "def main(): pass" in prompt

    def test_render_guidelines_judge_templates(self) -> None:
        """Test rendering guidelines judge templates."""
        system = render_template("guidelines_judge_system.xml.j2")
        assert "<system>" in system
        assert "adherence" in system.lower()

        prompt = render_template(
            "guidelines_judge.xml.j2",
            documentation="# Test doc",
            guidelines="Be formal and technical",
        )
        assert "# Test doc" in prompt
        assert "Be formal and technical" in prompt

    def test_render_guidelines_template(self) -> None:
        """Test rendering guidelines configuration template."""
        result = render_template("guidelines_template.xml.j2")

        assert "<guidelines_template>" in result
        assert "Audience" in result
        assert "Tone" in result
        assert "Scope" in result

    def test_template_not_found(self) -> None:
        """Test error when template doesn't exist."""
        from jinja2 import TemplateNotFound

        with pytest.raises(TemplateNotFound):
            render_template("nonexistent.xml.j2")
