# Quickstart

The SDK targets Python 3.10+ and the immutable OpenResponses `2026-04-24` release. Install it from a package index or a checkout:

```bash
python -m pip install openresponses-py
# or, from this repository:
python -m pip install -e .
```

## Configure a client

`OpenResponses` accepts a base URL, optional API key, default timeout, default headers, and custom authentication scheme. The HTTP base URL normally ends in the provider's API version, such as `https://api.openai.com/v1`; the SDK appends `/responses` and `/responses/compact`. The key is optional for local and private providers. Pass `timeout=` to `responses.create(...)` or `responses.compact(...)` to override the client timeout for one operation.

```python
import os

from openresponses import OpenResponses

client = OpenResponses(
    base_url=os.environ.get("OPENRESPONSES_BASE_URL", "https://api.openai.com/v1"),
    api_key=os.environ.get("OPENRESPONSES_API_KEY"),
    default_headers={"X-Client": "my-service"},
)
```

A key is sent as `Authorization: Bearer …` by default. Set `auth_header` and `auth_prefix=None` when a provider expects a different header or no prefix. Per-call `extra_headers` are merged without changing the defaults.

Clients created by the SDK own and close their HTTP transport. An injected `http_client` remains caller-owned. Use the context manager to close SDK-owned clients. HTTP 400 responses raise `BadRequestError`; 401, 403, 404, and 429 map to `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, and `RateLimitError`; provider `model_error` responses map to `ModelError`, and other 5xx responses map to `InternalServerError`.

## Create a JSON response

A mapping is convenient for short calls. `CreateResponseRequest` provides validation and typed IDE completion for full requests.

```python
from openresponses import CreateResponseRequest

with client:
    response = client.responses.create({
        "model": os.environ["OPENRESPONSES_MODEL"],
        "input": "Summarize why contract tests are useful.",
    })
    print(response.id, response.status)
    for item in response.output:
        print(item.model_dump(mode="json", by_alias=True))
```

Typed requests are preferable for application boundaries. Keep all operations in the same client context:

```python
with client:
    request = CreateResponseRequest(
        model=os.environ["OPENRESPONSES_MODEL"],
        input="Return three concise testing recommendations.",
        temperature=0.2,
        max_output_tokens=256,
    )
    response = client.responses.create(request)
```

Requests and responses are Pydantic models. Python names use snake case while wire aliases preserve the released field names. Serialize with `model_dump(mode="json", by_alias=True)`.

## Use the asynchronous client

The async client mirrors the synchronous configuration and operations.

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

## Continue a function call yourself

Define a function tool in the request, inspect the returned `function_call`, execute your own code, and return a `function_call_output` item. The SDK never runs application tools automatically.
```python
with client:
    request = CreateResponseRequest(
        model=os.environ["OPENRESPONSES_MODEL"],
        input="What is the weather in Paris?",
        tools=[{
            "type": "function",
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }],
    )
    first = client.responses.create(request)
    # Inspect first.output, execute the named application function, then:
    follow_up = client.responses.create({
        "model": os.environ["OPENRESPONSES_MODEL"],
        "previous_response_id": first.id,  # only when storage is supported
        "input": [{
            "type": "function_call_output",
            "call_id": "<call_id from the function_call item>",
            "output": "18°C and clear",
        }],
    })
```

With `store=False`, include enough explicit context yourself instead of assuming a previous-response ID is retained.

Next: [typed protocol models](protocol.md), [SSE streaming](streaming.md), or [WebSocket turns](websocket.md).
