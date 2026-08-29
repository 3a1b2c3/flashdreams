#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

source .venv/bin/activate

flashdreams-run lingbot-world-fast webrtc \
  --host=0.0.0.0 \
  --port=8089 \
  --device=cuda:0 \
  --example-idx=0 \
  --output.warmup-chunks=0

