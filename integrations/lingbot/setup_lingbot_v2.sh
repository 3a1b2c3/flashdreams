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

# Step 2: Create venv with Python 3.11
echo "[2/6] Creating Python 3.11 venv..."
/c/Users/kschmid/.local/bin/python3.11 -m venv .venv
source .venv/bin/activate

# Step 3: Upgrade pip
echo "[3/6] Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Step 4: Install torch with CUDA 13.2 (all matching)
echo "[4/6] Installing PyTorch with CUDA 13.2..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu132

# Step 5: Install flashdreams and all dependencies
echo "[5/6] Installing flashdreams..."
cd "$FLASHDREAMS_ROOT"
pip install transformers==4.56.0 sentencepiece scipy
pip install -e .
pip install -e apps/cam2v
pip install -e integrations/lingbot

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
echo "  bash run.sh"
echo ""
echo "Server will be available at:"
echo "  http://localhost:8089"
echo ""
