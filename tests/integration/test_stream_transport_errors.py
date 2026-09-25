from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from openresponses import APIConnectionError, CreateResponseRequest, OpenResponses


class FailingSyncStream(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield b"data: partial\n"
        raise httpx.ReadError("broken")

    def close(self) -> None:
        pass


class FailingAsyncStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"data: partial\n"
        raise httpx.ReadError("broken")

    async def aclose(self) -> None:
        pass


def test_sync_stream_transport_error_is_sdk_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=FailingSyncStream()
        )
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    with pytest.raises(APIConnectionError):
        list(client.responses.create(CreateResponseRequest(model="m", stream=True)))
    client.close()


async def test_async_stream_transport_error_is_sdk_error() -> None:
    from openresponses import AsyncOpenResponses

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=FailingAsyncStream()
        )
    )
    client = AsyncOpenResponses(
        base_url="http://test", http_client=httpx.AsyncClient(transport=transport)
    )
    with pytest.raises(APIConnectionError):
        [
            event
            async for event in await client.responses.create(
                CreateResponseRequest(model="m", stream=True)
            )
        ]
    await client.close()
