"""Integration tests for security scanning in workflows."""

import pytest

from josephus.security import SecretFoundError, scan_files


class TestSecurityScanningWorkflow:
    """Integration tests for secret scanning in doc generation workflow."""

    def test_scan_clean_repository(self) -> None:
        """Test scanning a repository with no secrets."""
        files = {
            "src/main.py": """
def main():
    print("Hello, world!")
    return 0

if __name__ == "__main__":
    main()
""",
            "src/utils.py": """
def add(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b
""",
            "README.md": """
# My Project

A simple Python project.

## Installation

pip install myproject

## Usage

python -m myproject
""",
            "config/settings.py": """
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DEBUG = True
""",
        }

        result = scan_files(files)

        assert result.has_secrets is False
        assert len(result.matches) == 0
        assert result.files_scanned == 4

    def test_scan_repository_with_secrets_blocks(self) -> None:
        """Test that repository with secrets raises SecretFoundError."""
        files = {
            "src/main.py": """
def main():
    print("Hello, world!")
""",
            ".env": """
# Database
DATABASE_URL=postgresql://user:password123@localhost:5432/mydb

# AWS (these are fake test values)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
""",
            "config.py": """
# API Keys
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
""",
        }

        result = scan_files(files)

        assert result.has_secrets is True
        assert len(result.matches) >= 2  # At least DB URL and GitHub token

        # Verify we can raise SecretFoundError
        with pytest.raises(SecretFoundError) as exc_info:
            if result.has_secrets:
                raise SecretFoundError(result)

        assert "potential secret" in str(exc_info.value)

    def test_scan_skips_lock_files(self) -> None:
        """Test that lock files are skipped during scanning."""
        files = {
            "package.json": '{"name": "test"}',
            "package-lock.json": """
{
  "packages": {
    "node_modules/some-package": {
      "resolved": "https://user:ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@registry.npmjs.org/pkg"
    }
  }
}
""",
            "yarn.lock": """
some-package@^1.0.0:
  resolved "https://user:ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@registry.yarnpkg.com/pkg"
""",
        }

        result = scan_files(files)

        # Lock files should be skipped, so no secrets found
        assert result.has_secrets is False
        assert result.files_scanned == 1  # Only package.json scanned

    def test_scan_result_summary(self) -> None:
        """Test that scan result provides useful summary."""
        files = {
            "config.py": 'API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"',
            ".env": "GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        }

        result = scan_files(files)

        summary = result.get_summary()

        assert "potential secret" in summary
        assert "config.py" in summary
        assert ".env" in summary

    def test_scan_detects_multiple_secrets_per_file(self) -> None:
        """Test detection of multiple secrets in single file."""
        files = {
            "secrets.env": """
# This file has multiple secrets for testing
OPENAI_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DATABASE_URL=postgresql://admin:secretpass@db.example.com:5432/prod
""",
        }

        result = scan_files(files)

        assert result.has_secrets is True
        # Should find multiple secrets in the same file
        secrets_in_file = [m for m in result.matches if m.file_path == "secrets.env"]
        assert len(secrets_in_file) >= 3


class TestSecurityWithConfig:
    """Integration tests for security scanning with config files."""

    def test_josephus_config_not_flagged(self) -> None:
        """Test that .josephus config files are not flagged as secrets."""
        files = {
            ".josephus/config.yml": """
output_dir: docs
output_format: markdown
create_pr: true
""",
            ".josephus/guidelines.xml": """
# Documentation Guidelines

Write clear, concise documentation for developers.
Use code examples where appropriate.

## Scope

Include all public APIs and their usage examples.
Exclude internal implementation details.
""",
        }

        result = scan_files(files)

        assert result.has_secrets is False

    def test_example_secrets_in_docs_flagged(self) -> None:
        """Test that example secrets in docs are still flagged (safety first)."""
        files = {
            "docs/getting-started.md": """
# Getting Started

## Configuration

Set your API key:

```bash
export OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
""",
        }

        result = scan_files(files)

        # Even in docs, we flag potential secrets for safety
        # The user can review and decide if it's a real secret or example
        assert result.has_secrets is True
