"""Compact conversation context, then start a new WebSocket chain.

Set OPENRESPONSES_BASE_URL, OPENRESPONSES_API_KEY, and OPENRESPONSES_MODEL.
The provider must support both HTTP compaction and WebSocket responses.
"""

import os

from openresponses import CreateResponseRequest, OpenResponses

BASE_URL = os.environ.get("OPENRESPONSES_BASE_URL", "https://api.openai.com/v1")
API_KEY = os.environ.get("OPENRESPONSES_API_KEY")
MODEL = os.environ["OPENRESPONSES_MODEL"]


def main() -> None:
    conversation = [
        {
            "type": "message",
            "role": "user",
            "content": "I am designing a long-running support assistant.",
        },
        {
            "type": "message",
            "role": "assistant",
            "content": "What information should the assistant retain between turns?",
        },
    ]

    with OpenResponses(base_url=BASE_URL, api_key=API_KEY) as client:
        compacted = client.responses.compact(
            {
                "model": MODEL,
                "input": conversation,
                "instructions": "Retain facts needed for future support requests.",
            }
        )
        print(f"compacted context: {compacted.id}")

        compacted_input = [item.model_dump(mode="json", by_alias=True) for item in compacted.output]
        with client.websocket() as websocket:
            # A compacted response seeds a new chain; it is not a previous_response_id.
            turn = websocket.create(
                CreateResponseRequest(
                    model=MODEL,
                    input=compacted_input,
                    instructions="Summarize the retained support context.",
                )
            )
            for event in turn:
                if event.type == "response.output_text.delta":
                    print(event.delta, end="", flush=True)
            print()

            if turn.error is not None:
                print(f"turn error: {turn.error.error.code}: {turn.error.error.message}")


if __name__ == "__main__":
    main()
