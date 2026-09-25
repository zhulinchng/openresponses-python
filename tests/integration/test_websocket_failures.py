from __future__ import annotations

import json

import pytest
from websockets.sync.server import serve

from openresponses import CreateResponseRequest, OpenResponses
from openresponses.errors import WebSocketError


@pytest.fixture
def faulty_server():
    def handler(connection):
        connection.recv()
        connection.send("not json")
        connection.recv()
        connection.send(
            json.dumps({"type": "response.completed", "sequence_number": 0, "response": {}})
        )

    server = serve(handler, "127.0.0.1", 0)
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.socket.getsockname()[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_malformed_turn_closes_connection(faulty_server: str) -> None:
    with OpenResponses(base_url=faulty_server) as client, client.websocket() as connection:
        turn = connection.create(CreateResponseRequest(model="m", input="one"))
        with pytest.raises(WebSocketError):
            list(turn)
        assert not connection.connected
        with pytest.raises(WebSocketError):
            connection.create(CreateResponseRequest(model="m", input="two"))
