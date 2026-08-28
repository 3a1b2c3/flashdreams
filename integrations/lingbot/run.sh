#!/bin/bash
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if [ ! -d ".venv" ]; then
    echo "ERROR: venv not found. Run: bash setup_lingbot_v2.sh"
    exit 1
fi

source .venv/bin/activate
export PYTHONPATH="/localhome/kschmid/flashdreams:/localhome/kschmid/flashdreams/apps:/localhome/kschmid/flashdreams/integrations:$PYTHONPATH"

IP_ADDR=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")

echo ""
echo "=========================================="
echo "LingBot WebRTC Server"
echo "=========================================="
echo ""
echo "Access at: http://$IP_ADDR:8089/request_session"
echo ""
echo "Camera: W/A/S/D = movement, I/K = pitch"
echo ""
echo "=========================================="
echo ""

python -c "from lingbot.demo.app import main; import sys; sys.argv = ['lingbot', 'webrtc', '--host', '0.0.0.0', '--port', '8089', '--example-idx', '0']; main()"
