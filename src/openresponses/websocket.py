"""Synchronous and asynchronous WebSocket transport for response turns."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, Mapping
from types import TracebackType
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

from websockets.asyncio.client import connect as async_connect
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect as sync_connect

from .config import ClientConfig, WebSocketConfig
from .errors import SSEProtocolError, WebSocketError
from .streaming import StreamState
from .types.generated import WebSocketErrorEvent
from .types.protocol import (
    CreateResponseRequest,
    StreamingEventAdapter,
    WebSocketResponseCreateRequest,
)

_TERMINAL_EVENTS = {"response.completed", "response.failed", "response.incomplete"}


def websocket_url(base_url: str) -> str:
    """Return the Responses WebSocket endpoint for an HTTP(S)/WS(S) base URL."""
    parts = urlsplit(base_url.rstrip("/"))
    schemes = {"http": "ws", "https": "wss", "ws": "ws", "wss": "wss"}
    scheme = schemes.get(parts.scheme.lower())
    if scheme is None or not parts.netloc:
        raise WebSocketError("base_url must use an absolute HTTP(S) or WS(S) URL")
    return urlunsplit(
        (scheme, parts.netloc, f"{parts.path.rstrip('/')}/responses", parts.query, parts.fragment)
    )


def _forbidden_present(request: Any) -> set[str]:
    names = {"stream", "stream_options", "background"}
    if isinstance(request, Mapping):
        return names.intersection(request)
    fields_set: set[str] = getattr(request, "model_fields_set", set())
    return names.intersection(fields_set)


def _coerce_request(
    request: WebSocketResponseCreateRequest | CreateResponseRequest | Mapping[str, Any],
) -> WebSocketResponseCreateRequest:
    forbidden = _forbidden_present(request)
    if forbidden:
        raise WebSocketError(
            "WebSocket response.create cannot include " + ", ".join(sorted(forbidden))
        )
    try:
        if isinstance(request, WebSocketResponseCreateRequest):
            return request
        if isinstance(request, CreateResponseRequest):
            return WebSocketResponseCreateRequest.model_validate(
                request.model_dump(exclude_unset=True)
            )
        return WebSocketResponseCreateRequest.model_validate(request)
    except WebSocketError:
        raise
    except Exception as exc:
        raise WebSocketError(f"invalid WebSocket response.create request: {exc}") from exc


def _decode_frame(frame: str | bytes) -> dict[str, Any]:
    if isinstance(frame, bytes):
        try:
            frame = frame.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WebSocketError("WebSocket binary frame is not valid UTF-8") from exc
    try:
        payload = json.loads(frame)
    except (TypeError, ValueError) as exc:
        raise WebSocketError("WebSocket message is not valid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
        raise WebSocketError("WebSocket message requires an object with a string type")
    return payload


def _close_details(exc: ConnectionClosed) -> tuple[int | None, str | None]:
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(exc, "close_code", None)
    reason = getattr(exc, "reason", None)
    if reason is None:
        reason = getattr(exc, "close_reason", None)
    return code, reason


def _envelope_or_event(payload: dict[str, Any]) -> Any:
    # Responses WebSocket errors have an HTTP-style ``status`` field. A
    # regular streaming error event instead has ``sequence_number``.
    if payload.get("type") == "error" and "status" in payload and "sequence_number" not in payload:
        try:
            return WebSocketErrorEvent.model_validate(payload)
        except Exception as exc:
            raise WebSocketError(f"invalid WebSocket error envelope: {exc}") from exc
    try:
        return StreamingEventAdapter.validate_python(payload)
    except Exception as exc:
        raise WebSocketError(f"invalid WebSocket streaming event: {exc}") from exc


class _TurnState:
    def __init__(
        self, connection: WebSocketConnection | AsyncWebSocketConnection, generation: int
    ) -> None:
        self._connection = connection
        self._generation = generation
        self._state = StreamState()
        self._finished = False
        self._closed = False
        self.error: WebSocketErrorEvent | None = None
        self.final_response: Any | None = None

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def response_id(self) -> str | None:
        return getattr(self.final_response, "id", None)

    @property
    def last_sequence_number(self) -> int | None:
        return self._state.last_sequence_number

    def _release(self) -> None:
        connection = self._connection
        if getattr(connection, "_active_turn", None) is self:
            connection._active_turn = None

    def close(self) -> None:
        if not self._finished:
            self._closed = True
            self._finished = True

    def event(self, payload: dict[str, Any]) -> Any | None:
        if self._finished:
            raise WebSocketError("WebSocket turn has already ended")
        item = _envelope_or_event(payload)
        if isinstance(item, WebSocketErrorEvent):
            self.error = item
            self._finished = True
            self._release()
            return None
        try:
            self._state.accept(item)
        except SSEProtocolError as exc:
            self.close()
            raise WebSocketError(str(exc)) from exc
        if item.type in _TERMINAL_EVENTS:
            self.final_response = item.response
            self._finished = True
            self._release()
        return item

    def connection_closed(self, exc: ConnectionClosed) -> WebSocketError:
        code, reason = _close_details(exc)
        detail = f"code={code}" if code is not None else "code=unknown"
        if reason:
            detail += f", reason={reason!r}"
        self._finished = True
        return WebSocketError(
            f"WebSocket closed before a terminal response ({detail})",
            code=str(code) if code is not None else None,
            error={"close_code": code, "close_reason": reason},
        )


class WebSocketTurn(Iterator[Any]):
    """One synchronous WebSocket response turn."""

    def __init__(self, connection: WebSocketConnection) -> None:
        self._state = _TurnState(connection, connection._generation)
        self._connection = connection

    @property
    def error(self) -> WebSocketErrorEvent | None:
        return self._state.error

    @property
    def final_response(self) -> Any | None:
        return self._state.final_response

    @property
    def response_id(self) -> str | None:
        return self._state.response_id

    @property
    def last_sequence_number(self) -> int | None:
        return self._state.last_sequence_number

    def close(self) -> None:
        if not self._state.finished:
            self._state.close()
            self._connection._poison()

    def __iter__(self) -> WebSocketTurn:
        return self

    def __next__(self) -> Any:
        if self._state.finished:
            raise StopIteration
        if self._state._closed or self._state._generation != self._connection._generation:
            raise WebSocketError("WebSocket turn is closed")
        try:
            frame = self._connection._recv()
        except ConnectionClosed as exc:
            error = self._state.connection_closed(exc)
            self._connection._poison()
            raise error from exc
        except WebSocketError:
            self._connection._poison()
            raise
        try:
            item = self._state.event(_decode_frame(frame))
        except WebSocketError:
            self._connection._poison()
            raise
        if item is None:
            raise StopIteration
        return item


class AsyncWebSocketTurn:
    """One asynchronous response turn."""

    def __init__(self, connection: AsyncWebSocketConnection) -> None:
        self._state = _TurnState(connection, connection._generation)
        self._connection = connection

    @property
    def error(self) -> WebSocketErrorEvent | None:
        return self._state.error

    @property
    def final_response(self) -> Any | None:
        return self._state.final_response

    @property
    def response_id(self) -> str | None:
        return self._state.response_id

    @property
    def last_sequence_number(self) -> int | None:
        return self._state.last_sequence_number

    async def close(self) -> None:
        if not self._state.finished:
            self._state.close()
            await self._connection._poison()

    def __aiter__(self) -> AsyncWebSocketTurn:
        return self

    async def __anext__(self) -> Any:
        if self._state.finished:
            raise StopAsyncIteration
        if self._state._closed or self._state._generation != self._connection._generation:
            raise WebSocketError("WebSocket turn is closed")
        try:
            frame = await self._connection._recv()
        except ConnectionClosed as exc:
            error = self._state.connection_closed(exc)
            await self._connection._poison()
            raise error from exc
        except asyncio.CancelledError:
            await self._connection._poison()
            raise
        except WebSocketError:
            await self._connection._poison()
            raise
        try:
            item = self._state.event(_decode_frame(frame))
        except WebSocketError:
            await self._connection._poison()
            raise
        if item is None:
            raise StopAsyncIteration
        return item


class WebSocketConnection:
    """A synchronous Responses WebSocket connection."""

    def __init__(
        self, config: ClientConfig, websocket_config: WebSocketConfig | None = None
    ) -> None:
        self._config = config
        self._generation = 0
        self._websocket_config = websocket_config or WebSocketConfig.from_client(config)
        self._ws: Any | None = None
        self._active_turn: _TurnState | None = None

    @property
    def url(self) -> str:
        return websocket_url(self._config.base_url)

    @property
    def connected(self) -> bool:
        return self._ws is not None

    @property
    def state(self) -> str:
        return "open" if self._ws is not None else "closed"

    def connect(self) -> WebSocketConnection:
        if self._ws is not None:
            return self
        options = self._websocket_config
        try:
            self._ws = sync_connect(
                self.url,
                additional_headers=self._config.headers(),
                open_timeout=options.open_timeout,
                close_timeout=options.close_timeout,
                ping_interval=options.ping_interval,
                ping_timeout=options.ping_timeout,
                max_size=options.max_size,
            )
        except Exception as exc:
            raise WebSocketError(f"could not connect to WebSocket endpoint: {exc}") from exc
        self._generation += 1
        return self

    def close(self) -> None:
        active_turn = self._active_turn
        ws, self._ws = self._ws, None
        self._active_turn = None
        if active_turn is not None:
            active_turn._closed = True
            active_turn._finished = True
        if ws is not None:
            try:
                ws.close()
            except Exception as exc:
                raise WebSocketError(f"could not close WebSocket connection: {exc}") from exc

    def __enter__(self) -> WebSocketConnection:
        return self.connect()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _poison(self) -> None:
        self.close()

    def create(
        self, request: WebSocketResponseCreateRequest | CreateResponseRequest | Mapping[str, Any]
    ) -> WebSocketTurn:
        if self._ws is None:
            raise WebSocketError("WebSocket connection is not open")
        if self._active_turn is not None:
            raise WebSocketError("WebSocket connection already has an in-flight turn")
        payload = _coerce_request(request)
        turn = WebSocketTurn(self)
        self._active_turn = turn._state
        try:
            self._ws.send(
                json.dumps(
                    {
                        **payload.model_dump(mode="json", by_alias=True, exclude_unset=True),
                        "type": "response.create",
                    }
                )
            )
        except Exception as exc:
            self._poison()
            raise WebSocketError(f"could not send WebSocket response.create: {exc}") from exc
        return turn

    def _recv(self) -> str | bytes:
        if self._ws is None:
            raise WebSocketError("WebSocket connection is not open")
        return cast(str | bytes, self._ws.recv())


class AsyncWebSocketConnection:
    """An asynchronous Responses WebSocket connection."""

    def __init__(
        self, config: ClientConfig, websocket_config: WebSocketConfig | None = None
    ) -> None:
        self._config = config
        self._websocket_config = websocket_config or WebSocketConfig.from_client(config)
        self._generation = 0
        self._ws: Any | None = None
        self._active_turn: _TurnState | None = None

    @property
    def url(self) -> str:
        return websocket_url(self._config.base_url)

    @property
    def connected(self) -> bool:
        return self._ws is not None

    @property
    def state(self) -> str:
        return "open" if self._ws is not None else "closed"

    async def connect(self) -> AsyncWebSocketConnection:
        if self._ws is not None:
            return self
        options = self._websocket_config
        try:
            self._ws = await async_connect(
                self.url,
                additional_headers=self._config.headers(),
                open_timeout=options.open_timeout,
                close_timeout=options.close_timeout,
                ping_interval=options.ping_interval,
                ping_timeout=options.ping_timeout,
                max_size=options.max_size,
            )
        except Exception as exc:
            raise WebSocketError(f"could not connect to WebSocket endpoint: {exc}") from exc
        self._generation += 1
        return self

    async def close(self) -> None:
        active_turn = self._active_turn
        ws, self._ws = self._ws, None
        self._active_turn = None
        if active_turn is not None:
            active_turn._closed = True
            active_turn._finished = True
        if ws is not None:
            try:
                await ws.close()
            except Exception as exc:
                raise WebSocketError(f"could not close WebSocket connection: {exc}") from exc

    async def __aenter__(self) -> AsyncWebSocketConnection:
        return await self.connect()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def _poison(self) -> None:
        await self.close()

    async def create(
        self, request: WebSocketResponseCreateRequest | CreateResponseRequest | Mapping[str, Any]
    ) -> AsyncWebSocketTurn:
        if self._ws is None:
            raise WebSocketError("WebSocket connection is not open")
        if self._active_turn is not None:
            raise WebSocketError("WebSocket connection already has an in-flight turn")
        payload = _coerce_request(request)
        turn = AsyncWebSocketTurn(self)
        self._active_turn = turn._state
        try:
            await self._ws.send(
                json.dumps(
                    {
                        **payload.model_dump(mode="json", by_alias=True, exclude_unset=True),
                        "type": "response.create",
                    }
                )
            )
        except asyncio.CancelledError:
            await self._poison()
            raise
        except Exception as exc:
            await self._poison()
            raise WebSocketError(f"could not send WebSocket response.create: {exc}") from exc
        return turn

    async def _recv(self) -> str | bytes:
        if self._ws is None:
            raise WebSocketError("WebSocket connection is not open")
        return cast(str | bytes, await self._ws.recv())


__all__ = [
    "AsyncWebSocketConnection",
    "AsyncWebSocketTurn",
    "WebSocketConnection",
    "WebSocketTurn",
    "websocket_url",
]
