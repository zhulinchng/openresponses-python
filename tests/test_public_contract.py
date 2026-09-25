from __future__ import annotations

import importlib


def test_public_imports() -> None:
    module = importlib.import_module("openresponses")
    for name in [
        "OpenResponses",
        "AsyncOpenResponses",
        "CreateResponseRequest",
        "CompactResponseRequest",
        "ResponseResource",
        "CompactResource",
        "WebSocketErrorEvent",
        "ErrorStreamingEvent",
        "ResponseOutputTextDeltaStreamingEvent",
        "UnknownStreamingEvent",
        "OpenResponsesError",
    ]:
        assert hasattr(module, name), name


def test_generated_event_literals_are_exported() -> None:
    module = importlib.import_module("openresponses")
    events = [
        "ResponseCreatedStreamingEvent",
        "ResponseQueuedStreamingEvent",
        "ResponseInProgressStreamingEvent",
        "ResponseCompletedStreamingEvent",
        "ResponseFailedStreamingEvent",
        "ResponseIncompleteStreamingEvent",
        "ResponseOutputItemAddedStreamingEvent",
        "ResponseOutputItemDoneStreamingEvent",
        "ResponseReasoningSummaryPartAddedStreamingEvent",
        "ResponseReasoningSummaryPartDoneStreamingEvent",
        "ResponseContentPartAddedStreamingEvent",
        "ResponseContentPartDoneStreamingEvent",
        "ResponseOutputTextDeltaStreamingEvent",
        "ResponseOutputTextDoneStreamingEvent",
        "ResponseRefusalDeltaStreamingEvent",
        "ResponseRefusalDoneStreamingEvent",
        "ResponseReasoningDeltaStreamingEvent",
        "ResponseReasoningDoneStreamingEvent",
        "ResponseReasoningSummaryDeltaStreamingEvent",
        "ResponseReasoningSummaryDoneStreamingEvent",
        "ResponseOutputTextAnnotationAddedStreamingEvent",
        "ResponseFunctionCallArgumentsDeltaStreamingEvent",
        "ResponseFunctionCallArgumentsDoneStreamingEvent",
        "ErrorStreamingEvent",
    ]
    assert all(hasattr(module, name) for name in events)
