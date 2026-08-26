# OmniDreams Setup Guide

Complete setup for OmniDreams with venv, model/scene downloads, and CUDA 13.2 compilation.

## Prerequisites

- Python 3.10-3.12 (3.11 recommended for Windows)
- CUDA 13.2 toolkit
- 250+ GB disk space for models/scenes (~200GB models + ~50GB scenes + caches)
- Hugging Face token with access to:
  - `nvidia/omni-dreams-models` (model repo)
  - `nvidia/omni-dreams-samples` (dataset repo)
  - `nvidia/omni-dreams-scenes` (dataset repo)

## Quick Start

### Windows (using Command Prompt)

```batch
cd C:\workspace\world\flashdream_public\integrations\omnidreams

REM Copy and edit .env file
copy .env.example .env
REM Now edit .env and add your HF_TOKEN

REM Run full setup: venv + dependencies + models + scenes + CUDA build
setup_and_download.bat

REM Or skip parts with flags:
setup_and_download.bat --skip-venv        # Skip venv setup
setup_and_download.bat --skip-download    # Skip model/scene downloads
setup_and_download.bat --skip-build       # Skip CUDA compilation
```

### Linux / WSL

```bash
cd /path/to/flashdream_public/integrations/omnidreams

# Copy and edit .env file
cp .env.example .env
# Now edit .env and add your HF_TOKEN

# Run full setup
bash setup_and_download.sh

# Or skip parts with flags:
bash setup_and_download.sh --skip-venv        # Skip venv setup
bash setup_and_download.sh --skip-download    # Skip model/scene downloads
bash setup_and_download.sh --skip-build       # Skip CUDA compilation
```

## What the Script Does

### Step 1: Virtual Environment
- Creates `.venv` in the omnidreams directory
- Activates it for all subsequent steps
- Skip with `--skip-venv` if you already have one set up

### Step 2: Dependency Sync
- Installs all required Python packages via `uv sync`
- Includes the `interactive-drive` extra for desktop demo support
- Non-skippable (required for all other steps)

### Step 3: Model & Scene Downloads
- Downloads 3 Hugging Face repositories:
  1. `nvidia/omni-dreams-models` (model checkpoints) - ~200GB
  2. `nvidia/omni-dreams-samples` (example data) - ~5GB
  3. `nvidia/omni-dreams-scenes` (scene datasets) - ~50GB
- Requires `HF_TOKEN` in environment or `.env` file
- Cached in `~/.cache/huggingface` (or `HF_HOME`)
- Resume-able if interrupted (uses `hf download` which supports resuming)
- Skip with `--skip-download` if already downloaded

### Step 4: CUDA Build (Step 3)
- Syncs thirdparty sources (CUTLASS, SageAttention, cuDNN-frontend)
- Compiles Ludus renderer CUDA extensions
- Builds OmniDreams single-view model extensions with CUDA 13.2
- Sets `TORCH_CUDA_ARCH_LIST=8.0 8.6 8.9 9.0 12.0a` for Blackwell/Hopper/Ampere
- May take 10-20 minutes
- Skip with `--skip-build` if extensions are already built

## Environment Variables

Create `.env` file with:

```bash
# Required: Hugging Face token
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Override default cache locations
HF_HOME=/custom/path/huggingface
FLASHDREAMS_CACHE_DIR=/custom/path/flashdreams

# Optional: CUDA compute capability (auto-detected by default)
TORCH_CUDA_ARCH_LIST=8.0 8.6 8.9 9.0 12.0a
```

Or set them in the terminal:
```bash
# Windows
set HF_TOKEN=...

# Linux/WSL
export HF_TOKEN=...
```

## Disk Space Requirements

| Component | Size | Notes |
|-----------|------|-------|
| Models (checkpoints) | ~200GB | `nvidia/omni-dreams-models` |
| Scenes (datasets) | ~50GB | `nvidia/omni-dreams-scenes` |
| Samples | ~5GB | `nvidia/omni-dreams-samples` |
| HF cache overhead | ~10GB | Metadata, symlinks, partial downloads |
| **Total** | **~265GB** | Adjust `HF_HOME` or use alternate drive if needed |

### Large Drive Setup

If your main drive doesn't have 265GB free:

```bash
# Windows
set HF_HOME=E:\.cache\huggingface
set FLASHDREAMS_CACHE_DIR=E:\.cache\flashdreams
setup_and_download.bat

# Linux/WSL
export HF_HOME=/mnt/e/.cache/huggingface
export FLASHDREAMS_CACHE_DIR=/mnt/e/.cache/flashdreams
bash setup_and_download.sh
```

## Running After Setup

### Desktop Demo (Linux/WSL only)
```bash
uv run --package flashdreams-omnidreams interactive-drive --auto-start --game-mode
```

### Batch Inference
```bash
uv run --python 3.12 --package flashdreams-omnidreams flashdreams-run \
  omnidreams mp4 \
  --scenario.example-data true \
  --output.path outputs/omnidreams.mp4
```

### WebRTC Server
```bash
uv run --python 3.12 --package flashdreams-omnidreams flashdreams-run \
  omnidreams webrtc \
  --host 0.0.0.0 --port 8089 \
  --device cuda:0
```

Then visit: http://localhost:8089/request_session

### gRPC Server
```bash
uv run --package flashdreams-omnidreams torchrun --nproc_per_node 1 \
  -m omnidreams.grpc.server \
  --pipeline_config_name omnidreams-sv-2steps-chunk2-loc6-lightvae-lighttae-perf \
  --host 0.0.0.0 --port 50051
```

## Troubleshooting

### Issue: "HF_TOKEN not found"
**Solution:** Create `.env` file in the omnidreams directory with `HF_TOKEN=...`

### Issue: "uv not found"
**Solution:** Install uv with `pip install uv`

### Issue: "CUDA out of memory" during build
**Solution:** Close other GPU applications or reduce `TORCH_CUDA_ARCH_LIST` to specific architectures

### Issue: Build hangs or crashes
**Solution:** Check for stale compiler cache files:
```bash
# Windows
del /s "%USERPROFILE%\.triton\*"
del /s "%USERPROFILE%\.cache\ludus-renderer\*"

# Linux/WSL
rm -rf ~/.triton/*
rm -rf ~/.cache/ludus-renderer/*
```

### Issue: Downloads slow or interrupted
**Solution:** Re-run `setup_and_download.bat/sh` — it will resume from where it left off.

## Full Cleanup

To completely remove setup (if needed):

```bash
# Windows
rmdir /s /q .venv                    # Remove venv
rmdir /s /q omnidreams_singleview    # Remove built extensions
del *.egg-info                       # Remove build artifacts

# Linux/WSL
rm -rf .venv
rm -rf omnidreams_singleview
rm -rf *.egg-info
```

## See Also

- [Parent README.md](README.md) - Full OmniDreams documentation
- [Interactive Drive README](omnidreams/interactive_drive/README.md) - Desktop demo controls
- [Evaluation Guide](README.md#run-batch-evaluation) - Batch evaluation with metrics
