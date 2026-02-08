"""LLM-as-judge for evaluating documentation quality."""

import json
import re
from typing import Any

import logfire

from josephus.eval.metrics import GuidelinesAdherenceScores, JudgeScores
from josephus.llm import LLMProvider, get_provider
from josephus.templates import render_template


def get_judge_system_prompt() -> str:
    """Get the system prompt for documentation judging.

    Returns:
        Rendered system prompt
    """
    return render_template("judge_system.xml.j2")


def build_judge_prompt(
    generated: str,
    expected: str,
    code_context: str,
) -> str:
    """Build prompt for documentation evaluation.

    Args:
        generated: Generated documentation content
        expected: Ground truth reference documentation
        code_context: Relevant source code for verification

    Returns:
        Formatted prompt string
    """
    return render_template(
        "judge.xml.j2",
        generated=generated,
        expected=expected,
        code_context=code_context[:50000],  # Limit code context size
    )


def get_guidelines_judge_system_prompt() -> str:
    """Get the system prompt for guidelines adherence judging.

    Returns:
        Rendered system prompt
    """
    return render_template("guidelines_judge_system.xml.j2")


def build_guidelines_judge_prompt(
    documentation: str,
    guidelines: str,
) -> str:
    """Build prompt for guidelines adherence evaluation.

    Args:
        documentation: Generated documentation content
        guidelines: Guidelines the documentation should follow

    Returns:
        Formatted prompt string
    """
    return render_template(
        "guidelines_judge.xml.j2",
        documentation=documentation[:50000],  # Limit size
        guidelines=guidelines,
    )


# Backwards compatibility
JUDGE_SYSTEM_PROMPT = get_judge_system_prompt()
JUDGE_PROMPT_TEMPLATE = None  # Deprecated, use build_judge_prompt instead
GUIDELINES_JUDGE_SYSTEM_PROMPT = get_guidelines_judge_system_prompt()
GUIDELINES_JUDGE_PROMPT_TEMPLATE = None  # Deprecated, use build_guidelines_judge_prompt instead


