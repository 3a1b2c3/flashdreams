#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "========== OmniDreams WebRTC Server (High Quality) =========="
echo "Directory: $SCRIPT_DIR"
echo "Starting WebRTC server..."
echo ""
echo "Settings:"
echo "  Resolution: 1920x1080"
echo "  Frame Rate: 30 fps"
echo "  Bitrate: 12 Mbps"
echo "  Post-Processing: RTX Super Resolution"
echo ""
echo "Access: http://10.74.11.118:8082/request_session"
echo ""

cd "$SCRIPT_DIR"
uv run --active python -m omnidreams.webrtc.server

echo ""
echo "========== Application Closed =========="

