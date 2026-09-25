from __future__ import annotations

import pytest
from pydantic import ValidationError

from openresponses.types import (
    CompactResponseRequest,
    CreateResponseRequest,
    FunctionCallOutputItemParam,
    FunctionToolParam,
    InputImageContentParamAutoParam,
    ItemReferenceParam,
    UserMessageItemParam,
)


def response_payload() -> dict[str, object]:
    return {
        "id": "resp_matrix",
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


def test_basic_and_system_prompt_request_shapes() -> None:
    assert CreateResponseRequest(model="m", input="hello").input == "hello"
    assert CreateResponseRequest(model="m", instructions="be brief").instructions == "be brief"
    assert CreateResponseRequest(model="m", input=[AssistantPhaseItem()]).input == [
        AssistantPhaseItem()
    ]


def AssistantPhaseItem() -> UserMessageItemParam:
    return UserMessageItemParam(type="message", role="user", content="phase")


def test_output_phase_item_reference_round_trip() -> None:
    item = ItemReferenceParam(id="item_1")
    request = CreateResponseRequest(model="m", input=[item])
    assert request.model_dump(mode="json", by_alias=True, exclude_none=True)["input"] == [
        {"id": "item_1"}
    ]


def test_tool_and_function_output_shapes() -> None:
    tool = FunctionToolParam(name="lookup", type="function")
    output = FunctionCallOutputItemParam(call_id="call_1", type="function_call_output", output="ok")
    request = CreateResponseRequest(model="m", tools=[tool], input=[output])
    payload = request.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert payload["tools"] == [{"name": "lookup", "type": "function"}]
    assert payload["input"][0]["call_id"] == "call_1"


def test_image_input_shape() -> None:
    image = InputImageContentParamAutoParam(
        type="input_image", image_url="data:image/png;base64,AA=="
    )
    message = UserMessageItemParam(type="message", role="user", content=[image])
    assert CreateResponseRequest(model="m", input=[message]).input == [message]


def test_compact_requires_model_before_transport() -> None:
    with pytest.raises(ValidationError):
        CompactResponseRequest()
