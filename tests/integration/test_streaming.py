from __future__ import annotations

import json

import httpx
import pytest

from openresponses.client import OpenResponses
from openresponses.errors import SSEProtocolError
from openresponses.streaming import SSEParser
from openresponses.types import CreateResponseRequest, UnknownStreamingEvent


def response_payload(status: str = "completed") -> dict[str, object]:
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 1,
        "completed_at": 1,
        "status": status,
        "incomplete_details": None,
        "model": "m",
        "previous_response_id": None,
        "instructions": None,
        "output": [],
        "error": None if status != "failed" else {"code": "server_error", "message": "bad"},
        "tools": [],
        "tool_choice": "auto",
        "truncation": "auto",
        "parallel_tool_calls": True,
        "text": {"format": {"type": "text"}},
        "top_p": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "top_logprobs": 0,
        "temperature": 1.0,
        "reasoning": None,
        "usage": None,
        "max_output_tokens": None,
        "max_tool_calls": None,
        "store": True,
        "background": False,
        "service_tier": "default",
        "metadata": {},
        "safety_identifier": None,
        "prompt_cache_key": None,
    }


def sse(event: dict[str, object], done: bool = False) -> bytes:
    data = json.dumps(event, separators=(",", ":"))
    return f"event: {event['type']}\ndata: {data}\n\n".encode() + (
        b"data: [DONE]\n\n" if done else b""
    )


def test_sse_parser_handles_split_lines_and_crlf() -> None:
    parser = SSEParser()
    raw = (
        b'event: response.created\r\ndata: {"type":"response.created","sequence_number":0}\r\n\r\n'
    )
    assert not parser.feed(raw[:10])
    assert not parser.feed(raw[10:-2])
    parsed = parser.feed(raw[-2:])
    assert len(parsed) == 1
    assert parsed[0].event == "response.created"
    assert json.loads(parsed[0].data)["type"] == "response.created"


def test_sse_parser_handles_carriage_return_only_lines() -> None:
    parser = SSEParser()
    assert parser.feed(b'event: response.created\rdata: {"type":"response.created"}\r\r') == []
    parsed = parser.finish()
    assert len(parsed) == 1
    assert json.loads(parsed[0].data)["type"] == "response.created"


def test_sse_parser_dispatches_done_as_data() -> None:
    parser = SSEParser()
    parsed = parser.feed(b"data: [DONE]\n\n")
    assert parsed[0].data == "[DONE]"


def test_sse_parser_preserves_split_utf8_character() -> None:
    parser = SSEParser()
    assert parser.feed(b"data: \xe2\x82") == []
    parsed = parser.feed(b"\xac\n\n")
    assert parsed[0].data == "€"


def test_sse_parser_translates_invalid_utf8_from_feed() -> None:
    parser = SSEParser()
    with pytest.raises(SSEProtocolError, match="not valid UTF-8"):
        parser.feed(b"data: \xff\n\n")


def test_sse_parser_translates_incomplete_utf8_from_finish() -> None:
    parser = SSEParser()
    assert parser.feed(b"data: \xe2\x82") == []
    with pytest.raises(SSEProtocolError, match="not valid UTF-8"):
        parser.finish()


def test_stream_emits_typed_events() -> None:
    created = {
        "type": "response.created",
        "sequence_number": 0,
        "response": response_payload("in_progress"),
    }
    completed = {
        "type": "response.completed",
        "sequence_number": 1,
        "response": response_payload(),
    }
    body = sse(created) + sse(completed, done=True)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    stream = client.responses.create(CreateResponseRequest(model="m", stream=True))
    events = list(stream)
    assert [event.type for event in events] == ["response.created", "response.completed"]
    assert stream.final_response is not None
    assert stream.final_response.id == "resp_1"
    client.close()


def test_stream_preserves_unknown_provider_event() -> None:
    completed = {
        "type": "response.completed",
        "sequence_number": 1,
        "response": response_payload(),
    }
    extension = {
        "type": "vendor.example.event",
        "sequence_number": 0,
        "payload": {"value": 7},
    }
    body = sse(extension) + sse(completed, done=True)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    events = list(client.responses.create(CreateResponseRequest(model="m", stream=True)))
    assert isinstance(events[0], UnknownStreamingEvent)
    assert events[0].type == "vendor.example.event"
    assert events[0].payload == {"value": 7}
    client.close()


def test_stream_rejects_missing_done() -> None:
    created = {
        "type": "response.created",
        "sequence_number": 0,
        "response": response_payload("in_progress"),
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=sse(created)
        )
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    with pytest.raises(SSEProtocolError):
        list(client.responses.create(CreateResponseRequest(model="m", stream=True)))
    client.close()


def test_stream_rejects_duplicate_output_item_done() -> None:
    body = b"".join(
        sse(
            {
                "type": "response.output_item.done",
                "sequence_number": sequence,
                "output_index": 0,
                "item": None,
            }
        )
        for sequence in (0, 1)
    ) + sse(
        {
            "type": "response.completed",
            "sequence_number": 2,
            "response": response_payload(),
        },
        done=True,
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    with pytest.raises(SSEProtocolError, match="completed more than once"):
        list(client.responses.create(CreateResponseRequest(model="m", stream=True)))
    client.close()


def test_stream_rejects_error_before_non_failed_terminal() -> None:
    body = sse(
        {
            "type": "error",
            "sequence_number": 0,
            "error": {"type": "server_error", "code": "failed", "message": "failed", "param": None},
        }
    ) + sse(
        {
            "type": "response.completed",
            "sequence_number": 1,
            "response": response_payload(),
        },
        done=True,
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    with pytest.raises(SSEProtocolError, match="response.failed"):
        list(client.responses.create(CreateResponseRequest(model="m", stream=True)))
    client.close()
