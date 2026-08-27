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

# Parse arguments
IMAGE_PATH="${1:-../../integrations/omnidreams/omnidreams/interactive_drive/screenshot.jpg}"
WORLD_SCALE="${2:-1000}"

# Convert Windows paths to WSL paths if needed
if [[ "$IMAGE_PATH" == C:\\* ]]; then
    IMAGE_PATH="${IMAGE_PATH//C:\\workspace/\/workspace}"
    IMAGE_PATH="${IMAGE_PATH//\\/\/}"
fi

# Check if image exists
if [ ! -f "$IMAGE_PATH" ]; then
    echo "ERROR: Image not found: $IMAGE_PATH"
    echo "Usage: bash run_and_connect.sh [image] [world_scale]"
    exit 1
fi

# Build command (args after -- go to the app)
CMD="uv run --no-sync flashdreams-run-v2 cam2v-lingbot --mode webrtc --host 0.0.0.0 --port 8089 -- --image-path $IMAGE_PATH --world-scale $WORLD_SCALE"

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
