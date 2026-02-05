"""Unit tests for secret scanning."""

import pytest

from josephus.security import (
    ScanResult,
    SecretFoundError,
    SecretMatch,
    SecretType,
    scan_content,
    scan_files,
)


class TestSecretPatterns:
    """Tests for individual secret pattern detection."""

    def test_detect_aws_access_key(self) -> None:
        """Test AWS access key detection."""
        content = "aws_access_key = AKIAIOSFODNN7EXAMPLE"
        matches = scan_content(content, "config.py")

        assert len(matches) == 1
        assert matches[0].secret_type == SecretType.AWS_ACCESS_KEY

    def test_detect_github_token(self) -> None:
        """Test GitHub token detection."""
        content = "token = ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        matches = scan_content(content, "config.py")

        assert len(matches) == 1
        assert matches[0].secret_type == SecretType.GITHUB_TOKEN

    def test_detect_openai_api_key(self) -> None:
        """Test OpenAI API key detection."""
        content = "OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        matches = scan_content(content, ".env")

        assert len(matches) >= 1
        assert any(m.secret_type == SecretType.OPENAI_API_KEY for m in matches)

    def test_detect_anthropic_api_key(self) -> None:
        """Test Anthropic API key detection."""
        # Anthropic keys are longer
        key = "sk-ant-" + "x" * 100
        content = f"ANTHROPIC_API_KEY={key}"
        matches = scan_content(content, ".env")

        assert len(matches) >= 1
        assert any(m.secret_type == SecretType.ANTHROPIC_API_KEY for m in matches)

    def test_detect_stripe_key(self) -> None:
        """Test Stripe API key detection."""
        # Using test prefix which is safe
        content = "stripe_key = sk_test_xxxxTESTKEYxxxxxxxxxxxxxxx"
        matches = scan_content(content, "config.py")

        assert len(matches) == 1
        assert matches[0].secret_type == SecretType.STRIPE_API_KEY

    def test_detect_database_url(self) -> None:
        """Test database URL detection."""
        content = 'DATABASE_URL = "postgresql://user:password123@localhost:5432/mydb"'
        matches = scan_content(content, ".env")

        assert len(matches) == 1
        assert matches[0].secret_type == SecretType.DATABASE_URL

    def test_detect_private_key(self) -> None:
        """Test private key detection."""
        content = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""
        matches = scan_content(content, "key.pem")

        assert len(matches) >= 1
        # RSA private keys are matched as GitHub App keys or generic private keys
        assert any(
            m.secret_type in (SecretType.PRIVATE_KEY, SecretType.GITHUB_APP_KEY) for m in matches
        )

    def test_detect_jwt_token(self) -> None:
        """Test JWT token detection."""
        content = "token = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        matches = scan_content(content, "auth.py")

        assert len(matches) == 1
        assert matches[0].secret_type == SecretType.JWT_TOKEN

    def test_detect_slack_webhook(self) -> None:
        """Test Slack webhook URL detection."""
        # Using obviously fake test values (TXXXXXXXX pattern)
        content = "SLACK_WEBHOOK=https://hooks.slack.com/services/TXXXXXXXX/BXXXXXXXX/testwebhookvalue123"
        matches = scan_content(content, ".env")

        assert len(matches) == 1
        assert matches[0].secret_type == SecretType.SLACK_WEBHOOK

    def test_detect_generic_api_key(self) -> None:
        """Test generic API key detection."""
        content = "api_key = abcdef1234567890abcdef1234567890"
        matches = scan_content(content, "config.py")

        assert len(matches) >= 1
        assert any(m.secret_type == SecretType.GENERIC_API_KEY for m in matches)

    def test_detect_basic_auth_url(self) -> None:
        """Test basic auth in URL detection."""
        content = 'url = "https://user:password@api.example.com/endpoint"'
        matches = scan_content(content, "config.py")

        assert len(matches) >= 1
        assert any(m.secret_type == SecretType.BASIC_AUTH for m in matches)


