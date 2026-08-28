#!/bin/bash
# Setup lingbot WebRTC server with all dependencies
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "=========================================="
echo "LingBot WebRTC - Complete Setup"
echo "=========================================="
echo ""

# Step 1: Create venv
echo "[1/3] Creating Python 3.11 venv..."
if [ -d ".venv" ]; then
    rm -rf .venv
fi
python3.11 -m venv .venv
source .venv/bin/activate

# Step 2: Install dependencies
echo "[2/3] Installing dependencies..."
pip install --upgrade pip setuptools wheel

# Install torch first
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# Install main flashdreams with all deps
cd ../../
pip install -e .
cd integrations/lingbot

# Step 3: Install lingbot-specific
echo "[3/3] Installing lingbot packages..."
pip install huggingface_hub

echo ""
echo "=========================================="
echo "✓ Setup Complete!"
echo "=========================================="
echo ""
echo "Run server:"
echo "  bash run.sh"
echo ""
echo "Or manually:"
echo "  source .venv/bin/activate"
echo "  python -m flashdreams.lingbot.webrtc lingbot-world-v2-14b-causal-fast --host 0.0.0.0 --port 8089 --scenario.example-idx 0"
echo ""
