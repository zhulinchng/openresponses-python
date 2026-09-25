from __future__ import annotations

import json
import threading

from websockets.sync.server import serve

from openresponses import CreateResponseRequest, OpenResponses


def test_websocket_omits_http_defaults():
    received = []

    def handler(connection):
        received.append(json.loads(connection.recv()))
        connection.send(
            json.dumps(
                {"type": "error", "status": 400, "error": {"code": "stop", "message": "stop"}}
            )
        )

    server = serve(handler, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with (
            OpenResponses(base_url=f"http://127.0.0.1:{server.socket.getsockname()[1]}") as client,
            client.websocket() as connection,
        ):
            turn = connection.create(CreateResponseRequest(model="m", input="x"))
            list(turn)
        assert received == [{"model": "m", "input": "x", "type": "response.create"}]
    finally:
        server.shutdown()
        thread.join(timeout=2)
