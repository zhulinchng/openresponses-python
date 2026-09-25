from __future__ import annotations

import json

import httpx
import pytest

from openresponses.client import OpenResponses
from openresponses.errors import AuthenticationError
from openresponses.types import CreateResponseRequest


def response_payload() -> dict[str, object]:
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 1,
        "completed_at": 1,
        "status": "completed",
        "incomplete_details": None,
        "model": "m",
        "previous_response_id": None,
        "instructions": None,
        "output": [],
        "error": None,
        "tools": [],
        "tool_choice": "auto",
        "truncation": "auto",
        "parallel_tool_calls": True,
        "text": {"format": {"type": "text"}},
        "top_p": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "top_logprobs": 0,
        "temperature": 1.0,
        "reasoning": None,
        "usage": None,
        "max_output_tokens": None,
        "max_tool_calls": None,
        "store": True,
        "background": False,
        "service_tier": "default",
        "metadata": {},
        "safety_identifier": None,
        "prompt_cache_key": None,
    }


def test_json_create_sends_contract_body() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=response_payload())

    client = OpenResponses(
        base_url="http://test/v1",
        api_key="secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.responses.create(CreateResponseRequest(model="m", input="hello"))
    assert result.id == "resp_1"
    assert len(captured) == 1
    assert captured[0].url == "http://test/v1/responses"
    assert captured[0].headers["authorization"] == "Bearer secret"
    assert json.loads(captured[0].content) == {"model": "m", "input": "hello"}
    client.close()


def test_json_error_mapping() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": {"message": "bad key"}})
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    with pytest.raises(AuthenticationError):
        client.responses.create({"model": "m"})
    client.close()


def test_compact_requires_json() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "id": "cmp_1",
                "object": "response.compaction",
                "output": [],
                "created_at": 1,
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0},
                },
            },
        )
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    result = client.responses.compact({"model": "m"})
    assert result.id == "cmp_1"
    client.close()
