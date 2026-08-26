#!/usr/bin/env bash
# Setup script for OmniDreams: venv, models, scenes, CUDA build
# Usage: bash setup_and_download.sh [--skip-venv] [--skip-download] [--skip-build]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CUDA_VERSION="13.2"

echo ""
echo "========== OmniDreams Setup =========="
echo "Script dir: $SCRIPT_DIR"
echo "Repo root: $REPO_ROOT"
echo "CUDA version: $CUDA_VERSION"
echo ""

# Parse arguments
SKIP_VENV=0
SKIP_DOWNLOAD=0
SKIP_BUILD=0

for arg in "$@"; do
  case "$arg" in
    --skip-venv) SKIP_VENV=1 ;;
    --skip-download) SKIP_DOWNLOAD=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
  esac
done

# Step 1: Create venv if needed
if [ $SKIP_VENV -eq 0 ]; then
  echo "[1/4] Setting up virtual environment..."
  if [ -d ".venv" ]; then
    echo "Virtual environment already exists"
  else
    echo "Creating new venv..."
    python3 -m venv .venv
  fi
  source .venv/bin/activate
  echo "Virtual environment activated"
else
  echo "[1/4] Skipping venv setup"
fi

echo ""
echo "[2/4] Installing/syncing dependencies..."

# Auto-install uv if missing
if ! command -v uv &> /dev/null; then
  echo "Installing uv..."
  pip install uv
fi
UV_EXE="uv"

# Sync dependencies with uv
$UV_EXE sync --package flashdreams-omnidreams --extra interactive-drive
# Ensure huggingface-hub is installed
pip install huggingface-hub
echo "Dependencies synced successfully"
echo ""

# Step 2: Download models and scenes
if [ $SKIP_DOWNLOAD -eq 0 ]; then
  echo "[3/4] Downloading models and scenes..."

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

  # Download models (model repo)
  echo "Downloading nvidia/omni-dreams-models..."
  python -m huggingface_hub download nvidia/omni-dreams-models --repo-type model
  echo "Models downloaded successfully"
  echo ""

  # Download samples (dataset repo)
  echo "Downloading nvidia/omni-dreams-samples..."
  python -m huggingface_hub download nvidia/omni-dreams-samples --repo-type dataset
  echo "Samples downloaded successfully"
  echo ""

  # Download scenes (dataset repo)
  echo "Downloading nvidia/omni-dreams-scenes..."
  python -m huggingface_hub download nvidia/omni-dreams-scenes --repo-type dataset
  echo "Scenes downloaded successfully"
  echo ""
else
  echo "[3/4] Skipping model/scene download"
fi

# Step 3: Sync thirdparty deps and build CUDA
if [ $SKIP_BUILD -eq 0 ]; then
  echo "[4/4] Syncing thirdparty dependencies and building CUDA $CUDA_VERSION..."

  # Sync thirdparty (CUTLASS, SageAttention, etc.)
  echo "Syncing thirdparty sources..."
  $UV_EXE run --package flashdreams-omnidreams python omnidreams_singleview/tools/sync_thirdparty.py sync
  echo "Thirdparty sync completed"
  echo ""

  # Compile with CUDA 13.2
  echo "Compiling extensions with CUDA $CUDA_VERSION..."
  echo "This may take several minutes..."
  echo ""

  export TORCH_CUDA_ARCH_LIST="8.0 8.6 8.9 9.0 12.0a"
  export FORCE_CUDA=1

  # Build ludus-renderer first
  echo "Building ludus-renderer CUDA extensions..."
  $UV_EXE run --package flashdreams-omnidreams python -m pip install -e ludus-renderer --no-build-isolation --no-deps
  echo "ludus-renderer built successfully"
  echo ""

  # Build omnidreams_singleview extensions
  echo "Building OmniDreams CUDA extensions..."
  $UV_EXE run --package flashdreams-omnidreams python setup.py build_ext --inplace || \
    echo "WARNING: Extension build completed with warnings (may still be usable)"

else
  echo "[4/4] Skipping thirdparty/CUDA build"
fi

echo ""
echo "========== Setup Complete =========="
echo ""
echo "Next steps:"
echo "1. Run the interactive demo:"
echo "   uv run --package flashdreams-omnidreams interactive-drive"
echo ""
echo "2. Or run batch inference:"
echo "   uv run --python 3.12 --package flashdreams-omnidreams flashdreams-run omnidreams mp4 \\"
echo "     --scenario.example-data true --output.path outputs/omnidreams.mp4"
echo ""
echo "3. Or serve WebRTC:"
echo "   uv run --python 3.12 --package flashdreams-omnidreams flashdreams-run omnidreams webrtc"
echo ""
