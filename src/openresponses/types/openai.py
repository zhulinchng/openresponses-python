"""Current OpenAI Responses API models.

The pinned OpenResponses models remain the default contract. These models are
used only when a client explicitly selects ``response_compatibility="openai"``.
They preserve current OpenAI fields and provider-specific output/event shapes
without weakening strict OpenResponses validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .base import OpenResponsesModel


class OpenAIAccessPrograms(OpenResponsesModel):
    cyber: Literal["standard", "daybreak_blue", "daybreak_red"] | None = None


class OpenAIContextManagement(OpenResponsesModel):
    type: str
    compact_threshold: int | None = None


class OpenAIRequest(OpenResponsesModel):
    """Current OpenAI Responses API request."""

    input: str | list[Any] | None = None
    instructions: Any = None
    previous_response_id: str | None = None
    conversation: str | dict[str, Any] | None = None
    include: list[str] | None = None
    tools: list[Any] | None = None
    tool_choice: Any = None
    metadata: dict[str, str] | None = Field(default=None, max_length=16)
    text: Any = None
    temperature: float | None = None
    top_p: float | None = None
    parallel_tool_calls: bool | None = None
    stream: bool | None = None
    stream_options: dict[str, Any] | None = None
    background: bool | None = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    reasoning: Any = None
    safety_identifier: str | None = Field(default=None, max_length=64)
    prompt_cache_key: str | None = Field(default=None, max_length=64)
    prompt_cache_options: dict[str, Any] | None = None
    prompt_cache_retention: Literal["in_memory", "24h"] | None = None
    prompt: dict[str, Any] | None = None
    access_programs: OpenAIAccessPrograms | None = None
    context_management: list[OpenAIContextManagement] | None = None
    moderation: dict[str, Any] | None = None
    service_tier: str | None = None
    store: bool | None = None
    truncation: Literal["auto", "disabled"] | None = None
    top_logprobs: int | None = Field(default=None, ge=0, le=20)
    user: str | None = None


class OpenAICompactRequest(OpenResponsesModel):
    """Current OpenAI Responses API compact request."""

    input: str | list[Any] | None = None
    previous_response_id: str | None = None
    instructions: Any = None
    prompt_cache_key: str | None = Field(default=None, max_length=64)


class OpenAIWebSocketRequest(OpenAIRequest):
    """Current OpenAI Responses API WebSocket ``response.create`` event."""

    type: Literal["response.create"] = "response.create"
    stream_id: str | None = Field(default=None, min_length=1, max_length=256)
    generate: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_http_only_fields(cls, value: Any) -> Any:
        if isinstance(value, Mapping) and any(
            name in value for name in ("stream", "stream_options", "background")
        ):
            raise ValueError(
                "stream, stream_options, and background are not allowed in WebSocket requests"
            )
        return value

    @field_validator("stream", "stream_options", "background")
    @classmethod
    def reject_explicit_http_fields(cls, value: Any) -> Any:
        if value is not None:
            raise ValueError("HTTP-only fields are not allowed in WebSocket requests")
        return value


class OpenAIResponseItem(OpenResponsesModel):
    """A current OpenAI Responses output item."""

    type: str
    id: str | None = None
    status: str | None = None
    role: str | None = None
    content: list[dict[str, Any]] | str | None = None
    call_id: str | None = None
    name: str | None = None
    arguments: str | None = None
    output: Any = None
    phase: str | None = None
    action: Any = None
    summary: list[dict[str, Any]] | str | None = None


class OpenAIResponse(OpenResponsesModel):
    """The current OpenAI Responses API response object."""

    id: str
    object: Literal["response"]
    created_at: float
    access_programs: Any = None
    completed_at: float | None = None
    status: str | None = None
    error: Any = None
    incomplete_details: Any = None
    instructions: Any = None
    metadata: dict[str, str] | None = None
    model: str
    output: list[OpenAIResponseItem] = Field(default_factory=list)
    parallel_tool_calls: bool | None = None
    temperature: float | None = None
    tool_choice: Any = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    top_p: float | None = None
    background: bool | None = None
    conversation: Any = None
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    moderation: Any = None
    previous_response_id: str | None = None
    prompt: Any = None
    prompt_cache_diagnostics: Any = None
    prompt_cache_key: str | None = None
    prompt_cache_options: Any = None
    prompt_cache_retention: str | None = None
    reasoning: Any = None
    safety_identifier: str | None = None
    service_tier: str | None = None
    text: Any = None
    top_logprobs: int | None = None
    truncation: str | None = None
    usage: Any = None
    user: str | None = None

    @property
    def output_text(self) -> str:
        """Aggregate assistant ``output_text`` content parts."""

        texts: list[str] = []
        for item in self.output:
            if item.type != "message" or not isinstance(item.content, list):
                continue
            for content in item.content:
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    texts.append(content["text"])
        return "".join(texts)


class OpenAICompactedResponse(OpenResponsesModel):
    """The current OpenAI Responses API compact response object."""

    id: str
    object: Literal["response.compaction"]
    created_at: float
    output: list[OpenAIResponseItem] = Field(default_factory=list)
    usage: Any = None


class OpenAIStreamingEvent(OpenResponsesModel):
    """A typed envelope for a current OpenAI Responses stream event."""

    type: str
    sequence_number: int | None = None
    response: OpenAIResponse | None = None
    item: Any = None
    output_index: int | None = None
    content_index: int | None = None
    item_id: str | None = None
    delta: str | None = None
    text: str | None = None
    part: Any = None
    arguments: str | None = None
    code: str | None = None
    message: str | None = None
    param: str | None = None
    obfuscation: str | None = None
    logprobs: list[Any] | None = None
    error: Any = None
    status: str | None = None
    stream_id: str | None = None


class OpenAIWebSocketError(OpenResponsesModel):
    """A current OpenAI Responses WebSocket error event."""

    type: str
    status: int | None = None
    code: str | None = None
    message: str
    param: str | None = None
    error: Any = None


__all__ = [
    "OpenAIAccessPrograms",
    "OpenAICompactRequest",
    "OpenAICompactedResponse",
    "OpenAIContextManagement",
    "OpenAIRequest",
    "OpenAIResponse",
    "OpenAIResponseItem",
    "OpenAIStreamingEvent",
    "OpenAIWebSocketError",
    "OpenAIWebSocketRequest",
]
