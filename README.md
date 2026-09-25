# OpenResponses Python SDK

A typed Python client for the [OpenResponses](https://github.com/openresponses/openresponses) protocol. This SDK implements the pinned **`2026-04-24`** wire contract, including JSON and SSE response creation, compaction, WebSocket turns and continuation, typed models, structured errors, and opaque provider extensions.

## Requirements and installation

Python 3.10 or newer is required.

```bash
python -m pip install openresponses
```

For a checkout of this repository:

```bash
python -m pip install -e .
```

The default HTTP base URL is `https://api.openai.com/v1`. Supply a provider-specific URL when needed. An API key is optional for local or private providers.

## Synchronous and asynchronous JSON

```python
import os

from openresponses import OpenResponses

client = OpenResponses(
    base_url=os.environ.get("OPENRESPONSES_BASE_URL", "https://api.openai.com/v1"),
    api_key=os.environ.get("OPENRESPONSES_API_KEY"),
)
with client:
    response = client.responses.create({
        "model": os.environ["OPENRESPONSES_MODEL"],
        "input": "Give me one practical tip for testing an API.",
    })
    print(response.id)
    for item in response.output:
        print(item.root)
```

`AsyncOpenResponses` has the same `responses.create(...)` API; await the call and iterate asynchronous streams with `async for`:

```python
import asyncio
import os

from openresponses import AsyncOpenResponses

async def main() -> None:
    async with AsyncOpenResponses(
        base_url=os.environ.get("OPENRESPONSES_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.environ.get("OPENRESPONSES_API_KEY"),
    ) as client:
        response = await client.responses.create({
            "model": os.environ["OPENRESPONSES_MODEL"],
            "input": "Hello",
        })
        print(response.id)

asyncio.run(main())
```

Requests may be dictionaries or typed `CreateResponseRequest` models. Successful JSON responses are validated as `ResponseResource`; the typed model surface is re-exported from `openresponses`.

## Streaming

Set `stream=True` to receive a `ResponseStream`; the asynchronous client returns `AsyncResponseStream`. Each yielded value is a typed streaming event.

```python
from openresponses import OpenResponses

with OpenResponses() as client:
    with client.responses.create({
        "model": "your-model",
        "input": "Write a short greeting.",
        "stream": True,
    }) as stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
        print()
        print(stream.final_response.id if stream.final_response else "no final response")
```

A valid SSE response contains exactly one terminal event—`response.completed`, `response.failed`, or `response.incomplete`—followed by the private `[DONE]` sentinel. The sentinel is not yielded as a protocol event. Sequence gaps are allowed, but supplied sequence numbers must strictly increase. See [streaming semantics](docs/streaming.md).

## WebSockets and continuation

A connection accepts one in-flight turn at a time. A completed, failed, or errored turn releases it for the next turn. The SDK never reconnects or resends automatically: with `store=False`, continuation state can be local to the connection and replay may execute work twice.

```python
from openresponses import CreateResponseRequest, OpenResponses

with OpenResponses() as client, client.websocket() as websocket:
    turn = websocket.create(CreateResponseRequest(model="your-model", input="Hello"))
    for event in turn:
        print(event.type)

    if turn.error is not None:
        print(f"turn failed: {turn.error.error.code}: {turn.error.error.message}")
    elif turn.final_response is not None:
        previous_response_id = turn.final_response.id
```

`AsyncWebSocketConnection` provides the corresponding asynchronous API. For continuation, recovery, compaction handoff, and reconnect guidance, see [WebSocket semantics](docs/websocket.md).

## Function calls are not executed

The SDK is a protocol client, not an agent runner. It returns `function_call` items but **never executes tools automatically**. Inspect each call, run application-owned code yourself, then send a matching `function_call_output` item, using `previous_response_id` only when the provider has retained that response. See [protocol models](docs/protocol.md#function-call-continuation).

## Compaction

`responses.compact(...)` posts a `CompactResponseRequest` to `/responses/compact` and returns a `CompactResource`. Compaction has no streaming mode. Its `output` can seed a new request or WebSocket turn, typically without `previous_response_id`.

## Errors and retries

All SDK exceptions derive from `OpenResponsesError`. HTTP failures retain the status, raw body, headers, request URL, and parsed provider error where available. Common subclasses include `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `RateLimitError`, `InternalServerError`, `APIConnectionError`, and `APITimeoutError`. Invalid success payloads and malformed event streams raise validation or protocol errors.

The SDK performs **no automatic retries**. Response creation can bill or execute work and the protocol has no universal idempotency key. Retry only when your application understands duplicate-work risk and provider semantics.

## Provider extensions

Models preserve unknown extension fields and serialize them with `model_dump(mode="json", by_alias=True)`. Unknown provider-prefixed streaming events become `UnknownStreamingEvent` records rather than being discarded. Malformed records claiming a known standard event type are rejected, not downgraded to an opaque event.

For Ollama, vLLM, llama.cpp, LM Studio, SGLang, and other partial OpenAI-compatible runtimes, see [provider compatibility](docs/compatibility.md). Compatibility mode is explicit and preserves strict OpenResponses validation by default.

## Documentation and examples

- [Quickstart](docs/quickstart.md)
- [Typed protocol models](docs/protocol.md)
- [SSE streaming](docs/streaming.md)
- [WebSocket turns](docs/websocket.md)
- Runnable-style programs in [`examples/`](examples/)

The package includes the pinned schema at `openresponses/openapi/2026-04-24.json`. Compatibility is for that dated release; later protocol versions require an explicit SDK/model update.
