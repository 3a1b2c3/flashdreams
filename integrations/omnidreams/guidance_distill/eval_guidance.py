# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Held-out eval / kill gate for the guidance-distillation LoRA.

For each held-out clip x bank prompt, three RNG-matched rollouts are scored
against one shared no-edit control (the ``sweep_text_edit.py`` protocol,
re-plumbed for precomputed embeddings so the 14 GB text encoder stays
unloaded):

- ``guided``:     base weights + guided swap (s = ``GUIDE_SCALE``,
  ``GUIDE_CHUNKS`` chunks) — the teacher's ceiling.
- ``lora_plain``: LoRA + plain swap, LoRA gated to the ``LORA_CHUNKS``
  chunks after the swap (the deployment gating, ``PLAN.md``).
- ``base_plain``: base weights + plain swap — the floor.

Per-chunk divergence-vs-control curves (mean |diff| x 127.5 on decoded
frames) are reported per combo; the pass bar (``PLAN.md``) is
``lora_plain`` reaching >= 80% of the ``guided`` divergence over the
guided window: ``ratio = sum(gap_lora) / sum(gap_guided) >= 0.8``,
averaged across combos.

Run from the flashdreams repo root (after training)::

    LORA=integrations/omnidreams/guidance_distill/outputs/lora_guidance_step800.pt \
        .venv/bin/python integrations/omnidreams/guidance_distill/eval_guidance.py

``LORA`` defaults to the newest ``lora_guidance_step*.pt``. ``SAVE_VIDEOS=1``
also writes per-arm MP4s for eyeballing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drift_correction"))

import torch
from _host import build_pipeline
from _lora import apply_lora, load_lora, set_lora_scale, unwrap_compiled
from build_pairs import _sample_files
from einops import rearrange
from omnidreams.pipeline import OmnidreamsPipeline
from omnidreams.runner import (
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
    _load_video,
    _write_video,
)
from prompts import EDIT_PROMPTS, clip_key
from torch import Tensor
from train_guidance import LORA_TARGETS, RANK

## Eval configuration

BASE = Path("integrations/omnidreams/guidance_distill")
EMB_DIR = BASE / "outputs"
OUT_DIR = Path(os.environ.get("OUT_DIR", str(BASE / "outputs" / "eval")))

LORA = os.environ.get("LORA", "")
"""Checkpoint path; empty resolves to the newest ``lora_guidance_step*.pt``."""

N_CHUNKS = int(os.environ.get("N_CHUNKS", "28"))
SWAP_AT = int(os.environ.get("SWAP_AT", "8"))
GUIDE_CHUNKS = int(os.environ.get("GUIDE_CHUNKS", "6"))
GUIDE_SCALE = float(os.environ.get("GUIDE_SCALE", "3.0"))
LORA_CHUNKS = int(os.environ.get("LORA_CHUNKS", str(GUIDE_CHUNKS)))
"""Post-swap chunks with the LoRA enabled (deployment gate width)."""

SEED = int(os.environ.get("SEED", "42"))
HOLDOUT = int(os.environ.get("HOLDOUT", "2"))
"""Held-out clips (last of the precomputed index; must match training)."""

EVAL_PROMPTS = [s for s in os.environ.get("EVAL_PROMPTS", "").split(",") if s] or [
    p.name for p in EDIT_PROMPTS
]
"""Bank prompt names to evaluate (default: the whole bank)."""

SAVE_VIDEOS = os.environ.get("SAVE_VIDEOS", "0") == "1"
PASS_BAR = 0.8


def _resolve_lora() -> Path:
    """Return the checkpoint path (``LORA`` env or the newest step file)."""
    if LORA:
        return Path(LORA)
    ckpts = sorted(
        EMB_DIR.glob("lora_guidance_step*.pt"),
        key=lambda p: int(p.stem.rsplit("step", 1)[-1]),
    )
    assert ckpts, f"no lora_guidance_step*.pt under {EMB_DIR}; set LORA=<path>"
    return ckpts[-1]


