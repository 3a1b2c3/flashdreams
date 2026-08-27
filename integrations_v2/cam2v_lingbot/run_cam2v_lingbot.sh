#!/bin/bash
# Run cam2v_lingbot with example data
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "=========================================="
echo "Running cam2v_lingbot (LingBot World v2)"
echo "=========================================="
echo ""

# Check python
if ! command -v python &>/dev/null; then
    echo "ERROR: Python not found"
    exit 1
fi

# Install package
echo "[1/2] Installing cam2v_lingbot..."
pip install -e .

# Run app
echo "[2/2] Starting WebRTC server..."
echo ""
flashdreams-run-v2 cam2v-lingbot --mode webrtc --host 0.0.0.0 --port 8089 -- --example-data

echo ""
echo "=========================================="
echo "Camera Controls:"
echo "  W/S = move forward/back"
echo "  A/D = yaw left/right"
echo "  Q/E = strafe left/right"
echo "  I/K = pitch up/down"
echo "=========================================="
