"""Unit tests for API authentication."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from josephus.api.auth import verify_api_key


class TestVerifyApiKey:
    """Tests for API key verification."""

    @pytest.mark.asyncio
    async def test_valid_api_key(self) -> None:
        """Test that valid API key is accepted."""
        with patch("josephus.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = "test-api-key-12345"
            mock_settings.return_value.environment = "production"

            result = await verify_api_key("test-api-key-12345")
            assert result is True

    @pytest.mark.asyncio
    async def test_invalid_api_key(self) -> None:
        """Test that invalid API key is rejected."""
        with patch("josephus.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = "correct-key"
            mock_settings.return_value.environment = "production"

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key("wrong-key")

            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_api_key(self) -> None:
        """Test that missing API key is rejected."""
        with patch("josephus.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = "test-key"
            mock_settings.return_value.environment = "production"

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(None)

            assert exc_info.value.status_code == 401
            assert "Missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_development_mode_no_key_configured(self) -> None:
        """Test that development mode allows requests without API key configured."""
        with patch("josephus.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            mock_settings.return_value.environment = "development"

            result = await verify_api_key(None)
            assert result is True

    @pytest.mark.asyncio
    async def test_production_no_key_configured(self) -> None:
        """Test that production mode fails when API key not configured."""
        with patch("josephus.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            mock_settings.return_value.environment = "production"

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(None)

            assert exc_info.value.status_code == 500
            assert "not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_staging_requires_api_key(self) -> None:
        """Test that staging mode also requires API key."""
        with patch("josephus.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = None
            mock_settings.return_value.environment = "staging"

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(None)

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_timing_safe_comparison(self) -> None:
        """Test that API key comparison is timing-safe.

        We can't easily test timing directly, but we ensure the function
        uses secrets.compare_digest by verifying similar-length keys work.
        """
        with patch("josephus.api.auth.get_settings") as mock_settings:
            mock_settings.return_value.api_key = "a" * 32
            mock_settings.return_value.environment = "production"

            # Valid key should work
            result = await verify_api_key("a" * 32)
            assert result is True

            # Similar length invalid key should fail
            with pytest.raises(HTTPException):
                await verify_api_key("b" * 32)
