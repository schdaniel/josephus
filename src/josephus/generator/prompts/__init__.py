"""Prompt templates for documentation generation.

This module provides Jinja2-based XML templates for LLM prompts.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Template directory
TEMPLATE_DIR = Path(__file__).parent

# Jinja2 environment for loading templates
_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_template(template_name: str, **kwargs: object) -> str:
    """Render a prompt template with the given context.

    Args:
        template_name: Name of the template file (e.g., "system_prompt.xml.j2")
        **kwargs: Variables to pass to the template

    Returns:
        Rendered template string
    """
    template = _env.get_template(template_name)
    return template.render(**kwargs)


def get_system_prompt() -> str:
    """Get the system prompt for documentation generation."""
    return render_template("system_prompt.xml.j2")


def build_generation_prompt(
    repo_context: str,
    guidelines: str = "",
    existing_docs: str = "",
    structure_plan: str = "",
    audience_context: str = "",
) -> str:
    """Build the prompt for documentation generation.

    Args:
        repo_context: XML-formatted repository context
        guidelines: User's documentation guidelines
        existing_docs: Existing documentation to consider
        structure_plan: Pre-planned documentation structure
        audience_context: Inferred audience context

    Returns:
        Formatted prompt string
    """
    return render_template(
        "generation_prompt.xml.j2",
        repo_context=repo_context,
        guidelines=guidelines,
        existing_docs=existing_docs,
        structure_plan=structure_plan,
        audience_context=audience_context,
    )


def build_refinement_prompt(
    generated_docs: dict[str, str],
    feedback: str,
) -> str:
    """Build prompt for refining generated documentation.

    Args:
        generated_docs: Previously generated documentation
        feedback: User feedback or refinement instructions

    Returns:
        Formatted prompt string
    """
    return render_template(
        "refinement_prompt.xml.j2",
        generated_docs=generated_docs,
        feedback=feedback,
    )


def get_fix_system_prompt() -> str:
    """Get the system prompt for fixing documentation."""
    return render_template("fix_prompt.xml.j2")


def build_fix_prompt(
    content: str,
    guidelines: str,
    deviations: list[str],
) -> str:
    """Build the prompt for fixing documentation to adhere to guidelines.

    Args:
        content: Original documentation content
        guidelines: Guidelines to follow
        deviations: List of specific deviations to fix

    Returns:
        Formatted prompt string
    """
    return render_template(
        "fix_user_prompt.xml.j2",
        content=content,
        guidelines=guidelines,
        deviations=deviations,
    )


# Legacy exports for backwards compatibility
SYSTEM_PROMPT = get_system_prompt()

__all__ = [
    "SYSTEM_PROMPT",
    "build_generation_prompt",
    "build_refinement_prompt",
    "get_system_prompt",
    "get_fix_system_prompt",
    "build_fix_prompt",
    "render_template",
]
