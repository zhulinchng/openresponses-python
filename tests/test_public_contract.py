from __future__ import annotations

import importlib
from pathlib import Path

import tomllib


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
        "BadRequestError",
        "ModelError",
    ]:
        assert hasattr(module, name), name


def test_package_and_runtime_versions_match() -> None:
    module = importlib.import_module("openresponses")
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert module.__version__ == project["project"]["version"]


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
