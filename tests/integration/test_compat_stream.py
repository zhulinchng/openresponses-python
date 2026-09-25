from __future__ import annotations

import json

import httpx

from openresponses import CreateResponseRequest, OpenResponses


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
