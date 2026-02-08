"""Consistent error handling for API responses."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    """Standard error codes for API responses."""

    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"

    # Authentication errors (401)
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_API_KEY = "INVALID_API_KEY"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"

    # Authorization errors (403)
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"

    # Not found errors (404)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"

    # Conflict errors (409)
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    JOB_ALREADY_EXISTS = "JOB_ALREADY_EXISTS"

    # Rate limiting errors (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"


class FieldError(BaseModel):
    """Details about a specific field validation error."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")
    code: str = Field("invalid", description="Error code for this field")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Human-readable error description")
    request_id: str = Field(..., description="Unique request ID for support reference")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the error occurred"
    )
    details: dict[str, Any] | None = Field(
        None, description="Additional error details if available"
    )
    errors: list[FieldError] | None = Field(
        None, description="List of field-specific errors for validation failures"
    )
    suggestion: str | None = Field(None, description="Suggested action to resolve the error")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "VALIDATION_ERROR",
                "message": "The request contains invalid fields",
                "request_id": "req_abc123",
                "timestamp": "2024-01-15T10:30:00Z",
                "errors": [
                    {"field": "owner", "message": "This field is required", "code": "required"}
                ],
                "suggestion": "Please provide the required 'owner' field",
            }
        }
    }


@dataclass
class APIError(Exception):
    """Base class for API errors with consistent formatting."""

    code: ErrorCode
    message: str
    status_code: int = 400
    details: dict[str, Any] | None = None
    errors: list[FieldError] = field(default_factory=list)
    suggestion: str | None = None

    def to_response(self, request_id: str) -> ErrorResponse:
        """Convert to ErrorResponse."""
        return ErrorResponse(
            error=self.code.value,
            message=self.message,
            request_id=request_id,
            details=self.details,
            errors=self.errors if self.errors else None,
            suggestion=self.suggestion,
        )


class ValidationError(APIError):
    """Validation error for invalid request data."""

    def __init__(
        self,
        message: str = "The request contains invalid fields",
        errors: list[FieldError] | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=422,
            errors=errors or [],
            suggestion=suggestion,
        )


class AuthenticationError(APIError):
    """Authentication error for missing or invalid credentials."""

    def __init__(
        self,
        message: str = "Authentication is required to access this resource",
        code: ErrorCode = ErrorCode.AUTHENTICATION_REQUIRED,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=401,
            suggestion=suggestion or "Provide a valid API key in the Authorization header",
        )


class NotFoundError(APIError):
    """Error for resources that don't exist."""

    def __init__(
        self,
        resource: str = "Resource",
        resource_id: str | None = None,
        code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND,
    ) -> None:
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} '{resource_id}' not found"
        super().__init__(
            code=code,
            message=message,
            status_code=404,
        )


class RateLimitError(APIError):
    """Error for rate limit exceeded."""

    def __init__(
        self,
        retry_after: int | None = None,
        limit: str | None = None,
    ) -> None:
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        if limit:
            details["limit"] = limit

        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded. Please slow down your requests.",
            status_code=429,
            details=details if details else None,
            suggestion=f"Wait {retry_after} seconds before retrying"
            if retry_after
            else "Please slow down your requests",
        )


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


def get_request_id(request: Request) -> str:
    """Get or generate the request ID for a request."""
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    return generate_request_id()


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions and return consistent error responses."""
    request_id = get_request_id(request)
    response = exc.to_response(request_id)

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(mode="json", exclude_none=True),
        headers={"X-Request-ID": request_id},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException and return consistent error responses."""
    request_id = get_request_id(request)

    # Map status codes to error codes
    error_code_map = {
        400: ErrorCode.INVALID_REQUEST,
        401: ErrorCode.AUTHENTICATION_REQUIRED,
        403: ErrorCode.PERMISSION_DENIED,
        404: ErrorCode.RESOURCE_NOT_FOUND,
        409: ErrorCode.RESOURCE_CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.INTERNAL_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }

    error_code = error_code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

    response = ErrorResponse(
        error=error_code.value,
        message=str(exc.detail) if exc.detail else "An error occurred",
        request_id=request_id,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(mode="json", exclude_none=True),
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic validation errors and return consistent error responses."""
    from pydantic import ValidationError as PydanticValidationError

    request_id = get_request_id(request)

    if isinstance(exc, PydanticValidationError):
        errors = []
        for error in exc.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            errors.append(
                FieldError(
                    field=field_path,
                    message=error["msg"],
                    code=error["type"],
                )
            )

        response = ErrorResponse(
            error=ErrorCode.VALIDATION_ERROR.value,
            message="Request validation failed",
            request_id=request_id,
            errors=errors,
            suggestion="Check the 'errors' field for details on invalid fields",
        )
    else:
        response = ErrorResponse(
            error=ErrorCode.VALIDATION_ERROR.value,
            message=str(exc),
            request_id=request_id,
        )

    return JSONResponse(
        status_code=422,
        content=response.model_dump(mode="json", exclude_none=True),
        headers={"X-Request-ID": request_id},
    )
