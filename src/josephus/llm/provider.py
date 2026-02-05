"""LLM provider abstraction for documentation generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import anthropic
import logfire

from josephus.core.config import get_settings


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt/message
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            LLMResponse with generated content and metadata
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections."""
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider.

    Uses Claude for documentation generation. Claude is recommended
    for its strong code understanding and XML parsing capabilities.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        """Initialize Claude provider.

        Args:
            api_key: Anthropic API key (defaults to env var)
            model: Model to use (defaults to Claude 3.5 Sonnet)
        """
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key

        if not self.api_key:
            raise ValueError(
                "Anthropic API key not configured. "
                "Set ANTHROPIC_API_KEY environment variable."
            )

        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response using Claude.

        Args:
            prompt: User prompt/message
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            LLMResponse with generated content and metadata
        """
        logfire.info(
            "Calling Claude API",
            model=self.model,
            max_tokens=max_tokens,
            prompt_preview=prompt[:100] + "..." if len(prompt) > 100 else prompt,
        )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)

        # Extract text content
        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        logfire.info(
            "Claude API response",
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )

        return LLMResponse(
            content=content,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
        )

    async def close(self) -> None:
        """Close the Anthropic client."""
        await self._client.close()


def get_provider(provider_name: str | None = None) -> LLMProvider:
    """Get an LLM provider instance.

    Args:
        provider_name: Provider name (claude, openai, ollama)
                      Defaults to config setting

    Returns:
        LLMProvider instance
    """
    settings = get_settings()
    name = provider_name or settings.llm_provider

    match name:
        case "claude":
            return ClaudeProvider()
        case "openai":
            raise NotImplementedError("OpenAI provider not yet implemented")
        case "ollama":
            raise NotImplementedError("Ollama provider not yet implemented")
        case _:
            raise ValueError(f"Unknown LLM provider: {name}")
