"""Prompts for documentation generation."""

SYSTEM_PROMPT = """You are Josephus, an expert technical writer specializing in creating \
clear, user-friendly documentation for software projects.

Your task is to generate customer-facing documentation based on the provided codebase. \
Focus on helping users understand and use the software, not on internal implementation details.

Guidelines:
- Write for the target audience specified in the guidelines (technical or non-technical)
- Use clear, concise language
- Include practical examples where helpful
- Organize content logically with clear headings
- Focus on "what" and "how" for users, not "why" for developers
- Skip internal utilities, test helpers, and developer-only features
- Generate valid markdown with proper formatting

Output format:
- Return documentation as a JSON object with file paths as keys and markdown content as values
- Use standard documentation structure (getting-started, installation, features, etc.)
- Each file should be self-contained but link to related pages where appropriate"""


def build_generation_prompt(
    repo_context: str,
    guidelines: str = "",
    existing_docs: str = "",
) -> str:
    """Build the prompt for documentation generation.

    Args:
        repo_context: XML-formatted repository context
        guidelines: User's documentation guidelines
        existing_docs: Existing documentation to consider

    Returns:
        Formatted prompt string
    """
    parts = [
        "Generate comprehensive customer-facing documentation for this repository.",
        "",
        repo_context,
    ]

    if guidelines:
        parts.extend(
            [
                "",
                "<user_guidelines>",
                guidelines,
                "</user_guidelines>",
            ]
        )

    if existing_docs:
        parts.extend(
            [
                "",
                "<existing_documentation>",
                existing_docs,
                "</existing_documentation>",
                "",
                "Consider the existing documentation style and content, but feel free to improve or restructure.",
            ]
        )

    parts.extend(
        [
            "",
            "Generate documentation files as a JSON object. Example format:",
            "```json",
            "{",
            '  "docs/index.md": "# Project Name\\n\\nWelcome to...",',
            '  "docs/getting-started.md": "# Getting Started\\n\\n## Installation...",',
            '  "docs/features/feature-a.md": "# Feature A\\n\\n..."',
            "}",
            "```",
            "",
            "Requirements:",
            "- Include at minimum: index.md (overview), getting-started.md (installation & quickstart)",
            "- Add feature documentation for each major user-facing feature",
            "- Use clear section headings",
            "- Include code examples where appropriate",
            "- Return ONLY the JSON object, no additional text",
        ]
    )

    return "\n".join(parts)


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
    docs_text = "\n\n".join(
        f"### {path}\n```markdown\n{content}\n```" for path, content in generated_docs.items()
    )

    return f"""Refine the following documentation based on the feedback provided.

<current_documentation>
{docs_text}
</current_documentation>

<feedback>
{feedback}
</feedback>

Return the refined documentation as a JSON object with the same format (file paths as keys, markdown content as values).
Only include files that need changes. Return ONLY the JSON object, no additional text."""
