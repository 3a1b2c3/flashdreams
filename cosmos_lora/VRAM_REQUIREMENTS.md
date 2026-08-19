# Cosmos-Predict2.5-2B LoRA Fine-Tuning: VRAM Feasibility

## Reference requirement (NVIDIA's published guide)

Source: [Fine-Tuning NVIDIA Cosmos Predict 2.5 with LoRA/DoRA for Robot Video Generation](https://huggingface.co/blog/nvidia/cosmos-fine-tuning-for-robot-video-generation)

- **Minimum: one 80 GB GPU** for single-GPU training (8× H100 recommended for faster iteration)
- Config used: `accelerate launch`, batch size 1, resolution 432×768
- 100 epochs: ~17 hours on 1× H100 80GB, ~2.5 hours on 8× H100
- Base 2B-param model stays frozen; LoRA adapters (~50M params, rank=32) are the only trainable weights, injected into attention + feedforward layers

The 80GB figure is dominated by **activation memory** from video-frame batches at that resolution, not model or optimizer weights — the frozen base model itself is only a few GB in bf16, and optimizer state only needs to cover the ~50M LoRA params.

## GPU comparison

| GPU | VRAM | Architecture | Fit vs. 80GB reference |
|---|---|---|---|
| RTX 5090 (this machine) | 32 GB | Blackwell (sm_120) | Large gap — needs gradient checkpointing + reduced resolution/frames; unverified whether their training script supports those knobs out of the box |
| A100 | 40 GB | Ampere | Meaningful gap — gradient checkpointing likely closes it without resolution compromise |
| A40 | 48 GB | Ampere | Smallest gap of the three — most headroom; gradient checkpointing alone should be enough to match their reference 432×768/batch-1 config, no resolution/frame-count reduction expected to be necessary |

All three meet the repo's minimum "Ampere or newer" GPU requirement (`docs/setup.md`).

## Bottom line

- **RTX 5090 (32GB, this machine):** feasible only with real workarounds (bf16 + gradient checkpointing + CPU offload + possibly reduced resolution/frame count); not officially supported at this VRAM tier, may still OOM.
- **A40 (48GB):** best of the three options if available — closest to NVIDIA's tested 80GB config, gradient checkpointing should be sufficient on its own, low risk of needing to touch resolution/batch settings from their reference script.
- **A100 40GB:** workable, slightly more headroom needed than A40 but same approach (gradient checkpointing) should work.

## Open questions before committing to a GPU target

1. Does `cosmos-predict2.5`'s training script (`scripts/train.py` / `accelerate launch` path) expose a gradient-checkpointing flag, or does it need a code change?
2. Is a smaller LoRA rank (e.g. 16 instead of 32) an acceptable tradeoff if headroom is still tight on 48GB?
3. Confirm actual peak VRAM empirically once a GPU is available — the 80GB figure is NVIDIA's own default-config number, not a hard floor.
