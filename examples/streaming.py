"""Consume a typed SSE response.

Set OPENRESPONSES_BASE_URL, OPENRESPONSES_API_KEY, and OPENRESPONSES_MODEL.
"""

import os

from openresponses import OpenResponses

BASE_URL = os.environ.get("OPENRESPONSES_BASE_URL", "https://api.openai.com/v1")
API_KEY = os.environ.get("OPENRESPONSES_API_KEY")
MODEL = os.environ["OPENRESPONSES_MODEL"]


def main() -> None:
    with (
        OpenResponses(base_url=BASE_URL, api_key=API_KEY) as client,
        client.responses.create(
            {
                "model": MODEL,
                "input": "Write two short sentences about server-sent events.",
                "stream": True,
            }
        ) as stream,
    ):
        for event in stream:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)

        print()
        if stream.final_response is not None:
            print(f"completed response: {stream.final_response.id}")


if __name__ == "__main__":
    main()
