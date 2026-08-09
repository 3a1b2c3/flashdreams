# Guidance self-distillation (Tier-2a) — see PLAN.md

Bake the two-prompt text-edit guidance (s=3) into a LoRA so a plain mid-stream prompt swap edits like a guided one. Run from the repo root, in order:

1. `N_CLIPS=10 .venv/bin/python integrations/omnidreams/guidance_distill/precompute_embeddings.py` — encode bank + clip prompts and first frames once (~10 min incl. the 14 GB text-encoder load; set `SAMPLE_UUIDS` to skip the HF listing API).
2. `STEPS=800 .venv/bin/python integrations/omnidreams/guidance_distill/train_guidance.py` — on-policy trainer; ~30 GB VRAM eager, roughly 20-40 s/step on the shared GB300 (~5-9 h at 800 steps). Checkpoints (LoRA A/B only, no resume) land in `outputs/lora_guidance_stepN.pt` every 100 steps.
3. `LORA=integrations/omnidreams/guidance_distill/outputs/lora_guidance_step800.pt .venv/bin/python integrations/omnidreams/guidance_distill/eval_guidance.py` — held-out kill gate (~1 h for 2 clips x 6 prompts); PASS = LoRA plain-swap >= 80% of guided divergence over the guided window (`outputs/eval/report.json`, `SAVE_VIDEOS=1` for MP4s).

Knobs: `STEPS`, `LR` (2e-4), `GUIDE_SCALE` (3.0), `SEED` (trainer); `N_CLIPS` / `HOLDOUT` (10 / 2, shared clip split); `LORA`, `N_CHUNKS`, `SWAP_AT`, `GUIDE_CHUNKS`, `LORA_CHUNKS`, `EVAL_PROMPTS` (eval).
