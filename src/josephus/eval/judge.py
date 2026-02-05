"""LLM-as-judge for evaluating documentation quality."""

import json
import re
from typing import Any

import logfire

from josephus.eval.metrics import JudgeScores
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
