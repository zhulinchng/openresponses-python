from __future__ import annotations

import pytest

from openresponses import OpenResponses


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:secret@example.invalid/v1",
        "https://example.invalid/v1?token=secret",
        "https://example.invalid/v1#secret",
    ],
)
def test_base_url_rejects_credential_components(base_url: str) -> None:
    with pytest.raises(ValueError):
        OpenResponses(base_url=base_url)


def test_base_url_normalizes_path() -> None:
    client = OpenResponses(base_url="https://example.invalid/v1/")
    assert client.config.responses_url == "https://example.invalid/v1/responses"
    assert client.config.compact_url == "https://example.invalid/v1/responses/compact"
    client.close()
