from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import Field

from .config import ClientConfig
from .errors import (
    APIResponseValidationError,
    APIStatusError,
    AuthenticationError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ResponseTooLargeError,
)
from .types.base import OpenResponsesModel
from .types.generated import (
    AllowedToolChoice,
    Error1,
    FunctionTool,
    FunctionToolChoice,
    IncompleteDetails,
    TextField,
    ToolChoiceValueEnum,
    TruncationEnum,
)


def model_json(value: Any) -> Any:

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True, exclude_unset=True)
    if hasattr(value, "root") and value.__class__.__name__.endswith("RootModel"):
        return model_json(value.root)
    if isinstance(value, Mapping):
        return {key: model_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [model_json(item) for item in value]
    return value


def request_json(value: Any) -> dict[str, Any]:
    payload = model_json(value)
    if not isinstance(payload, dict):
        raise TypeError("request payload must serialize to an object")
    return payload


def _bounded_content(response: httpx.Response, max_bytes: int) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise APIResponseValidationError("provider returned invalid Content-Length") from exc
        if declared > max_bytes:
            raise ResponseTooLargeError(
                f"provider response Content-Length {declared} exceeds {max_bytes} bytes"
            )
    content = response.content
    if len(content) > max_bytes:
        raise ResponseTooLargeError(f"provider response exceeds {max_bytes} bytes")
    return content


def _validate_response_payload(
    payload: dict[str, Any], model: type[Any], compatibility: str
) -> Any:
    object_type = payload.get("object")
    expected_object = "response.compaction" if model.__name__ == "CompactResource" else "response"
    if compatibility == "strict":
        return model.model_validate(payload)
    if object_type != expected_object:
        raise APIResponseValidationError(
            f"provider response object must be {expected_object!r}, got {object_type!r}"
        )
    if not isinstance(payload.get("id"), str):
        raise APIResponseValidationError("provider response requires string id")
    if not isinstance(payload.get("output"), list):
        raise APIResponseValidationError("provider response requires list output")
    normalized = dict(payload)
    if "created_at" not in normalized and "created" in normalized:
        normalized["created_at"] = normalized["created"]
    if expected_object == "response.compaction" or compatibility != "openai-compatible":
        return model.model_validate(normalized)
    return OpenAICompatibleResponse.model_validate(normalized)


def parse_json_response(response: httpx.Response, model: type[Any], config: ClientConfig) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        raise APIResponseValidationError(
            f"expected application/json response, got {content_type or 'missing content-type'}"
        )
    content = _bounded_content(response, config.max_response_bytes)
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeDecodeError) as exc:
        raise APIResponseValidationError("provider returned malformed JSON") from exc
    if not isinstance(payload, dict):
        raise APIResponseValidationError("provider response must be a JSON object")
    try:
        return _validate_response_payload(payload, model, config.response_compatibility)
    except APIResponseValidationError:
        raise
    except Exception as exc:
        raise APIResponseValidationError(f"provider response failed validation: {exc}") from exc


def status_error(
    response: httpx.Response,
    max_bytes: int = 16 * 1024 * 1024,
    request: httpx.Request | None = None,
) -> APIStatusError:
    status = response.status_code
    raw = response.content[: max_bytes + 1]
    body = raw[:max_bytes].decode("utf-8", errors="replace")
    error = None
    try:
        payload = json.loads(body)
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
    except (ValueError, UnicodeDecodeError):
        pass
    message = "provider returned an error"
    if isinstance(error, dict) and error.get("message"):
        message = str(error["message"])
    common: dict[str, Any] = {
        "status_code": status,
        "body": body,
        "headers": dict(response.headers),
        "request_url": (
            str((request or response.request).url) if (request or response.request) else None
        ),
        "error": error,
    }
    if status == 401:
        return AuthenticationError(message, **common)
    if status == 403:
        return PermissionDeniedError(message, **common)
    if status == 404:
        return NotFoundError(message, **common)
    if status == 429:
        return RateLimitError(message, **common)
    if status >= 500:
        return InternalServerError(message, **common)
    return APIStatusError(message, **common)


class CompatibleContent(OpenResponsesModel):
    type: str
    text: str | None = None
    annotations: list[Any] = Field(default_factory=list)
    image_url: str | None = None
    detail: str | None = None
    filename: str | None = None
    file_url: str | None = None
    file_data: str | None = None
    video_url: str | None = None
    refusal: str | None = None
    summary: str | None = None
    id: str | None = None
    status: str | None = None
    role: str | None = None
    logprobs: list[Any] | None = None


class CompatibleItem(OpenResponsesModel):
    type: str
    id: str | None = None
    call_id: str | None = None
    name: str | None = None
    arguments: str | None = None
    output: Any = None
    status: str | None = None
    role: str | None = None
    content: list[CompatibleContent] | None = None
    phase: str | None = None
    encrypted_content: str | None = None
    created_by: str | None = None
    summary: list[CompatibleContent] | None = None


class OpenAICompatibleResponse(OpenResponsesModel):
    id: str
    object: str
    created_at: int | None = None
    completed_at: int | None = None
    status: str | None = None
    incomplete_details: IncompleteDetails | None = None
    model: str | None = None
    previous_response_id: str | None = None
    instructions: str | None = None
    output: list[CompatibleItem] = Field(default_factory=list)
    output_text: str | None = None
    error: Error1 | None = None
    tools: list[FunctionTool] = Field(default_factory=list)
    tool_choice: FunctionToolChoice | ToolChoiceValueEnum | AllowedToolChoice | str | None = None
    truncation: TruncationEnum | None = None
    parallel_tool_calls: bool | None = None
    text: TextField | None = None
    top_p: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    top_logprobs: int | None = None
    temperature: float | None = None
    reasoning: Any = None
    usage: Any = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    store: bool | None = None
    background: bool | None = None
    service_tier: str | None = None
    metadata: Any = None
    safety_identifier: str | None = None
    prompt_cache_key: str | None = None
