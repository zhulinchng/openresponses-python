#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from openresponses import AsyncOpenResponses, CreateResponseRequest


def payload(kind: str, sequence: int, response_id: str) -> dict[str, Any]:
    return {
        "type": kind,
        "sequence_number": sequence,
        "response": {
            "id": response_id,
            "object": "response",
            "created_at": 1,
            "completed_at": 1 if kind == "response.completed" else None,
            "status": "completed" if kind == "response.completed" else "in_progress",
            "incomplete_details": None,
            "model": "local",
            "previous_response_id": None,
            "instructions": None,
            "output": [],
            "error": None,
            "tools": [],
            "tool_choice": "auto",
            "truncation": "auto",
            "parallel_tool_calls": True,
            "text": {"format": {"type": "text"}},
            "top_p": 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "top_logprobs": 0,
            "temperature": 1.0,
            "reasoning": None,
            "usage": None,
            "max_output_tokens": None,
            "max_tool_calls": None,
            "store": True,
            "background": False,
            "service_tier": "default",
            "metadata": {},
            "safety_identifier": None,
            "prompt_cache_key": None,
        },
    }


async def run(base_url: str, model: str, compatibility: str) -> dict[str, Any]:
    result: dict[str, Any] = {"base_url": base_url, "compatibility": compatibility}
    async with AsyncOpenResponses(
        base_url=base_url,
        response_compatibility=compatibility,
        timeout=300,
    ) as client:
        response = await client.responses.create(
            CreateResponseRequest(model=model, input="Reply with the single word SDK_OK.")
        )
        result["json"] = {
            "ok": True,
            "id": getattr(response, "id", None),
            "type": type(response).__name__,
            "status": getattr(response, "status", None),
        }
        stream = await client.responses.create(
            CreateResponseRequest(
                model=model,
                input="Reply with one word.",
                stream=True,
                max_output_tokens=32,
            )
        )
        types: list[str] = []
        text: list[str] = []
        try:
            async for event in stream:
                types.append(event.type)
                if event.type == "response.output_text.delta":
                    text.append(event.delta)
        except Exception as exc:
            result["stream"] = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "types": types,
            }
        else:
            result["stream"] = {
                "ok": True,
                "types": types,
                "text": "".join(text),
                "final_id": stream.response_id,
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--compatibility", default="openai-compatible")
    args = parser.parse_args()
    print(
        json.dumps(asyncio.run(run(args.base_url, args.model, args.compatibility)), sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
