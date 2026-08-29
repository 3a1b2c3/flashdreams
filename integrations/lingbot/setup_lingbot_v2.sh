#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLASHDREAMS_ROOT="$HERE/../.."

echo "=========================================="
echo "LingBot WebRTC - Complete Working Setup"
echo "=========================================="
echo ""

# Step 1: Clean everything
echo "[1/7] Cleaning old setup..."
cd "$HERE"
rm -rf .venv
find "$FLASHDREAMS_ROOT" -type d -name __pycache__ -delete 2>/dev/null || true
find "$FLASHDREAMS_ROOT" -type d -name "*.egg-info" -delete 2>/dev/null || true

# Step 2: Create venv with Python
echo "[2/7] Creating Python venv..."
python -m venv .venv
source .venv/bin/activate

# Step 3: Upgrade pip
echo "[3/7] Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Step 4: Install torch with CUDA 13.2 (all matching)
echo "[4/7] Installing PyTorch with CUDA 13.2..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu132 --force-reinstall

# Step 5: Install all dependencies
echo "[5/7] Installing dependencies..."
pip install "transformers>=5.0,<6" sentencepiece scipy opencv-python
pip install aiohttp aiortc python-multipart loguru
pip install tyro pydantic fastapi uvicorn pillow numpy gradio websockets
pip install flash-attn==2.6.3 --no-build-isolation 2>/dev/null || pip install flash-attn==2.6.3 --only-binary :all: 2>/dev/null || true

# Step 6: Clear caches
echo "[6/6] Clearing caches..."
find "$HERE" -type d -name __pycache__ -delete 2>/dev/null || true
cd "$HERE"

echo ""
echo "=========================================="
echo "✓✓✓ SETUP COMPLETE ✓✓✓"
echo "=========================================="
echo ""
echo "To run WebRTC server:"
echo "  cd $HERE"
echo "  bash run.sh"
echo ""
