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
#   LIGHT=1 bash run.sh                                      # lighter stream
#   WIDTH=640 HEIGHT=352 FPS=10 bash run.sh                  # explicit sizing
#
# LIGHT=1 lowers the generated frame size and rate (512x288 @ 12fps by
# default; override with WIDTH/HEIGHT/FPS). There is no encoder choice to
# make here: the v2 WebRTC server hands raw frames straight to aiortc, which
# encodes in software (VP8 unless the browser negotiates H.264). The NVENC
# hardware encoder only exists in the v1 serving stack
# (flashdreams/serving/webrtc/nvenc.py), which v2 does not use -- so the only
# way to cut encode cost today is to give the encoder fewer pixels and fewer
# frames, which is what these knobs do.
#
# Note this changes what the *model generates*, not just what gets encoded:
# smaller frames are cheaper end to end but also lower quality. Keep width
# and height multiples of 16 (the model's default is 832x464 @ 16fps).
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
WIDTH="${WIDTH:-}"
HEIGHT="${HEIGHT:-}"
FPS="${FPS:-}"

# LIGHT=1 only supplies defaults, so an explicit WIDTH/HEIGHT/FPS still wins.
if [ "${LIGHT:-0}" = "1" ]; then
  WIDTH="${WIDTH:-512}"
  HEIGHT="${HEIGHT:-288}"
  FPS="${FPS:-12}"
fi

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

# Runtime args go before the `--`; everything after it belongs to the app.
RUNTIME_ARGS=(--mode webrtc --host "$HOST" --port "$PORT")
if [ -n "$WIDTH" ]; then
  RUNTIME_ARGS+=(--pixel-width "$WIDTH")
fi
if [ -n "$HEIGHT" ]; then
  RUNTIME_ARGS+=(--pixel-height "$HEIGHT")
fi
if [ -n "$FPS" ]; then
  RUNTIME_ARGS+=(--fps "$FPS")
fi

echo "Starting $APP on $HOST:$PORT ..."
if [ -n "$WIDTH$HEIGHT$FPS" ]; then
  echo "Stream: ${WIDTH:-default}x${HEIGHT:-default} @ ${FPS:-default}fps"
fi
echo "Open http://localhost:$PORT once the model reports ready."
echo
exec flashdreams-run-v2 "$APP" "${RUNTIME_ARGS[@]}" -- --example-data