class TestScanBehavior:
    """Tests for scanning behavior."""

    def test_no_secrets_found(self) -> None:
        """Test scanning content with no secrets."""
        content = """
def hello():
    print("Hello, world!")
    return 42
"""
        matches = scan_content(content, "main.py")
        assert len(matches) == 0

    def test_multiple_secrets_same_file(self) -> None:
        """Test detecting multiple secrets in same file."""
        content = """
AWS_ACCESS_KEY = AKIAIOSFODNN7EXAMPLE
GITHUB_TOKEN = ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
"""
        matches = scan_content(content, "config.py")

        assert len(matches) == 2
        types = {m.secret_type for m in matches}
        assert SecretType.AWS_ACCESS_KEY in types
        assert SecretType.GITHUB_TOKEN in types

    def test_line_numbers_correct(self) -> None:
        """Test that line numbers are correctly reported."""
        content = """line 1
line 2
AWS_ACCESS_KEY = AKIAIOSFODNN7EXAMPLE
line 4
"""
        matches = scan_content(content, "config.py")

        assert len(matches) == 1
        assert matches[0].line_number == 3

    def test_secret_redacted(self) -> None:
        """Test that matched secrets are redacted."""
        content = "token = ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        matches = scan_content(content, "config.py")

        assert len(matches) == 1
        # Redacted text should not contain the full secret
        assert "ghp_abcdefghij" not in matches[0].matched_text
        # But should contain partial (first 2 chars)
        assert "gh" in matches[0].matched_text

    def test_skip_binary_files(self) -> None:
        """Test that binary file extensions are skipped."""
        content = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

        # These should be skipped
        assert scan_content(content, "image.png") == []
        assert scan_content(content, "archive.zip") == []
        assert scan_content(content, "compiled.pyc") == []

    def test_skip_lock_files(self) -> None:
        """Test that lock files are skipped."""
        content = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

        assert scan_content(content, "package-lock.json") == []
        assert scan_content(content, "yarn.lock") == []
        assert scan_content(content, "poetry.lock") == []


class TestScanFiles:
    """Tests for scanning multiple files."""

    def test_scan_multiple_files(self) -> None:
        """Test scanning multiple files."""
        files = {
            "config.py": "AWS_KEY = AKIAIOSFODNN7EXAMPLE",
            "main.py": "print('hello')",
            "auth.py": "token = ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        }

        result = scan_files(files)

        assert result.has_secrets is True
        assert len(result.matches) == 2
        assert result.files_scanned == 3

    def test_scan_no_secrets(self) -> None:
        """Test scanning files with no secrets."""
        files = {
            "main.py": "print('hello')",
            "utils.py": "def add(a, b): return a + b",
        }

        result = scan_files(files)

        assert result.has_secrets is False
        assert len(result.matches) == 0
        assert result.files_scanned == 2

    def test_scan_empty_files(self) -> None:
        """Test scanning empty file dict."""
        result = scan_files({})

        assert result.has_secrets is False
        assert len(result.matches) == 0
        assert result.files_scanned == 0


class TestScanResult:
    """Tests for ScanResult."""

    def test_summary_no_secrets(self) -> None:
        """Test summary when no secrets found."""
        result = ScanResult(has_secrets=False, matches=[], files_scanned=10)
        summary = result.get_summary()

        assert "No secrets found" in summary
        assert "10 files" in summary

    def test_summary_with_secrets(self) -> None:
        """Test summary when secrets are found."""
        matches = [
            SecretMatch(
                file_path="config.py",
                line_number=5,
                secret_type=SecretType.AWS_ACCESS_KEY,
                matched_text="redacted",
                context="redacted",
            ),
            SecretMatch(
                file_path="config.py",
                line_number=10,
                secret_type=SecretType.GITHUB_TOKEN,
                matched_text="redacted",
                context="redacted",
            ),
            SecretMatch(
                file_path=".env",
                line_number=1,
                secret_type=SecretType.DATABASE_URL,
                matched_text="redacted",
                context="redacted",
            ),
        ]
        result = ScanResult(has_secrets=True, matches=matches, files_scanned=5)
        summary = result.get_summary()

        assert "3 potential secret(s)" in summary
        assert "config.py" in summary
        assert ".env" in summary
        assert "Line 5" in summary
        assert "AWS Access Key" in summary


class TestSecretFoundError:
    """Tests for SecretFoundError exception."""

    def test_exception_message(self) -> None:
        """Test exception includes summary."""
        matches = [
            SecretMatch(
                file_path="config.py",
                line_number=5,
                secret_type=SecretType.AWS_ACCESS_KEY,
                matched_text="redacted",
                context="redacted",
            ),
        ]
        result = ScanResult(has_secrets=True, matches=matches, files_scanned=1)

        error = SecretFoundError(result)

        assert "1 potential secret(s)" in str(error)
        assert error.scan_result is result

    def test_exception_can_be_raised(self) -> None:
        """Test exception can be raised and caught."""
        result = ScanResult(has_secrets=True, matches=[], files_scanned=1)

        with pytest.raises(SecretFoundError) as exc_info:
            raise SecretFoundError(result)

        assert exc_info.value.scan_result is result
