#!/bin/bash
# Run Cam2V LingBot and print connection instructions
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Get hostname/IP
HOSTNAME=$(hostname)
IP_ADDR=$(hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo "Cam2V LingBot + WebRTC Server"
echo "=========================================="
echo ""
echo "Starting server on port 8089..."
echo ""

# Default to example-data mode
CMD="uv run --no-sync flashdreams-run-v2 cam2v-lingbot --mode webrtc --host 0.0.0.0 --port 8089 -- --example-data"

# Print connection options BEFORE starting server
echo "=========================================="
echo "CONNECTION OPTIONS (Choose one)"
echo "=========================================="
echo ""
echo "LOCAL (same machine):"
echo "  → http://localhost:8089"
echo ""
echo "REMOTE (SSH tunnel from your local machine):"
echo "  → ssh -L 8089:localhost:8089 $HOSTNAME"
echo "  → Then open: http://localhost:8089"
echo ""
echo "DIRECT (if on same network):"
echo "  → http://$IP_ADDR:8089"
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
echo "Starting server..."
echo "=========================================="
echo ""

# Run server
eval "$CMD"
