"""Prompts for documentation generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from josephus.templates import render_template

if TYPE_CHECKING:
    from josephus.generator.planning import PlannedFile


def get_system_prompt() -> str:
    """Get the system prompt for documentation generation.

    Returns:
        Rendered system prompt
    """
    return render_template("system.xml.j2")


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
        structure_plan: Pre-planned documentation structure (from DocStructurePlan.to_prompt_context())
        audience_context: Inferred audience context (from AudienceInference.to_prompt_context())

    Returns:
        Formatted prompt string
    """
    return render_template(
        "generation.xml.j2",
        repo_context=repo_context,
        guidelines=guidelines,
        existing_docs=existing_docs,
        structure_plan=structure_plan,
        audience_context=audience_context,
    )


def build_page_generation_prompt(
    repo_context: str,
    planned_file: PlannedFile,
    structure_plan: str = "",
    audience_context: str = "",
    guidelines: str = "",
    generated_manifest: dict[str, str] | None = None,
) -> str:
    """Build the prompt for generating a single documentation page.

    Args:
        repo_context: XML-formatted repository context (subset of relevant files)
        planned_file: The specific PlannedFile to generate
        structure_plan: Full documentation structure plan context
        audience_context: Inferred audience context
        guidelines: User's documentation guidelines
        generated_manifest: Dict of already-generated page paths to titles

    Returns:
        Formatted prompt string
    """
    return render_template(
        "generation_page.xml.j2",
        repo_context=repo_context,
        planned_file=planned_file,
        structure_plan=structure_plan,
        audience_context=audience_context,
        guidelines=guidelines,
        generated_manifest=generated_manifest or {},
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
        "refinement.xml.j2",
        generated_docs=generated_docs,
        feedback=feedback,
    )


# Backwards compatibility - lazily evaluated property
class _SystemPromptProxy:
    """Proxy for lazy loading of SYSTEM_PROMPT."""

    _value: str | None = None

    def __str__(self) -> str:
        if self._value is None:
            self._value = get_system_prompt()
        return self._value

    def __repr__(self) -> str:
        return str(self)


# For backwards compatibility with code that imports SYSTEM_PROMPT directly
SYSTEM_PROMPT = _SystemPromptProxy()
