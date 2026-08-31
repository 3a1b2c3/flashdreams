#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

source .venv/bin/activate

# Lighter-memory variant: window_size_t=15 (down from 63) + sink_size_t=3 +
# LightTAE decoder, for GPUs that OOM on the default lingbot-world-fast
# KV cache size.
python run_direct.py \
  --runner=lingbot-world-fast-taehv-window15-sink3 \
  --host=0.0.0.0 \
  --port=8089 \
  --device=cuda:0 \
  --example-idx=0 \
  --warmup-chunks=1
