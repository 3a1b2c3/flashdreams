#!/bin/bash
# Run LingBot WebRTC server
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if [ ! -d ".venv" ]; then
    echo "ERROR: venv not found. Run: bash setup.sh"
    exit 1
fi

source .venv/bin/activate

HOSTNAME=$(hostname)
IP_ADDR=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")

echo ""
echo "=========================================="
echo "LingBot World v2 WebRTC Server"
echo "=========================================="
echo ""
echo "Camera controls:"
echo "  W/S = forward/back"
echo "  A/D = yaw"
echo "  Q/E = strafe"
echo "  I/K = pitch"
echo ""
echo "Access at:"
echo "  Local:  http://localhost:8089/request_session"
echo "  Remote: http://$IP_ADDR:8089/request_session"
echo ""
echo "=========================================="
echo ""

python -m flashdreams.lingbot.webrtc \
  lingbot-world-v2-14b-causal-fast \
  --host 0.0.0.0 --port 8089 \
  --scenario.example-idx 0