class DocumentationJudge:
    """LLM-based judge for evaluating documentation quality."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """Initialize the judge.

        Args:
            provider: LLM provider to use. Defaults to configured provider.
        """
        self._provider = provider
        self._owns_provider = provider is None

    async def _get_provider(self) -> LLMProvider:
        """Get or create LLM provider."""
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    async def evaluate(
        self,
        generated: str,
        expected: str,
        code_context: str,
    ) -> JudgeScores:
        """Evaluate generated documentation against ground truth.

        Args:
            generated: Generated documentation content
            expected: Ground truth reference documentation
            code_context: Relevant source code for verification

        Returns:
            JudgeScores with ratings and issues
        """
        provider = await self._get_provider()

        prompt = build_judge_prompt(
            generated=generated,
            expected=expected,
            code_context=code_context,
        )

        logfire.info(
            "Running LLM judge evaluation",
            generated_len=len(generated),
            expected_len=len(expected),
            code_context_len=len(code_context),
        )

        response = await provider.generate(
            prompt=prompt,
            system=get_judge_system_prompt(),
            max_tokens=1024,
            temperature=0.1,  # Low temperature for consistent evaluation
        )

        scores = self._parse_response(response.content)

        logfire.info(
            "LLM judge evaluation complete",
            accuracy=scores.accuracy,
            completeness=scores.completeness,
            clarity=scores.clarity,
            hallucination_free=scores.hallucination_free,
            issues_count=len(scores.issues),
        )

        return scores

    def _parse_response(self, response: str) -> JudgeScores:
        """Parse LLM response into JudgeScores.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed JudgeScores
        """
        # Try to extract JSON from response
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if not json_match:
            logfire.warn("Could not find JSON in judge response", response=response[:500])
            return JudgeScores(
                accuracy=3.0,
                completeness=3.0,
                clarity=3.0,
                hallucination_free=3.0,
                issues=["Failed to parse judge response"],
            )

        try:
            data: dict[str, Any] = json.loads(json_match.group())

            return JudgeScores(
                accuracy=self._validate_score(data.get("accuracy", 3)),
                completeness=self._validate_score(data.get("completeness", 3)),
                clarity=self._validate_score(data.get("clarity", 3)),
                hallucination_free=self._validate_score(data.get("hallucinations", 3)),
                issues=data.get("issues", []) or [],
            )
        except (json.JSONDecodeError, ValueError) as e:
            logfire.warn(
                "Failed to parse judge response JSON",
                error=str(e),
                response=response[:500],
            )
            return JudgeScores(
                accuracy=3.0,
                completeness=3.0,
                clarity=3.0,
                hallucination_free=3.0,
                issues=[f"Failed to parse: {e}"],
            )

    def _validate_score(self, score: Any) -> float:
        """Validate and clamp score to 1-5 range."""
        try:
            value = float(score)
            return max(1.0, min(5.0, value))
        except (TypeError, ValueError):
            return 3.0

    async def close(self) -> None:
        """Close the LLM provider if we own it."""
        if self._owns_provider and self._provider is not None:
            await self._provider.close()
            self._provider = None


async def evaluate_documentation(
    generated: str,
    expected: str,
    code_context: str,
    provider: LLMProvider | None = None,
) -> JudgeScores:
    """Convenience function to evaluate documentation.

    Args:
        generated: Generated documentation content
        expected: Ground truth reference documentation
        code_context: Relevant source code for verification
        provider: Optional LLM provider

    Returns:
        JudgeScores with ratings and issues
    """
    judge = DocumentationJudge(provider)
    try:
        return await judge.evaluate(generated, expected, code_context)
    finally:
        await judge.close()


class GuidelinesJudge:
    """LLM-based judge for evaluating guidelines adherence."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """Initialize the judge.

        Args:
            provider: LLM provider to use. Defaults to configured provider.
        """
        self._provider = provider
        self._owns_provider = provider is None

    async def _get_provider(self) -> LLMProvider:
        """Get or create LLM provider."""
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    async def evaluate(
        self,
        documentation: str,
        guidelines: str,
    ) -> GuidelinesAdherenceScores:
        """Evaluate documentation adherence to guidelines.

        Args:
            documentation: Generated documentation content
            guidelines: Guidelines the documentation should follow

        Returns:
            GuidelinesAdherenceScores with ratings and deviations
        """
        provider = await self._get_provider()

        prompt = build_guidelines_judge_prompt(
            documentation=documentation,
            guidelines=guidelines,
        )

        logfire.info(
            "Running guidelines adherence evaluation",
            documentation_len=len(documentation),
            guidelines_len=len(guidelines),
        )

        response = await provider.generate(
            prompt=prompt,
            system=get_guidelines_judge_system_prompt(),
            max_tokens=1024,
            temperature=0.1,  # Low temperature for consistent evaluation
        )

        scores = self._parse_response(response.content)

        logfire.info(
            "Guidelines adherence evaluation complete",
            tone=scores.tone_adherence,
            format=scores.format_adherence,
            content=scores.content_adherence,
            overall=scores.overall_adherence,
            deviations_count=len(scores.deviations),
        )

        return scores

    def _parse_response(self, response: str) -> GuidelinesAdherenceScores:
        """Parse LLM response into GuidelinesAdherenceScores.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed GuidelinesAdherenceScores
        """
        # Try to extract JSON from response
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if not json_match:
            logfire.warn(
                "Could not find JSON in guidelines judge response", response=response[:500]
            )
            return GuidelinesAdherenceScores(
                tone_adherence=3.0,
                format_adherence=3.0,
                content_adherence=3.0,
                overall_adherence=3.0,
                deviations=["Failed to parse judge response"],
            )

        try:
            data: dict[str, Any] = json.loads(json_match.group())

            return GuidelinesAdherenceScores(
                tone_adherence=self._validate_score(data.get("tone_adherence", 3)),
                format_adherence=self._validate_score(data.get("format_adherence", 3)),
                content_adherence=self._validate_score(data.get("content_adherence", 3)),
                overall_adherence=self._validate_score(data.get("overall_adherence", 3)),
                deviations=data.get("deviations", []) or [],
            )
        except (json.JSONDecodeError, ValueError) as e:
            logfire.warn(
                "Failed to parse guidelines judge response JSON",
                error=str(e),
                response=response[:500],
            )
            return GuidelinesAdherenceScores(
                tone_adherence=3.0,
                format_adherence=3.0,
                content_adherence=3.0,
                overall_adherence=3.0,
                deviations=[f"Failed to parse: {e}"],
            )

    def _validate_score(self, score: Any) -> float:
        """Validate and clamp score to 1-5 range."""
        try:
            value = float(score)
            return max(1.0, min(5.0, value))
        except (TypeError, ValueError):
            return 3.0

    async def close(self) -> None:
        """Close the LLM provider if we own it."""
        if self._owns_provider and self._provider is not None:
            await self._provider.close()
            self._provider = None


async def evaluate_guidelines_adherence(
    documentation: str,
    guidelines: str,
    provider: LLMProvider | None = None,
) -> GuidelinesAdherenceScores:
    """Convenience function to evaluate guidelines adherence.

    Args:
        documentation: Generated documentation content
        guidelines: Guidelines the documentation should follow
        provider: Optional LLM provider

    Returns:
        GuidelinesAdherenceScores with ratings and deviations
    """
    judge = GuidelinesJudge(provider)
    try:
        return await judge.evaluate(documentation, guidelines)
    finally:
        await judge.close()
