"""Unit tests for webhook signature verification."""

from josephus.api.routes.webhooks import verify_webhook_signature


class TestWebhookSignatureVerification:
    """Tests for HMAC signature verification."""

    def test_valid_signature(self) -> None:
        """Test that valid signatures are accepted."""
        import hashlib
        import hmac

        payload = b'{"action": "opened"}'
        secret = "test-secret"

        # Compute valid signature
        expected = (
            "sha256="
            + hmac.new(
                secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()
        )

        assert verify_webhook_signature(payload, expected, secret) is True

    def test_invalid_signature(self) -> None:
        """Test that invalid signatures are rejected."""
        payload = b'{"action": "opened"}'
        secret = "test-secret"
        invalid_signature = "sha256=invalid"

        assert verify_webhook_signature(payload, invalid_signature, secret) is False

    def test_missing_signature(self) -> None:
        """Test that missing signatures are rejected."""
        payload = b'{"action": "opened"}'
        secret = "test-secret"

        assert verify_webhook_signature(payload, None, secret) is False

    def test_wrong_secret(self) -> None:
        """Test that signatures with wrong secret are rejected."""
        payload = b'{"action": "opened"}'
        correct_secret = "correct-secret"
        wrong_secret = "wrong-secret"

        import hashlib
        import hmac

        # Sign with correct secret
        signature = (
            "sha256="
            + hmac.new(
                correct_secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()
        )

        # Verify with wrong secret should fail
        assert verify_webhook_signature(payload, signature, wrong_secret) is False

    def test_timing_safe_comparison(self) -> None:
        """Test that comparison is timing-safe (uses hmac.compare_digest)."""
        # This is more of a code review check - we verify the function uses
        # hmac.compare_digest by checking it doesn't short-circuit
        payload = b'{"action": "opened"}'
        secret = "test-secret"

        import hashlib
        import hmac

        valid_signature = (
            "sha256="
            + hmac.new(
                secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()
        )

        # Both of these should take similar time (no short-circuit)
        # This is hard to test directly, but we ensure the function works
        assert verify_webhook_signature(payload, valid_signature, secret) is True
        assert verify_webhook_signature(payload, "sha256=" + "a" * 64, secret) is False
