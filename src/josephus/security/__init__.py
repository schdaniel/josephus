"""Security module for Josephus."""

from josephus.security.errors import (
    get_error_code,
    sanitize_error_message,
)
from josephus.security.scanner import (
    ScanResult,
    SecretFoundError,
    SecretMatch,
    SecretType,
    scan_content,
    scan_files,
)

__all__ = [
    "ScanResult",
    "SecretFoundError",
    "SecretMatch",
    "SecretType",
    "get_error_code",
    "sanitize_error_message",
    "scan_content",
    "scan_files",
]
