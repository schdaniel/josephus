"""LLM provider abstraction for documentation generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

import anthropic
import logfire

from josephus.core.config import get_settings

# --- Content block types (mirrors Anthropic API structure) ---


@dataclass
class TextBlock:
    """A text content block."""

    text: str
    type: Literal["text"] = "text"


@dataclass
class ImageBlock:
    """An image content block for multimodal prompts."""

    data: str  # Base64-encoded image data
    media_type: str  # e.g., "image/png", "image/jpeg"
    detail: Literal["low", "high", "auto"] = "auto"
    type: Literal["image"] = "image"


ContentBlock = TextBlock | ImageBlock


@dataclass
class Message:
    """A message with mixed content blocks."""

    role: Literal["user", "assistant"]
    content: list[ContentBlock] = field(default_factory=list)


# --- Response ---


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None


# --- Provider abstraction ---


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
        """Generate a response from a text prompt.

        This is the simple text-only interface. For multimodal prompts,
        use generate_messages() instead.
        """
        pass

    async def generate_messages(
        self,
        messages: list[Message],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response from structured messages with mixed content.

        Supports text and image content blocks. Default implementation
        extracts text from messages and falls back to generate().
        """
        # Default fallback: extract text only
        text_parts = []
        for msg in messages:
            for block in msg.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
        prompt = "\n".join(text_parts)
        return await self.generate(prompt, system, max_tokens, temperature)

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections."""
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider.

    Uses Claude for documentation generation. Claude is recommended
    for its strong code understanding and multimodal capabilities.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key

        if not self.api_key:
            raise ValueError(
                "Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable."
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
        """Generate a response from a text prompt."""
        messages = [Message(role="user", content=[TextBlock(text=prompt)])]
        return await self.generate_messages(messages, system, max_tokens, temperature)

    async def generate_messages(
        self,
        messages: list[Message],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response from structured messages with mixed content."""
        logfire.info(
            "Calling Claude API",
            model=self.model,
            max_tokens=max_tokens,
            message_count=len(messages),
        )

        # Convert Message objects to Anthropic API format
        api_messages = [self._message_to_api(msg) for msg in messages]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": api_messages,
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

    def _message_to_api(self, message: Message) -> dict[str, Any]:
        """Convert a Message to Anthropic API format."""
        content_blocks: list[dict[str, Any]] = []

        for block in message.content:
            if isinstance(block, TextBlock):
                content_blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ImageBlock):
                content_blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": block.media_type,
                            "data": block.data,
                        },
                    }
                )

        return {"role": message.role, "content": content_blocks}

    async def close(self) -> None:
        """Close the Anthropic client."""
        await self._client.close()


def get_provider(provider_name: str | None = None) -> LLMProvider:
    """Get an LLM provider instance."""
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
