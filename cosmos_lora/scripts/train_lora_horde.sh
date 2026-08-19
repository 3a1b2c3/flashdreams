#!/bin/bash
# Train the cosmos_lora 2B video2world LoRA ON HORDE.
#
# Prereqs on horde:
#   - cosmos-predict2.5 repo at $REPO_DIR (below), its venv usable as `python`
#   - dataset synced by sync_dataset_to_horde.bat -> $DATASET_DIR (has videos/ + metas/)
#   - HF_TOKEN exported (for the base 2B checkpoint download)
#   - a CUDA GPU (A40 48GB is plenty for a 2B LoRA)
#
# Usage:
#   export HF_TOKEN=hf_xxx
#   bash train_lora_horde.sh                 # train on videos/ in $DATASET_DIR
#   bash train_lora_horde.sh stylized        # train on the DECART-stylized clips instead
set -euo pipefail

# ---- config (edit these paths to match horde) ----------------------------
REPO_DIR="$HOME/flashdream_public/cosmos_lora/cosmos-predict2.5"
DATASET_DIR="$HOME/flashdream_public/cosmos_lora/datasets"   # synced dir: has videos/ + videos_stylized/ + metas/
EXPERIMENT="predict2_lora_training_2b_cosmos_lora_sample"
# --------------------------------------------------------------------------

if [ -z "${HF_TOKEN:-}" ]; then
    echo "WARN: HF_TOKEN not set -- fine if the base 2B checkpoint is already downloaded;" >&2
    echo "      it's only needed to FETCH the checkpoint from HuggingFace the first time." >&2
fi
[ -d "$REPO_DIR" ] || { echo "ERROR: repo not found: $REPO_DIR" >&2; exit 1; }
[ -d "$DATASET_DIR" ] || { echo "ERROR: dataset not found: $DATASET_DIR (run sync_dataset_to_horde.bat)" >&2; exit 1; }

# Optional 1st arg "stylized": build a videos/ made of the DECART-stylized clips so
# the LoRA learns the stylized look. VideoDataset reads <dataset_dir>/videos + /metas,
# so we assemble a sibling dataset dir whose videos/ are the stylized mp4s and copy the
# matching metas across (stylized files are named decart_<...>_<clip>.mp4).
TRAIN_DIR="$DATASET_DIR"
if [ "${1:-}" = "stylized" ]; then
    TRAIN_DIR="$DATASET_DIR/../datasets_stylized"
    mkdir -p "$TRAIN_DIR/videos" "$TRAIN_DIR/metas"
    for f in "$DATASET_DIR"/videos_stylized/*.mp4; do
        [ -e "$f" ] || { echo "ERROR: no stylized clips in $DATASET_DIR/videos_stylized" >&2; exit 1; }
        base="$(basename "$f")"
        # decart_<folder>_<clip>.mp4 -> recover <clip> to find its caption
        clip="${base#decart_*_}"; clip="${clip%.mp4}"
        ln -sf "$f" "$TRAIN_DIR/videos/$base"
        [ -f "$DATASET_DIR/metas/$clip.txt" ] && cp -f "$DATASET_DIR/metas/$clip.txt" "$TRAIN_DIR/metas/${base%.mp4}.txt"
    done
    echo "Prepared stylized training set: $TRAIN_DIR (videos=$(ls "$TRAIN_DIR/videos" | wc -l), metas=$(ls "$TRAIN_DIR/metas" | wc -l))"
fi

# The experiment hardcodes a Windows dataset_dir -- repoint it at the Linux path.
EXP_FILE="$REPO_DIR/cosmos_predict2/experiments/base/cosmos_lora_sample.py"
[ -f "$EXP_FILE" ] || { echo "ERROR: experiment file not found: $EXP_FILE" >&2; exit 1; }
sed -i "s#dataset_dir=\"[^\"]*\"#dataset_dir=\"$TRAIN_DIR\"#" "$EXP_FILE"
echo "dataset_dir set to: $TRAIN_DIR"

cd "$REPO_DIR"
# cosmos_oss / cosmos_predict2 are uv-workspace packages that aren't pip-installed on
# horde -- put them on PYTHONPATH so `from cosmos_oss...` resolves.
export PYTHONPATH="$REPO_DIR:$REPO_DIR/packages/cosmos-oss:${PYTHONPATH:-}"
echo "Starting LoRA training (experiment=$EXPERIMENT) ..."
torchrun --nproc_per_node=1 scripts/train.py \
    --config=cosmos_predict2/_src/predict2/configs/video2world/config.py -- \
    experiment="$EXPERIMENT"