@torch.no_grad()
def _rollout(
    pipe: OmnidreamsPipeline,
    network,
    *,
    hdmap: Tensor,
    text_embeddings: Tensor,
    image_embeddings: Tensor,
    edit: tuple[Tensor, float, int] | None,
    lora_chunks: range | None,
    seed: int,
) -> Tensor:
    """One RNG-matched rollout -> decoded video ``[T, 3, H, W]`` on CPU.

    Minimal copy of ``sweep_text_edit._rollout``: the sweep's helper closes
    over its module env constants and encodes prompts with the resident
    text encoder, while this host runs from precomputed embeddings.

    Args:
        pipe: Eager pipeline (encoders not loaded).
        network: Unwrapped, LoRA-wrapped DiT (for the per-chunk gate).
        hdmap: ``[T, 3, H, W]`` conditioning pixels on CPU.
        text_embeddings: ``[1, 1, L, D]`` base-prompt embeddings.
        image_embeddings: ``[1, 1, 1, Cl, Hl, Wl]`` first-frame latent.
        edit: ``(embeddings, guidance_scale, guidance_chunks)`` applied at
            :data:`SWAP_AT`, or ``None`` for the control.
        lora_chunks: Chunks rolled at LoRA scale 1 (all others at 0), or
            ``None`` for pure base weights.
        seed: Diffusion-model RNG seed; arms sharing it are RNG-matched
            (guidance and the LoRA gate draw no extra noise).
    """
    device = pipe.device
    pipe.diffusion_model._rng = torch.Generator(device=device).manual_seed(seed)
    cache = pipe.initialize_cache_from_embeddings(
        text_embeddings=text_embeddings, image_embeddings=image_embeddings
    )
    chunks: list[Tensor] = []
    start = 0
    for ar_idx in range(N_CHUNKS):
        set_lora_scale(
            network, 1.0 if lora_chunks is not None and ar_idx in lora_chunks else 0.0
        )
        if edit is not None and ar_idx == SWAP_AT:
            emb, scale, guide_chunks = edit
            pipe.replace_text_from_embeddings(
                cache, emb, guidance_scale=scale, guidance_chunks=guide_chunks
            )
        num_frames = pipe.get_num_frames(ar_idx)
        chunk = pipe.generate(
            ar_idx,
            cache,
            hdmap=hdmap[start : start + num_frames][None, None].to(device),
        )
        pipe.finalize(ar_idx, cache)
        chunks.append(chunk[0, 0].float().cpu())
        start += num_frames
    set_lora_scale(network, 0.0)
    del cache
    torch.cuda.empty_cache()
    return torch.cat(chunks, dim=0)


def _per_chunk_gap(a: Tensor, b: Tensor) -> list[float]:
    """Per-chunk mean |a - b| x 127.5 (``sweep_text_edit`` metric)."""
    gaps, start = [], 0
    for ar_idx in range(N_CHUNKS):
        n = 5 if ar_idx == 0 else 8
        gaps.append(
            float((a[start : start + n] - b[start : start + n]).abs().mean() * 127.5)
        )
        start += n
    return gaps


def _window_ratio(gaps_num: list[float], gaps_den: list[float]) -> float:
    """Divergence ratio over the guided window ``[SWAP_AT, SWAP_AT + GUIDE_CHUNKS)``."""
    lo, hi = SWAP_AT, min(SWAP_AT + GUIDE_CHUNKS, N_CHUNKS)
    return sum(gaps_num[lo:hi]) / (sum(gaps_den[lo:hi]) + 1e-9)


