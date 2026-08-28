#!/usr/bin/env bash
# Setup script for LingBot-World v2: venv, dependencies, checkpoint
# Usage: bash setup_lingbot_v2.sh [--skip-venv] [--skip-download]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo ""
echo "========== LingBot World v2 Setup =========="
echo "Script dir: $SCRIPT_DIR"
echo "Repo root: $REPO_ROOT"
echo ""

# Parse arguments
SKIP_VENV=0
SKIP_DOWNLOAD=0

for arg in "$@"; do
  case "$arg" in
    --skip-venv) SKIP_VENV=1 ;;
    --skip-download) SKIP_DOWNLOAD=1 ;;
  esac
done

# Step 1: Create venv if needed
if [ $SKIP_VENV -eq 0 ]; then
  echo "[1/3] Setting up virtual environment..."
  if [ -d ".venv" ]; then
    echo "Virtual environment already exists"
  else
    echo "Creating new venv..."
    python3 -m venv .venv
  fi
  source .venv/bin/activate
  echo "Virtual environment activated"
else
  echo "[1/3] Skipping venv setup"
fi

echo ""
echo "[2/3] Installing/syncing dependencies..."

# Install dependencies with pip
echo "Installing dependencies..."
pip install --upgrade pip setuptools wheel

# Install torch for CUDA 13.2 first
echo "Installing torch for CUDA 13.2..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu132

# Install other dependencies
pip install -r "$REPO_ROOT/requirements.txt" 2>/dev/null || echo "Note: requirements.txt not found, skipping"
pip install -e "$REPO_ROOT" 2>/dev/null || echo "Note: editable install not available"
echo "Dependencies installed successfully"
echo ""

# Step 2: Download checkpoint and example data
if [ $SKIP_DOWNLOAD -eq 0 ]; then
  echo "[3/3] Downloading LingBot v2 checkpoint and example data..."

  # Check HF_TOKEN
  if [ -z "${HF_TOKEN:-}" ]; then
    if [ -f ".env" ]; then
      export $(grep -E "^HF_TOKEN=" .env | xargs)
    fi
  fi

  if [ -z "${HF_TOKEN:-}" ]; then
    echo "ERROR: HF_TOKEN not set in environment or .env file"
    echo "       Create .env file or set: export HF_TOKEN=..."
    exit 1
  fi

  echo "HF_TOKEN is set (length: ${#HF_TOKEN})"
  echo ""

  # Download v2 checkpoint
  echo "Downloading robbyant/lingbot-world-v2-14b-causal-fast checkpoint..."
  python << 'PYEOF'
from huggingface_hub import snapshot_download
try:
    snapshot_download("robbyant/lingbot-world-v2-14b-causal-fast", repo_type="model")
    print("Checkpoint downloaded successfully (~200GB)")
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
PYEOF
  echo ""

  # Download example data
  echo "Downloading example data..."
  python << 'PYEOF'
from huggingface_hub import snapshot_download
try:
    snapshot_download("robbyant/lingbot-world-v2-examples", repo_type="dataset")
    print("Example data downloaded successfully")
except Exception as e:
    print(f"WARNING: Failed to download example data: {e}")
    print("         Examples will download on first run instead")
PYEOF
  echo ""

else
  echo "[3/3] Skipping checkpoint/example download"
fi

echo ""
echo "========== Setup Complete =========="
echo ""
echo "Next steps:"
echo "1. Test inference with example data:"
echo "   python -m flashdreams.lingbot.run \\"
echo "     lingbot-world-v2-14b-causal-fast mp4 \\"
echo "     --scenario.example-idx 0 \\"
echo "     --scenario.total-blocks 10 \\"
echo "     --output.path outputs/lingbot-v2-demo.mp4"
echo ""
echo "2. Or stream with WebRTC:"
echo "   python -m flashdreams.lingbot.webrtc \\"
echo "     lingbot-world-v2-14b-causal-fast \\"
echo "     --host 0.0.0.0 --port 8089 \\"
echo "     --scenario.example-idx 0"
echo ""
echo "3. Then open: http://localhost:8089/request_session"
echo ""
