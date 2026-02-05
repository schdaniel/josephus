"""Unit tests for GitHub App authentication."""

import time
from unittest.mock import AsyncMock, Mock, patch

import jwt
import pytest

from josephus.github.auth import GitHubAuth, InstallationToken

# Test RSA key pair (DO NOT USE IN PRODUCTION)
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA2kch+5SChZ25RhUgY2TSPy7mnTUDGw4n66XZEKOL6+7o2Jql
0uZdfiE1KoShKVMobziXYPmSEVXwTQcpsPhe4r30OszJBXTB4ZFlNlOpToD/UNrD
DriTckP/UaNjcbJFC1RmJqDB0GB0ChCR0Lqc+RN8LdvnPc4Xssv+vUbh0p1ZvDtN
OVaTPFPlcBBSVn9XyXqWK7WSPryi4jsK7oAiQRIVm4iDcGkqX4L9yN8lRjW3UoeZ
Onq0pn9emsM8EZZX4kwZlUlkA/YVqJs9+F7BgMT9rNeN/63t5JS5fBCuBf7DEYlS
w6HvKw+yLXTdXC9OyBCo/sHxuRuG9dVxqDdgNwIDAQABAoIBAAFx9VG9Y6w8MjG6
fXq0leD3aW1C07C8qo5lWTQPTFbCDKzOc7WbP9g2oqvG5NHcuPvpIIHZKFq3OnGQ
HOCmkrfZyrTbwTyPgtWAlggPjFa2nobr0KnKyaZShYcfvhtOsyVTKDmUpX1z/gcV
1MyDri4tLyYwlAd1OcC9yzbemF7BsWf2rtyvNWidqne44K/wA2319aDcuR/eapSx
oaMwx/vfQmxG9A9g5AAljoKPQcQ0NP9U+sjy1kel+PWDiENoI2RFC1Z2UIJS/fWv
cDz2bHN/8BuUxaZ6Vez/cEULTj5Bn+cBJ01ok5sK77hfFwzoFFc9aFM79i5jxdZ6
txsHheECgYEA+J8/O/DW6GqltvbAD0FnBTb02ZT9aNooHXKw1tH9l/G5lt/rQG7J
uC1DZ4n6xqxeajNHstN0GXQ/TZXbV9QUuHogi7b8r6ZFTIOd9rEFd4L4D6h/9Ocv
4wSBQqKNfwPbQL3Uzddz8i2RzbFmcwVTP08kUhT7w7Ci1vCVwkYcmpcCgYEA4MFd
SLQDehIfh6ErrTbIkwPtK2+/x8/gbLVyhrK2W27EWXt+2tpbqu6Z0rX5H0IfwI/G
liVns/wd157XYpg/P7Rgad/rudSD9JTpvFVpzQQesvJrDKWRr+/ZmspsTJb0grkI
phpUcp/VloqQcB+PJ+MJCLa/RIpqgun1pjZAO2ECgYEA8a4DzyXIEzgQjPICMxI1
rfkFPTk6uSFQW4fw5XJN3NVKvqI+0myfxFyjqFOVpmlKglwE943bzx6Uprvk89Si
q810M7yWl7y+oqlS9cqQ8OMsdjQq5ouRnlHzwS249F5wVNfztIEbIbEwic5IM8la
ajFpsizZrBnZwa0vNyHmjlMCgYEAks3al511U+u4ioe8lqRc+KIs7R1OAD6I0Zjn
GJJsyGYefHBM2Lid/ZViBh70fPVc9hMzXGlMRmTcPTW0a+MUFRFFlII9X6EvG7eU
wH5t4Arb3ni3cYhIE8ovsYqcmJ5VUXl4673xAPnjsjQJyiLjB+Okx/tODX/3uFEH
MiznYaECgYAYF+rqSnQqNwWWsjJ7jMcl5I2zWVkchfVVX+WIVHihnX35bKdfsuiy
LD7Hc7AI+xUVDpTlHJ7WGhqZEdQ9FR8Q04ozKlqX8aWCS2zghz9srZVO1oAn4doe
45vcgzhDSJsUYByrBhn57JkjDPGBuVFSbJyqkMlbr5vDCzGLAH1BSw==
-----END RSA PRIVATE KEY-----"""

TEST_APP_ID = 12345


class TestGitHubAuth:
    """Tests for GitHubAuth class."""

    def test_generate_jwt_structure(self) -> None:
        """Test JWT has correct structure and claims."""
        auth = GitHubAuth(app_id=TEST_APP_ID, private_key=TEST_PRIVATE_KEY)
        token = auth._generate_jwt()

        # Decode without verification to check structure
        decoded = jwt.decode(token, options={"verify_signature": False})

        assert decoded["iss"] == str(TEST_APP_ID)
        assert "iat" in decoded
        assert "exp" in decoded

        # Check expiration is ~9 minutes from issued time
        assert decoded["exp"] - decoded["iat"] <= 10 * 60

    def test_generate_jwt_valid_signature(self) -> None:
        """Test JWT has valid RSA signature."""
        auth = GitHubAuth(app_id=TEST_APP_ID, private_key=TEST_PRIVATE_KEY)
        token = auth._generate_jwt()

        # Extract public key from private key for verification
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        private_key = load_pem_private_key(TEST_PRIVATE_KEY.encode(), password=None)
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # Should not raise
        decoded = jwt.decode(token, public_pem, algorithms=["RS256"])
        assert decoded["iss"] == str(TEST_APP_ID)

    def test_missing_credentials_raises(self) -> None:
        """Test that missing credentials raises ValueError."""
        with patch("josephus.github.auth.get_settings") as mock_settings:
            mock_settings.return_value.github_app_id = None
            mock_settings.return_value.github_app_private_key = None

            with pytest.raises(ValueError, match="GitHub App credentials not configured"):
                GitHubAuth()

    @pytest.mark.asyncio
    async def test_get_installation_token_caching(self) -> None:
        """Test that installation tokens are cached."""
        auth = GitHubAuth(app_id=TEST_APP_ID, private_key=TEST_PRIVATE_KEY)

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "token": "test_token_123",
            "expires_at": "2099-01-01T00:00:00Z",
            "permissions": {"contents": "read"},
            "repository_selection": "all",
        }
        mock_response.raise_for_status = lambda: None
        mock_client.post.return_value = mock_response

        # First call - should hit API
        token1 = await auth.get_installation_token(123, http_client=mock_client)
        assert token1.token == "test_token_123"
        assert mock_client.post.call_count == 1

        # Second call - should use cache
        token2 = await auth.get_installation_token(123, http_client=mock_client)
        assert token2.token == "test_token_123"
        assert mock_client.post.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_get_installation_token_cache_expiry(self) -> None:
        """Test that expired tokens are refreshed."""
        auth = GitHubAuth(app_id=TEST_APP_ID, private_key=TEST_PRIVATE_KEY)

        # Pre-populate cache with expired token
        expired_token = InstallationToken(
            token="expired_token",
            expires_at="2020-01-01T00:00:00Z",
            permissions={},
            repository_selection="all",
        )
        auth._token_cache[123] = (expired_token, time.time() - 100)

        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "token": "new_token",
            "expires_at": "2099-01-01T00:00:00Z",
            "permissions": {},
            "repository_selection": "all",
        }
        mock_response.raise_for_status = lambda: None
        mock_client.post.return_value = mock_response

        # Should fetch new token
        token = await auth.get_installation_token(123, http_client=mock_client)
        assert token.token == "new_token"
        assert mock_client.post.call_count == 1
