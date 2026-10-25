#!/bin/sh
# docker compose with the GPU override added when the host can use it.
# Usage: scripts/compose.sh up -d   (any docker compose args pass through)
# NVIDIA: needs a working driver (nvidia-smi) AND the nvidia runtime in Docker
# (nvidia-container-toolkit). Otherwise Ollama runs on CPU.
set -eu
cd "$(dirname "$0")/.."
files="-f docker-compose.yml"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q nvidia; then
    files="$files -f docker-compose.gpu.yml"
    echo "GPU: NVIDIA ($(nvidia-smi --query-gpu=name --format=csv,noheader | head -1))" >&2
  else
    echo "GPU: NVIDIA found but Docker lacks the nvidia runtime; install nvidia-container-toolkit. Using CPU." >&2
  fi
else
  echo "GPU: none detected, Ollama uses CPU." >&2
fi
# shellcheck disable=SC2086
exec docker compose $files "$@"