def main() -> None:
    """Run the held-out grid and print the pass/fail verdict."""
    torch.set_grad_enabled(False)
    lora_path = _resolve_lora()

    prompt_emb = torch.load(
        EMB_DIR / "prompt_embeddings.pt", map_location="cpu", weights_only=False
    )
    assets = torch.load(
        EMB_DIR / "clip_assets.pt", map_location="cpu", weights_only=False
    )
    uuids: list[str] = assets["uuids"][-HOLDOUT:]
    missing = [n for n in EVAL_PROMPTS if n not in prompt_emb]
    assert not missing, f"prompts {missing} not in prompt_embeddings.pt"

    # Load HDMaps BEFORE any model work (ffmpeg fork hazard; build_pairs note).
    total_frames = 5 + (N_CHUNKS - 1) * 8
    hdmaps: dict[str, Tensor] = {}
    for uuid in uuids:
        (hdmap_path,), _ = _sample_files(uuid)
        hdmaps[uuid] = _load_video(
            hdmap_path,
            pixel_height=DEFAULT_VIDEO_HEIGHT,
            pixel_width=DEFAULT_VIDEO_WIDTH,
            device="cpu",
            dtype=torch.bfloat16,
        )[:total_frames]
        assert hdmaps[uuid].shape[0] >= total_frames, (
            f"clip {uuid}: {hdmaps[uuid].shape[0]} HDMap frames < {total_frames}"
        )

    pipe = build_pipeline(with_oneshot_encoders=False)
    assert pipe.V_group is None, "single-GPU eval; run without CP"
    network = unwrap_compiled(pipe.diffusion_model.transformer.network)
    apply_lora(network, rank=RANK, targets=LORA_TARGETS)
    load_lora(network, lora_path)
    set_lora_scale(network, 0.0)
    print(
        f"LoRA {lora_path} | {len(uuids)} held-out clips x {len(EVAL_PROMPTS)} "
        f"prompts | swap@{SWAP_AT} guided s={GUIDE_SCALE}x{GUIDE_CHUNKS} "
        f"LoRA gate {LORA_CHUNKS} chunks",
        flush=True,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lora_window = range(SWAP_AT, SWAP_AT + LORA_CHUNKS)
    report: dict[str, dict] = {}
    ratios_lora: list[float] = []
    ratios_base: list[float] = []
    for c, uuid in enumerate(uuids):
        common = dict(
            hdmap=hdmaps[uuid],
            text_embeddings=prompt_emb[clip_key(uuid)],
            image_embeddings=assets["image_embeddings"][uuid],
            seed=SEED + c,
        )
        print(f"clip {uuid}: control ...", flush=True)
        control = _rollout(pipe, network, edit=None, lora_chunks=None, **common)
        if SAVE_VIDEOS:
            _write_video(
                rearrange(control, "t c h w -> t h w c"),
                OUT_DIR / f"{uuid[:8]}_control.mp4",
                fps=30,
            )
        for name in EVAL_PROMPTS:
            arms = {
                "guided": _rollout(
                    pipe,
                    network,
                    edit=(prompt_emb[name], GUIDE_SCALE, GUIDE_CHUNKS),
                    lora_chunks=None,
                    **common,
                ),
                "lora_plain": _rollout(
                    pipe,
                    network,
                    edit=(prompt_emb[name], 1.0, 0),
                    lora_chunks=lora_window,
                    **common,
                ),
                "base_plain": _rollout(
                    pipe,
                    network,
                    edit=(prompt_emb[name], 1.0, 0),
                    lora_chunks=None,
                    **common,
                ),
            }
            gaps = {arm: _per_chunk_gap(video, control) for arm, video in arms.items()}
            if SAVE_VIDEOS:
                for arm, video in arms.items():
                    _write_video(
                        rearrange(video, "t c h w -> t h w c"),
                        OUT_DIR / f"{uuid[:8]}_{name}_{arm}.mp4",
                        fps=30,
                    )
            r_lora = _window_ratio(gaps["lora_plain"], gaps["guided"])
            r_base = _window_ratio(gaps["base_plain"], gaps["guided"])
            ratios_lora.append(r_lora)
            ratios_base.append(r_base)
            report[f"{uuid[:8]}/{name}"] = {
                "ratio_lora_vs_guided": r_lora,
                "ratio_base_vs_guided": r_base,
                "pre_swap_max_gap": {arm: max(g[:SWAP_AT]) for arm, g in gaps.items()},
                "post_swap_gaps": {arm: g[SWAP_AT:] for arm, g in gaps.items()},
            }
            print(
                f"{uuid[:8]}/{name:>12}: lora/guided {r_lora:5.3f} "
                f"base/guided {r_base:5.3f} | window gaps "
                f"guided {sum(gaps['guided'][SWAP_AT : SWAP_AT + GUIDE_CHUNKS]):6.1f} "
                f"lora {sum(gaps['lora_plain'][SWAP_AT : SWAP_AT + GUIDE_CHUNKS]):6.1f} "
                f"base {sum(gaps['base_plain'][SWAP_AT : SWAP_AT + GUIDE_CHUNKS]):6.1f}",
                flush=True,
            )

    mean_lora = sum(ratios_lora) / len(ratios_lora)
    mean_base = sum(ratios_base) / len(ratios_base)
    verdict = "PASS" if mean_lora >= PASS_BAR else "FAIL"
    meta = {
        "lora": str(lora_path),
        "uuids": uuids,
        "prompts": EVAL_PROMPTS,
        "n_chunks": N_CHUNKS,
        "swap_at": SWAP_AT,
        "guide_scale": GUIDE_SCALE,
        "guide_chunks": GUIDE_CHUNKS,
        "lora_chunks": LORA_CHUNKS,
        "seed": SEED,
        "mean_ratio_lora_vs_guided": mean_lora,
        "mean_ratio_base_vs_guided": mean_base,
        "pass_bar": PASS_BAR,
        "verdict": verdict,
        "combos": report,
    }
    (OUT_DIR / "report.json").write_text(json.dumps(meta, indent=2))
    print(
        f"EVAL-GUIDANCE-DONE | {verdict} | lora/guided {mean_lora:.3f} "
        f"(bar {PASS_BAR}) | base/guided {mean_base:.3f} | {OUT_DIR}/report.json",
        flush=True,
    )


if __name__ == "__main__":
    main()
