# Server-sent event streaming

Set `stream=True` on a create request. `OpenResponses.responses.create` returns a closeable `ResponseStream`; `AsyncOpenResponses.responses.create` returns an `AsyncResponseStream`.

```python
from openresponses import OpenResponses

with OpenResponses() as client:
    stream = client.responses.create({
        "model": "my-model",
        "input": "Write a haiku about HTTP streaming.",
        "stream": True,
    })
    with stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
        print()
```

The async form is:

```python
stream = await client.responses.create(request)
async with stream:
    async for event in stream:
        print(event.type)
```

## Typed lifecycle

Each yielded standard value is a `Response*StreamingEvent` model. A typical completed lifecycle is:

1. `response.created`;
2. one or more `response.output_item.added` and `response.content_part.added` events;
3. incremental events such as `response.output_text.delta`, reasoning events, or function-call argument deltas;
4. matching `.done` events and `response.output_item.done`;
5. exactly one terminal event: `response.completed`, `response.failed`, or `response.incomplete`;
6. the SSE sentinel `data: [DONE]`.

`[DONE]` is transport framing, not a protocol event, and is never yielded. `response.failed` and `response.incomplete` are valid typed terminal results. An earlier `error` event must be followed by `response.failed`.

After normal exhaustion, inspect:

- `stream.final_response`: the snapshot carried by the terminal event;
- `stream.response_id`: its ID, or `None` before completion;
- `stream.last_sequence_number`: the last accepted sequence number.

## State validation

The stream validates release semantics while still permitting provider extensions:

- supplied `sequence_number` values strictly increase; gaps are allowed;
- a standard output item is not completed twice;
- a content part is not completed twice;
- events after the terminal response are rejected;
- terminal response and `[DONE]` must both arrive.

The server must use `Content-Type: text/event-stream`. Wrong content types, invalid JSON, mismatched SSE event names, malformed standard events, and lifecycle violations raise typed SDK exceptions rather than being returned as successful text.
Use a stream as a context manager or call `close()` (`await aclose()` for async streams) when abandoning it early. Exhaustion, parse failure, and cancellation also release the HTTP response.

## Incremental framing and extensions

`SSEParser` is reusable and incremental. It handles UTF-8 split across byte chunks, LF/CRLF/CR line endings, comments, optional field values, multiple `data:` lines, incomplete final records, and event boundaries split across chunks. This low-level parser yields parsed frames; application streams additionally apply event validation and lifecycle state.

Unknown provider-prefixed event types become `UnknownStreamingEvent` values and are yielded with extension fields intact. If an event supplies a sequence number, it is sequence-checked. Unknown records do not participate in standard item/content lifecycle tracking.

## Errors

- HTTP status and connection failures raise the corresponding `APIStatusError` or connection exception.
- invalid framing or lifecycle raises `SSEProtocolError`.
- a known event that violates its model raises an SDK protocol/validation exception rather than being silently downgraded.

See `docs/quickstart.md` for client setup and the import surface. There are no automatic retries: the stream is not replayed after disconnect because partial response generation may duplicate billed or externally visible work.
