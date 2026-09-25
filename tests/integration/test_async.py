from __future__ import annotations

import httpx

from openresponses.client import AsyncOpenResponses
from openresponses.types import CreateResponseRequest


def response_payload() -> dict[str, object]:
    return {
        "id": "resp_a",
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


async def test_async_json_create() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_payload())

    transport = httpx.MockTransport(handler)
    client = AsyncOpenResponses(
        base_url="http://test", http_client=httpx.AsyncClient(transport=transport)
    )
    result = await client.responses.create(CreateResponseRequest(model="m", input="hi"))
    assert result.id == "resp_a"
    await client.close()


async def test_async_stream() -> None:
    import json

    events = [
        {"type": "response.created", "sequence_number": 0, "response": response_payload()},
        {"type": "response.completed", "sequence_number": 1, "response": response_payload()},
    ]
    body = (
        b"".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n".encode() for e in events)
        + b"data: [DONE]\n\n"
    )
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = AsyncOpenResponses(
        base_url="http://test", http_client=httpx.AsyncClient(transport=transport)
    )
    stream = await client.responses.create(CreateResponseRequest(model="m", stream=True))
    result = [event async for event in stream]
    assert [event.type for event in result] == ["response.created", "response.completed"]
    await client.close()
