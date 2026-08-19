#!/bin/bash
# Pre-fetch the base 2B video2world checkpoint the cosmos_lora LoRA trains on top of.
# Lands in the HF cache as models--nvidia--Cosmos-Predict2.5-2B, which is exactly where
# checkpoint_db looks -- so after this, train_lora_horde.sh won't stall on a download
# (and HF_TOKEN is no longer needed at train time).
#
# Usage:
#   export HF_TOKEN=hf_xxx        # needed to fetch from HuggingFace the first time
#   bash /home/horde/flashdream_public/cosmos_lora/scripts/download_lora_base.sh
#   bash /home/horde/flashdream_public/cosmos_lora/scripts/download_lora_base.sh full   # whole repo, not just the base .pt
set -euo pipefail

REPO="nvidia/Cosmos-Predict2.5-2B"
BASE_FILE="base/pre-trained/d20b7120-df3e-4911-919d-db6e08bad31c_ema_bf16.pt"

if [ -z "${HF_TOKEN:-}" ]; then
    echo "ERROR: export HF_TOKEN first (this repo is gated on HuggingFace)." >&2
    exit 1
fi

# pip may drop the CLI in ~/.local/bin without putting it on PATH
export PATH="$HOME/.local/bin:$PATH"
# hub >=1.0 renamed the CLI to `hf` (huggingface-cli is a deprecated alias);
# the old `python -m huggingface_hub.commands...` module was removed.
if command -v hf >/dev/null 2>&1; then
    DL="hf"
elif command -v huggingface-cli >/dev/null 2>&1; then
    DL="huggingface-cli"
else
    echo "ERROR: neither 'hf' nor 'huggingface-cli' found. Run: pip install --user huggingface_hub" >&2
    exit 1
fi

if [ "${1:-}" = "full" ]; then
    echo "Downloading FULL repo $REPO into the HF cache ..."
    $DL download "$REPO"
else
    echo "Downloading base checkpoint only:"
    echo "  $REPO :: $BASE_FILE"
    $DL download "$REPO" "$BASE_FILE"
fi

echo ""
echo "Done. Cached under: ${HF_HOME:-$HOME/.cache/huggingface}/hub/models--nvidia--Cosmos-Predict2.5-2B"
