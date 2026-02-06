"""Documentation generator."""

from josephus.generator.docs import (
    DocGenerator,
    GeneratedDocs,
    GenerationConfig,
    generate_docs,
)
from josephus.generator.planning import (
    DocPlanner,
    DocStructurePlan,
    PlannedFile,
    PlannedSection,
)
from josephus.generator.prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_refinement_prompt,
)
from josephus.generator.validation import (
    ValidationAgent,
    ValidationReport,
    ValidationResult,
    validate_and_fix_docs,
)

__all__ = [
    "DocGenerator",
    "DocPlanner",
    "DocStructurePlan",
    "GeneratedDocs",
    "GenerationConfig",
    "PlannedFile",
    "PlannedSection",
    "SYSTEM_PROMPT",
    "ValidationAgent",
    "ValidationReport",
    "ValidationResult",
    "build_generation_prompt",
    "build_refinement_prompt",
    "generate_docs",
    "validate_and_fix_docs",
]
