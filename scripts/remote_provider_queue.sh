#!/usr/bin/env bash
set -uo pipefail
WORK=$(cd "$(dirname "$0")" && pwd)
LOCK=/tmp/jevper-gpu.lock
export PATH="$HOME/.local/bin:$HOME/.lmstudio/bin:$PATH"

wait_idle() {
  local limit=${1:-3600} waited=0 used busy
  while [ "$waited" -lt "$limit" ]; do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)
    busy=$(pgrep -fa "vllm serve|sglang.launch_server|llama-server|ollama run" 2>/dev/null | grep -v "run-queued" | wc -l)
    [ "${used:-0}" -lt 1000 ] && [ "$busy" -eq 0 ] && return 0
    sleep 30; waited=$((waited + 30))
  done
  return 1
}

run_probe() {
  "$WORK/venv/bin/python" "$WORK/provider_review.py" --base-url "$1" --model "$2"
}

run_llamacpp() {
  local port=18081 model=qwen3.5-9b
  local bin="$HOME/llama.cpp/build/bin/llama-server" file="$HOME/models/gguf/Qwen_Qwen3.5-9B-Q4_K_M.gguf"
  "$bin" -m "$file" --alias "$model" --host 127.0.0.1 --port "$port" -ngl 99 --ctx-size 4096 -np 1 --jinja --reasoning-format deepseek >"$WORK/llamacpp.log" 2>&1 & SRV=$!
  for _ in $(seq 1 300); do curl -fsS -m 3 "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1 && break; sleep 1; done
  run_probe "http://127.0.0.1:$port/v1" "$model" || true
  kill "$SRV" 2>/dev/null || true; wait "$SRV" 2>/dev/null || true; SRV=
}

run_vllm() {
  local port=18082 model=qwen3.5-9b
  "$HOME/vllm-env/bin/vllm" serve "$HOME/models/Qwen3.5-9B-AWQ-4bit" --served-model-name "$model" --host 127.0.0.1 --port "$port" --max-model-len 4096 --gpu-memory-utilization 0.85 --max-num-seqs 1 >"$WORK/vllm.log" 2>&1 & SRV=$!
  for _ in $(seq 1 600); do curl -fsS -m 3 "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1 && break; sleep 1; done
  run_probe "http://127.0.0.1:$port/v1" "$model" || true
  kill "$SRV" 2>/dev/null || true; wait "$SRV" 2>/dev/null || true; SRV=
  if ! curl -fsS -m 3 "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
    kill "$SRV" 2>/dev/null || true; wait "$SRV" 2>/dev/null || true
    "$HOME/vllm-env/bin/vllm" serve "$HOME/models/Qwen3.5-9B-AWQ-4bit" --served-model-name "$model" --host 127.0.0.1 --port "$port" --max-model-len 2048 --gpu-memory-utilization 0.95 --max-num-seqs 1 --enforce-eager >"$WORK/vllm.log" 2>&1 & SRV=$!
    for _ in $(seq 1 600); do curl -fsS -m 3 "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1 && break; sleep 1; done
    run_probe "http://127.0.0.1:$port/v1" "$model" || true
  fi
}

run_sglang() {
  local port=18083 model=qwen3.5-9b
  export CUDA_HOME="$HOME/sglang-env/lib/python3.12/site-packages/nvidia/cu13" CUDA_PATH="$HOME/sglang-env/lib/python3.12/site-packages/nvidia/cu13"
  local gxx="$HOME/toolchain/gxx/bin"
  export CC="$gxx/x86_64-conda-linux-gnu-gcc" CXX="$gxx/x86_64-conda-linux-gnu-g++" NVCC_PREPEND_FLAGS="-ccbin $gxx/x86_64-conda-linux-gnu-g++"
  export CPATH="$HOME/.local/share/uv/python/cpython-3.12.14-linux-x86_64-gnu/include/python3.12"
  export PATH="$CUDA_HOME/bin:$gxx:$HOME/bin:$HOME/sglang-env/bin:$PATH" LD_LIBRARY_PATH="$HOME/toolchain/gxx/lib:$CUDA_HOME/lib:${LD_LIBRARY_PATH:-}" TRITON_CACHE_DIR="$HOME/.cache/triton-sglang-conda"
  "$HOME/sglang-env/bin/python" -m sglang.launch_server --model-path "$HOME/models/Qwen3.5-9B-AWQ-4bit" --served-model-name "$model" --host 127.0.0.1 --port "$port" --tp-size 1 --mem-fraction-static 0.85 --context-length 4096 --max-running-requests 1 --max-mamba-cache-size 8 --reasoning-parser qwen3 --disable-cuda-graph --attention-backend triton --sampling-backend pytorch >"$WORK/sglang.log" 2>&1 & SRV=$!
  for _ in $(seq 1 750); do curl -fsS -m 3 "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1 && break; sleep 1; done
  run_probe "http://127.0.0.1:$port/v1" "$model" || true
  kill "$SRV" 2>/dev/null || true; wait "$SRV" 2>/dev/null || true; SRV=
}

run_ollama() {
  local port=18084 model=qwen3.5:9b
  OLLAMA_HOST="127.0.0.1:$port" OLLAMA_CONTEXT_LENGTH=4096 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_KEEP_ALIVE=5m ollama serve >"$WORK/ollama.log" 2>&1 & SRV=$!
  for _ in $(seq 1 90); do curl -fsS -m 3 "http://127.0.0.1:$port/api/version" >/dev/null 2>&1 && break; sleep 1; done
  run_probe "http://127.0.0.1:$port/v1" "$model" || true
  kill "$SRV" 2>/dev/null || true; wait "$SRV" 2>/dev/null || true; SRV=
}

run_lmstudio() {
  run_probe http://127.0.0.1:1234/v1 qwen3-4b-instruct-2507 || true
}

for provider in llamacpp vllm sglang ollama lmstudio; do
  echo "QUEUE_START $provider $(date -Is)"
  wait_idle 3600 || { echo "QUEUE_SKIP $provider idle-timeout"; continue; }
  "run_$provider"
  echo "QUEUE_END $provider $(date -Is)"
done
