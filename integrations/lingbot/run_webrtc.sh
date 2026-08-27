#!/bin/bash
# Run LingBot World v2 WebRTC server with interactive camera controls
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Get hostname/IP
HOSTNAME=$(hostname)
IP_ADDR=$(hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo "LingBot World v2 + WebRTC Interactive"
echo "=========================================="
echo ""

# Parse arguments
EXAMPLE_IDX="${1:-0}"
HOST="${2:-0.0.0.0}"
PORT="${3:-8089}"

echo "=========================================="
echo "CONNECTION OPTIONS (Choose one)"
echo "=========================================="
echo ""
echo "LOCAL (same machine):"
echo "  → http://localhost:$PORT"
echo ""
echo "REMOTE (SSH tunnel from your local machine):"
echo "  → ssh -L $PORT:localhost:$PORT $HOSTNAME"
echo "  → Then open: http://localhost:$PORT"
echo ""
echo "DIRECT (if on same network):"
echo "  → http://$IP_ADDR:$PORT"
echo ""
echo "=========================================="
echo "CAMERA CONTROLS"
echo "=========================================="
echo ""
echo "  W/S = move forward/back"
echo "  A/D = yaw left/right"
echo "  Q/E = strafe left/right"
echo "  I/K = pitch up/down"
echo ""
echo "=========================================="
echo "Starting WebRTC server..."
echo "=========================================="
echo ""

# Run server
uv run flashdreams-run lingbot-world-v2-14b-causal-fast \
  --host "$HOST" --port "$PORT" \
  -- --example-idx "$EXAMPLE_IDX"
