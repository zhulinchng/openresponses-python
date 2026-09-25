# Provider compatibility

Strict mode validates the pinned OpenResponses `2026-04-24` models and is the default.

## Local runtimes

Ollama 0.13.3+ documents `POST /v1/responses` with stateless streaming/tools/reasoning support, but omits several OpenResponses response fields. vLLM, llama.cpp, LM Studio, and SGLang expose version-dependent Responses routes with varying event/snapshot completeness. Use `response_compatibility="openai-compatible"` only for the documented partial OpenAI-compatible JSON shape:

```python
client = OpenResponses(
    base_url="http://127.0.0.1:11434/v1",
    response_compatibility="openai-compatible",
)
```

Compatibility mode also relaxes known response snapshots embedded in standard SSE events, synthesizes missing provider sequence numbers and output indexes, accepts provider-specific unknown events, and accepts streams that terminate after `response.completed` without a `[DONE]` frame. Function-call argument events receive the same missing-output-index normalization. Response tool definitions without the optional `strict` field are normalized to `strict=False`. Strict mode still requires the pinned OpenResponses event fields, terminal event, and `[DONE]` framing. No automatic Chat Completions fallback occurs.

`/responses/compact` and WebSocket mode remain OpenResponses-specific capabilities. Unsupported endpoints fail explicitly.

## Current OpenAI Responses

The pinned OpenResponses contract remains the default. For the current OpenAI Responses API, select the explicit provider mode and use the current OpenAI request types:

```python
from openresponses import OpenAIRequest, OpenResponses

with OpenResponses(response_compatibility="openai") as client:
    response = client.responses.create(OpenAIRequest(
        model="gpt-5.5",
        input="Hello",
        conversation={"id": "conv_123"},
        text={"format": {"type": "text"}},
    ))
    print(response.output_text)
```

This mode preserves current OpenAI response fields and output-item/event extensions while keeping strict `response_compatibility="strict"` unchanged. It does not add a Chat Completions fallback.

## MLflow tracing

MLflow is optional. Install the extra with `pip install "openresponses-py[mlflow]"`, then wrap either client:

```python
from openresponses import OpenResponses
from openresponses.integrations import MLflowOpenResponses

with MLflowOpenResponses(OpenResponses()) as client:
    response = client.responses.create({"model": "gpt-5.5", "input": "Hello"})
```

The adapter traces synchronous, asynchronous, compact, and streaming response creation through MLflow's manual span API. It does not import MLflow unless used, and it does not replace the official `mlflow.openai.autolog()` integration for the official `openai` package.

## Remote verification

On the configured review host, Ollama, llama.cpp, and LM Studio passed synchronous JSON, asynchronous JSON, synchronous SSE, asynchronous SSE, and function-tool calls through the current consumer project. Ollama and LM Studio also passed explicit `response_compatibility="openai"` mode. llama.cpp and Ollama Responses streams omit `sequence_number` and some event indexes; compatibility mode handles those provider-specific omissions. vLLM and SGLang could not be started in this run because the shared RTX 3080 was already occupied and the available memory was below their requested startup budget; no unrelated provider process was stopped.

The live consumer project also exercised current `response_compatibility="openai"` mode against Ollama and LM Studio. Both providers completed JSON, async JSON, SSE, async SSE, and function-tool requests with the current OpenAI response/event models. The compatibility-only fixes do not alter strict mode or current OpenAI mode.
