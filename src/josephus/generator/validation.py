"""Post-generation validation agent for checking and fixing guidelines adherence."""

from dataclasses import dataclass, field

import logfire

from josephus.eval.judge import GuidelinesJudge
from josephus.eval.metrics import GuidelinesAdherenceScores
from josephus.generator.prompts import build_fix_prompt, get_fix_system_prompt
from josephus.llm import LLMProvider


@dataclass
class ValidationResult:
    """Result of validation check for a single file."""

    file_path: str
    original_content: str
    scores: GuidelinesAdherenceScores
    fixed_content: str | None = None  # None if no fix needed or check-only mode
    was_fixed: bool = False
    fix_summary: str = ""

    @property
    def needs_fix(self) -> bool:
        """Check if the content needs fixing based on scores."""
        # Consider needing fix if overall adherence is below 4 (Good)
        return self.scores.overall_adherence < 4.0


@dataclass
class ValidationReport:
    """Complete validation report for all generated docs."""

    file_results: list[ValidationResult] = field(default_factory=list)
    guidelines: str = ""
    check_only: bool = False

    @property
    def total_files(self) -> int:
        return len(self.file_results)

    @property
    def files_needing_fix(self) -> int:
        return sum(1 for r in self.file_results if r.needs_fix)

    @property
    def files_fixed(self) -> int:
        return sum(1 for r in self.file_results if r.was_fixed)

    @property
    def average_adherence(self) -> float:
        if not self.file_results:
            return 0.0
        return sum(r.scores.overall_adherence for r in self.file_results) / len(self.file_results)

    @property
    def all_deviations(self) -> list[str]:
        """Get all deviations across all files."""
        deviations = []
        for result in self.file_results:
            for deviation in result.scores.deviations:
                deviations.append(f"{result.file_path}: {deviation}")
        return deviations

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_files": self.total_files,
            "files_needing_fix": self.files_needing_fix,
            "files_fixed": self.files_fixed,
            "average_adherence": self.average_adherence,
            "check_only": self.check_only,
            "deviations": self.all_deviations,
            "file_results": [
                {
                    "file_path": r.file_path,
                    "overall_adherence": r.scores.overall_adherence,
                    "needs_fix": r.needs_fix,
                    "was_fixed": r.was_fixed,
                    "fix_summary": r.fix_summary,
                    "deviations": r.scores.deviations,
                }
                for r in self.file_results
            ],
        }


class ValidationAgent:
    """Agent for validating and fixing documentation against guidelines.

    Runs after documentation generation to ensure adherence to guidelines.
    Can operate in check-only mode or automatically fix issues.
    """

    def __init__(
        self,
        llm: LLMProvider,
        adherence_threshold: float = 4.0,
    ) -> None:
        """Initialize the validation agent.

        Args:
            llm: LLM provider for validation and fixes
            adherence_threshold: Minimum adherence score (1-5) to pass without fixing
        """
        self.llm = llm
        self.adherence_threshold = adherence_threshold
        self._judge = GuidelinesJudge(llm)

    async def validate(
        self,
        docs: dict[str, str],
        guidelines: str,
        check_only: bool = False,
    ) -> ValidationReport:
        """Validate documentation against guidelines.

        Args:
            docs: Dict of file_path -> content for generated docs
            guidelines: Guidelines the docs should follow
            check_only: If True, only check without fixing

        Returns:
            ValidationReport with results and fixes
        """
        logfire.info(
            "Starting documentation validation",
            file_count=len(docs),
            guidelines_length=len(guidelines),
            check_only=check_only,
        )

        if not guidelines.strip():
            logfire.warn("No guidelines provided, skipping validation")
            return ValidationReport(
                file_results=[],
                guidelines="",
                check_only=check_only,
            )

        results: list[ValidationResult] = []

        for file_path, content in docs.items():
            logfire.info(f"Validating {file_path}")

            # Check adherence
            scores = await self._judge.evaluate(content, guidelines)

            result = ValidationResult(
                file_path=file_path,
                original_content=content,
                scores=scores,
            )

            # Fix if needed and not in check-only mode
            if result.needs_fix and not check_only:
                logfire.info(
                    f"Fixing {file_path}",
                    adherence=scores.overall_adherence,
                    deviations=scores.deviations,
                )

                fixed_content = await self._fix_content(
                    content=content,
                    guidelines=guidelines,
                    deviations=scores.deviations,
                )

                if fixed_content and fixed_content != content:
                    result.fixed_content = fixed_content
                    result.was_fixed = True
                    result.fix_summary = self._generate_fix_summary(scores.deviations)

                    logfire.info(
                        f"Fixed {file_path}",
                        changes_made=result.fix_summary,
                    )

            results.append(result)

        report = ValidationReport(
            file_results=results,
            guidelines=guidelines,
            check_only=check_only,
        )

        logfire.info(
            "Validation complete",
            total_files=report.total_files,
            files_needing_fix=report.files_needing_fix,
            files_fixed=report.files_fixed,
            average_adherence=report.average_adherence,
        )

        return report

    async def _fix_content(
        self,
        content: str,
        guidelines: str,
        deviations: list[str],
    ) -> str | None:
        """Fix content to better adhere to guidelines.

        Args:
            content: Original documentation content
            guidelines: Guidelines to follow
            deviations: List of specific deviations to fix

        Returns:
            Fixed content, or None if fix failed
        """
        if not deviations:
            return content

        prompt = build_fix_prompt(
            content=content,
            guidelines=guidelines,
            deviations=deviations,
        )

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system=get_fix_system_prompt(),
                max_tokens=len(content) * 2,  # Allow some expansion
                temperature=0.3,  # Lower temperature for more consistent fixes
            )

            # Clean up the response
            fixed = response.content.strip()

            # Remove any markdown code fences if present
            if fixed.startswith("```") and fixed.endswith("```"):
                lines = fixed.split("\n")
                fixed = "\n".join(lines[1:-1])

            return fixed

        except Exception as e:
            logfire.error("Failed to fix content", error=str(e))
            return None

    def _generate_fix_summary(self, deviations: list[str]) -> str:
        """Generate a human-readable summary of fixes made."""
        if not deviations:
            return "No specific fixes made"

        if len(deviations) == 1:
            return f"Fixed: {deviations[0]}"

        return f"Fixed {len(deviations)} issues: {', '.join(deviations[:3])}" + (
            f" (+{len(deviations) - 3} more)" if len(deviations) > 3 else ""
        )

    def get_fixed_docs(self, report: ValidationReport) -> dict[str, str]:
        """Get the final documentation content after fixes.

        Args:
            report: Validation report with results

        Returns:
            Dict of file_path -> content (fixed if available, original otherwise)
        """
        docs = {}
        for result in report.file_results:
            if result.was_fixed and result.fixed_content:
                docs[result.file_path] = result.fixed_content
            else:
                docs[result.file_path] = result.original_content
        return docs

    async def close(self) -> None:
        """Close the judge."""
        await self._judge.close()


async def validate_and_fix_docs(
    docs: dict[str, str],
    guidelines: str,
    llm: LLMProvider,
    check_only: bool = False,
) -> tuple[dict[str, str], ValidationReport]:
    """Convenience function to validate and fix documentation.

    Args:
        docs: Dict of file_path -> content
        guidelines: Guidelines to follow
        llm: LLM provider
        check_only: If True, only check without fixing

    Returns:
        Tuple of (fixed_docs, validation_report)
    """
    agent = ValidationAgent(llm)
    try:
        report = await agent.validate(docs, guidelines, check_only)
        fixed_docs = agent.get_fixed_docs(report)
        return fixed_docs, report
    finally:
        await agent.close()
