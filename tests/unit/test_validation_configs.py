"""Tests for validation agent with multiple configuration variations.

These tests verify that the validation agent correctly handles different
guideline configurations and identifies appropriate violations.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from josephus.eval.metrics import GuidelinesAdherenceScores
from josephus.generator.validation import (
    ValidationAgent,
    validate_and_fix_docs,
)

# Sample guideline configurations for testing
GUIDELINES = {
    "formal_tone": """# Documentation Guidelines

## Tone
- Use formal, professional language
- Avoid contractions (don't, can't, won't)
- Use third person (avoid "you" and "we")
- No slang or colloquialisms
""",
    "casual_tone": """# Documentation Guidelines

## Tone
- Use friendly, conversational language
- Contractions are encouraged for readability
- Address the reader directly with "you"
- Keep it approachable and fun
""",
    "code_examples_required": """# Documentation Guidelines

## Content Requirements
- Every function must include a code example
- Examples should be complete and runnable
- Include expected output where applicable
- Use Python for all examples
""",
    "no_code_examples": """# Documentation Guidelines

## Content Requirements
- Focus on conceptual explanations
- Avoid code snippets in main documentation
- Link to separate API reference for code details
""",
    "technical_audience": """# Documentation Guidelines

## Target Audience
- Write for experienced developers
- Assume familiarity with design patterns
- Use technical terminology without explanation
- Focus on implementation details
""",
    "beginner_audience": """# Documentation Guidelines

## Target Audience
- Write for beginners with no prior experience
- Explain all technical terms
- Provide step-by-step instructions
- Include diagrams and visual aids
""",
    "strict_formatting": """# Documentation Guidelines

## Format Requirements
- All headings must use sentence case
- Use tables for parameter documentation
- Include a "Quick Start" section at the top
- Every page must have a "See Also" section
""",
    "comprehensive": """# Documentation Guidelines

## Tone
- Use formal, professional language
- Be concise but thorough

## Content Requirements
- Include code examples for all public APIs
- Document all parameters and return values
- Include error handling examples

## Format Requirements
- Use consistent heading hierarchy
- Include navigation links
- Add version badges

## Target Audience
- Experienced developers integrating with the API
""",
}

# Sample documentation that adheres or violates guidelines
DOCS = {
    "formal_doc": """# API Reference

The authentication module provides secure token-based authentication.
Users authenticate by providing credentials to the authentication endpoint.

## authenticate()

This method validates user credentials and returns an access token.
The token should be included in subsequent API requests.
""",
    "informal_doc": """# Getting Started

Hey there! Let's get you set up with our awesome API. Don't worry,
it's super easy and you'll be up and running in no time!

## authenticate()

Just call this bad boy with your username and password, and boom -
you've got yourself a token! Can't get simpler than that!
""",
    "with_code_examples": """# API Reference

## authenticate()

Authenticates a user and returns an access token.

```python
from mylib import authenticate

token = authenticate(username="user", password="secret")
print(token)  # Output: "abc123..."
```

## get_user()

Retrieves user information.

```python
user = get_user(user_id=123)
print(user.name)  # Output: "John Doe"
```
""",
    "without_code_examples": """# API Reference

## authenticate()

Authenticates a user and returns an access token. Pass the username
and password as parameters.

## get_user()

Retrieves user information for the specified user ID.
""",
    "technical_doc": """# Implementation Details

The authentication subsystem implements OAuth 2.0 with PKCE flow.
Token refresh uses sliding window expiration with JTI-based revocation.

## Architecture

The singleton AuthManager leverages dependency injection via the
IoC container. Request middleware extracts and validates JWTs using
RS256 asymmetric signatures.
""",
    "beginner_doc": """# Getting Started Guide

Welcome! This guide will help you understand how to log in to our system.

## What is Authentication?

Authentication is how the system verifies who you are. Think of it like
showing your ID card at a building entrance.

## Step-by-Step Instructions

1. First, find your username (usually your email address)
2. Enter your password carefully
3. Click the "Login" button
4. Wait for the confirmation message
""",
    "well_formatted": """# Quick Start

Get up and running in 5 minutes.

## Installation

| Package | Version | Command |
|---------|---------|---------|
| mylib   | 1.0.0   | pip install mylib |

## Basic usage

See the examples below.

## See also

- [API Reference](./api.md)
- [Tutorials](./tutorials.md)
""",
    "poorly_formatted": """# QUICK START

Get up and running in 5 minutes.

Installation:
mylib 1.0.0 - pip install mylib

Basic Usage:
See the examples below.
""",
}


class TestValidationWithGuidelines:
    """Tests for validation against various guideline configurations."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock = AsyncMock()
        mock.generate = AsyncMock(
            return_value=MagicMock(
                content="# Fixed Content\n\nProfessionally written documentation."
            )
        )
        mock.close = AsyncMock()
        return mock

    def _create_mock_judge(
        self,
        tone: float = 4.0,
        format_score: float = 4.0,
        content: float = 4.0,
        overall: float = 4.0,
        deviations: list[str] | None = None,
    ) -> MagicMock:
        """Create a mock judge with specified scores."""
        mock = MagicMock()
        mock.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=tone,
                format_adherence=format_score,
                content_adherence=content,
                overall_adherence=overall,
                deviations=deviations or [],
            )
        )
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_formal_tone_with_informal_doc(self, mock_llm: MagicMock) -> None:
        """Test that informal docs fail formal tone guidelines."""
        agent = ValidationAgent(mock_llm)
        agent._judge = self._create_mock_judge(
            tone=2.0,  # Low tone adherence
            format_score=4.0,
            content=4.0,
            overall=2.5,  # Below threshold
            deviations=[
                "Uses contractions ('don't', 'can't')",
                "Informal language ('awesome', 'bad boy')",
                "Uses second person ('you')",
            ],
        )

        docs = {"docs/index.md": DOCS["informal_doc"]}
        report = await agent.validate(docs, GUIDELINES["formal_tone"])

        assert report.files_needing_fix == 1
        assert report.file_results[0].needs_fix is True
        assert "contractions" in str(report.file_results[0].scores.deviations).lower()

    @pytest.mark.asyncio
    async def test_formal_tone_with_formal_doc(self, mock_llm: MagicMock) -> None:
        """Test that formal docs pass formal tone guidelines."""
        agent = ValidationAgent(mock_llm)
        agent._judge = self._create_mock_judge(
            tone=4.5,
            format_score=4.0,
            content=4.0,
            overall=4.5,
            deviations=[],
        )

        docs = {"docs/index.md": DOCS["formal_doc"]}
        report = await agent.validate(docs, GUIDELINES["formal_tone"])

        assert report.files_needing_fix == 0
        assert report.file_results[0].needs_fix is False

    @pytest.mark.asyncio
    async def test_code_examples_required_without_examples(self, mock_llm: MagicMock) -> None:
        """Test that docs without code examples fail when examples required."""
        agent = ValidationAgent(mock_llm)
        agent._judge = self._create_mock_judge(
            tone=4.0,
            format_score=4.0,
            content=2.0,  # Low content adherence
            overall=2.5,
            deviations=[
                "Missing code examples for authenticate()",
                "Missing code examples for get_user()",
                "No runnable examples provided",
            ],
        )

        docs = {"docs/index.md": DOCS["without_code_examples"]}
        report = await agent.validate(docs, GUIDELINES["code_examples_required"])

        assert report.files_needing_fix == 1
        assert any("code example" in d.lower() for d in report.all_deviations)

    @pytest.mark.asyncio
    async def test_code_examples_required_with_examples(self, mock_llm: MagicMock) -> None:
        """Test that docs with code examples pass when examples required."""
        agent = ValidationAgent(mock_llm)
        agent._judge = self._create_mock_judge(
            tone=4.0,
            format_score=4.0,
            content=4.5,
            overall=4.5,
            deviations=[],
        )

        docs = {"docs/index.md": DOCS["with_code_examples"]}
        report = await agent.validate(docs, GUIDELINES["code_examples_required"])

        assert report.files_needing_fix == 0

    @pytest.mark.asyncio
    async def test_technical_audience_with_beginner_doc(self, mock_llm: MagicMock) -> None:
        """Test that beginner docs fail technical audience guidelines."""
        agent = ValidationAgent(mock_llm)
        agent._judge = self._create_mock_judge(
            tone=3.0,
            format_score=4.0,
            content=2.5,
            overall=3.0,
            deviations=[
                "Too basic for target audience",
                "Unnecessary explanations of standard concepts",
                "Missing implementation details",
            ],
        )

        docs = {"docs/index.md": DOCS["beginner_doc"]}
        report = await agent.validate(docs, GUIDELINES["technical_audience"])

        assert report.files_needing_fix == 1

    @pytest.mark.asyncio
    async def test_beginner_audience_with_technical_doc(self, mock_llm: MagicMock) -> None:
        """Test that technical docs fail beginner audience guidelines."""
        agent = ValidationAgent(mock_llm)
        agent._judge = self._create_mock_judge(
            tone=3.0,
            format_score=3.5,
            content=2.0,
            overall=2.5,
            deviations=[
                "Uses unexplained jargon (OAuth 2.0, PKCE, JWT)",
                "No step-by-step instructions",
                "Missing visual aids",
                "Assumes prior knowledge",
            ],
        )

        docs = {"docs/index.md": DOCS["technical_doc"]}
        report = await agent.validate(docs, GUIDELINES["beginner_audience"])

        assert report.files_needing_fix == 1
        assert any("jargon" in d.lower() for d in report.all_deviations)

    @pytest.mark.asyncio
    async def test_strict_formatting_with_poor_format(self, mock_llm: MagicMock) -> None:
        """Test that poorly formatted docs fail strict formatting guidelines."""
        agent = ValidationAgent(mock_llm)
        agent._judge = self._create_mock_judge(
            tone=4.0,
            format_score=2.0,  # Low format adherence
            content=4.0,
            overall=3.0,
            deviations=[
                "Heading uses all caps instead of sentence case",
                "Missing table for parameters",
                "No 'See Also' section",
            ],
        )

        docs = {"docs/index.md": DOCS["poorly_formatted"]}
        report = await agent.validate(docs, GUIDELINES["strict_formatting"])

        assert report.files_needing_fix == 1
        assert report.file_results[0].scores.format_adherence == 2.0

    @pytest.mark.asyncio
    async def test_strict_formatting_with_good_format(self, mock_llm: MagicMock) -> None:
        """Test that well-formatted docs pass strict formatting guidelines."""
        agent = ValidationAgent(mock_llm)
        agent._judge = self._create_mock_judge(
            tone=4.0,
            format_score=4.5,
            content=4.0,
            overall=4.5,
            deviations=[],
        )

        docs = {"docs/index.md": DOCS["well_formatted"]}
        report = await agent.validate(docs, GUIDELINES["strict_formatting"])

        assert report.files_needing_fix == 0


