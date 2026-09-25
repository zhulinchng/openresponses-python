import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from openresponses.types import (
    CompactResponseRequest,
    CreateResponseRequest,
    InputItemAdapter,
    ResponseResource,
    WebSocketResponseCreateRequest,
)

SCHEMA = Path("openresponses/openapi/2026-04-24.json")


def test_pinned_schema_is_release() -> None:
    document = json.loads(SCHEMA.read_text())
    assert document["info"]["version"] == "2026-04-24"
    assert "/responses" in document["paths"]
    assert "/responses/compact" in document["paths"]


def test_user_message_discriminator() -> None:
    item = InputItemAdapter.validate_python({"type": "message", "role": "user", "content": "hi"})
    assert item.type == "message"
    assert item.role == "user"
    assert item.content.root == "hi"


def test_create_request_constraints() -> None:
    assert CreateResponseRequest(model="m", max_output_tokens=16).max_output_tokens == 16
    with pytest.raises(ValidationError):
        CreateResponseRequest(model="m", max_output_tokens=15)
    with pytest.raises(ValidationError):
        CreateResponseRequest(model="m", top_logprobs=21)


@pytest.mark.parametrize("field", ["include", "truncation", "service_tier"])
def test_create_request_rejects_explicit_null_for_non_nullable_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        CreateResponseRequest(model="m", **{field: None})


def test_create_request_omits_unspecified_non_nullable_fields() -> None:
    request = CreateResponseRequest(model="m")
    assert request.model_dump(exclude_unset=True) == {"model": "m"}


def test_websocket_rejects_http_fields() -> None:
    assert WebSocketResponseCreateRequest(model="m").type == "response.create"
    with pytest.raises(ValidationError):
        WebSocketResponseCreateRequest(model="m", stream=False)
    with pytest.raises(ValidationError):
        WebSocketResponseCreateRequest(model="m", background=False)


def test_compact_requires_model() -> None:
    with pytest.raises(ValidationError):
        CompactResponseRequest()


def test_response_validation_requires_release_fields() -> None:
    with pytest.raises(ValidationError):
        ResponseResource.model_validate({"id": "resp_1"})
