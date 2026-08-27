#!/bin/bash
# Setup and run cam2v_lingbot with all dependencies
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "=========================================="
echo "Setup: cam2v_lingbot (LingBot World v2)"
echo "=========================================="
echo ""

# Create venv
echo "[1/5] Creating venv..."
if [ -d ".venv" ]; then
    echo "  Using existing venv"
else
    python3.12 -m venv .venv
fi
source .venv/bin/activate

# Install base packages in order
echo "[2/5] Installing flashdreams..."
pip install --upgrade pip setuptools wheel
pip install -e flashdreams/

echo "[3/5] Installing flashdreams-cam2v..."
pip install -e apps/cam2v/

echo "[4/5] Installing flashdreams-lingbot..."
pip install -e integrations/lingbot/

echo "[5/5] Installing flashdreams-cam2v-lingbot..."
pip install -e integrations_v2/cam2v_lingbot/

echo ""
echo "=========================================="
echo "Starting WebRTC server..."
echo "=========================================="
echo ""

flashdreams-run-v2 cam2v-lingbot --mode webrtc --host 0.0.0.0 --port 8089 -- --example-data

echo ""
echo "=========================================="
echo "Camera Controls:"
echo "  W/S = move forward/back"
echo "  A/D = yaw left/right"
echo "  Q/E = strafe left/right"
echo "  I/K = pitch up/down"
echo "=========================================="