class TestValidationFixBehavior:
    """Tests for validation fix behavior with different configurations."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create a mock LLM provider that tracks calls."""
        mock = AsyncMock()
        mock.generate = AsyncMock(
            return_value=MagicMock(
                content="# Fixed Content\n\nThis has been professionally revised."
            )
        )
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_fix_includes_deviations_in_prompt(self, mock_llm: MagicMock) -> None:
        """Test that fix prompt includes all identified deviations."""
        agent = ValidationAgent(mock_llm)

        deviations = [
            "Uses contractions",
            "Informal language",
            "Missing code examples",
        ]

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=2.0,
                format_adherence=3.0,
                content_adherence=2.5,
                overall_adherence=2.5,
                deviations=deviations,
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {"docs/index.md": DOCS["informal_doc"]}
        await agent.validate(docs, GUIDELINES["comprehensive"])

        # Verify LLM was called with fix prompt containing deviations
        assert mock_llm.generate.called
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args[1].get("prompt")

        for deviation in deviations:
            assert deviation in prompt, f"Deviation '{deviation}' not found in fix prompt"

    @pytest.mark.asyncio
    async def test_fix_includes_guidelines_in_prompt(self, mock_llm: MagicMock) -> None:
        """Test that fix prompt includes the full guidelines."""
        agent = ValidationAgent(mock_llm)

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=2.0,
                format_adherence=2.0,
                content_adherence=2.0,
                overall_adherence=2.0,
                deviations=["Multiple issues"],
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {"docs/index.md": DOCS["informal_doc"]}
        guidelines = GUIDELINES["comprehensive"]
        await agent.validate(docs, guidelines)

        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs.get("prompt") or call_args[1].get("prompt")

        # Key phrases from guidelines should be in fix prompt
        assert "formal, professional" in prompt
        assert "code examples" in prompt

    @pytest.mark.asyncio
    async def test_no_fix_when_above_threshold(self, mock_llm: MagicMock) -> None:
        """Test that no fix is attempted when scores are above threshold."""
        agent = ValidationAgent(mock_llm)

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=4.5,
                format_adherence=4.5,
                content_adherence=4.5,
                overall_adherence=4.5,
                deviations=[],
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {"docs/index.md": DOCS["formal_doc"]}
        await agent.validate(docs, GUIDELINES["formal_tone"])

        # LLM should not be called for fixes
        assert not mock_llm.generate.called

    @pytest.mark.asyncio
    async def test_check_only_mode_skips_fixes(self, mock_llm: MagicMock) -> None:
        """Test that check_only mode doesn't attempt fixes."""
        agent = ValidationAgent(mock_llm)

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=2.0,
                format_adherence=2.0,
                content_adherence=2.0,
                overall_adherence=2.0,
                deviations=["Many issues"],
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {"docs/index.md": DOCS["informal_doc"]}
        report = await agent.validate(docs, GUIDELINES["formal_tone"], check_only=True)

        # LLM should not be called for fixes
        assert not mock_llm.generate.called
        assert report.files_needing_fix == 1
        assert report.files_fixed == 0


