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
HOST="${1:-0.0.0.0}"
PORT="${2:-8089}"
EXAMPLE_IDX="${3:-0}"

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

# Run server using lingbot.demo CLI
python -m lingbot.demo webrtc \
  --host "$HOST" --port "$PORT" \
  --example-idx "$EXAMPLE_IDX"
