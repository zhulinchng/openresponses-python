# WebSocket turns and continuation

Open a WebSocket through the same configured client used for HTTP:

```python
from openresponses import CreateResponseRequest, OpenResponses

with OpenResponses() as client, client.websocket() as websocket:
    turn = websocket.create(CreateResponseRequest(model="my-model", input="Hello"))
    for event in turn:
        print(event.type)

    print(turn.error)        # a typed WebSocket error event, or None
    print(turn.final_response)
```

`with client.websocket() as websocket:` is the complete connection lifecycle: entering connects and exiting closes. The WebSocket URL is derived from the HTTP base URL (`http`→`ws`, `https`→`wss`) with `/responses` appended. Configured API-key authentication and default headers are sent on the upgrade.

`websocket.create(...)` accepts an ergonomic `CreateResponseRequest` and validates it as the WebSocket-specific `WebSocketResponseCreateRequest`. It adds `type: "response.create"` and rejects `stream`, `stream_options`, or `background`, including explicit `None` or `False` values. WebSocket turns are already incremental and do not use HTTP streaming or background response modes.

The async form is:

```python
from openresponses import AsyncOpenResponses, CreateResponseRequest

async with AsyncOpenResponses() as client, client.websocket() as websocket:
    turn = await websocket.create(CreateResponseRequest(model="my-model", input="Hello"))
    async for event in turn:
        print(event.type)
```

## Sequential turns

A connection permits one in-flight turn. Calling `create` again before the first turn reaches a terminal response or typed error raises `WebSocketError`. After iteration ends, inspect `turn.error` and `turn.final_response`, then create the next turn:

```python
next_turn = websocket.create(CreateResponseRequest(
    model="my-model",
    input="Now make it shorter.",
    previous_response_id=turn.final_response.id if turn.final_response else None,
))
```

Text and binary frames are decoded as UTF-8. Malformed JSON, invalid known events, and invalid error envelopes raise `WebSocketError` or the corresponding protocol/validation error. A connection close before terminal completion raises `WebSocketError`; the exception does not cause an automatic reconnect. A typed error envelope has `turn.error.status` and nested `turn.error.error.code` / `turn.error.error.message`.


## Stored continuation

When a provider stores responses, continue with the terminal response ID:

```python
request = CreateResponseRequest(
    model="my-model",
    input="Continue from the previous answer.",
    previous_response_id=turn.final_response.id,
)
```

The server can reject an unavailable or evicted prior response with a typed error such as `previous_response_not_found`. Read `turn.error.error.code` and decide how to recover.

## `store=False` continuation

With `store=False`, previous-response state may exist only in the active connection's cache. Reusing its ID on the same connection can work; the same ID on a new connection can return `previous_response_not_found`. The SDK deliberately never reconnects or resends a turn automatically because replay can duplicate model work and billable execution.

If a connection is lost, explicitly choose a recovery strategy:

- resend sufficient explicit input on a new connection;
- request or retain enough context to reconstruct a safe request;
- compact the conversation and start a new chain;
- use a stored `previous_response_id` only if the provider confirms it remains available.

Do not blindly retry the original frame after a disconnect.

## Compaction handoff

Compaction is an HTTP operation and is not a WebSocket stream:

```python
compacted = client.responses.compact({
    "model": "my-model",
    "input": conversation,
    "previous_response_id": prior_id,
})
new_chain = websocket.create(CreateResponseRequest(
    model="my-model",
    input=[item.model_dump(mode="json", by_alias=True) for item in compacted.output],
))
```

A compacted response starts a new chain; do not assume its ID is a continuation target. Compaction output is protocol input, not an instruction to execute tools.

## Turn and connection errors

`WebSocketError` includes the protocol status and code when available. A typed `error` event is a normal end for that turn: inspect it and decide whether to send another turn. Malformed frames and pre-terminal closes are exceptional. There is no hidden retry/reconnect loop, so application policy remains explicit and can account for duplicate execution.
