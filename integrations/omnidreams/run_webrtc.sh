#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "========== OmniDreams WebRTC Server =========="
echo "Directory: $SCRIPT_DIR"
echo "Starting WebRTC server..."
echo ""
echo "Access: http://127.0.0.1:8082/request_session"
echo "Remote: http://10.74.11.118:8082/request_session"
echo ""

uv run --python 3.12 --package flashdreams-omnidreams flashdreams-run omnidreams webrtc

echo ""
echo "========== Server Stopped =========="
