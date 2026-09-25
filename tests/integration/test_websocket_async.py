from __future__ import annotations

import json
import threading

import pytest
from websockets.sync.server import serve

from openresponses import AsyncOpenResponses, CreateResponseRequest


def response_payload() -> dict[str, object]:
    return {
        "id": "resp_async",
        "object": "response",
        "created_at": 1,
        "completed_at": 1,
        "status": "completed",
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


@pytest.fixture
def websocket_server():
    def handler(connection):
        for raw in connection:
            request = json.loads(raw)
            assert request["type"] == "response.create"
            connection.send(
                json.dumps(
                    {
                        "type": "response.created",
                        "sequence_number": 0,
                        "response": response_payload(),
                    }
                )
            )
            connection.send(
                json.dumps(
                    {
                        "type": "response.completed",
                        "sequence_number": 1,
                        "response": response_payload(),
                    }
                )
            )

    server = serve(handler, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.socket.getsockname()[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


async def test_async_websocket_turn(websocket_server: str) -> None:
    async with (
        AsyncOpenResponses(base_url=websocket_server) as client,
        client.websocket() as connection,
    ):
        turn = await connection.create(CreateResponseRequest(model="m", input="hello"))
        events = [event async for event in turn]
        assert [event.type for event in events] == ["response.created", "response.completed"]
        assert turn.final_response is not None
        assert turn.final_response.id == "resp_async"
