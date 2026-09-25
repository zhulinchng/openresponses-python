from __future__ import annotations

import json
import threading

import pytest
from websockets.sync.server import serve

from openresponses import CreateResponseRequest, OpenResponses
from openresponses.errors import WebSocketError


def response_payload(status: str = "completed") -> dict[str, object]:
    return {
        "id": "resp_ws",
        "object": "response",
        "created_at": 1,
        "completed_at": 1,
        "status": status,
        "incomplete_details": None,
        "model": "m",
        "previous_response_id": None,
        "instructions": None,
        "output": [],
        "error": None,
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


def event(kind: str, sequence: int) -> dict[str, object]:
    status = "in_progress" if kind == "response.created" else "completed"
    return {"type": kind, "sequence_number": sequence, "response": response_payload(status)}


@pytest.fixture
def websocket_server():
    def handler(connection):
        for raw in connection:
            request = json.loads(raw)
            assert request["type"] == "response.create"
            if request.get("bad"):
                connection.send(
                    json.dumps(
                        {
                            "type": "error",
                            "status": 400,
                            "error": {"code": "bad_request", "message": "no"},
                        }
                    )
                )
                continue
            connection.send(json.dumps(event("response.created", 0)))
            connection.send(json.dumps(event("response.completed", 1)))

    server = serve(handler, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.socket.getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_websocket_turn_and_sequential_turn(websocket_server: str) -> None:
    with OpenResponses(base_url=websocket_server) as client, client.websocket() as connection:
        first = connection.create(CreateResponseRequest(model="m", input="one"))
        first_events = list(first)
        assert [item.type for item in first_events] == [
            "response.created",
            "response.completed",
        ]
        assert first.final_response is not None
        second = connection.create(CreateResponseRequest(model="m", input="two"))
        assert len(list(second)) == 2


def test_websocket_rejects_http_stream_field(websocket_server: str) -> None:
    with (
        OpenResponses(base_url=websocket_server) as client,
        client.websocket() as connection,
        pytest.raises(WebSocketError),
    ):
        connection.create({"model": "m", "stream": False})


def test_websocket_error_envelope(websocket_server: str) -> None:
    with OpenResponses(base_url=websocket_server) as client, client.websocket() as connection:
        turn = connection.create({"model": "m", "bad": True})
        assert list(turn) == []
        assert turn.error is not None
        assert turn.error.error.code == "bad_request"
