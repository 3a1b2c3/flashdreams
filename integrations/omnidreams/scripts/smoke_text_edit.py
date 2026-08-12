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

"""Smoke test: mid-stream prompt swap on the real distilled model.

Rolls the same seed / HDMap / first frame several ways and reports how
strongly the video diverges after the swap chunk:

    A  control           original clip prompt throughout
    B  swap              hot-swap to ``EDIT_PROMPT`` at chunk ``SWAP_AT``
    C  swap+guide        same swap with two-prompt edit guidance
    D  swap+recache      same swap plus previous-chunk KV re-commit
    E  sequential        multiple prompts: A→B→C in sequence
    F  determinism       verify bit-clean determinism (run twice)

B and C consume the identical RNG stream as A (the swap itself draws no noise),
so the per-chunk ``|B - A|`` pixel gap is a pure measure of prompt
responsiveness: ~0 before the swap (sanity check), and the post-swap
magnitude/growth is the signal. D draws one extra context-noise sample at
the recache, so its pre-swap sanity still holds but its post-swap gap is
noise-shifted — judge D visually against B.

**Env knobs:**
    UUID                    Sample ID (default: 23599139-948f-4681-b7f4-74794113086d)
    EDIT_PROMPT             Text to swap to (default: snowstorm prompt)
    N_CHUNKS                Total chunks to generate (default: 16)
    SWAP_AT                 Comma-separated chunk positions for timing variation
                            (default: 8; e.g., "4,8,12" tests swaps at three times)
    GUIDE_SCALES            Comma-separated guidance scales for strength sweep
                            (default: 2.5; e.g., "1.0,2.5,5.0" tests three strengths)
    GUIDE_CHUNKS            Guidance window duration (default: 4 chunks)
    SEQUENTIAL_PROMPTS      Comma-separated prompts for A→B→C edits
                            (e.g., "rain,night,snow" edits to rain at chunk 8, night at 12, snow at 16)
    CHECK_DETERMINISM       Enable determinism verification (run each variant twice)
                            (default: off; set to 1/true/yes to enable)
    SEED                    RNG seed (default: 42)
    OUT_DIR                 Output directory (default: integrations/omnidreams/scripts/outputs/text_edit_smoke)

**Prompt Design Guide:**

Effective EDIT_PROMPT and SEQUENTIAL_PROMPTS should:

1. **Be specific & visual** — describe what the camera sees, not abstract concepts
   - ✓ "Heavy rain on the road with wet reflections and windshield droplets"
   - ✗ "It's raining" (too vague)

2. **Match distribution** — use phrasing similar to training captions
   - ✓ "Driving scene from a front-facing car camera at night under streetlights"
   - ✗ "Nighttime photography, neon signs, cyberpunk aesthetic"

3. **Vary in semantics, not style** — test content changes, not art direction
   - ✓ "Rain" vs "Snow" (weather change, same road)
   - ✗ "Photorealistic" vs "oil painting" (style, not scene)

4. **Keep length reasonable** — 15-30 words per prompt
   - Longer: more control but slower convergence
   - Shorter: faster response but less specificity

5. **For sequential edits, ensure orthogonal changes** — test transitions
   - ✓ "Sunny day" → "Heavy rain" → "Snowstorm" (clear progression)
   - ✗ "Day" → "Day at noon" → "Day in afternoon" (too similar)

**Example prompts for testing:**

Weather/Lighting:
    "Driving scene in heavy rain with wet road and windshield droplets"
    "Driving scene at night with streetlights and vehicle lights"
    "Driving scene in a heavy snowstorm with snow covering the road"
    "Driving scene at sunset with golden hour lighting and long shadows"
    "Driving scene in thick fog with limited visibility"

Dynamic events (good for responsiveness testing):
    "Driving scene with a pedestrian crossing the road ahead"
    "Driving scene following a truck on the highway"
    "Driving scene in heavy traffic with cars around"
    "Driving scene passing a construction zone with barriers"

Challenging transitions (good for sequential testing):
    "Sunny highway" → "Heavy downpour" → "Clear skies after storm"
    "Daytime city" → "Evening dusk" → "Night with lights"
    "Empty road" → "Heavy traffic" → "Empty road again"

**Examples:**

Baseline (single swap, single guidance scale):

    python integrations/omnidreams/scripts/smoke_text_edit.py

Guidance strength sweep (test s=1.0, 2.5, 5.0):

    GUIDE_SCALES=1.0,2.5,5.0 python integrations/omnidreams/scripts/smoke_text_edit.py

Swap timing variation (test chunks 4, 8, 12):

    SWAP_AT=4,8,12 python integrations/omnidreams/scripts/smoke_text_edit.py

Sequential edits (rain → night → snow):

    SEQUENTIAL_PROMPTS="Driving scene in heavy rain with wet road,Driving scene at night with streetlights,Driving scene in heavy snowstorm" python integrations/omnidreams/scripts/smoke_text_edit.py

Determinism check (run each variant twice):

    CHECK_DETERMINISM=1 python integrations/omnidreams/scripts/smoke_text_edit.py

Full suite (all above):

    SWAP_AT=4,8,12 GUIDE_SCALES=1.0,2.5,5.0 SEQUENTIAL_PROMPTS="rain,night,snow" CHECK_DETERMINISM=1 python integrations/omnidreams/scripts/smoke_text_edit.py

Run from the repo root::

    .venv/bin/python integrations/omnidreams/scripts/smoke_text_edit.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Must land before the first CUDA allocation (co-tenant VRAM share).
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from omnidreams.config import SV_2STEPS_CHUNK2_LOC6_LIGHTVAE_LIGHTTAE
from omnidreams.pipeline import OmnidreamsPipeline
from omnidreams.runner import DEFAULT_VIDEO_HEIGHT, DEFAULT_VIDEO_WIDTH
from torch import Tensor

from flashdreams.infra.config import derive_config
from flashdreams.infra.runner_io import (
    load_first_frame_tensor,
    load_video_tensor,
    write_video_tensor,
)

SAMPLES_ROOT = (
    Path.home()
    / ".cache/huggingface/hub/datasets--nvidia--omni-dreams-samples/snapshots"
)

UUID = os.environ.get("UUID", "23599139-948f-4681-b7f4-74794113086d")
N_CHUNKS = int(os.environ.get("N_CHUNKS", "16"))
SEED = int(os.environ.get("SEED", "42"))
OUT_DIR = Path(
    os.environ.get("OUT_DIR", "integrations/omnidreams/scripts/outputs/text_edit_smoke")
)
EDIT_PROMPT = os.environ.get(
    "EDIT_PROMPT",
    "Driving scene from a front-facing car camera at night in a heavy "
    "snowstorm. Thick snow falling, snow-covered road and buildings, "
    "headlights and streetlights glowing through the snow. Photorealistic "
    "dashcam footage.",
)

_parse_list = lambda s, cast: [cast(x.strip()) for x in s.split(",") if x.strip()]

SWAP_AT_VALUES = _parse_list(os.environ.get("SWAP_AT", "8"), int)
GUIDE_SCALES = _parse_list(os.environ.get("GUIDE_SCALES", "2.5"), float)
GUIDE_CHUNKS = int(os.environ.get("GUIDE_CHUNKS", "4"))

SEQUENTIAL_PROMPTS = _parse_list(os.environ.get("SEQUENTIAL_PROMPTS", ""), str)
CHECK_DETERMINISM = os.environ.get("CHECK_DETERMINISM", "").lower() in ("1", "true", "yes")


def _sample_paths(uuid: str) -> tuple[Path, Path, str]:
    hdmaps = sorted(SAMPLES_ROOT.glob(f"*/data/single_view/{uuid}/*_hdmap.mp4"))
    frames = sorted(SAMPLES_ROOT.glob(f"*/data/single_view/{uuid}/first_frame.png"))
    prompts = sorted(SAMPLES_ROOT.glob(f"*/data/single_view/{uuid}/prompt.txt"))
    assert hdmaps and frames and prompts, (
        f"sample {uuid} not in the local HF cache under {SAMPLES_ROOT}"
    )
    return hdmaps[0], frames[0], prompts[0].read_text().strip()


def _build_pipeline() -> OmnidreamsPipeline:
    cfg = derive_config(
        SV_2STEPS_CHUNK2_LOC6_LIGHTVAE_LIGHTTAE,
        enable_sync_and_profile=False,
        diffusion_model=dict(
            seed=SEED,
            transformer=dict(compile_network=False, use_cuda_graph=False),
        ),
    )
    pipe = cfg.setup()
    assert isinstance(pipe, OmnidreamsPipeline)
    pipe = pipe.to("cuda")
    # EDIT_LORA=<ckpt>: deploy the pre-merged guidance-distillation LoRA, so
    # the guided variants exercise the production use_lora window instead of
    # the two-branch combine.
    if os.environ.get("EDIT_LORA"):
        from omnidreams._edit_lora import TextEditLoRA

        transformer = pipe.diffusion_model.transformer
        edit_lora = TextEditLoRA(transformer.network, os.environ["EDIT_LORA"])
        transformer.set_text_edit_lora(edit_lora)
        print(f"deployed {edit_lora.describe()}", flush=True)
    return pipe


@torch.no_grad()
def _rollout(
    pipe: OmnidreamsPipeline,
    *,
    hdmap: Tensor,
    first: Tensor,
    base_prompt: str,
    swap: dict | None = None,
) -> Tensor:
    """Return the decoded rollout ``[T, 3, H, W]`` in ``[-1, 1]`` on CPU."""
    device = pipe.device
    pipe.diffusion_model._rng = torch.Generator(device=device).manual_seed(SEED)
    cache = pipe.initialize_cache(text=[[base_prompt]], image=first)
    chunks: list[Tensor] = []
    start = 0
    for ar_idx in range(N_CHUNKS):
        if swap is not None and ar_idx == swap["at"]:
            pipe.replace_text(
                cache,
                [[swap["prompt"]]],
                guidance_scale=swap.get("scale", 1.0),
                guidance_chunks=swap.get("chunks", 0),
                recache_last_chunk=swap.get("recache", False),
            )
        num_frames = pipe.get_num_frames(ar_idx)
        end = start + num_frames
        assert end <= hdmap.shape[2], f"hdmap too short at chunk {ar_idx}"
        chunk = pipe.generate(ar_idx, cache, hdmap=hdmap[:, :, start:end])
        pipe.finalize(ar_idx, cache)
        chunks.append(chunk[0, 0].float().cpu())
        start = end
    del cache
    torch.cuda.empty_cache()
    return torch.cat(chunks, dim=0)


def _chunk_bounds() -> list[tuple[int, int]]:
    bounds, start = [], 0
    for ar_idx in range(N_CHUNKS):
        n = 5 if ar_idx == 0 else 8
        bounds.append((start, start + n))
        start += n
    return bounds


def _per_chunk_gap(a: Tensor, b: Tensor) -> list[float]:
    """Mean |a - b| per chunk in uint8 units (0..255)."""
    return [float((a[s:e] - b[s:e]).abs().mean() * 127.5) for s, e in _chunk_bounds()]


def _rollout_determinism(
    pipe: OmnidreamsPipeline,
    *,
    hdmap: Tensor,
    first: Tensor,
    base_prompt: str,
    swap: dict | None = None,
    runs: int = 2,
) -> tuple[Tensor, bool]:
    """Verify determinism by running twice with same seed; return video + is_deterministic."""
    result = None
    for run in range(runs):
        video = _rollout(pipe, hdmap=hdmap, first=first, base_prompt=base_prompt, swap=swap)
        if result is None:
            result = video
        elif not torch.allclose(result, video, atol=1e-6):
            print(f"    ⚠ determinism check FAILED (runs differ)", flush=True)
            return video, False
    return result, True


def main() -> None:
    hdmap_path, frame_path, clip_prompt = _sample_paths(UUID)
    total_frames = 5 + (N_CHUNKS - 1) * 8
    print(f"clip {UUID}\n  prompt: {clip_prompt}\n  edit:   {EDIT_PROMPT}")
    print(f"  chunks={N_CHUNKS} swap_at_values={SWAP_AT_VALUES} guide_scales={GUIDE_SCALES}")
    print(f"  guide_chunks={GUIDE_CHUNKS} frames={total_frames}")
    if SEQUENTIAL_PROMPTS:
        print(f"  sequential_prompts={SEQUENTIAL_PROMPTS}")
    if CHECK_DETERMINISM:
        print(f"  determinism_check=enabled (runs each variant twice)")

    device = torch.device("cuda")
    hdmap = load_video_tensor(
        hdmap_path,
        pixel_height=DEFAULT_VIDEO_HEIGHT,
        pixel_width=DEFAULT_VIDEO_WIDTH,
        device=device,
        dtype=torch.bfloat16,
    )[:total_frames][None, None]
    first = load_first_frame_tensor(
        frame_path,
        pixel_height=DEFAULT_VIDEO_HEIGHT,
        pixel_width=DEFAULT_VIDEO_WIDTH,
        device=device,
        dtype=torch.bfloat16,
    )[None, None]  # [B=1, V=1, 1, C, H, W]

    pipe = _build_pipeline()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n=== baseline control ===", flush=True)
    if CHECK_DETERMINISM:
        control, is_det = _rollout_determinism(
            pipe, hdmap=hdmap, first=first, base_prompt=clip_prompt, swap=None
        )
        print(f"  deterministic: {is_det}", flush=True)
    else:
        control = _rollout(pipe, hdmap=hdmap, first=first, base_prompt=clip_prompt, swap=None)
    write_video_tensor(control, OUT_DIR / "control.mp4", fps=30, layout="tchw")

    report: dict[str, dict] = {"control": {"per_chunk_gap_uint8": []}}

    print("\n=== timing variation ===", flush=True)
    for swap_at in SWAP_AT_VALUES:
        print(f"  swap_at={swap_at}", flush=True)
        for scale in GUIDE_SCALES:
            is_guided = scale > 1.0
            if is_guided:
                name = f"swap_at{swap_at}_s{scale:.1f}"
                swap_spec = {
                    "at": swap_at,
                    "prompt": EDIT_PROMPT,
                    "scale": scale,
                    "chunks": GUIDE_CHUNKS,
                }
            else:
                name = f"swap_at{swap_at}"
                swap_spec = {"at": swap_at, "prompt": EDIT_PROMPT}

            print(f"    rolling {name} ...", end=" ", flush=True)
            if CHECK_DETERMINISM:
                video, is_det = _rollout_determinism(
                    pipe, hdmap=hdmap, first=first, base_prompt=clip_prompt, swap=swap_spec
                )
                print(f"deterministic={is_det}", flush=True)
            else:
                video = _rollout(pipe, hdmap=hdmap, first=first, base_prompt=clip_prompt, swap=swap_spec)
                print("done", flush=True)

            write_video_tensor(video, OUT_DIR / f"{name}.mp4", fps=30, layout="tchw")
            gaps = _per_chunk_gap(video, control)
            report[name] = {
                "swap_at": swap_at,
                "guide_scale": scale,
                "guide_chunks": GUIDE_CHUNKS if is_guided else 0,
                "per_chunk_gap_uint8": gaps,
                "pre_swap_max": float(max(gaps[:swap_at]) if swap_at > 0 else 0),
                "post_swap_mean": float(sum(gaps[swap_at:]) / len(gaps[swap_at:]) if swap_at < len(gaps) else 0),
            }

    print("\n=== recache variant (bit-level semantics) ===", flush=True)
    for swap_at in SWAP_AT_VALUES[:1]:
        name = f"swap_at{swap_at}_recache"
        print(f"  rolling {name} ...", end=" ", flush=True)
        video = _rollout(
            pipe,
            hdmap=hdmap,
            first=first,
            base_prompt=clip_prompt,
            swap={"at": swap_at, "prompt": EDIT_PROMPT, "recache": True},
        )
        print("done", flush=True)
        write_video_tensor(video, OUT_DIR / f"{name}.mp4", fps=30, layout="tchw")
        gaps = _per_chunk_gap(video, control)
        report[name] = {
            "swap_at": swap_at,
            "recache": True,
            "per_chunk_gap_uint8": gaps,
            "note": "ReCache uses dedicated seeded generator; noise-shifted relative to swap",
        }

    if SEQUENTIAL_PROMPTS:
        print(f"\n=== sequential edits: {' → '.join(SEQUENTIAL_PROMPTS)} ===", flush=True)
        seq_name = "sequential_" + "_".join(p[:3].lower() for p in SEQUENTIAL_PROMPTS)
        current_video = control.clone()
        seq_report = {"edits": []}

        for i, prompt in enumerate(SEQUENTIAL_PROMPTS):
            swap_chunk = SWAP_AT_VALUES[0] + (i * 4)
            if swap_chunk >= N_CHUNKS:
                print(f"  skipping edit {i+1} (chunk {swap_chunk} ≥ {N_CHUNKS})", flush=True)
                break
            print(f"  edit {i+1} → '{prompt[:40]}...' at chunk {swap_chunk}", end=" ", flush=True)
            video = _rollout(
                pipe,
                hdmap=hdmap,
                first=first,
                base_prompt=clip_prompt,
                swap={"at": swap_chunk, "prompt": prompt, "scale": GUIDE_SCALES[0], "chunks": GUIDE_CHUNKS},
            )
            print("done", flush=True)
            gaps = _per_chunk_gap(video, control)
            seq_report["edits"].append(
                {
                    "edit_number": i + 1,
                    "prompt": prompt,
                    "swap_at": swap_chunk,
                    "post_swap_mean": float(sum(gaps[swap_chunk:]) / len(gaps[swap_chunk:]) if swap_chunk < len(gaps) else 0),
                }
            )

        report[seq_name] = seq_report

    meta = {
        "uuid": UUID,
        "clip_prompt": clip_prompt,
        "edit_prompts": {
            "single": EDIT_PROMPT,
            "sequential": SEQUENTIAL_PROMPTS,
        },
        "n_chunks": N_CHUNKS,
        "swap_at_values": SWAP_AT_VALUES,
        "guide_scales": GUIDE_SCALES,
        "guide_chunks": GUIDE_CHUNKS,
        "seed": SEED,
        "determinism_checked": CHECK_DETERMINISM,
        "variants": report,
    }
    (OUT_DIR / "report.json").write_text(json.dumps(meta, indent=2))

    print(f"\n=== summary ===", flush=True)
    for name, data in report.items():
        if isinstance(data, dict) and "per_chunk_gap_uint8" in data:
            pre = data.get("pre_swap_max", 0)
            post = data.get("post_swap_mean", 0)
            print(f"  {name:30s}: pre-swap={pre:6.2f}, post-swap={post:6.2f}", flush=True)

    print(f"\nvideos + report under {OUT_DIR}/", flush=True)


if __name__ == "__main__":
    main()
