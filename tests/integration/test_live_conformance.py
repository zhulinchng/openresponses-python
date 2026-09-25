from __future__ import annotations

import os

import pytest

from openresponses import OpenResponses


@pytest.mark.live
def test_live_json_smoke() -> None:
    if os.getenv("OPENRESPONSES_RUN_LIVE") != "1":
        pytest.skip("set OPENRESPONSES_RUN_LIVE=1 for live provider tests")
    base_url = os.getenv("OPENRESPONSES_BASE_URL")
    api_key = os.getenv("OPENRESPONSES_API_KEY")
    model = os.getenv("OPENRESPONSES_MODEL")
    if not base_url or not model:
        pytest.skip("live conformance requires OPENRESPONSES_BASE_URL and OPENRESPONSES_MODEL")
    with OpenResponses(base_url=base_url, api_key=api_key) as client:
        response = client.responses.create({"model": model, "input": "Reply with OK."})
        assert response.id
