"""LLM-as-judge for evaluating documentation quality."""

import json
import re
from typing import Any

import logfire

from josephus.eval.metrics import GuidelinesAdherenceScores, JudgeScores
from josephus.llm import LLMProvider, get_provider

JUDGE_SYSTEM_PROMPT = """You are an expert documentation evaluator. Your task is to assess the quality of AI-generated documentation against ground truth reference documentation and source code.

You will evaluate documentation on four dimensions:
1. Factual accuracy: Are all claims supported by the source code?
2. Completeness: Are all features from the ground truth covered?
3. Clarity: Would a non-technical user understand this?
4. No hallucinations: Are there any invented features or incorrect behavior described?

Always respond with valid JSON in the specified format."""


JUDGE_PROMPT_TEMPLATE = """Evaluate the following AI-generated documentation against the ground truth reference.

<generated_documentation>
{generated}
</generated_documentation>

<ground_truth_reference>
{expected}
</ground_truth_reference>

<source_code_context>
{code_context}
</source_code_context>

Rate the generated documentation on each dimension from 1-5:
- 1: Very poor / completely wrong
- 2: Poor / mostly wrong
- 3: Acceptable / partially correct
- 4: Good / mostly correct
- 5: Excellent / fully correct

Return your evaluation as JSON with this exact structure:
{{
    "accuracy": <1-5>,
    "completeness": <1-5>,
    "clarity": <1-5>,
    "hallucinations": <1-5>,
    "issues": ["list of specific issues found, if any"]
}}

Important:
- For "hallucinations", 5 means NO hallucinations (perfect), 1 means many hallucinations
- Be strict but fair in your assessment
- List specific issues in the "issues" array"""


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

        prompt = JUDGE_PROMPT_TEMPLATE.format(
            generated=generated,
            expected=expected,
            code_context=code_context[:50000],  # Limit code context size
        )

        logfire.info(
            "Running LLM judge evaluation",
            generated_len=len(generated),
            expected_len=len(expected),
            code_context_len=len(code_context),
        )

        response = await provider.generate(
            prompt=prompt,
            system=JUDGE_SYSTEM_PROMPT,
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


GUIDELINES_JUDGE_SYSTEM_PROMPT = """You are an expert documentation reviewer. Your task is to evaluate whether generated documentation adheres to specified guidelines.

You will assess how well the documentation follows the provided guidelines across multiple dimensions:
1. Tone adherence: Does the writing style match the guidelines' tone requirements?
2. Format adherence: Does the structure/format match what's specified in guidelines?
3. Content adherence: Does the content cover topics/aspects specified in guidelines?
4. Overall adherence: How well does the documentation follow all guidelines overall?

Always respond with valid JSON in the specified format."""


GUIDELINES_JUDGE_PROMPT_TEMPLATE = """Evaluate whether the following documentation adheres to the specified guidelines.

<documentation>
{documentation}
</documentation>

<guidelines>
{guidelines}
</guidelines>

Rate the documentation's adherence to guidelines on each dimension from 1-5:
- 1: Very poor adherence / completely ignores guidelines
- 2: Poor adherence / mostly ignores guidelines
- 3: Partial adherence / follows some guidelines
- 4: Good adherence / follows most guidelines
- 5: Excellent adherence / fully follows guidelines

Return your evaluation as JSON with this exact structure:
{{
    "tone_adherence": <1-5>,
    "format_adherence": <1-5>,
    "content_adherence": <1-5>,
    "overall_adherence": <1-5>,
    "deviations": ["list of specific guideline deviations found, if any"]
}}

Important:
- Be specific about which guidelines are or aren't followed
- List concrete deviations in the "deviations" array
- Consider both explicit and implicit guideline requirements"""


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

        prompt = GUIDELINES_JUDGE_PROMPT_TEMPLATE.format(
            documentation=documentation[:50000],  # Limit size
            guidelines=guidelines,
        )

        logfire.info(
            "Running guidelines adherence evaluation",
            documentation_len=len(documentation),
            guidelines_len=len(guidelines),
        )

        response = await provider.generate(
            prompt=prompt,
            system=GUIDELINES_JUDGE_SYSTEM_PROMPT,
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
