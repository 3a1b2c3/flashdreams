#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "========== OmniDreams Interactive-Drive (Game Mode) =========="
echo "Directory: $SCRIPT_DIR"
echo "Starting with physics simulation and collisions..."
echo ""

uv run --python 3.12 --package flashdreams-omnidreams interactive-drive --game-mode --width 2560 --height 1440 --fps 60

echo ""
echo "========== Application Closed =========="
