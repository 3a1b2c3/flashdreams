# LingBot-World v2 Setup Guide

Complete setup for LingBot-World v2 streaming I2V model with pre-downloaded checkpoint and example data.

## Prerequisites

- Python 3.10-3.12 (3.11 recommended for Windows)
- CUDA-capable GPU (tested on RTX 6000 Pro Blackwell, works on RTX 5090)
- 220+ GB disk space for checkpoint + HF cache
- Hugging Face token with access to:
  - `robbyant/lingbot-world-v2-14b-causal-fast` (checkpoint)

## Quick Start

### Windows (using Command Prompt)

```batch
cd C:\workspace\world\flashdream_public\integrations\lingbot

REM Copy and edit .env file
copy .env.example .env
REM Now edit .env and add your HF_TOKEN

REM Run full setup: venv + dependencies + checkpoint
setup_lingbot_v2.bat

REM Or skip parts with flags:
setup_lingbot_v2.bat --skip-venv        # Skip venv setup
setup_lingbot_v2.bat --skip-download    # Skip checkpoint download
```

### Linux / WSL

```bash
cd /path/to/flashdream_public/integrations/lingbot

# Copy and edit .env file
cp .env.example .env
# Now edit .env and add your HF_TOKEN

# Run full setup
bash setup_lingbot_v2.sh

# Or skip parts with flags:
bash setup_lingbot_v2.sh --skip-venv        # Skip venv setup
bash setup_lingbot_v2.sh --skip-download    # Skip checkpoint download
```

## What the Script Does

### Step 1: Virtual Environment
- Creates `.venv` in the lingbot directory
- Activates it for all subsequent steps
- Skip with `--skip-venv` if you already have one set up

### Step 2: Dependency Sync
- Installs all required Python packages via `uv sync`
- Includes flashdreams framework and WebRTC dependencies
- Non-skippable (required for all other steps)

### Step 3: Checkpoint & Example Data Download
- Downloads `robbyant/lingbot-world-v2-14b-causal-fast` checkpoint (~200GB)
- Optionally downloads example data from GitHub mirror (~300MB)
- Requires `HF_TOKEN` in environment or `.env` file
- Cached in `~/.cache/huggingface` (or `HF_HOME`)
- Resume-able if interrupted
- Skip with `--skip-download` if already downloaded

## Environment Variables

Create `.env` file with:

```bash
# Required: Hugging Face token
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Override default cache locations
HF_HOME=/custom/path/huggingface
FLASHDREAMS_CACHE_DIR=/custom/path/flashdreams
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
| LingBot v2 checkpoint | ~200GB | `robbyant/lingbot-world-v2-14b-causal-fast` |
| HF cache overhead | ~10GB | Metadata, symlinks |
| Example data | ~300MB | Optional, downloaded on first run if missing |
| **Total** | **~210GB** | Adjust `HF_HOME` if needed |

### Large Drive Setup

If your main drive doesn't have 210GB free:

```bash
# Windows
set HF_HOME=E:\.cache\huggingface
set FLASHDREAMS_CACHE_DIR=E:\.cache\flashdreams
setup_lingbot_v2.bat

# Linux/WSL
export HF_HOME=/mnt/e/.cache/huggingface
export FLASHDREAMS_CACHE_DIR=/mnt/e/.cache/flashdreams
bash setup_lingbot_v2.sh
```

## Running After Setup

### Batch Inference (MP4 export)

Generate video from example data:
```bash
uv run --python 3.12 --package flashdreams-lingbot flashdreams-run \
  lingbot-world-v2-14b-causal-fast mp4 \
  --scenario.example-idx 0 \
  --scenario.total-blocks 10 \
  --output.fps 16 \
  --output.path outputs/lingbot-v2-demo.mp4
```

With custom inputs:
```bash
uv run --python 3.12 --package flashdreams-lingbot flashdreams-run \
  lingbot-world-v2-14b-causal-fast mp4 \
  --image-path first_frame.jpg \
  --pose-path poses.npy \
  --intrinsic-path intrinsics.npy \
  --prompt "A cinematic flythrough" \
  --total-blocks 10 \
  --output.path outputs/lingbot-v2-custom.mp4
```

Available example indices: `0` through `5`

### WebRTC Streaming Server

Start interactive server:
```bash
uv run --python 3.12 --package flashdreams-lingbot flashdreams-run \
  lingbot-world-v2-14b-causal-fast webrtc \
  --host 0.0.0.0 --port 8089 \
  --device cuda:0 \
  --scenario.example-idx 0
```

Then visit: http://localhost:8089/request_session

### Multi-GPU (Context Parallel)

Use 4 GPUs for context parallelism:
```bash
uv run --python 3.12 --package flashdreams-lingbot \
  torchrun --standalone --nnodes=1 --nproc_per_node=4 --no-python \
  flashdreams-run lingbot-world-v2-14b-causal-fast webrtc \
  --host 0.0.0.0 --port 8089
```

### Performance Variant (LightTAE)

Use LightTAE decoder for lower-latency streaming:
```bash
uv run --python 3.12 --package flashdreams-lingbot flashdreams-run \
  lingbot-world-v2-14b-causal-fast-taehv-window15-sink3 webrtc \
  --host 0.0.0.0 --port 8089 \
  --scenario.example-idx 0
```

## Input Format

For custom inputs, provide:

1. **first_frame.jpg** - Initial RGB image (any resolution)
2. **poses.npy** - Camera poses, shape `[T, 4, 4]` (camera-to-world matrices)
3. **intrinsics.npy** - Camera intrinsics, shape `[T, 4]` as `(fx, fy, cx, cy)`
4. **prompt.txt** (optional) - Text guidance for style/content

## DataChannel Message Format (WebRTC)

Browser -> server:
```json
{
  "type": "action",
  "action": {
    "event": "keydown",
    "key": "w"
  }
}
```

Supported keys:
- `w/s`: forward/backward
- `a/d` or `j/l`: yaw left/right
- `q/e`: strafe left/right
- `i/k`: pitch up/down

## Troubleshooting

### Issue: "HF_TOKEN not found"
**Solution:** Create `.env` file in the lingbot directory with `HF_TOKEN=...`

### Issue: "uv not found"
**Solution:** Install uv with `pip install uv`

### Issue: "CUDA out of memory"
**Solution:** The v2 model requires ~100GB VRAM on a single GPU. Use multi-GPU setup or reduce resolution.

### Issue: Downloads slow or interrupted
**Solution:** Re-run the script — it will resume from where it left off.

### Issue: Examples don't download
**Solution:** Example data auto-downloads on first run if missing. No action needed.

## Full Cleanup

To completely remove setup (if needed):

```bash
# Windows
rmdir /s /q .venv                    # Remove venv

# Linux/WSL
rm -rf .venv
```

Checkpoint is cached in `~/.cache/huggingface` and can be safely deleted if needed.

## Programmatic Access

Access v2 pipeline directly in Python:

```python
import torch
from lingbot.config import RUNNER_LINGBOT_WORLD_V2_14B_CAUSAL_FAST as runner_config
from flashdreams.infra.config import derive_config

cfg = derive_config(
    runner_config,
    prompt="A cinematic flythrough",
    example_data=True,
    example_idx=0,
    total_blocks=21
)
runner = cfg.setup()
runner.run()
```

## See Also

- [Parent README.md](README.md) - Full LingBot documentation
- [WebRTC API docs](README.md#run-compatibility-webrtc-server) - Server message format
- [Example data format](README.md#runtime-requirements) - Input specifications
