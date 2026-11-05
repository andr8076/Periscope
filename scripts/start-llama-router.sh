#!/usr/bin/env bash
# Run from a terminal. Close the terminal / Ctrl+C to stop llama.cpp.
# Never creates/enables a systemd service.
set -euo pipefail

if ! command -v llama-server >/dev/null 2>&1; then
  echo "llama-server is not installed. Install a GPU-enabled llama.cpp build." >&2
  exit 1
fi

SELF_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="${PERISCOPE_MODEL_DIR:-$HOME/.local/share/periscope/model-links}"
PORT="${PERISCOPE_LLAMA_PORT:-18090}"
CTX="${PERISCOPE_CTX_SIZE:-8192}"

python3 "$SELF_DIR/refresh-model-links.py" --catalog "$MODEL_DIR"

if curl -fsS --max-time 1 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "Port $PORT already has a responding model server; not starting a duplicate." >&2
  exit 1
fi

echo ""
echo "Periscope llama.cpp model router"
echo "Model catalogue: $MODEL_DIR (symlinks only)"
echo "Open WebUI endpoint: http://127.0.0.1:$PORT/v1"
echo "One model loaded at a time; context size: $CTX"
echo "Stop with Ctrl+C. No boot/login service is installed."
echo ""

# Do not expose the unauthenticated model API on LAN or internet.
exec llama-server --models-dir "$MODEL_DIR" \
  --host 127.0.0.1 --port "$PORT" \
  --models-max 1 \
  --ctx-size "$CTX" --parallel 1 \
  --n-gpu-layers 99 --fit on
