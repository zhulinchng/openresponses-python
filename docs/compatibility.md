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

Compatibility mode also relaxes known response snapshots embedded in standard SSE events, synthesizes missing provider sequence numbers and output indexes, accepts provider-specific unknown events, and accepts streams that terminate after `response.completed` without a `[DONE]` frame. Strict mode still requires the pinned OpenResponses event fields, terminal event, and `[DONE]` framing. No automatic Chat Completions fallback occurs.

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

On the configured review host, llama.cpp and LM Studio JSON/SSE both passed in `openai-compatible` mode. Ollama JSON/SSE passed for the installed local model. llama.cpp's provider stream required compatibility normalization for missing event sequence numbers, response model, and output indexes; those normalizations are not applied in strict mode. vLLM could not start because the shared RTX 3080 had insufficient free GPU memory at the requested utilization, and SGLang startup failed because the remote environment lacked `CUDA_HOME` for its DeepEP import. No provider process was force-killed or reconfigured during those failed startup attempts.
