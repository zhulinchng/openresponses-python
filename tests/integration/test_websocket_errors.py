from __future__ import annotations

from openresponses.websocket import _envelope_or_event


def response_payload() -> dict[str, object]:
    return {
        "id": "resp_e",
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


def test_streaming_error_with_extension_status_is_not_envelope() -> None:
    payload = {
        "type": "error",
        "sequence_number": 1,
        "status": 500,
        "error": {"type": "server_error", "code": "x", "message": "m", "param": None},
    }
    event = _envelope_or_event(payload)
    assert event.type == "error"
    assert event.status == 500
