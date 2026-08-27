#!/bin/bash
# Run cam2v_lingbot with example data
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "=========================================="
echo "Running cam2v_lingbot (LingBot World v2)"
echo "=========================================="
echo ""

# Check uv
if ! command -v uv &>/dev/null; then
    echo "ERROR: uv not found. Install with: pip install uv"
    exit 1
fi

# Sync workspace
echo "[1/2] Syncing dependencies..."
uv sync --package flashdreams-cam2v-lingbot --inexact

# Run app
echo "[2/2] Starting WebRTC server..."
echo ""
uv run --no-sync flashdreams-run-v2 cam2v-lingbot \
    --mode webrtc --host 0.0.0.0 --port 8089 -- --example-data

echo ""
echo "=========================================="
echo "Camera Controls:"
echo "  W/S = move forward/back"
echo "  A/D = yaw left/right"
echo "  Q/E = strafe left/right"
echo "  I/K = pitch up/down"
echo "=========================================="
