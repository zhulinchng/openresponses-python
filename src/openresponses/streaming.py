from __future__ import annotations

import codecs
import json
import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from .errors import APIConnectionError, APITimeoutError, SSEProtocolError
from .types.generated import ResponseResource
from .types.protocol import StreamingEventAdapter


@dataclass(frozen=True)
class ParsedSSEEvent:
    event: str | None
    data: str
    id: str | None = None


class SSEParser:
    """Incremental parser for the server-sent event framing."""

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")()
        self._buffer = ""
        self._event: str | None = None
        self._data: list[str] = []
        self._id: str | None = None
        self._pending_cr = False

    def reset(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")()
        self._buffer = ""
        self._event = None
        self._data = []
        self._id = None
        self._pending_cr = False

    def feed(self, chunk: bytes) -> list[ParsedSSEEvent]:
        try:
            decoded = self._decoder.decode(chunk, final=False)
        except UnicodeDecodeError as exc:
            raise SSEProtocolError("SSE stream is not valid UTF-8") from exc
        if self._pending_cr:
            decoded = "\r" + decoded
            self._pending_cr = False
        if decoded.endswith("\r"):
            decoded = decoded[:-1]
            self._pending_cr = True
        self._buffer += decoded
        return self._drain(final=False)

    def finish(self) -> list[ParsedSSEEvent]:
        try:
            decoded = self._decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            raise SSEProtocolError("SSE stream is not valid UTF-8") from exc
        if self._pending_cr:
            decoded = "\r" + decoded
            self._pending_cr = False
        self._buffer += decoded
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> list[ParsedSSEEvent]:
        events: list[ParsedSSEEvent] = []
        while self._buffer:
            match = re.search(r"\r\n|\r|\n", self._buffer)
            if match is None:
                break
            line = self._buffer[: match.start()]
            self._buffer = self._buffer[match.end() :]
            if not line:
                if self._data:
                    events.append(ParsedSSEEvent(self._event, "\n".join(self._data), self._id))
                self._event = None
                self._data = []
                self._id = None
                continue
            self._process_line(line, events)
        if final and self._buffer:
            line = self._buffer
            self._buffer = ""
            if line:
                self._process_line(line, events)
        if final and self._data:
            events.append(ParsedSSEEvent(self._event, "\n".join(self._data), self._id))
            self._event = None
            self._data = []
            self._id = None
        return events

    def _process_line(self, line: str, events: list[ParsedSSEEvent]) -> None:
        if line.startswith(":"):
            return
        if ":" in line:
            field, value = line.split(":", 1)
            value = value[1:] if value.startswith(" ") else value
        else:
            field, value = line, ""
        if field == "event":
            self._event = value
        elif field == "data":
            self._data.append(value)
        elif field == "id":
            self._id = value


@dataclass
class StreamState:
    last_sequence_number: int | None = None
    final_response: ResponseResource | None = None
    terminal_seen: bool = False
    saw_error: bool = False
    item_done: set[int] = field(default_factory=set)
    content_done: set[tuple[int, int]] = field(default_factory=set)
    item_added: set[int] = field(default_factory=set)
    content_added: set[tuple[int, int]] = field(default_factory=set)
    error_pending: bool = False

    def accept(self, event: Any) -> Any:
        if self.terminal_seen:
            raise SSEProtocolError("event received after terminal response event")
        sequence = getattr(event, "sequence_number", None)
        if sequence is not None:
            if self.last_sequence_number is not None and sequence <= self.last_sequence_number:
                raise SSEProtocolError("event sequence_number must strictly increase")
            self.last_sequence_number = sequence
        event_type = event.type
        if self.error_pending and event_type != "response.failed":
            raise SSEProtocolError("error event must be followed by response.failed")
        output_index = getattr(event, "output_index", None)
        if (
            output_index is not None
            and output_index in self.item_done
            and event_type != "response.output_item.done"
        ):
            raise SSEProtocolError("output item received updates after completion")
        content_index = getattr(event, "content_index", None)
        content_key = (
            (output_index, content_index)
            if output_index is not None and content_index is not None
            else None
        )
        if content_key is not None and content_key in self.content_done:
            raise SSEProtocolError("content part received updates after completion")
        if event_type == "response.output_item.added":
            index = event.output_index
            if index in self.item_added or index in self.item_done:
                raise SSEProtocolError("output item was added more than once")
            self.item_added.add(index)
        elif event_type == "response.output_item.done":
            index = event.output_index
            if index in self.item_done:
                raise SSEProtocolError("output item was completed more than once")
            self.item_done.add(index)
        elif event_type == "response.content_part.added":
            key = (event.output_index, event.content_index)
            if key in self.content_added or key in self.content_done:
                raise SSEProtocolError("content part was added more than once")
            self.content_added.add(key)
        elif event_type == "response.content_part.done":
            key = (event.output_index, event.content_index)
            if key in self.content_done:
                raise SSEProtocolError("content part was completed more than once")
            self.content_done.add(key)
        elif event_type == "error":
            self.saw_error = True
            self.error_pending = True
        elif event_type in {"response.completed", "response.failed", "response.incomplete"}:
            self.terminal_seen = True
            self.final_response = event.response
            self.error_pending = False
        return event


def _compatible_response_payload(value: Any) -> dict[str, Any]:
    from .serialization import OpenAICompatibleResponse

    if not isinstance(value, dict):
        raise SSEProtocolError("compatible response snapshot must be an object")
    response = OpenAICompatibleResponse.model_validate(value).model_dump(
        mode="python", by_alias=True, exclude_none=True
    )
    response["created_at"] = value.get("created_at", value.get("created", 0))
    if isinstance(response.get("usage"), dict):
        response["usage"].setdefault("input_tokens_details", {"cached_tokens": 0})
        response["usage"].setdefault("output_tokens_details", {"reasoning_tokens": 0})
    if isinstance(response.get("output"), list):
        for index, item in enumerate(response["output"]):
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                item.setdefault("id", f"msg_{index}")
                item.setdefault("status", "completed")
                item.setdefault("role", "assistant")
                if isinstance(item.get("content"), list):
                    for part in item["content"]:
                        if isinstance(part, dict) and part.get("type") == "output_text":
                            part.setdefault("annotations", [])
    response["created_at"] = value.get("created_at", value.get("created", 0))
    response.setdefault("completed_at", None)
    response.setdefault("status", "in_progress")
    response.setdefault("incomplete_details", None)
    response.setdefault("model", "unknown")
    response.setdefault("previous_response_id", None)
    response.setdefault("instructions", None)
    response.setdefault("output", [])
    response.setdefault("error", None)
    response.setdefault("tools", [])
    response.setdefault("tool_choice", "auto")
    response.setdefault("truncation", "auto")
    response.setdefault("parallel_tool_calls", True)
    response.setdefault("text", {"format": {"type": "text"}})
    response.setdefault("top_p", 1.0)
    response.setdefault("presence_penalty", 0.0)
    response.setdefault("frequency_penalty", 0.0)
    response.setdefault("top_logprobs", 0)
    response.setdefault("temperature", 1.0)
    response.setdefault("reasoning", None)
    response.setdefault("usage", None)
    response.setdefault("max_output_tokens", None)
    response.setdefault("max_tool_calls", None)
    response.setdefault("store", True)
    response.setdefault("background", False)
    response.setdefault("service_tier", "default")
    response.setdefault("metadata", {})
    response.setdefault("safety_identifier", None)
    response.setdefault("prompt_cache_key", None)
    return response


def _decode_event(
    parsed: ParsedSSEEvent,
    response_compatibility: str = "strict",
    synthesized_sequence_number: int | None = None,
) -> Any:
    if parsed.data.strip() == "[DONE]":
        return None
    try:
        payload = json.loads(parsed.data)
    except (ValueError, TypeError) as exc:
        raise SSEProtocolError("SSE data is not valid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
        raise SSEProtocolError("SSE event payload requires a string type")
    if parsed.event is not None and parsed.event != payload["type"]:
        raise SSEProtocolError("SSE event name does not match payload type")
    if (
        response_compatibility == "openai-compatible"
        and "sequence_number" not in payload
        and synthesized_sequence_number is not None
    ):
        payload = {**payload, "sequence_number": synthesized_sequence_number}
    if response_compatibility == "openai-compatible" and payload.get("type") in {
        "response.output_item.added",
        "response.output_item.done",
    }:
        payload = {"output_index": 0, **payload}
    if response_compatibility == "openai-compatible" and "response" in payload:
        try:
            payload = {**payload, "response": _compatible_response_payload(payload["response"])}
        except Exception as exc:
            raise SSEProtocolError(f"invalid compatible response snapshot: {exc}") from exc
    try:
        return StreamingEventAdapter.validate_python(payload)
    except Exception as exc:
        raise SSEProtocolError(f"invalid streaming event: {exc}") from exc


class _StreamBase:
    def __init__(
        self,
        stream_context: Any,
        response_compatibility: str = "strict",
        max_response_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        self._stream_context = stream_context
        self._response_compatibility = response_compatibility
        self._max_response_bytes = max_response_bytes
        self._response_context: Any = None
        self._state = StreamState()
        self._closed = False
        self._finished = False
        self._parser: SSEParser | None = None
        self._iterator: Any = None
        self._pending: list[ParsedSSEEvent] = []

    @property
    def final_response(self) -> ResponseResource | None:
        return self._state.final_response

    @property
    def response_id(self) -> str | None:
        return self._state.final_response.id if self._state.final_response else None

    @property
    def last_sequence_number(self) -> int | None:
        return self._state.last_sequence_number

    def _parse(self, parsed: ParsedSSEEvent) -> Any:
        if parsed.data.strip() == "[DONE]":
            if not self._state.terminal_seen:
                raise SSEProtocolError("[DONE] received before a terminal response event")
            self._finished = True
            return None
        next_sequence_number = (
            0 if self._state.last_sequence_number is None else self._state.last_sequence_number + 1
        )
        return self._state.accept(
            _decode_event(
                parsed,
                self._response_compatibility,
                next_sequence_number,
            )
        )

    def _finish_check(self) -> None:
        if self._response_compatibility == "openai-compatible" and self._state.terminal_seen:
            self._finished = True
            return
        if not self._finished or not self._state.terminal_seen:
            raise SSEProtocolError("stream ended before [DONE] and terminal response event")


class ResponseStream(_StreamBase, Iterator[Any]):
    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        if self._closed:
            raise StopIteration
        try:
            if self._response_context is None:
                self._response_context = self._stream_context.__enter__()
            if self._response_context.status_code >= 300:
                response = self._response_context
                response.read()
                from .serialization import status_error

                raise status_error(
                    response, self._max_response_bytes, request=self._response_context.request
                )
            content_type = self._response_context.headers.get("content-type", "")
            if "text/event-stream" not in content_type.lower():
                raise SSEProtocolError("streaming response must use text/event-stream")
            if self._parser is None:
                self._parser = SSEParser()
            if self._pending:
                event = self._parse(self._pending.pop(0))
                if event is not None:
                    return event
                raise StopIteration
            if self._iterator is None:
                self._iterator = self._response_context.iter_bytes()
            while True:
                try:
                    chunk = next(self._iterator)
                except StopIteration:
                    self._pending.extend(self._parser.finish())
                    if not self._pending:
                        self._finish_check()
                        raise StopIteration from None
                    event = self._parse(self._pending.pop(0))
                    if event is not None:
                        return event
                    raise StopIteration from None
                self._pending.extend(self._parser.feed(chunk))
                if self._pending:
                    event = self._parse(self._pending.pop(0))
                    if event is not None:
                        return event
                    raise StopIteration
        except httpx.TimeoutException as exc:
            self.close()
            raise APITimeoutError("streaming request timed out") from exc
        except httpx.HTTPError as exc:
            self.close()
            raise APIConnectionError("streaming request failed") from exc
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._response_context is not None:
            self._response_context.close()

    def __enter__(self) -> ResponseStream:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class AsyncResponseStream(_StreamBase, AsyncIterator[Any]):
    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        if self._closed:
            raise StopAsyncIteration
        try:
            if self._response_context is None:
                self._response_context = await self._stream_context.__aenter__()
            if self._response_context.status_code >= 300:
                await self._response_context.aread()
                from .serialization import status_error

                raise status_error(
                    self._response_context,
                    self._max_response_bytes,
                    request=self._response_context.request,
                )
            content_type = self._response_context.headers.get("content-type", "")
            if "text/event-stream" not in content_type.lower():
                raise SSEProtocolError("streaming response must use text/event-stream")
            if self._parser is None:
                self._parser = SSEParser()
            if self._pending:
                event = self._parse(self._pending.pop(0))
                if event is not None:
                    return event
                raise StopAsyncIteration
            if self._iterator is None:
                self._iterator = self._response_context.aiter_bytes().__aiter__()
            while True:
                try:
                    chunk = await self._iterator.__anext__()
                except StopAsyncIteration:
                    self._pending.extend(self._parser.finish())
                    if not self._pending:
                        self._finish_check()
                        raise StopAsyncIteration from None
                    event = self._parse(self._pending.pop(0))
                    if event is not None:
                        return event
                    raise StopAsyncIteration from None
                self._pending.extend(self._parser.feed(chunk))
                if self._pending:
                    event = self._parse(self._pending.pop(0))
                    if event is not None:
                        return event
                    raise StopAsyncIteration from None
        except httpx.TimeoutException as exc:
            await self.aclose()
            raise APITimeoutError("streaming request timed out") from exc
        except httpx.HTTPError as exc:
            await self.aclose()
            raise APIConnectionError("streaming request failed") from exc
        except BaseException:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._response_context is not None:
            await self._response_context.aclose()

    async def __aenter__(self) -> AsyncResponseStream:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


__all__ = ["AsyncResponseStream", "ParsedSSEEvent", "ResponseStream", "SSEParser", "StreamState"]
