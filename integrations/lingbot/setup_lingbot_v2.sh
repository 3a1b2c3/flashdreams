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

# Find uv
if command -v uv &> /dev/null; then
  UV_EXE="uv"
else
  echo "ERROR: uv not found. Install with: pip install uv"
  exit 1
fi

# Sync dependencies with uv
$UV_EXE sync --package flashdreams-lingbot
echo "Dependencies synced successfully"
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
  $UV_EXE run --from huggingface_hub hf download robbyant/lingbot-world-v2-14b-causal-fast --repo-type model
  echo "Checkpoint downloaded successfully (~200GB)"
  echo ""

  # Download example data from GitHub
  echo "Downloading example data from GitHub..."
  if $UV_EXE run --from huggingface_hub hf download --repo-type dataset robbyant/lingbot-world-v2-examples; then
    echo "Example data downloaded successfully"
  else
    echo "WARNING: Failed to download example data from HF mirror"
    echo "         Examples will download on first run instead"
  fi
  echo ""

else
  echo "[3/3] Skipping checkpoint/example download"
fi

echo ""
echo "========== Setup Complete =========="
echo ""
echo "Next steps:"
echo "1. Test inference with example data:"
echo "   uv run --python 3.12 --package flashdreams-lingbot flashdreams-run \\"
echo "     lingbot-world-v2-14b-causal-fast mp4 \\"
echo "     --scenario.example-idx 0 \\"
echo "     --scenario.total-blocks 10 \\"
echo "     --output.path outputs/lingbot-v2-demo.mp4"
echo ""
echo "2. Or stream with WebRTC:"
echo "   uv run --python 3.12 --package flashdreams-lingbot flashdreams-run \\"
echo "     lingbot-world-v2-14b-causal-fast webrtc \\"
echo "     --host 0.0.0.0 --port 8089 \\"
echo "     --scenario.example-idx 0"
echo ""
echo "3. Then open: http://localhost:8089/request_session"
echo ""
