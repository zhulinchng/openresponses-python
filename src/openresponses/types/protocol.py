"""Handwritten protocol unions and request models."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import Discriminator, Field, Tag, TypeAdapter, field_validator, model_validator

from .base import OpenResponsesModel
from .generated import (
    AllowedToolsParam,
    AssistantMessageItemParam,
    CompactionBody,
    CompactionSummaryItemParam,
    DeveloperMessageItemParam,
    ErrorStreamingEvent,
    FunctionCall,
    FunctionCallItemParam,
    FunctionCallOutput,
    FunctionCallOutputItemParam,
    FunctionToolParam,
    InputFileContent,
    InputImageContent,
    InputTextContent,
    InputVideoContent,
    ItemReferenceParam,
    Message,
    OutputTextContent,
    ReasoningBody,
    ReasoningItemParam,
    ReasoningParam,
    ReasoningTextContent,
    RefusalContent,
    ResponseCompletedStreamingEvent,
    ResponseContentPartAddedStreamingEvent,
    ResponseContentPartDoneStreamingEvent,
    ResponseCreatedStreamingEvent,
    ResponseFailedStreamingEvent,
    ResponseFunctionCallArgumentsDeltaStreamingEvent,
    ResponseFunctionCallArgumentsDoneStreamingEvent,
    ResponseIncompleteStreamingEvent,
    ResponseInProgressStreamingEvent,
    ResponseOutputItemAddedStreamingEvent,
    ResponseOutputItemDoneStreamingEvent,
    ResponseOutputTextAnnotationAddedStreamingEvent,
    ResponseOutputTextDeltaStreamingEvent,
    ResponseOutputTextDoneStreamingEvent,
    ResponseQueuedStreamingEvent,
    ResponseReasoningDeltaStreamingEvent,
    ResponseReasoningDoneStreamingEvent,
    ResponseReasoningSummaryDeltaStreamingEvent,
    ResponseReasoningSummaryDoneStreamingEvent,
    ResponseReasoningSummaryPartAddedStreamingEvent,
    ResponseReasoningSummaryPartDoneStreamingEvent,
    ResponseRefusalDeltaStreamingEvent,
    ResponseRefusalDoneStreamingEvent,
    SpecificFunctionParam,
    StreamOptionsParam,
    SummaryTextContent,
    SystemMessageItemParam,
    TextContent,
    TextParam,
    ToolChoiceValueEnum,
    UserMessageItemParam,
)


class UnknownItem(OpenResponsesModel):
    type: str


class UnknownStreamingEvent(OpenResponsesModel):
    type: str
    sequence_number: int | None = None


def _input_item_tag(value: Any) -> str:
    if isinstance(
        value,
        (
            UserMessageItemParam,
            SystemMessageItemParam,
            DeveloperMessageItemParam,
            AssistantMessageItemParam,
        ),
    ):
        return f"message:{value.role}"
    if isinstance(
        value,
        (
            ItemReferenceParam,
            ReasoningItemParam,
            CompactionSummaryItemParam,
            FunctionCallItemParam,
            FunctionCallOutputItemParam,
        ),
    ):
        return str(value.type or "item_reference")
    if not isinstance(value, dict):
        return "unknown"
    item_type = value.get("type")
    if item_type in {None, "item_reference"} and "id" in value:
        return "item_reference"
    if item_type == "message":
        return f"message:{value.get('role', 'unknown')}"
    if item_type in {
        "reasoning",
        "compaction",
        "function_call",
        "function_call_output",
    }:
        return str(item_type)
    return "unknown"


InputItem = Annotated[
    Annotated[ItemReferenceParam, Tag("item_reference")]
    | Annotated[ReasoningItemParam, Tag("reasoning")]
    | Annotated[CompactionSummaryItemParam, Tag("compaction")]
    | Annotated[UserMessageItemParam, Tag("message:user")]
    | Annotated[SystemMessageItemParam, Tag("message:system")]
    | Annotated[DeveloperMessageItemParam, Tag("message:developer")]
    | Annotated[AssistantMessageItemParam, Tag("message:assistant")]
    | Annotated[FunctionCallItemParam, Tag("function_call")]
    | Annotated[FunctionCallOutputItemParam, Tag("function_call_output")]
    | Annotated[UnknownItem, Tag("unknown")],
    Discriminator(_input_item_tag),
]
InputItemAdapter: TypeAdapter[InputItem] = TypeAdapter(InputItem)

ResponseContentPart: TypeAlias = (
    InputTextContent
    | OutputTextContent
    | TextContent
    | SummaryTextContent
    | InputImageContent
    | InputFileContent
    | InputVideoContent
    | ReasoningTextContent
    | RefusalContent
)
ResponseContentPartAdapter: TypeAdapter[ResponseContentPart] = TypeAdapter(ResponseContentPart)

ResponseItem: TypeAlias = (
    Message | FunctionCall | FunctionCallOutput | ReasoningBody | CompactionBody
)
ResponseItemAdapter: TypeAdapter[ResponseItem] = TypeAdapter(ResponseItem)

ToolParam: TypeAlias = FunctionToolParam
ToolChoice: TypeAlias = SpecificFunctionParam | ToolChoiceValueEnum | AllowedToolsParam
ToolChoiceAdapter: TypeAdapter[ToolChoice] = TypeAdapter(ToolChoice)

_STREAMING_EVENT_TAGS = {
    "response.created",
    "response.queued",
    "response.in_progress",
    "response.completed",
    "response.failed",
    "response.incomplete",
    "response.output_item.added",
    "response.output_item.done",
    "response.reasoning_summary_part.added",
    "response.reasoning_summary_part.done",
    "response.content_part.added",
    "response.content_part.done",
    "response.output_text.delta",
    "response.output_text.done",
    "response.refusal.delta",
    "response.refusal.done",
    "response.reasoning.delta",
    "response.reasoning.done",
    "response.reasoning_summary_text.delta",
    "response.reasoning_summary_text.done",
    "response.output_text.annotation.added",
    "response.function_call_arguments.delta",
    "response.function_call_arguments.done",
    "error",
}


def _streaming_event_tag(value: Any) -> str:
    if not isinstance(value, dict):
        return "unknown"
    event_type = value.get("type")
    return str(event_type) if event_type in _STREAMING_EVENT_TAGS else "unknown"


StreamingEvent: TypeAlias = Annotated[
    Annotated[ResponseCreatedStreamingEvent, Tag("response.created")]
    | Annotated[ResponseQueuedStreamingEvent, Tag("response.queued")]
    | Annotated[ResponseInProgressStreamingEvent, Tag("response.in_progress")]
    | Annotated[ResponseCompletedStreamingEvent, Tag("response.completed")]
    | Annotated[ResponseFailedStreamingEvent, Tag("response.failed")]
    | Annotated[ResponseIncompleteStreamingEvent, Tag("response.incomplete")]
    | Annotated[ResponseOutputItemAddedStreamingEvent, Tag("response.output_item.added")]
    | Annotated[ResponseOutputItemDoneStreamingEvent, Tag("response.output_item.done")]
    | Annotated[
        ResponseReasoningSummaryPartAddedStreamingEvent,
        Tag("response.reasoning_summary_part.added"),
    ]
    | Annotated[
        ResponseReasoningSummaryPartDoneStreamingEvent, Tag("response.reasoning_summary_part.done")
    ]
    | Annotated[ResponseContentPartAddedStreamingEvent, Tag("response.content_part.added")]
    | Annotated[ResponseContentPartDoneStreamingEvent, Tag("response.content_part.done")]
    | Annotated[ResponseOutputTextDeltaStreamingEvent, Tag("response.output_text.delta")]
    | Annotated[ResponseOutputTextDoneStreamingEvent, Tag("response.output_text.done")]
    | Annotated[ResponseRefusalDeltaStreamingEvent, Tag("response.refusal.delta")]
    | Annotated[ResponseRefusalDoneStreamingEvent, Tag("response.refusal.done")]
    | Annotated[ResponseReasoningDeltaStreamingEvent, Tag("response.reasoning.delta")]
    | Annotated[ResponseReasoningDoneStreamingEvent, Tag("response.reasoning.done")]
    | Annotated[
        ResponseReasoningSummaryDeltaStreamingEvent, Tag("response.reasoning_summary_text.delta")
    ]
    | Annotated[
        ResponseReasoningSummaryDoneStreamingEvent, Tag("response.reasoning_summary_text.done")
    ]
    | Annotated[
        ResponseOutputTextAnnotationAddedStreamingEvent,
        Tag("response.output_text.annotation.added"),
    ]
    | Annotated[
        ResponseFunctionCallArgumentsDeltaStreamingEvent,
        Tag("response.function_call_arguments.delta"),
    ]
    | Annotated[
        ResponseFunctionCallArgumentsDoneStreamingEvent,
        Tag("response.function_call_arguments.done"),
    ]
    | Annotated[ErrorStreamingEvent, Tag("error")]
    | Annotated[UnknownStreamingEvent, Tag("unknown")],
    Discriminator(_streaming_event_tag),
]
StreamingEventAdapter: TypeAdapter[StreamingEvent] = TypeAdapter(StreamingEvent)


class CreateResponseRequest(OpenResponsesModel):
    model: str | None = None
    input: str | list[InputItem] | None = None
    previous_response_id: str | None = None
    include: list[Literal["reasoning.encrypted_content", "message.output_text.logprobs"]] | None = (
        None
    )
    tools: list[ToolParam] | None = None
    tool_choice: ToolChoice | None = None
    metadata: dict[str, str] | None = Field(default=None, max_length=16)
    text: TextParam | None = None
    temperature: float | None = None
    top_p: float | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    parallel_tool_calls: bool | None = None
    stream: bool = False
    stream_options: StreamOptionsParam | None = None
    background: bool = False
    max_output_tokens: int | None = Field(default=None, ge=16)
    max_tool_calls: int | None = Field(default=None, ge=1)
    reasoning: ReasoningParam | None = None
    safety_identifier: str | None = Field(default=None, max_length=64)
    prompt_cache_key: str | None = Field(default=None, max_length=64)
    truncation: Literal["auto", "disabled"] | None = None
    instructions: str | None = None
    store: bool = True
    service_tier: Literal["auto", "default", "flex", "priority"] | None = None
    top_logprobs: int | None = Field(default=None, ge=0, le=20)

    @field_validator("input")
    @classmethod
    def validate_input_length(
        cls, value: str | list[InputItem] | None
    ) -> str | list[InputItem] | None:
        if isinstance(value, str) and len(value) > 10_485_760:
            raise ValueError("input strings must be at most 10485760 characters")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        if len(value) > 16:
            raise ValueError("metadata supports at most 16 entries")
        for key, item in value.items():
            if len(key) > 64:
                raise ValueError("metadata keys must be at most 64 characters")
            if len(item) > 512:
                raise ValueError("metadata values must be at most 512 characters")
        return value


class CompactResponseRequest(OpenResponsesModel):
    model: str
    input: str | list[InputItem] | None = None
    previous_response_id: str | None = None
    instructions: str | None = None
    prompt_cache_key: str | None = Field(default=None, max_length=64)

    @field_validator("input")
    @classmethod
    def validate_input_length(
        cls, value: str | list[InputItem] | None
    ) -> str | list[InputItem] | None:
        if isinstance(value, str) and len(value) > 10_485_760:
            raise ValueError("input strings must be at most 10485760 characters")
        return value

    @model_validator(mode="before")
    @classmethod
    def reject_http_only_fields(cls, value: Any) -> Any:
        if isinstance(value, dict) and {"stream", "stream_options", "background"}.intersection(
            value
        ):
            raise ValueError(
                "stream, stream_options, and background are not allowed in compact requests"
            )
        return value


class WebSocketResponseCreateRequest(CreateResponseRequest):
    type: Literal["response.create"] = "response.create"

    @field_validator("stream", "stream_options", "background")
    @classmethod
    def reject_http_only_fields(cls, value: Any, info: Any) -> Any:
        if value is not None:
            raise ValueError(f"{info.field_name} is not allowed in WebSocket response.create")
        return value


__all__ = [
    "CompactResponseRequest",
    "CreateResponseRequest",
    "InputItem",
    "InputItemAdapter",
    "ResponseContentPart",
    "ResponseContentPartAdapter",
    "ResponseItem",
    "ResponseItemAdapter",
    "StreamingEvent",
    "StreamingEventAdapter",
    "ToolChoice",
    "ToolChoiceAdapter",
    "ToolParam",
    "UnknownItem",
    "UnknownStreamingEvent",
    "WebSocketResponseCreateRequest",
]
