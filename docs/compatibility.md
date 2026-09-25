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

Compatibility mode also relaxes known response snapshots embedded in standard SSE events and accepts provider streams that terminate after `response.completed` without a `[DONE]` frame. Strict mode still requires the pinned OpenResponses terminal plus `[DONE]` framing. No automatic Chat Completions fallback occurs.

`/responses/compact` and WebSocket mode remain OpenResponses-specific capabilities. Unsupported endpoints fail explicitly.

## Remote verification

On the configured review host, llama.cpp JSON and SSE both passed in `openai-compatible` mode. LM Studio JSON and SSE both passed in `openai-compatible` mode, including a provider stream without `[DONE]`. vLLM did not start because its KV cache had no available blocks on the shared RTX 3080; it was stopped without modifying unrelated workloads. The remaining Ollama/SGLang matrix entries were queued behind the shared GPU lock and were not force-started while another tenant was active.
