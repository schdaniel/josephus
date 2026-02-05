"""Unit tests for GitHub App authentication."""

import time
from unittest.mock import AsyncMock, patch

import jwt
import pytest

from josephus.github.auth import GitHubAuth, InstallationToken

# Test RSA key pair (DO NOT USE IN PRODUCTION)
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGy0AHB7MfszK0BYmr0dwHD0
DiOw8A1JLSPgEuCPuIA/S1qe2bCMpvhpwZLlAGkrZsf/gFvFD2TEQF6sJeGvPx+q
+0aOnyROAB5BxPy1S1kPz1KJxuXvNwPy9s5xAaBvPpORdwts1xgCMVaLWXZoR4hS
9mD0lIBoqPHZkPOz3LpkgDMxDBILpvMizHkSvYMUakXf6FHPhzJE9v7GrxOkFLYh
vvwFNFGG6qGMDVSPkHiFlAb5rlWKB+SaA7b2d7p/E1PCb5hG8VExCjDJbdKXAv4M
jKqnv2FRPA3cZhIBPHzwGd6vv8vR3ng/aIzVbwIDAQABAoIBAFmBv5CbdGrQkJD0
hERkWHR2M1XOyDM8rWK/h8YAhHxZQEsj5kN/3M1mcyOPk5vpFUnb9gLiA3ULvNJB
EpKrX+FNpjJsTpLAhvFtJwm34+L6bBPAZUpZpxMKMPgL7Um+V7psZ8LAIhIxBSKM
wCAVa4r7+aVYMi7PYKjzlK6EOIU2n5f0RYnDlJjFOqGjMmnPBZ/9wHq5c8wp2kSP
k7uKPEYPjlGhvu02NdYaP6J7e0AKYy9q+FZgKbQvPCLg++mowp7bZfIGLzCJ2bzL
aI4OKpLYJvNB4X4HdJmXMJwHspe/EQkskxGy9eFJmdWL8xXVDjBRK3bWO18FGKFC
iiJJAAECgYEA7OVBqpRxBSLwMl6Ngf8HDESHVFMdG9HJmr2A8A5F3Rxl+lXrekCT
mYsRzSJDxKCysdCGSYHDM0/K8kLBzh0dPzAaZ1Dej7zAPnQpJNMPA5w+F/0+6wfK
z3H/7s7s9QNMB7sxxstDzIFji7qERMJpKg8n5p0f9V0BUypwRK9hcK8CgYEA4iLq
yl9ww8yGJDHnP5dawif5PbPJDwFf/RRzPfTe3LRRX+NhcN6bnhdj82xoKAa+8GDq
t2Kvdb0OChOaBGSuS4ic3T7FmHIpjnG3grDiGa1UMdcNQB4QLUm7t7X7XjD7YR/q
FUxaBAR3EGvx5Y2MJ3ax4k5CUy4YfGMC4p51+0ECgYASFn5JER7b4MrehPyzuKaR
xrlNFwzPV0aqNJNJxchJLpQwCI9lS1V2sRkJ0fNZbG4leNfrJZgGpXzm48F+aP/O
NwuGjvXxnHvMtkLi1B0GFHI4fN1n7O1GjGVOlv5p7F3sZWU0JU3Q3mxzCK+jlhcp
T2FWLi1i6bD8W8ybAqnmDwKBgBpQYwuVObqFMCRbZnW5rmW3FKQeGt0fVIp+NLJz
nKEh/qpfhZqn3F7g8F3D/FgOMPNgOoC0hwdm22B0JnipGfco3K0zqXpK2IVBdvfJ
DZq3UgngvDN3eDHG5BvBwt8KIhWoL60djvFhwPtqDrnVBZ5NjTlqPcRj7qDKhfBm
dBYBAoGBAMbbfZC3cTz0lPNPoLdWOLqJIpd7IPXRUMU2HK/FrS06uF5awNA3f9kx
hI2qRdL9WXCuH8yj1CFFofbLcXFJd/J4jnPcqAp6BZKM8z2TD6pGVbC5LPbqSvpj
EGA0fBfLWTCF5pF9VE1UcYzIjrdBmeBRwq5l4u5xpEV0k8WPczDd
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

        assert decoded["iss"] == TEST_APP_ID
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
        assert decoded["iss"] == TEST_APP_ID

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
        mock_response = AsyncMock()
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
        mock_response = AsyncMock()
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
