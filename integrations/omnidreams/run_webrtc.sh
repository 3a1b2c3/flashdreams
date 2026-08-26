#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "========== OmniDreams Interactive-Drive (Game Mode + High Quality) =========="
echo "Directory: $SCRIPT_DIR"
echo "Starting with physics simulation and high-quality rendering..."
echo ""
echo "Settings:"
echo "  Game Mode: Enabled (physics, collisions, vehicle limits)"
echo "  Resolution: 2560x1440"
echo "  Frame Rate: 60 fps"
echo ""
echo "Command:"
echo "uv run --python 3.12 --package flashdreams-omnidreams interactive-drive"
echo "  --game-mode --width 2560 --height 1440 --fps 60"
echo ""

cd "$SCRIPT_DIR"
uv run --python 3.12 --package flashdreams-omnidreams python -m omnidreams.interactive_drive.cli \
  --game-mode --width 2560 --height 1440 --fps 60

echo ""
echo "========== Application Closed =========="

