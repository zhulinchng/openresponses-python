from __future__ import annotations

import pytest

from openresponses import CreateResponseRequest, InputItemAdapter
from openresponses.types.generated import ItemReferenceParam


@pytest.mark.parametrize("item_type", [None, "item_reference"])
def test_item_reference_accepts_optional_type(item_type: str | None) -> None:
    payload = {"id": "item_1"}
    if item_type is not None:
        payload["type"] = item_type
    item = InputItemAdapter.validate_python(payload)
    assert isinstance(item, ItemReferenceParam)
    assert item.id == "item_1"


def test_item_reference_model_dump_feeds_request() -> None:
    item = ItemReferenceParam(id="item_1")
    request = CreateResponseRequest(input=[item])
    assert request.model_dump(mode="json", by_alias=True, exclude_unset=True) == {
        "input": [{"id": "item_1"}]
    }
