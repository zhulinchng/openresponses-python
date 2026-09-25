"""Run two sequential WebSocket turns and inspect each result.

Set OPENRESPONSES_BASE_URL, OPENRESPONSES_API_KEY, and OPENRESPONSES_MODEL.
The provider must support the OpenResponses WebSocket endpoint.
"""

import os

from openresponses import CreateResponseRequest, OpenResponses

BASE_URL = os.environ.get("OPENRESPONSES_BASE_URL", "https://api.openai.com/v1")
API_KEY = os.environ.get("OPENRESPONSES_API_KEY")
MODEL = os.environ["OPENRESPONSES_MODEL"]


def main() -> None:
    with (
        OpenResponses(base_url=BASE_URL, api_key=API_KEY) as client,
        client.websocket() as websocket,
    ):
        first = websocket.create(
            CreateResponseRequest(model=MODEL, input="Name one HTTP status code.")
        )
        for event in first:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
        print()

        if first.error is not None:
            print(f"first turn error: {first.error.error.code}: {first.error.error.message}")
            return
        if first.final_response is None:
            return

        second = websocket.create(
            CreateResponseRequest(
                model=MODEL,
                input="Explain that status code in one sentence.",
                previous_response_id=first.final_response.id,
            )
        )
        for event in second:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
        print()


if __name__ == "__main__":
    main()
