#!/usr/bin/env bash
# Manually launched: nothing starts at login.
set -euo pipefail

if ! command -v uvx >/dev/null 2>&1; then
  echo "uvx is required. Install uv first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

export DATA_DIR="${PERISCOPE_WEBUI_DATA:-$HOME/.local/share/periscope/open-webui}"
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"

# All inference stays in Jan. We do NOT start Ollama or download models.
export ENABLE_OLLAMA_API=false
export ENABLE_OPENAI_API=true
export OPENAI_API_BASE_URL="${PERISCOPE_JAN_API:-http://127.0.0.1:1337/v1}"
export OPENAI_API_KEY="${PERISCOPE_JAN_KEY:-jan-local}"
export WEBUI_AUTH=true

HOST="${PERISCOPE_WEBUI_HOST:-127.0.0.1}"
PORT="${PERISCOPE_WEBUI_PORT:-3000}"

echo "Periscope browser UI: http://$HOST:$PORT"
echo "Jan models: $OPENAI_API_BASE_URL"
echo "Open WebUI data: $DATA_DIR"
echo "Stop with Ctrl+C. There is no startup service."
exec uvx --python 3.12 open-webui@latest serve --host "$HOST" --port "$PORT"
