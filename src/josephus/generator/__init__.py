"""Documentation generator."""

from josephus.generator.docs import (
    DocGenerator,
    GeneratedDocs,
    GenerationConfig,
    generate_docs,
)
from josephus.generator.prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_refinement_prompt,
)

__all__ = [
    "DocGenerator",
    "GeneratedDocs",
    "GenerationConfig",
    "SYSTEM_PROMPT",
    "build_generation_prompt",
    "build_refinement_prompt",
    "generate_docs",
]
