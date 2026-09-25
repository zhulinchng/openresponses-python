from __future__ import annotations

import asyncio
import json

import pytest
from websockets.sync.server import serve

from openresponses import CreateResponseRequest, OpenResponses
from openresponses.config import ClientConfig
from openresponses.errors import WebSocketError
from openresponses.websocket import AsyncWebSocketConnection, WebSocketConnection


@pytest.fixture
def faulty_server():
    def handler(connection):
        connection.recv()
        connection.send("not json")
        connection.recv()
        connection.send(
            json.dumps({"type": "response.completed", "sequence_number": 0, "response": {}})
        )

    server = serve(handler, "127.0.0.1", 0)
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.socket.getsockname()[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_malformed_turn_closes_connection(faulty_server: str) -> None:
    with OpenResponses(base_url=faulty_server) as client, client.websocket() as connection:
        turn = connection.create(CreateResponseRequest(model="m", input="one"))
        with pytest.raises(WebSocketError):
            list(turn)
        assert not connection.connected
        with pytest.raises(WebSocketError):
            connection.create(CreateResponseRequest(model="m", input="two"))


class FailingSendSocket:
    def __init__(self) -> None:
        self.closed = False

    def send(self, message: str) -> None:
        raise OSError("send failed")

    def close(self) -> None:
        self.closed = True


class FailingCloseSocket:
    def close(self) -> None:
        raise OSError("close failed")


def test_sync_send_failure_closes_uncertain_connection() -> None:
    connection = WebSocketConnection(ClientConfig(base_url="http://test"))
    socket = FailingSendSocket()
    connection._ws = socket
    with pytest.raises(WebSocketError, match="could not send"):
        connection.create(CreateResponseRequest(model="m"))
    assert socket.closed
    assert not connection.connected
    with pytest.raises(WebSocketError, match="not open"):
        connection.create(CreateResponseRequest(model="m"))


def test_sync_close_failure_is_translated() -> None:
    connection = WebSocketConnection(ClientConfig(base_url="http://test"))
    connection._ws = FailingCloseSocket()
    with pytest.raises(WebSocketError, match="could not close"):
        connection.close()
    assert not connection.connected


async def test_async_send_failure_awaits_close() -> None:
    class Socket:
        def __init__(self) -> None:
            self.closed = False

        async def send(self, message: str) -> None:
            raise OSError("send failed")

        async def close(self) -> None:
            self.closed = True

    connection = AsyncWebSocketConnection(ClientConfig(base_url="http://test"))
    socket = Socket()
    connection._ws = socket
    with pytest.raises(WebSocketError, match="could not send"):
        await connection.create(CreateResponseRequest(model="m"))
    assert socket.closed
    assert not connection.connected


async def test_async_send_cancellation_awaits_close() -> None:
    class Socket:
        def __init__(self) -> None:
            self.send_started = asyncio.Event()
            self.closed = False

        async def send(self, message: str) -> None:
            self.send_started.set()
            await asyncio.Future()
            raise AssertionError("unreachable")

        async def close(self) -> None:
            self.closed = True

    connection = AsyncWebSocketConnection(ClientConfig(base_url="http://test"))
    socket = Socket()
    connection._ws = socket
    task = asyncio.create_task(connection.create(CreateResponseRequest(model="m")))
    await socket.send_started.wait()
    state = connection._active_turn
    assert state is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert socket.closed
    assert not connection.connected
    assert state._closed
    assert state.finished


async def test_async_receive_cancellation_awaits_close_and_finishes_turn() -> None:
    class Socket:
        def __init__(self) -> None:
            self.recv_started = asyncio.Event()
            self.closed = False

        async def send(self, message: str) -> None:
            pass

        async def recv(self) -> str:
            self.recv_started.set()
            await asyncio.Future()
            raise AssertionError("unreachable")

        async def close(self) -> None:
            self.closed = True

    connection = AsyncWebSocketConnection(ClientConfig(base_url="http://test"))
    socket = Socket()
    connection._ws = socket
    turn = await connection.create(CreateResponseRequest(model="m"))
    state = turn._state
    task = asyncio.create_task(turn.__anext__())
    await socket.recv_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert socket.closed
    assert not connection.connected
    assert state._closed
    assert state.finished


async def test_async_close_failure_is_translated() -> None:
    class Socket:
        async def close(self) -> None:
            raise OSError("close failed")

    connection = AsyncWebSocketConnection(ClientConfig(base_url="http://test"))
    connection._ws = Socket()
    with pytest.raises(WebSocketError, match="could not close"):
        await connection.close()
    assert not connection.connected
