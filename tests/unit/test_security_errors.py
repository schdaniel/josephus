"""Tests for error sanitization utilities."""

from josephus.security.errors import (
    get_error_code,
    sanitize_error_message,
)


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message function."""

    def test_connection_error_sanitized(self):
        """Connection errors should return generic message."""
        error = ConnectionError("PostgreSQL at localhost:5432 refused connection")
        result = sanitize_error_message(error)
        assert result == "Unable to connect to external service"
        assert "PostgreSQL" not in result
        assert "localhost" not in result
        assert "5432" not in result

    def test_timeout_error_sanitized(self):
        """Timeout errors should return generic message."""
        error = TimeoutError("Connection to api.example.com:443 timed out after 30s")
        result = sanitize_error_message(error)
        assert result == "Request timed out"
        assert "api.example.com" not in result

    def test_file_not_found_sanitized(self):
        """File errors should not reveal paths."""
        error = FileNotFoundError("/app/src/josephus/templates/secret_config.yaml")
        result = sanitize_error_message(error)
        assert result == "Required resource not found"
        assert "/app" not in result
        assert "josephus" not in result
        assert "secret" not in result

    def test_permission_error_sanitized(self):
        """Permission errors should not reveal paths."""
        error = PermissionError("[Errno 13] Permission denied: '/etc/passwd'")
        result = sanitize_error_message(error)
        assert result == "Access denied to resource"
        assert "/etc/passwd" not in result

    def test_value_error_sanitized(self):
        """Value errors should be sanitized."""
        error = ValueError("Invalid API key: sk-abc123xyz")
        result = sanitize_error_message(error)
        assert result == "Invalid input provided"
        assert "sk-abc123xyz" not in result

    def test_unknown_error_generic_message(self):
        """Unknown errors should return generic message or sanitized content."""
        error = Exception("Something went wrong")
        result = sanitize_error_message(error)
        # Either generic message or the safe original
        assert "internal" in result.lower() or result == "Something went wrong"

    def test_database_path_redacted(self):
        """Database URLs should be redacted in unknown errors."""

        class CustomDBError(Exception):
            pass

        error = CustomDBError("Connection failed: postgres://user:pass@db.internal:5432/mydb")
        result = sanitize_error_message(error)
        assert "postgres://" not in result
        assert "user:pass" not in result
        assert "db.internal" not in result

    def test_ip_address_redacted(self):
        """IP addresses should be redacted."""

        class NetworkError(Exception):
            pass

        error = NetworkError("Failed to connect to 192.168.1.100:8080")
        result = sanitize_error_message(error)
        assert "192.168.1.100" not in result

    def test_email_redacted(self):
        """Email addresses should be redacted."""

        class NotificationError(Exception):
            pass

        error = NotificationError("Failed to send to admin@company.internal")
        result = sanitize_error_message(error)
        assert "admin@company.internal" not in result

    def test_api_key_redacted(self):
        """API keys in messages should be redacted."""

        class APIError(Exception):
            pass

        error = APIError("Invalid api_key=sk_live_abc123 provided")
        result = sanitize_error_message(error)
        assert "sk_live_abc123" not in result

    def test_empty_error_message(self):
        """Empty error messages should return generic message."""
        error = Exception("")
        result = sanitize_error_message(error)
        assert result == "An internal error occurred"

    def test_parent_class_mapping(self):
        """Errors should match parent class mappings."""

        class CustomConnectionError(ConnectionError):
            pass

        error = CustomConnectionError("Custom connection issue")
        result = sanitize_error_message(error)
        assert result == "Unable to connect to external service"

    def test_long_message_truncated(self):
        """Very long messages should be truncated."""

        class VerboseError(Exception):
            pass

        long_message = "Error details: " + "x" * 500
        error = VerboseError(long_message)
        result = sanitize_error_message(error)
        assert len(result) <= 200


class TestGetErrorCode:
    """Tests for get_error_code function."""

    def test_connection_error_code(self):
        """Connection errors should return CONNECTION_FAILED."""
        error = ConnectionError("test")
        assert get_error_code(error) == "CONNECTION_FAILED"

    def test_connection_refused_error_code(self):
        """Connection refused should return CONNECTION_REFUSED."""
        error = ConnectionRefusedError("test")
        assert get_error_code(error) == "CONNECTION_REFUSED"

    def test_timeout_error_code(self):
        """Timeout errors should return TIMEOUT."""
        error = TimeoutError("test")
        assert get_error_code(error) == "TIMEOUT"

    def test_file_not_found_error_code(self):
        """File not found should return NOT_FOUND."""
        error = FileNotFoundError("test")
        assert get_error_code(error) == "NOT_FOUND"

    def test_permission_error_code(self):
        """Permission errors should return PERMISSION_DENIED."""
        error = PermissionError("test")
        assert get_error_code(error) == "PERMISSION_DENIED"

    def test_unknown_error_code(self):
        """Unknown errors should return INTERNAL_ERROR."""
        error = Exception("test")
        assert get_error_code(error) == "INTERNAL_ERROR"

    def test_value_error_code(self):
        """Value errors should return INTERNAL_ERROR (not mapped)."""
        # ValueError is not explicitly mapped to a code, so it returns INTERNAL_ERROR
        # Only ValidationError (from pydantic, etc.) maps to VALIDATION_ERROR
        error = ValueError("test")
        assert get_error_code(error) == "INTERNAL_ERROR"
