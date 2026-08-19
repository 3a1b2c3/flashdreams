#!/usr/bin/env bash
# Runs LoRA video2world post-training for the cosmos_lora sample dataset
# (predict2_lora_training_2b_cosmos_lora_sample, see cosmos-predict2.5/cosmos_predict2/
# experiments/base/cosmos_lora_sample.py). Run from anywhere -- cd's into the repo itself.
#
# Requires: HF_TOKEN set (checkpoint auto-downloads on first run), the repo's own
# .venv activated (or run via its python directly), and enough GPU VRAM (tested
# against a single 40-50GB GPU, e.g. A40, via block_wise activation checkpointing).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$HERE/../cosmos-predict2.5"

if [ -z "${HF_TOKEN:-}" ]; then
    echo "ERROR: HF_TOKEN is not set." >&2
    exit 1
fi

cd "$REPO_DIR"

torchrun --nproc_per_node=1 scripts/train.py \
    --config=cosmos_predict2/_src/predict2/configs/video2world/config.py -- \
    experiment=predict2_lora_training_2b_cosmos_lora_sample
