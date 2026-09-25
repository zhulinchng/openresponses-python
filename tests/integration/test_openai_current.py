from __future__ import annotations

import json

import httpx

from openresponses import (
    AsyncOpenResponses,
    CreateResponseRequest,
    OpenAICompactRequest,
    OpenAIRequest,
    OpenAIResponse,
    OpenResponses,
)


def current_response() -> dict[str, object]:
    return {
        "id": "resp_current",
        "object": "response",
        "access_programs": {"cyber": "standard"},
        "created_at": 1.5,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": [{"role": "developer", "content": "be brief"}],
        "metadata": {"trace": "t1"},
        "model": "gpt-5.5",
        "output": [
            {
                "id": "msg_1",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "OK", "annotations": []}],
            }
        ],
        "parallel_tool_calls": True,
        "temperature": 1.0,
        "tool_choice": "auto",
        "tools": [{"type": "web_search"}],
        "top_p": 1.0,
        "background": False,
        "conversation": {"id": "conv_1"},
        "max_output_tokens": 100,
        "max_tool_calls": 2,
        "previous_response_id": "resp_prev",
        "prompt_cache_key": "cache",
        "prompt_cache_options": {"mode": "implicit"},
        "reasoning": {"effort": "low"},
        "safety_identifier": "user_1",
        "service_tier": "default",
        "text": {"format": {"type": "text"}},
        "top_logprobs": 0,
        "truncation": "disabled",
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        "user": "user_1",
    }


def test_current_openai_request_and_response_are_typed() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=current_response())

    client = OpenResponses(
        base_url="https://api.openai.test/v1",
        response_compatibility="openai",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.responses.create(
        OpenAIRequest(
            model="gpt-5.5",
            input="hello",
            conversation={"id": "conv_1"},
            context_management=[{"type": "compaction", "compact_threshold": 1000}],
            prompt_cache_options={"mode": "implicit"},
        )
    )
    assert isinstance(result, OpenAIResponse)
    assert result.output_text == "OK"
    assert result.conversation == {"id": "conv_1"}
    assert json.loads(captured[0].content)["context_management"][0]["type"] == "compaction"
    client.close()


def test_current_openai_mapping_request_is_supported() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=current_response()))
    client = OpenResponses(
        base_url="https://api.openai.test/v1",
        response_compatibility="openai",
        http_client=httpx.Client(transport=transport),
    )
    result = client.responses.create(
        CreateResponseRequest(model="gpt-5.5", input="hello", metadata={"trace": "t1"})
    )
    assert isinstance(result, OpenAIResponse)
    client.close()


def test_current_openai_compact_is_supported() -> None:
    payload = {
        "id": "cmp_current",
        "object": "response.compaction",
        "created_at": 1.5,
        "output": [],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = OpenResponses(
        base_url="https://api.openai.test/v1",
        response_compatibility="openai",
        http_client=httpx.Client(transport=transport),
    )
    result = client.responses.compact(OpenAICompactRequest(model="gpt-5.5", input="hello"))
    assert result.id == "cmp_current"
    client.close()


async def test_current_openai_async_stream_is_supported() -> None:
    event = {
        "type": "response.output_text.delta",
        "sequence_number": 0,
        "item_id": "msg_1",
        "output_index": 0,
        "content_index": 0,
        "delta": "OK",
    }
    completed = {
        "type": "response.completed",
        "sequence_number": 1,
        "response": current_response(),
    }
    body = (
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        f"event: {completed['type']}\ndata: {json.dumps(completed)}\n\n"
    ).encode()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )
    )
    client = AsyncOpenResponses(
        base_url="https://api.openai.test/v1",
        response_compatibility="openai",
        http_client=httpx.AsyncClient(transport=transport),
    )
    stream = await client.responses.create(
        OpenAIRequest(model="gpt-5.5", input="hello", stream=True)
    )
    events = [event async for event in stream]
    assert [event.type for event in events] == [
        "response.output_text.delta",
        "response.completed",
    ]
    assert stream.final_response is not None
    await client.close()


def test_current_openai_websocket_request_and_events() -> None:
    from openresponses import OpenAIWebSocketRequest

    request = OpenAIWebSocketRequest(
        type="response.create", model="gpt-5.5", input="hello", stream_id="main", generate=False
    )
    payload = request.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert payload["type"] == "response.create"
    assert payload["stream_id"] == "main"
    assert payload["generate"] is False
