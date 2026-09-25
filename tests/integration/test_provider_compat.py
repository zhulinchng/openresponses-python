from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from openresponses import APIResponseValidationError, OpenResponses
from openresponses.errors import APIStatusError, ResponseTooLargeError
from openresponses.serialization import OpenAICompatibleResponse
from openresponses.types import ResponseResource

OLLAMA_RESPONSE = {
    "id": "resp_123",
    "object": "response",
    "created": 1677652288,
    "model": "qwen3:8b",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Hello there!"}],
        }
    ],
    "usage": {"input_tokens": 9, "output_tokens": 12, "total_tokens": 21},
}

VLLM_RESPONSE = {
    "id": "resp-vllm",
    "object": "response",
    "created": 1677652288,
    "model": "Qwen/Qwen3-8B",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Hello!", "annotations": []}],
        }
    ],
    "usage": {"input_tokens": 5, "output_tokens": 10, "total_tokens": 15},
}


@pytest.mark.parametrize("payload", [OLLAMA_RESPONSE, VLLM_RESPONSE])
def test_documented_local_provider_json_shape_is_strictly_rejected(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ResponseResource.model_validate(payload)


@pytest.mark.parametrize("payload", [OLLAMA_RESPONSE, VLLM_RESPONSE])
def test_openai_compatibility_mode_accepts_documented_provider_shape(
    payload: dict[str, object],
) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = OpenResponses(
        base_url="http://test",
        response_compatibility="openai-compatible",
        http_client=httpx.Client(transport=transport),
    )
    result = client.responses.create({"model": "local", "input": "Hello"})
    assert isinstance(result, OpenAICompatibleResponse)
    assert result.id == payload["id"]
    output = payload["output"]
    assert isinstance(output, list)
    content = output[0]["content"]
    assert isinstance(content, list)
    assert result.output[0].content[0].text == content[0]["text"]
    client.close()


def test_strict_mode_rejects_local_provider_shape() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=OLLAMA_RESPONSE))
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    with pytest.raises(APIResponseValidationError):
        client.responses.create({"model": "qwen3:8b", "input": "Hello"})
    client.close()


def test_large_declared_response_is_rejected() -> None:
    response = httpx.Response(
        200,
        headers={"content-type": "application/json", "content-length": "1000"},
        content=b"{}",
    )
    client = OpenResponses(
        base_url="http://test",
        max_response_bytes=10,
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: response)),
    )
    with pytest.raises(ResponseTooLargeError):
        client.responses.create({"model": "m"})
    client.close()


def test_redirect_is_not_treated_as_success() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"location": "/elsewhere"}, content=b"")
    )
    client = OpenResponses(base_url="http://test", http_client=httpx.Client(transport=transport))
    with pytest.raises(APIStatusError):
        client.responses.create({"model": "m"})
    client.close()
