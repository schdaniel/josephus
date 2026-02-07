"""Template loader for XML/Jinja2 prompt templates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


def get_template_dirs() -> list[Path]:
    """Get the list of template directories.

    Returns:
        List of paths to template directories
    """
    base = Path(__file__).parent.parent
    return [
        base / "generator" / "prompts",
        base / "eval" / "prompts",
    ]


class TemplateLoader:
    """Loads and renders XML/Jinja2 templates for prompts.

    Templates are stored in:
    - src/josephus/generator/prompts/ - for generation-related prompts
    - src/josephus/eval/prompts/ - for evaluation-related prompts
    """

    def __init__(self, template_dirs: list[Path] | None = None) -> None:
        """Initialize the template loader.

        Args:
            template_dirs: Optional list of directories to search for templates.
                          Defaults to the standard prompt directories.
        """
        if template_dirs is None:
            template_dirs = get_template_dirs()

        # Ensure all directories exist
        for d in template_dirs:
            d.mkdir(parents=True, exist_ok=True)

        self._env = Environment(
            loader=FileSystemLoader([str(d) for d in template_dirs]),
            autoescape=False,  # Disable autoescape for prompt templates
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **context: Any) -> str:
        """Render a template with the given context.

        Args:
            template_name: Name of the template file (e.g., "system.xml.j2")
            **context: Variables to pass to the template

        Returns:
            Rendered template content

        Raises:
            jinja2.TemplateNotFound: If template doesn't exist
        """
        template = self._env.get_template(template_name)
        return template.render(**context)

    def get_template_content(self, template_name: str) -> str:
        """Get the raw content of a template without rendering.

        Args:
            template_name: Name of the template file

        Returns:
            Raw template content

        Raises:
            jinja2.TemplateNotFound: If template doesn't exist
        """
        template = self._env.get_template(template_name)
        return template.module.__loader__.get_source(self._env, template_name)[0]

    def list_templates(self) -> list[str]:
        """List all available templates.

        Returns:
            List of template names
        """
        return self._env.list_templates(extensions=["j2", "xml.j2"])


@lru_cache(maxsize=1)
def get_template_loader() -> TemplateLoader:
    """Get the global template loader instance.

    Returns:
        Singleton TemplateLoader instance
    """
    return TemplateLoader()


def render_template(template_name: str, **context: Any) -> str:
    """Convenience function to render a template.

    Args:
        template_name: Name of the template file
        **context: Variables to pass to the template

    Returns:
        Rendered template content
    """
    return get_template_loader().render(template_name, **context)
