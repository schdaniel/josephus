"""Error sanitization utilities to prevent information disclosure.

This module provides functions to sanitize error messages before they are
stored in the database or returned to clients, preventing leakage of
sensitive internal information.

References:
- CWE-209: Generation of Error Message Containing Sensitive Information
- OWASP: Error Handling
"""

import re
from typing import Final

# Error type to safe message mappings
_SAFE_ERROR_MESSAGES: Final[dict[str, str]] = {
    # Connection errors
    "ConnectionError": "Unable to connect to external service",
    "ConnectionRefusedError": "Unable to connect to external service",
    "ConnectionResetError": "Connection was interrupted",
    "BrokenPipeError": "Connection was interrupted",
    # Timeout errors
    "TimeoutError": "Request timed out",
    "asyncio.TimeoutError": "Request timed out",
    "ReadTimeout": "Request timed out",
    "ConnectTimeout": "Connection timed out",
    # HTTP errors
    "HTTPStatusError": "External API request failed",
    "HTTPError": "External API request failed",
    "RequestError": "External request failed",
    # Data format errors
    "JSONDecodeError": "Invalid response format",
    "ValidationError": "Invalid data format",
    "ValueError": "Invalid input provided",
    "TypeError": "Invalid input type",
    # File errors
    "FileNotFoundError": "Required resource not found",
    "PermissionError": "Access denied to resource",
    "IsADirectoryError": "Invalid resource type",
    "NotADirectoryError": "Invalid resource type",
    # Database errors
    "OperationalError": "Database operation failed",
    "IntegrityError": "Data constraint violation",
    "ProgrammingError": "Database operation failed",
    "InterfaceError": "Database connection failed",
    # Authentication/Authorization
    "AuthenticationError": "Authentication failed",
    "AuthorizationError": "Authorization failed",
    "PermissionDenied": "Access denied",
    # Rate limiting
    "RateLimitError": "Rate limit exceeded",
    "TooManyRequests": "Too many requests",
    # GitHub-specific
    "GitHubError": "GitHub API request failed",
    "RateLimitExceeded": "GitHub rate limit exceeded",
    # LLM-specific
    "AnthropicError": "AI service request failed",
    "OpenAIError": "AI service request failed",
    "APIError": "External API request failed",
    "APIConnectionError": "Unable to connect to AI service",
    "AnthropicRateLimitError": "AI service rate limit exceeded",
    "OpenAIRateLimitError": "AI service rate limit exceeded",
}

# Patterns that might leak sensitive information
_SENSITIVE_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    # File paths
    (re.compile(r"/[a-zA-Z0-9_/.-]+\.(py|js|ts|json|yaml|yml|env|cfg|conf|ini)"), "[path]"),
    # IP addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[ip]"),
    # Ports
    (re.compile(r":\d{2,5}\b"), ":[port]"),
    # Database URLs
    (re.compile(r"(postgres|mysql|sqlite|mongodb)://[^\s]+"), "[database_url]"),
    # API keys/tokens (generic patterns)
    (
        re.compile(r"(api[_-]?key|token|secret|password|credential)[=:]\s*\S+", re.IGNORECASE),
        "[redacted]",
    ),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[email]"),
    # UUIDs (might be internal IDs)
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE
        ),
        "[id]",
    ),
]

# Generic fallback message
_GENERIC_ERROR_MESSAGE: Final[str] = "An internal error occurred"


def sanitize_error_message(error: Exception) -> str:
    """Sanitize an exception for safe external display.

    This function converts exceptions into safe, non-revealing error messages
    suitable for storage in the database and display to end users.

    The full exception details should still be logged internally using
    logfire or similar before calling this function.

    Args:
        error: The exception to sanitize

    Returns:
        A safe error message that doesn't reveal internal details

    Example:
        >>> try:
        ...     raise ConnectionError("PostgreSQL at localhost:5432 refused")
        ... except Exception as e:
        ...     logfire.error("Task failed", error=str(e), exc_info=True)
        ...     safe_msg = sanitize_error_message(e)
        >>> safe_msg
        'Unable to connect to external service'
    """
    error_type = type(error).__name__

    # Check for known error types
    if error_type in _SAFE_ERROR_MESSAGES:
        return _SAFE_ERROR_MESSAGES[error_type]

    # Check parent classes for known types
    for cls in type(error).__mro__:
        cls_name = cls.__name__
        if cls_name in _SAFE_ERROR_MESSAGES:
            return _SAFE_ERROR_MESSAGES[cls_name]

    # For unknown errors, try to sanitize the message
    return _sanitize_message_content(str(error))


def _sanitize_message_content(message: str) -> str:
    """Sanitize a message string by removing sensitive patterns.

    This is a fallback for when we don't recognize the error type.
    It attempts to redact obviously sensitive information.

    Args:
        message: The raw error message

    Returns:
        Sanitized message or generic message if too much was redacted
    """
    if not message:
        return _GENERIC_ERROR_MESSAGE

    sanitized = message

    # Apply all sensitive pattern replacements
    for pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    # If the message was heavily redacted or is now mostly placeholders,
    # return a generic message instead
    placeholder_count = sanitized.count("[")
    if placeholder_count >= 3 or len(sanitized) < 10:
        return _GENERIC_ERROR_MESSAGE

    # Truncate very long messages
    if len(sanitized) > 200:
        sanitized = sanitized[:197] + "..."

    return sanitized


def get_error_code(error: Exception) -> str:
    """Get a stable error code for programmatic handling.

    Error codes follow the format: CATEGORY_SPECIFIC
    e.g., CONNECTION_REFUSED, TIMEOUT_READ, AUTH_FAILED

    Args:
        error: The exception

    Returns:
        A stable error code string
    """
    error_type = type(error).__name__

    # Map error types to codes
    error_codes: dict[str, str] = {
        "ConnectionError": "CONNECTION_FAILED",
        "ConnectionRefusedError": "CONNECTION_REFUSED",
        "TimeoutError": "TIMEOUT",
        "HTTPStatusError": "HTTP_ERROR",
        "JSONDecodeError": "PARSE_ERROR",
        "ValidationError": "VALIDATION_ERROR",
        "FileNotFoundError": "NOT_FOUND",
        "PermissionError": "PERMISSION_DENIED",
        "AuthenticationError": "AUTH_FAILED",
        "RateLimitError": "RATE_LIMITED",
    }

    return error_codes.get(error_type, "INTERNAL_ERROR")
