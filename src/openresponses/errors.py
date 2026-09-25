from __future__ import annotations

from typing import Any


class OpenResponsesError(Exception):
    """Base class for all SDK errors."""


class APIConnectionError(OpenResponsesError):
    """The request could not reach the provider."""


class APITimeoutError(APIConnectionError):
    """The request timed out."""


class APIStatusError(OpenResponsesError):
    """The provider returned a non-success HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: str = "",
        headers: dict[str, str] | None = None,
        request_url: str | None = None,
        error: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}
        self.request_url = request_url
        self.error = error


class AuthenticationError(APIStatusError):
    pass


class PermissionDeniedError(APIStatusError):
    pass


class NotFoundError(APIStatusError):
    pass


class RateLimitError(APIStatusError):
    pass


class InternalServerError(APIStatusError):
    pass


class APIResponseValidationError(OpenResponsesError):
    """The provider response did not conform to the pinned OpenAPI model."""


class ResponseTooLargeError(APIResponseValidationError):
    """The provider response exceeded the configured byte limit."""


class ProtocolError(OpenResponsesError):
    """The provider used an invalid protocol envelope or transport behavior."""


class SSEProtocolError(ProtocolError):
    pass


class WebSocketError(ProtocolError):
    """A WebSocket connection or turn failed."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        error: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.error = error
