from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx
import pytest

from openresponses import AsyncOpenResponses, CreateResponseRequest
from openresponses.errors import SSEProtocolError


def response_payload(status: str = "completed") -> dict[str, object]:
    return {
        "id": "resp_cleanup",
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


class TrackingAsyncByteStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


def event_bytes(kind: str, sequence: int, status: str) -> bytes:
    payload = {"type": kind, "sequence_number": sequence, "response": response_payload(status)}
    return f"event: {kind}\ndata: {json.dumps(payload)}\n\n".encode()


async def make_stream(byte_stream: TrackingAsyncByteStream):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=byte_stream
        )
    )
    client = AsyncOpenResponses(
        base_url="http://test", http_client=httpx.AsyncClient(transport=transport)
    )
    return client, await client.responses.create(CreateResponseRequest(model="m", stream=True))


async def test_async_stream_closes_after_done() -> None:
    source = TrackingAsyncByteStream(
        [
            event_bytes("response.created", 0, "in_progress"),
            event_bytes("response.completed", 1, "completed"),
            b"data: [DONE]\n\n",
        ]
    )
    client, stream = await make_stream(source)
    events = [event async for event in stream]
    assert len(events) == 2
    assert source.closed
    await client.close()


async def test_async_stream_closes_on_parse_error() -> None:
    source = TrackingAsyncByteStream([b"event: response.created\ndata: {bad}\n\n"])
    client, stream = await make_stream(source)
    with pytest.raises(SSEProtocolError):
        await stream.__anext__()
    assert source.closed
    await client.close()


async def test_async_stream_closes_on_cancellation() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingStream(TrackingAsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            started.set()
            await release.wait()
            yield b""

    source = BlockingStream([])
    _, stream = await make_stream(source)
    task = asyncio.create_task(stream.__anext__())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert source.closed