class TestMultipleFilesValidation:
    """Tests for validating multiple files with different configurations."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock = AsyncMock()
        mock.generate = AsyncMock(return_value=MagicMock(content="# Fixed\n\nFixed content."))
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_multiple_files_different_scores(self, mock_llm: MagicMock) -> None:
        """Test validation of multiple files with different adherence levels."""
        agent = ValidationAgent(mock_llm)

        # Create a judge that returns different scores based on content
        call_count = 0

        async def mock_evaluate(
            documentation: str,
            guidelines: str,  # noqa: ARG001
        ) -> GuidelinesAdherenceScores:
            nonlocal call_count
            call_count += 1

            # First file (formal) should pass, second (informal) should fail
            # Check for markers: formal doc has "authentication module", informal has "Hey there"
            if "authentication module" in documentation:
                return GuidelinesAdherenceScores(
                    tone_adherence=4.5,
                    format_adherence=4.5,
                    content_adherence=4.5,
                    overall_adherence=4.5,
                    deviations=[],
                )
            else:
                return GuidelinesAdherenceScores(
                    tone_adherence=2.0,
                    format_adherence=3.0,
                    content_adherence=3.0,
                    overall_adherence=2.5,
                    deviations=["Informal tone", "Uses contractions"],
                )

        mock_judge = MagicMock()
        mock_judge.evaluate = mock_evaluate
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {
            "docs/api.md": DOCS["formal_doc"],
            "docs/guide.md": DOCS["informal_doc"],
        }

        report = await agent.validate(docs, GUIDELINES["formal_tone"])

        assert report.total_files == 2
        assert report.files_needing_fix == 1
        assert report.files_fixed == 1

        # Find which file needed fix
        for result in report.file_results:
            if result.file_path == "docs/api.md":
                assert result.needs_fix is False
            elif result.file_path == "docs/guide.md":
                assert result.needs_fix is True
                assert result.was_fixed is True

    @pytest.mark.asyncio
    async def test_aggregate_deviations_across_files(self, mock_llm: MagicMock) -> None:
        """Test that deviations are properly aggregated across files."""
        agent = ValidationAgent(mock_llm)

        call_count = 0

        async def mock_evaluate(
            documentation: str,
            guidelines: str,  # noqa: ARG001
        ) -> GuidelinesAdherenceScores:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return GuidelinesAdherenceScores(
                    tone_adherence=3.0,
                    format_adherence=4.0,
                    content_adherence=4.0,
                    overall_adherence=3.5,
                    deviations=["File 1: Issue A", "File 1: Issue B"],
                )
            else:
                return GuidelinesAdherenceScores(
                    tone_adherence=4.0,
                    format_adherence=3.0,
                    content_adherence=4.0,
                    overall_adherence=3.5,
                    deviations=["File 2: Issue C"],
                )

        mock_judge = MagicMock()
        mock_judge.evaluate = mock_evaluate
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {
            "docs/a.md": "Content A",
            "docs/b.md": "Content B",
        }

        report = await agent.validate(docs, GUIDELINES["comprehensive"])

        # All deviations should be in the report
        all_devs = report.all_deviations
        assert len(all_devs) == 3
        assert any("Issue A" in d for d in all_devs)
        assert any("Issue B" in d for d in all_devs)
        assert any("Issue C" in d for d in all_devs)


class TestValidateAndFixDocsConvenience:
    """Tests for the validate_and_fix_docs convenience function."""

    @pytest.mark.asyncio
    async def test_returns_fixed_docs(self) -> None:
        """Test that convenience function returns fixed documents."""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(
            return_value=MagicMock(content="# Fixed Professional Doc\n\nProperly written.")
        )
        mock_llm.close = AsyncMock()

        # We need to patch the GuidelinesJudge since validate_and_fix_docs creates its own
        from unittest.mock import patch

        mock_scores = GuidelinesAdherenceScores(
            tone_adherence=2.0,
            format_adherence=2.0,
            content_adherence=2.0,
            overall_adherence=2.0,
            deviations=["Needs fixing"],
        )

        with patch("josephus.generator.validation.GuidelinesJudge") as MockJudge:
            mock_judge_instance = MagicMock()
            mock_judge_instance.evaluate = AsyncMock(return_value=mock_scores)
            mock_judge_instance.close = AsyncMock()
            MockJudge.return_value = mock_judge_instance

            docs = {"docs/index.md": DOCS["informal_doc"]}
            fixed_docs, report = await validate_and_fix_docs(
                docs=docs,
                guidelines=GUIDELINES["formal_tone"],
                llm=mock_llm,
            )

        assert "docs/index.md" in fixed_docs
        assert "Professional" in fixed_docs["docs/index.md"]
        assert report.files_fixed == 1

    @pytest.mark.asyncio
    async def test_check_only_returns_original(self) -> None:
        """Test that check_only mode returns original documents."""
        mock_llm = AsyncMock()
        mock_llm.close = AsyncMock()

        from unittest.mock import patch

        mock_scores = GuidelinesAdherenceScores(
            tone_adherence=2.0,
            format_adherence=2.0,
            content_adherence=2.0,
            overall_adherence=2.0,
            deviations=["Needs fixing"],
        )

        with patch("josephus.generator.validation.GuidelinesJudge") as MockJudge:
            mock_judge_instance = MagicMock()
            mock_judge_instance.evaluate = AsyncMock(return_value=mock_scores)
            mock_judge_instance.close = AsyncMock()
            MockJudge.return_value = mock_judge_instance

            original_content = DOCS["informal_doc"]
            docs = {"docs/index.md": original_content}
            fixed_docs, report = await validate_and_fix_docs(
                docs=docs,
                guidelines=GUIDELINES["formal_tone"],
                llm=mock_llm,
                check_only=True,
            )

        # Should return original since no fixes in check_only mode
        assert fixed_docs["docs/index.md"] == original_content
        assert report.files_fixed == 0
        assert report.files_needing_fix == 1


class TestEdgeCases:
    """Tests for edge cases in validation with configurations."""

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        """Create a mock LLM provider."""
        mock = AsyncMock()
        mock.generate = AsyncMock(return_value=MagicMock(content="Fixed content"))
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_empty_guidelines(self, mock_llm: MagicMock) -> None:
        """Test validation with empty guidelines."""
        agent = ValidationAgent(mock_llm)

        docs = {"docs/index.md": DOCS["informal_doc"]}
        report = await agent.validate(docs, "")

        # Should skip validation entirely
        assert report.total_files == 0

    @pytest.mark.asyncio
    async def test_whitespace_only_guidelines(self, mock_llm: MagicMock) -> None:
        """Test validation with whitespace-only guidelines."""
        agent = ValidationAgent(mock_llm)

        docs = {"docs/index.md": DOCS["informal_doc"]}
        report = await agent.validate(docs, "   \n\t  ")

        assert report.total_files == 0

    @pytest.mark.asyncio
    async def test_empty_docs(self, mock_llm: MagicMock) -> None:
        """Test validation with empty docs dict."""
        agent = ValidationAgent(mock_llm)

        mock_judge = MagicMock()
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        report = await agent.validate({}, GUIDELINES["formal_tone"])

        assert report.total_files == 0
        assert report.files_needing_fix == 0

    @pytest.mark.asyncio
    async def test_very_long_guidelines(self, mock_llm: MagicMock) -> None:
        """Test validation with very long guidelines."""
        agent = ValidationAgent(mock_llm)

        # Create long guidelines
        long_guidelines = GUIDELINES["comprehensive"] + "\n" + ("Additional detail. " * 1000)

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=4.0,
                format_adherence=4.0,
                content_adherence=4.0,
                overall_adherence=4.0,
                deviations=[],
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {"docs/index.md": DOCS["formal_doc"]}
        report = await agent.validate(docs, long_guidelines)

        assert report.total_files == 1

    @pytest.mark.asyncio
    async def test_guidelines_with_special_characters(self, mock_llm: MagicMock) -> None:
        """Test validation with guidelines containing special characters."""
        agent = ValidationAgent(mock_llm)

        special_guidelines = """# Guidelines with Special Characters

