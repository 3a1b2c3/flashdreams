#!/bin/bash
# Final working setup - handles everything
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLASHDREAMS_ROOT="$HERE/../.."

echo "=========================================="
echo "LingBot WebRTC - Complete Working Setup"
echo "=========================================="
echo ""

# Step 1: Clean everything
echo "[1/6] Cleaning old setup..."
cd "$HERE"
rm -rf .venv
find "$FLASHDREAMS_ROOT" -type d -name __pycache__ -delete 2>/dev/null || true
find "$FLASHDREAMS_ROOT" -type d -name "*.egg-info" -delete 2>/dev/null || true

# Step 2: Create venv with Python
echo "[2/6] Creating Python venv..."
python -m venv .venv
source .venv/bin/activate

# Step 3: Upgrade pip
echo "[3/6] Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Step 4: Install torch with CUDA 13.2 (all matching)
echo "[4/6] Installing PyTorch with CUDA 13.2..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu132

# Step 5: Install all dependencies
echo "[5/6] Installing dependencies..."
pip install transformers==4.40.0 sentencepiece scipy opencv-python
pip install aiohttp aiortc python-multipart loguru
pip install flash-attn==2.6.3 --no-build-isolation 2>/dev/null || pip install flash-attn==2.6.3 --only-binary :all: 2>/dev/null || true

# Step 6: Clear caches
echo "[6/6] Clearing caches..."
find "$FLASHDREAMS_ROOT" -type d -name __pycache__ -delete 2>/dev/null || true
cd "$HERE"

echo ""
echo "=========================================="
echo "✓✓✓ SETUP COMPLETE ✓✓✓"
echo "=========================================="
echo ""
echo "To run WebRTC server:"
echo "  cd $HERE"
echo "  source .venv/bin/activate"
echo "  export PYTHONPATH=\"/localhome/kschmid/flashdreams:/localhome/kschmid/flashdreams/apps:/localhome/kschmid/flashdreams/integrations:\$PYTHONPATH\""
echo "  python -c \"from lingbot.demo.app import main; import sys; sys.argv = ['lingbot', 'webrtc', '--preset-id', 'lingbot-world-v2-14b-causal-fast', '--example-idx', '0']; main()\""
echo ""
echo "Server will be available at:"
echo "  http://10.74.11.118:8089/request_session"
echo ""
