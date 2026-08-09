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

"""Guidance self-distillation trainer (Tier-2a of the live-edit hack).

Bakes the two-prompt text-edit guidance (``TextEditGuidance``, s=3) into a
LoRA so a *plain* mid-stream prompt swap responds like a *guided* one at
zero inference cost (``PLAN.md``). Teacher and student are the same
network on RNG-matched on-policy states:

    teacher = flow_old + s * (flow_new - flow_old)   (frozen base, LoRA 0)
    student = single branch under kv_new             (LoRA 1, grad)

Per step: sample a clip, a swap chunk ``k ~ U[4, 20]``, and a bank prompt
(10% no-op = the clip's own prompt, whose teacher degenerates to the plain
flow); roll the student (LoRA active, plain swap at ``k``) with the normal
``generate`` / ``finalize`` path to a random ``j in [k, k + 6]``; at chunk
``j`` distill both denoise steps (t = 1000, 450) plus a 0.5-weighted match
of the finalize/context forward (t = 128), so the committed KV history
tracks the guided flow too. The teacher's ``kv_old`` / ``kv_new`` are
cloned once at the swap (``BlockKVCache.clone_kv`` before / after
``replace_text_from_embeddings``) and loaded via ``overwrite_kv_``.

Host mechanics (proven in ``drift_correction/train_v2.py``): eager
pipeline (compile / graphs off), functional self-attention on grad
forwards (the stock KV-buffer write severs grads), per-block
``torch.utils.checkpoint`` (``use_reentrant=False``), and every backward
BEFORE the trained chunk's cache finalize. Each loss term backwards
immediately after its forward: the teacher's in-place cross-attn KV loads
would otherwise bump the version counters of tensors the student's graph
saved. Note the cross-attn ``k_proj`` / ``v_proj`` LoRA are structurally
inert on this host — the text K/V are precomputed into the cache buffers
under ``no_grad`` — so only ``q_proj`` / ``output_proj`` carry the
cross-attn training signal; they are still wrapped per the PLAN recipe so
the checkpoint shape matches the deployment premerge tooling.

VRAM (fits the ~65 GB co-tenant share): bf16 2B DiT ~4 GB + per-rollout
KV caches ~19 GB (28 blocks x 6-latent-frame window at 88x160 latents) +
fp32 LoRA/AdamW ~0.2 GB + one grad forward's checkpointed block inputs
~1.6 GB (immediate per-term backward keeps only one tape alive) +
recompute workspace — ~30 GB peak, eager.

Run from the flashdreams repo root (after ``precompute_embeddings.py``)::

    STEPS=800 .venv/bin/python \
        integrations/omnidreams/guidance_distill/train_guidance.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drift_correction"))

import numpy as np
import torch
from _host import build_pipeline
from _lora import (
    apply_lora,
    lora_parameters,
    save_lora,
    set_lora_scale,
    unwrap_compiled,
)
from _train_attn import functional_attention, patch_functional_attention
from build_pairs import _sample_files
from omnidreams.runner import DEFAULT_VIDEO_HEIGHT, DEFAULT_VIDEO_WIDTH, _load_video
from prompts import EDIT_PROMPTS, clip_key
from torch import Tensor

## Training configuration

BASE = Path("integrations/omnidreams/guidance_distill")
OUT_DIR = BASE / "outputs"

STEPS = int(os.environ.get("STEPS", "800"))
LR = float(os.environ.get("LR", "2e-4"))
GUIDE_SCALE = float(os.environ.get("GUIDE_SCALE", "3.0"))
"""Distilled edit strength s (fixed; the PLAN's open choice starts here)."""

SEED = int(os.environ.get("SEED", "0"))
HOLDOUT = int(os.environ.get("HOLDOUT", "2"))
"""Clips (last of the precomputed index) reserved for ``eval_guidance.py``."""

WARMUP = 40
GRAD_CLIP = 1.0
RANK = int(os.environ.get("RANK", "16"))
SAVE_EVERY = 100
LOG_EVERY = 10
EMA_DECAY = 0.98

NOOP_PROB = 0.1
"""Probability of a no-op swap (clip's own prompt; teacher == plain flow)."""

SWAP_MIN, SWAP_MAX = 4, 20
"""Swap chunk ``k ~ U[4, 20]`` — past the 3-chunk KV window fill."""

MAX_GAP = 6
"""Trained chunk ``j ~ U[k, k + MAX_GAP]`` — the guidance-countdown span."""

CTX_WEIGHT = 0.5
"""Weight of the finalize/context-forward (t=128) matching term."""

LORA_TARGETS = (
    "self_attn.q_proj",
    "self_attn.k_proj",
    "self_attn.v_proj",
    "self_attn.output_proj",
    "cross_attn.q_proj",
    "cross_attn.k_proj",
    "cross_attn.v_proj",
    "cross_attn.output_proj",
)
"""Drift-corrector recipe + cross-attn (the edit signal enters there)."""


def checkpoint_blocks(network) -> None:
    """Route every DiT block ``forward`` through gradient checkpointing.

    Per-instance overrides (not wrapper modules) so the network loop's
    ``isinstance(block, Block)`` assertion keeps passing — the
    ``hy_worldplay`` / ``lingbot`` trainer helper with the Cosmos block
    (no ``prefill_memory_kv`` here). Requires the functional-attention
    toggle on grad passes: recomputation must be side-effect free and must
    retake the same code path, so every backward runs inside
    ``functional_attention()``. No-op under ``no_grad`` passes (rollout,
    teacher probes, finalize).

    Args:
        network: The unwrapped ``CosmosDiTNetwork``.
    """
    from torch.utils.checkpoint import checkpoint

    def wrap(fn):
        def ckpt_fn(*args, _inner=fn, **kwargs):
            if not torch.is_grad_enabled():
                return _inner(*args, **kwargs)
            return checkpoint(_inner, *args, use_reentrant=False, **kwargs)

        return ckpt_fn

    for block in network.blocks:
        block.forward = wrap(block.forward)


def main() -> None:
    """Run the on-policy guidance-distillation loop."""
    rng = np.random.default_rng(SEED)
    prompt_emb = torch.load(
        OUT_DIR / "prompt_embeddings.pt", map_location="cpu", weights_only=False
    )
    assets = torch.load(
        OUT_DIR / "clip_assets.pt", map_location="cpu", weights_only=False
    )
    uuids: list[str] = assets["uuids"]
    assert len(uuids) > HOLDOUT, f"{len(uuids)} clips can't spare {HOLDOUT} held out"
    train_uuids = uuids[: len(uuids) - HOLDOUT]

    # Load every HDMap video BEFORE any model work: video decode forks
    # ffmpeg, which fails silently once this process has grown to rollout
    # size (build_pairs.py note). Trim to the trainable span.
    total_frames = 5 + (SWAP_MAX + MAX_GAP) * 8
    hdmaps: dict[str, Tensor] = {}
    for uuid in train_uuids:
        (hdmap_path,), _ = _sample_files(uuid)
        video = _load_video(
            hdmap_path,
            pixel_height=DEFAULT_VIDEO_HEIGHT,
            pixel_width=DEFAULT_VIDEO_WIDTH,
            device="cpu",
            dtype=torch.bfloat16,
        )[:total_frames]
        assert video.shape[0] >= total_frames, (
            f"clip {uuid} has {video.shape[0]} HDMap frames; need {total_frames}."
        )
        hdmaps[uuid] = video
        print(f"loaded hdmap for clip {uuid}: {tuple(video.shape)}", flush=True)

    pipe = build_pipeline(with_oneshot_encoders=False)
    assert pipe.V_group is None, "single-GPU trainer; run without CP"
    assert pipe.encoder is not None  # per-AR-step HDMap encoder (host invariant)
    device = pipe.device
    dtype = torch.bfloat16
    dm = pipe.diffusion_model
    transformer = dm.transformer
    scheduler = dm.scheduler
    timesteps = scheduler.denoising_step_list  # [1000, 450] on the chunk2 host
    sigmas = scheduler.denoising_sigmas
    n_steps = int(timesteps.shape[0])
    ctx_t = torch.tensor(float(dm.config.context_noise), device=device, dtype=dtype)

    network = unwrap_compiled(transformer.network)
    network.requires_grad_(False)  # frozen base; only the LoRA A/B path trains
    wrapped = apply_lora(network, rank=RANK, targets=LORA_TARGETS)
    params = lora_parameters(network)
    print(
        f"LoRA on {len(wrapped)} projections | "
        f"{sum(p.numel() for p in params) / 1e6:.2f}M params | "
        f"{len(train_uuids)} train clips ({HOLDOUT} held out) | "
        f"bank {[p.name for p in EDIT_PROMPTS]} | s={GUIDE_SCALE}",
        flush=True,
    )
    patch_functional_attention()
    checkpoint_blocks(network)
    opt = torch.optim.AdamW(params, lr=LR)

    def predict_v(tc, z_t: Tensor, timestep: Tensor, hd_p: Tensor) -> Tensor:
        """One functional-attention (non-writing) forward -> fp32 flow."""
        with functional_attention():
            flow = transformer.predict_flow(
                noisy_latent=z_t, timestep=timestep, cache=tc, input=hd_p
            )
        return flow.float()

    def load_kv(tc, kvs: list[tuple[Tensor, Tensor]]) -> None:
        """Load a cloned per-block cross-attn (text) KV set into the buffers."""
        for bc, (k, v) in zip(tc.network_cache.block_caches, kvs):
            bc.cross_attn.overwrite_kv_(k, v)

    def guided_teacher(
        tc,
        z_t: Tensor,
        timestep: Tensor,
        hd_p: Tensor,
        kv_old: list[tuple[Tensor, Tensor]],
        kv_new: list[tuple[Tensor, Tensor]],
        no_op: bool,
    ) -> Tensor:
        """Frozen-base guidance-combine target at one (z_t, t) state.

        Exactly ``CosmosTransformer._predict_with_text_edit_guidance`` on
        the unwrapped weights: load ``kv_old`` -> ``flow_old``, load
        ``kv_new`` -> ``flow_new``, combine at :data:`GUIDE_SCALE`. No-op
        swaps skip the redundant second branch (``kv_old == kv_new``, so
        the combine degenerates to the plain flow). Leaves the buffers
        holding ``kv_new`` — the student's conditioning.

        Returns:
            fp32 teacher flow, no grad.
        """
        with torch.no_grad():
            set_lora_scale(network, 0.0)
            if no_op:
                load_kv(tc, kv_new)
                teacher = predict_v(tc, z_t, timestep, hd_p)
            else:
                load_kv(tc, kv_old)
                flow_old = predict_v(tc, z_t, timestep, hd_p)
                load_kv(tc, kv_new)
                flow_new = predict_v(tc, z_t, timestep, hd_p)
                teacher = flow_old + GUIDE_SCALE * (flow_new - flow_old)
            set_lora_scale(network, 1.0)
        return teacher

    def train_step() -> tuple[dict[str, float], str]:
        """One on-policy rollout + distillation step -> (losses, episode).

        Backwards happen inside (per term, inside ``functional_attention``);
        the caller owns ``zero_grad`` / clip / ``opt.step``.
        """
        uuid = train_uuids[int(rng.integers(len(train_uuids)))]
        k = int(rng.integers(SWAP_MIN, SWAP_MAX + 1))
        j = k + int(rng.integers(0, MAX_GAP + 1))
        no_op = bool(rng.random() < NOOP_PROB)
        name = (
            clip_key(uuid)
            if no_op
            else EDIT_PROMPTS[int(rng.integers(len(EDIT_PROMPTS)))].name
        )

        # Seed the model RNG per rollout: generate draws initial noise and
        # renoise eps from it, finalize draws the context noise from it.
        dm._rng = torch.Generator(device=device).manual_seed(int(rng.integers(2**31)))
        cache = pipe.initialize_cache_from_embeddings(
            text_embeddings=prompt_emb[clip_key(uuid)],
            image_embeddings=assets["image_embeddings"][uuid],
        )
        tc = cache.transformer_cache
        hdmap = hdmaps[uuid]
        set_lora_scale(network, 1.0)  # the student rolls its own states

        kv_old: list[tuple[Tensor, Tensor]] | None = None
        kv_new: list[tuple[Tensor, Tensor]] | None = None

        def plain_swap() -> None:
            """Swap the prompt (guidance_scale=1) and snapshot old/new KV."""
            nonlocal kv_old, kv_new
            blocks = tc.network_cache.block_caches
            kv_old = [bc.cross_attn.clone_kv() for bc in blocks]
            pipe.replace_text_from_embeddings(cache, prompt_emb[name])
            kv_new = [bc.cross_attn.clone_kv() for bc in blocks]

        # On-policy student rollout to chunk j - 1 (normal generate/finalize,
        # both @no_grad; the plain swap lands at the chunk-k boundary).
        start = 0
        for ar_idx in range(j):
            if ar_idx == k:
                plain_swap()
            num_frames = pipe.get_num_frames(ar_idx)
            chunk_hdmap = hdmap[start : start + num_frames][None, None].to(device)
            pipe.generate(ar_idx, cache, hdmap=chunk_hdmap)
            pipe.finalize(ar_idx, cache)
            start += num_frames
        if j == k:
            plain_swap()
        assert kv_old is not None and kv_new is not None

        # Trained chunk j: encoder + patchify by hand (the normal generate
        # path is @no_grad), then the denoise steps under an open bracket.
        num_frames = pipe.get_num_frames(j)
        chunk_hdmap = hdmap[start : start + num_frames][None, None].to(device)
        with torch.no_grad():
            enc = pipe.encoder(
                input=chunk_hdmap, autoregressive_index=j, cache=cache.encoder_cache
            )
            hd_p = transformer.patchify_and_maybe_split_cp(enc)
        tc.start(j)

        model_rng = dm.rng
        assert model_rng is not None
        losses: dict[str, float] = {}
        denoise_mean = 0.0

        # Mirror scheduler.sample: the student's own (detached) flow advances
        # the trajectory, so states stay exactly on-policy.
        noisy = torch.randn(
            transformer.latent_shape, device=device, dtype=dtype, generator=model_rng
        )
        clean: Tensor | None = None
        for i in range(n_steps):
            sigma = sigmas[i]
            timestep = timesteps[i].to(dtype=dtype)
            if i > 0:
                assert clean is not None
                noise = torch.empty_like(noisy).normal_(generator=model_rng)
                noisy = ((1.0 - sigma) * clean + sigma * noise).to(dtype)
            teacher = guided_teacher(tc, noisy, timestep, hd_p, kv_old, kv_new, no_op)
            v_student = predict_v(tc, noisy, timestep, hd_p)
            term = (v_student - teacher).square().mean()
            # Backward now: the next teacher's in-place KV loads would bump
            # the version counters of tensors this graph saved; recompute
            # must retake the functional path.
            with functional_attention():
                (term / n_steps).backward()
            losses[f"t{int(timesteps[i].item())}"] = float(term)
            denoise_mean += float(term) / n_steps
            clean = noisy - sigma * v_student.detach()  # fp32 via promotion

        # Finalize/context-forward match (t=128): the same forward whose
        # K/V the stock finalize commits, so the history the next chunks
        # attend to is trained toward the guided teacher's.
        assert clean is not None
        x0 = clean.to(dtype)
        z_ctx = scheduler.add_noise(x0, ctx_t, rng=model_rng)
        teacher_ctx = guided_teacher(tc, z_ctx, ctx_t, hd_p, kv_old, kv_new, no_op)
        v_ctx = predict_v(tc, z_ctx, ctx_t, hd_p)
        term = (v_ctx - teacher_ctx).square().mean()
        with functional_attention():
            (CTX_WEIGHT * term).backward()
        losses["ctx"] = float(term)

        # All backwards done -> the stock finalize (buffer write + index
        # advance; guidance-free by construction: the plain swap left
        # text_edit_guidance=None) may now close the bracket.
        with torch.no_grad():
            transformer.finalize_kv_cache(
                noisy_latent=z_ctx.detach(), timestep=ctx_t, cache=tc, input=hd_p
            )
        tc.finalize(j)

        losses["total"] = denoise_mean + CTX_WEIGHT * losses["ctx"]
        episode = f"{uuid[:8]} {name.replace('clip:', 'no_op:')[:16]} k={k} j={j}"
        return losses, episode

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.set_grad_enabled(True)
    ema: float | None = None
    for step in range(1, STEPS + 1):
        for pg in opt.param_groups:
            pg["lr"] = LR * min(1.0, step / WARMUP)
        opt.zero_grad()
        losses, episode = train_step()
        torch.nn.utils.clip_grad_norm_(params, GRAD_CLIP)
        opt.step()
        torch.cuda.empty_cache()  # the step's rollout caches died with its frame
        ema = (
            losses["total"]
            if ema is None
            else EMA_DECAY * ema + (1.0 - EMA_DECAY) * losses["total"]
        )
        if step % LOG_EVERY == 0 or step == 1:
            terms = " ".join(f"{k} {v:.4f}" for k, v in losses.items() if k != "total")
            print(
                f"step {step:5d} | loss {losses['total']:.4f} (ema {ema:.4f})"
                f" | {terms} | {episode}",
                flush=True,
            )
        if step % SAVE_EVERY == 0 or step == STEPS:
            path = OUT_DIR / f"lora_guidance_step{step}.pt"
            save_lora(network, path)
            print(f"saved {path}", flush=True)

    print(f"TRAIN-GUIDANCE-DONE | final loss ema {ema:.4f}", flush=True)


if __name__ == "__main__":
    main()