## Code Style
- Use `backticks` for inline code
- Use <angle brackets> for placeholders
- Escape \\backslashes\\ properly
- Include $variables and {braces}
- Support émojis and ünïcödé 🎉
"""

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=4.0,
                format_adherence=4.0,
                content_adherence=4.0,
                overall_adherence=4.0,
                deviations=[],
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {"docs/index.md": "# Test"}
        report = await agent.validate(docs, special_guidelines)

        assert report.total_files == 1

    @pytest.mark.asyncio
    async def test_fix_failure_preserves_original(self, mock_llm: MagicMock) -> None:
        """Test that failed fix attempts preserve original content."""
        # Make LLM raise an error
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

        agent = ValidationAgent(mock_llm)

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=2.0,
                format_adherence=2.0,
                content_adherence=2.0,
                overall_adherence=2.0,
                deviations=["Needs fix"],
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        original = DOCS["informal_doc"]
        docs = {"docs/index.md": original}
        report = await agent.validate(docs, GUIDELINES["formal_tone"])

        # Should mark as needing fix but not fixed
        assert report.files_needing_fix == 1
        assert report.files_fixed == 0

        # get_fixed_docs should return original
        fixed = agent.get_fixed_docs(report)
        assert fixed["docs/index.md"] == original

    @pytest.mark.asyncio
    async def test_threshold_boundary_exactly_at_4(self, mock_llm: MagicMock) -> None:
        """Test behavior when score is exactly at threshold (4.0)."""
        agent = ValidationAgent(mock_llm)

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=4.0,
                format_adherence=4.0,
                content_adherence=4.0,
                overall_adherence=4.0,  # Exactly at threshold
                deviations=[],
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {"docs/index.md": "# Test"}
        report = await agent.validate(docs, GUIDELINES["formal_tone"])

        # Should NOT need fix (threshold is < 4.0)
        assert report.files_needing_fix == 0

    @pytest.mark.asyncio
    async def test_threshold_boundary_just_below_4(self, mock_llm: MagicMock) -> None:
        """Test behavior when score is just below threshold."""
        agent = ValidationAgent(mock_llm)

        mock_judge = MagicMock()
        mock_judge.evaluate = AsyncMock(
            return_value=GuidelinesAdherenceScores(
                tone_adherence=3.9,
                format_adherence=4.0,
                content_adherence=4.0,
                overall_adherence=3.99,  # Just below threshold
                deviations=["Minor issue"],
            )
        )
        mock_judge.close = AsyncMock()
        agent._judge = mock_judge

        docs = {"docs/index.md": "# Test"}
        report = await agent.validate(docs, GUIDELINES["formal_tone"])

        # Should need fix
        assert report.files_needing_fix == 1
