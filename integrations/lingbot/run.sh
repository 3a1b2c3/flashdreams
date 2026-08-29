#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(cd "$HERE/../.." && pwd)"

# Run WebRTC server
uv run flashdreams-run \
  lingbot-world-v2-14b-causal-fast-taehv-window15-sink3 webrtc \
  --host 0.0.0.0 \
  --port 8089 \
  --device cuda:0 \
  --scenario.example-idx 0 \
  --output.warmup-chunks 8 \
  --output.fps 16 \
  --output.video-height 352 \
  --output.video-width 640

