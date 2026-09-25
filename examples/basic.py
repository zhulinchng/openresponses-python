"""Create synchronous and asynchronous JSON responses.

Set OPENRESPONSES_BASE_URL, OPENRESPONSES_API_KEY, and OPENRESPONSES_MODEL.
"""

import asyncio
import os

from openresponses import AsyncOpenResponses, OpenResponses

BASE_URL = os.environ.get("OPENRESPONSES_BASE_URL", "https://api.openai.com/v1")
API_KEY = os.environ.get("OPENRESPONSES_API_KEY")
MODEL = os.environ["OPENRESPONSES_MODEL"]


def create_sync() -> None:
    with OpenResponses(base_url=BASE_URL, api_key=API_KEY) as client:
        response = client.responses.create(
            {
                "model": MODEL,
                "input": "Give me one practical API testing tip.",
            }
        )
        print(f"response {response.id}: {response.status}")
        for item in response.output:
            print(item.model_dump(mode="json", by_alias=True))


async def create_async() -> None:
    async with AsyncOpenResponses(base_url=BASE_URL, api_key=API_KEY) as client:
        response = await client.responses.create(
            {
                "model": MODEL,
                "input": "Name one common source of flaky network tests.",
            }
        )
        print(f"async response {response.id}: {response.status}")


if __name__ == "__main__":
    create_sync()
    asyncio.run(create_async())
