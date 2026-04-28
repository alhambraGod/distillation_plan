#!/usr/bin/env bash
# vLLM 推理服务启动脚本（单卡）。
# - OpenAI 兼容 API
# - 挂载 LoRA adapter
# - 监听 8000

set -euo pipefail

MODEL="${MODEL:-Qwen/Qwen2.5-7B-Instruct}"
ADAPTER="${ADAPTER:-/path/to/adapter}"
ADAPTER_NAME="${ADAPTER_NAME:-marketing}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
PORT="${PORT:-8000}"
GPU_MEM="${GPU_MEM:-0.90}"

# --enable-lora：开启 LoRA 支持
# --max-lora-rank：和训练时的 r 一致或更大
# --enforce-eager：关掉 CUDA Graph（adapter 热切换要用）
python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --served-model-name marketing \
  --enable-lora \
  --lora-modules "$ADAPTER_NAME=$ADAPTER" \
  --max-lora-rank 32 \
  --max-model-len "$MAX_MODEL_LEN" \
  --gpu-memory-utilization "$GPU_MEM" \
  --enforce-eager \
  --port "$PORT" \
  --host 0.0.0.0
