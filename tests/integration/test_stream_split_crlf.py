from __future__ import annotations

from openresponses.streaming import SSEParser


def test_crlf_split_across_chunks_is_one_terminator() -> None:
    parser = SSEParser()
    assert parser.feed(b"data: one\r") == []
    parsed = parser.feed(b"\ndata: two\n\n")
    assert len(parsed) == 1
    assert parsed[0].data == "one\ntwo"
