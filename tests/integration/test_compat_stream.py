from __future__ import annotations

import json

import httpx
import pytest

from openresponses import CreateResponseRequest, OpenResponses
from openresponses.errors import SSEProtocolError


def response_payload() -> dict[str, object]:
    return {
        "id": "resp_compat_stream",
        "object": "response",
        "created": 1,
        "model": "m",
        "output": [],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }


def test_compatibility_stream_accepts_partial_terminal_snapshot() -> None:
    event = {"type": "response.completed", "sequence_number": 0, "response": response_payload()}
    body = f"event: response.completed\ndata: {json.dumps(event)}\n\ndata: [DONE]\n\n".encode()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(
        base_url="http://test",
        response_compatibility="openai-compatible",
        http_client=httpx.Client(transport=transport),
    )
    stream = client.responses.create(CreateResponseRequest(model="m", stream=True))
    events = list(stream)
    assert [event.type for event in events] == ["response.completed"]
    client.close()


def test_compatibility_stream_synthesizes_missing_sequences_and_model() -> None:
    created_response = {key: value for key, value in response_payload().items() if key != "model"}
    completed_response = dict(created_response)
    body = b"".join(
        b"data: " + json.dumps(event).encode() + b"\n\n"
        for event in (
            {"type": "response.created", "response": created_response},
            {"type": "response.completed", "response": completed_response},
        )
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(
        base_url="http://test",
        response_compatibility="openai-compatible",
        http_client=httpx.Client(transport=transport),
    )
    stream = client.responses.create(CreateResponseRequest(model="m", stream=True))
    events = list(stream)
    assert [event.sequence_number for event in events] == [0, 1]
    assert stream.final_response is not None
    assert stream.final_response.model == "unknown"
    client.close()


def test_compatibility_stream_defaults_provider_output_index() -> None:
    item = {
        "id": "reasoning_1",
        "summary": [],
        "type": "reasoning",
        "content": [],
        "encrypted_content": "",
    }
    body = b"".join(
        b"data: " + json.dumps(event).encode() + b"\n\n"
        for event in (
            {"type": "response.created", "response": response_payload()},
            {"type": "response.output_item.added", "item": item},
            {"type": "response.output_item.done", "item": item},
            {"type": "response.completed", "response": response_payload()},
        )
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(
        base_url="http://test",
        response_compatibility="openai-compatible",
        http_client=httpx.Client(transport=transport),
    )
    events = list(client.responses.create(CreateResponseRequest(model="m", stream=True)))
    assert [event.type for event in events] == [
        "response.created",
        "response.output_item.added",
        "response.output_item.done",
        "response.completed",
    ]
    assert events[1].output_index == 0
    assert events[2].output_index == 0
    client.close()


def test_compatibility_stream_defaults_function_argument_output_index() -> None:
    body = b"".join(
        b"data: " + json.dumps(event).encode() + b"\n\n"
        for event in (
            {"type": "response.created", "response": response_payload()},
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "fc_1",
                "delta": '{"city":"Paris"}',
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "fc_1",
                "arguments": '{"city":"Paris"}',
            },
            {"type": "response.completed", "response": response_payload()},
        )
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(
        base_url="http://test",
        response_compatibility="openai-compatible",
        http_client=httpx.Client(transport=transport),
    )
    events = list(client.responses.create(CreateResponseRequest(model="m", stream=True)))
    assert [event.output_index for event in events[1:3]] == [0, 0]
    client.close()


def test_strict_stream_still_requires_event_sequence_number() -> None:
    event = {"type": "response.completed", "response": response_payload()}
    body = f"data: {json.dumps(event)}\n\ndata: [DONE]\n\n".encode()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(
        base_url="http://test",
        http_client=httpx.Client(transport=transport),
    )
    with pytest.raises(SSEProtocolError):
        list(client.responses.create(CreateResponseRequest(model="m", stream=True)))
    client.close()
