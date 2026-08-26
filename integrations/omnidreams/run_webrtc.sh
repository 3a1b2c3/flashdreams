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
uv run --active --python 3.12 --package flashdreams-omnidreams flashdreams-run omnidreams webrtc \
  --video-width 1920 --video-height 1080 --fps 30 \
  --encoder_bitrate_bps 12000000 --postprocess-preset flashvsr-v1.1-sparse-2.0

echo ""
echo "========== Application Closed =========="

