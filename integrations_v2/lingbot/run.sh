#!/bin/bash
# Launch the LingBot v2 Cam2V WebRTC demo from the venv setup.sh created.
#
# Uses the v2 CLI (`flashdreams-run-v2 <application-slug>`); the old
# `run_direct.py` / `python -m lingbot.runner` entry points no longer exist
# -- the v1 runner and its RUNNER_CONFIGS were removed in the v2 refactor.
#
#   bash run.sh                                              # default app
#   APP=cam2v-lingbot-world-fast-taehv-window15-sink3 bash run.sh   # low VRAM
#   PORT=8090 bash run.sh
#
# Application slugs (see pyproject.toml entry points):
#   cam2v-lingbot
#   cam2v-lingbot-world-fast
#   cam2v-lingbot-world-fast-taehv-window15-sink3
#   cam2v-lingbot-world-v2-14b-causal-fast
#   cam2v-lingbot-world-v2-14b-causal-fast-taehv-window15-sink3
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"
APP="${APP:-cam2v-lingbot}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8089}"

if [ ! -d "$VENV" ]; then
  echo "ERROR: $VENV not found -- run 'bash setup.sh' first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# The GPU is shared; show what's already resident before claiming memory.
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "--- GPU state ---"
  nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv
  echo
fi

echo "Starting $APP on $HOST:$PORT ..."
echo "Open http://localhost:$PORT once the model reports ready."
echo
exec flashdreams-run-v2 "$APP" --mode webrtc --host "$HOST" --port "$PORT" -- --example-data
