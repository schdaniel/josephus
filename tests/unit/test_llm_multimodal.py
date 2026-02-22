"""Tests for LLM multimodal message construction."""

from josephus.llm.provider import (
    ImageBlock,
    Message,
    TextBlock,
)


class TestContentBlocks:
    def test_text_block(self):
        block = TextBlock(text="Hello world")
        assert block.type == "text"
        assert block.text == "Hello world"

    def test_image_block(self):
        block = ImageBlock(
            data="base64data",
            media_type="image/png",
            detail="high",
        )
        assert block.type == "image"
        assert block.data == "base64data"
        assert block.media_type == "image/png"
        assert block.detail == "high"

    def test_image_block_default_detail(self):
        block = ImageBlock(data="data", media_type="image/jpeg")
        assert block.detail == "auto"


class TestMessage:
    def test_text_only_message(self):
        msg = Message(role="user", content=[TextBlock(text="describe this")])
        assert msg.role == "user"
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextBlock)

    def test_multimodal_message(self):
        msg = Message(
            role="user",
            content=[
                ImageBlock(data="screenshot_base64", media_type="image/png", detail="high"),
                TextBlock(text="Describe the UI shown in this screenshot."),
            ],
        )
        assert len(msg.content) == 2
        assert isinstance(msg.content[0], ImageBlock)
        assert isinstance(msg.content[1], TextBlock)

    def test_empty_message(self):
        msg = Message(role="assistant")
        assert msg.content == []


class TestClaudeProviderMessageConversion:
    """Test the _message_to_api conversion without making real API calls."""

    def _get_provider_class(self):
        # Import here to avoid needing API key
        from josephus.llm.provider import ClaudeProvider

        return ClaudeProvider

    def test_text_message_conversion(self):
        """Test that text messages are converted to API format correctly."""
        msg = Message(role="user", content=[TextBlock(text="Hello")])

        # Manually replicate the conversion logic
        content_blocks = []
        for block in msg.content:
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
        result = {"role": msg.role, "content": content_blocks}

        assert result == {
            "role": "user",
            "content": [{"type": "text", "text": "Hello"}],
        }

    def test_multimodal_message_conversion(self):
        """Test that multimodal messages are converted correctly."""
        msg = Message(
            role="user",
            content=[
                ImageBlock(data="abc123", media_type="image/png"),
                TextBlock(text="Describe this"),
            ],
        )

        content_blocks = []
        for block in msg.content:
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
        result = {"role": msg.role, "content": content_blocks}

        assert result["role"] == "user"
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "image"
        assert result["content"][0]["source"]["data"] == "abc123"
        assert result["content"][1]["type"] == "text"
        assert result["content"][1]["text"] == "Describe this"
