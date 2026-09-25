# API reference

The package root exports the supported public surface. Import protocol types from `openresponses`; transport-specific classes are also available from their modules when a lower-level import is useful.

## Clients

| Symbol | Purpose |
| --- | --- |
| `OpenResponses` | Synchronous HTTP client with `responses.create`, `responses.compact`, and `websocket()`. |
| `AsyncOpenResponses` | Asynchronous counterpart; await response operations and use `async for` for streams. |
| `ClientConfig` | Validated base URL, authentication, timeout, headers, compatibility, and response-size settings. |
| `WebSocketConfig` | WebSocket open/close timeouts, ping settings, and maximum frame size. |

Clients own transports they create and close them. An injected `httpx.Client` or `httpx.AsyncClient` remains caller-owned.

## HTTP resources

```python
from openresponses import AsyncOpenResponses, OpenResponses
```

`responses.create(request, *, extra_headers=None, timeout=None)` accepts a `CreateResponseRequest` or a mapping and returns:

- `ResponseResource` for strict JSON responses;
- `OpenAICompatibleResponse` when `response_compatibility="openai-compatible"` accepts a partial provider response;
- `ResponseStream` or `AsyncResponseStream` when `stream=True`.

`responses.compact(request, *, extra_headers=None, timeout=None)` returns `CompactResource`. The base URL is normalized and the SDK appends `/responses` and `/responses/compact`.

## Types

Request and response models are generated from the pinned OpenAPI artifact and re-exported from the package root:

- `CreateResponseRequest`, `CompactResponseRequest`, `WebSocketResponseCreateRequest`;
- `ResponseResource`, `CompactResource`, `ResponseItem`, `InputItem`;
- `FunctionToolParam`, `ToolChoice`, `ResponseContentPart`;
- `Response*StreamingEvent`, `UnknownStreamingEvent`, and `WebSocketErrorEvent`.

Use `model_dump(mode="json", by_alias=True)` to serialize Python models to the wire format. Unknown provider fields are preserved.

## Streams and WebSockets

`ResponseStream` and `AsyncResponseStream` are closeable iterators. They expose `final_response`, `response_id`, and `last_sequence_number`.

`WebSocketConnection` and `AsyncWebSocketConnection` expose `connect()`, `close()`, and `create()`. A connection permits one in-flight turn; inspect `turn.error`, `turn.final_response`, and `turn.response_id` before starting the next turn.

`SSEParser` is exported for reusable incremental SSE framing. The high-level streams add content-type, event-model, sequence, and lifecycle validation.

## Errors

All errors inherit from `OpenResponsesError`:

| Error | Typical condition |
| --- | --- |
| `BadRequestError` | HTTP 400 or invalid request semantics. |
| `AuthenticationError` | HTTP 401. |
| `PermissionDeniedError` | HTTP 403. |
| `NotFoundError` | HTTP 404. |
| `RateLimitError` | HTTP 429. |
| `ModelError` | Provider `model_error` response. |
| `InternalServerError` | Other 5xx responses. |
| `APIConnectionError` / `APITimeoutError` | Transport failure or timeout. |
| `APIResponseValidationError` | Successful response fails the pinned model. |
| `SSEProtocolError` / `WebSocketError` | Invalid stream or WebSocket protocol behavior. |

HTTP status errors retain the status, raw body, headers, request URL, and parsed provider error. No automatic retries are performed.

## Version boundary

`OPENRESPONSES_SPEC_VERSION` reports the pinned protocol version, currently `2026-04-24`. The client does not silently follow an unreleased upstream contract.
