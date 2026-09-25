from __future__ import annotations

import sys
import types
from typing import Any

import httpx
import pytest

from openresponses import AsyncOpenResponses, OpenResponses
from openresponses.integrations import MLflowAsyncOpenResponses, MLflowOpenResponses


class FakeSpan:
    def __init__(self) -> None:
        self.inputs: Any = None
        self.outputs: Any = None
        self.entered = False
        self.exited = 0

    def __enter__(self) -> FakeSpan:
        self.entered = True
        return self

    def __exit__(self, *_: Any) -> None:
        self.exited += 1

    def set_outputs(self, outputs: Any) -> None:
        self.outputs = outputs


def install_fake_mlflow(monkeypatch: pytest.MonkeyPatch) -> list[FakeSpan]:
    spans: list[FakeSpan] = []
    fake = types.ModuleType("mlflow")

    def start_span(**kwargs: Any) -> FakeSpan:
        span = FakeSpan()
        span.inputs = kwargs.get("inputs")
        spans.append(span)
        return span

    fake.start_span = start_span
    monkeypatch.setitem(sys.modules, "mlflow", fake)
    return spans


def response_payload() -> dict[str, object]:
    return {
        "id": "resp_mlflow",
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


def test_mlflow_wrapper_traces_sync_json(monkeypatch: pytest.MonkeyPatch) -> None:
    spans = install_fake_mlflow(monkeypatch)
    client = OpenResponses(
        base_url="http://test",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=response_payload())
            )
        ),
    )
    with MLflowOpenResponses(client) as traced:
        result = traced.responses.create({"model": "m", "input": "hello"})
    assert result.id == "resp_mlflow"
    assert spans[0].inputs == {"model": "m", "input": "hello"}
    assert spans[0].outputs["response"]["id"] == "resp_mlflow"
    assert spans[0].exited == 1


def test_mlflow_wrapper_traces_sync_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    import json

    spans = install_fake_mlflow(monkeypatch)
    body = (
        b"event: response.created\ndata: "
        + json.dumps(
            {"type": "response.created", "sequence_number": 0, "response": response_payload()}
        ).encode()
        + b"\n\n"
        + b"event: response.completed\ndata: "
        + json.dumps(
            {"type": "response.completed", "sequence_number": 1, "response": response_payload()}
        ).encode()
        + b"\n\ndata: [DONE]\n\n"
    )
    client = OpenResponses(
        base_url="http://test",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, headers={"content-type": "text/event-stream"}, content=body
                )
            )
        ),
    )
    with MLflowOpenResponses(client) as traced:
        events = list(traced.responses.create({"model": "m", "stream": True}))
    assert [event.type for event in events] == ["response.created", "response.completed"]
    assert spans[0].exited == 1


async def test_mlflow_wrapper_traces_async_json(monkeypatch: pytest.MonkeyPatch) -> None:
    spans = install_fake_mlflow(monkeypatch)
    client = AsyncOpenResponses(
        base_url="http://test",
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=response_payload())
            )
        ),
    )
    async with MLflowAsyncOpenResponses(client) as traced:
        result = await traced.responses.create({"model": "m", "input": "hello"})
    assert result.id == "resp_mlflow"
    assert spans[0].exited == 1
