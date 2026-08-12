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

    A  control       original clip prompt throughout
    B  swap          hot-swap to ``EDIT_PROMPT`` at chunk ``SWAP_AT``
    C  swap+guide    same swap with two-prompt edit guidance
    D  swap+recache  same swap plus previous-chunk KV re-commit

B and C consume the identical RNG stream as A (the swap itself draws no
noise), so the per-chunk ``|B - A|`` pixel gap is a pure measure of prompt
responsiveness: ~0 before the swap (sanity check), and the post-swap
magnitude/growth is the signal. D draws one extra context-noise sample at
the recache, so its pre-swap sanity still holds but its post-swap gap is
noise-shifted — judge D visually against B.

Env knobs: ``UUID``, ``EDIT_PROMPT``, ``N_CHUNKS``, ``SWAP_AT``,
``GUIDE_SCALE``, ``GUIDE_CHUNKS``, ``SEED``, ``OUT_DIR``.

Run from the repo root::

    .venv/bin/python integrations/omnidreams/scripts/smoke_text_edit.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Must land before the first CUDA allocation (co-tenant VRAM share).
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
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
N_CHUNKS = int(os.environ.get("N_CHUNKS", "4"))
SWAP_AT = int(os.environ.get("SWAP_AT", "2"))
GUIDE_SCALE = float(os.environ.get("GUIDE_SCALE", "2.5"))
GUIDE_CHUNKS = int(os.environ.get("GUIDE_CHUNKS", "4"))
VIDEO_HEIGHT = int(os.environ.get("VIDEO_HEIGHT", "320"))
VIDEO_WIDTH = int(os.environ.get("VIDEO_WIDTH", "512"))
SEED = int(os.environ.get("SEED", "42"))
OUT_DIR = Path(
    os.environ.get("OUT_DIR", "integrations/omnidreams/scripts/outputs/text_edit_smoke")
)
# Mid-stream edit prompts to sweep. Weather edits (rain/snow) are the natural
# fit for a text swap. The actor edits describe a /spawn <class> object as PROSE
# -- note this is NOT the /spawn HDMap-cuboid path (that injects geometry into the
# conditioning, which this pre-baked-hdmap smoke cannot do); it tests whether the
# model conjures the object from TEXT alone. Compare the per-chunk gaps: weather
# should move the whole frame; text-only actors typically move it far less than a
# real HDMap spawn would.
SWEEP_PROMPTS: dict[str, str] = {
    "rain": (
        "Driving scene from a front-facing car camera in heavy rain. Rain "
        "streaks falling, wet reflective road, water on the windshield, "
        "overcast gray sky. Photorealistic dashcam footage."
    ),
    "snow": (
        "Driving scene from a front-facing car camera at night in a heavy "
        "snowstorm. Thick snow falling, snow-covered road and buildings, "
        "headlights and streetlights glowing through the snow. Photorealistic "
        "dashcam footage."
    ),
    "car": "A car parked on the road directly ahead. Photorealistic dashcam footage.",
    "truck": "A large truck on the road directly ahead. Photorealistic dashcam footage.",
    "pedestrian": "A pedestrian walking across the road ahead. Photorealistic dashcam footage.",
    "cyclist": "A cyclist riding on the road ahead. Photorealistic dashcam footage.",
    "cone": "Orange traffic cones on the road ahead. Photorealistic dashcam footage.",
    "barrier": (
        "An orange and white striped construction barrier across the road "
        "ahead. Photorealistic dashcam footage."
    ),
}
# Optional filter: EDIT_KEYS="rain,truck" runs just those; default runs all.
_keys_env = os.environ.get("EDIT_KEYS", "").strip()
EDIT_KEYS = [k.strip() for k in _keys_env.split(",") if k.strip()] or list(SWEEP_PROMPTS)


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
        print(f"  chunk {ar_idx+1}/{N_CHUNKS}...", end=" ", flush=True)
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
        print("✓", flush=True)
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


def _burn_prompts(
    video: Tensor,
    base_prompt: str,
    swap: dict | None,
) -> Tensor:
    """Burn prompts onto video frames as text overlay."""
    device = video.device
    video = video.cpu()  # Move to CPU for PIL operations
    T, C, H, W = video.shape

    # Convert to uint8 for PIL (from [-1, 1] to [0, 255])
    frames_uint8 = ((video + 1) / 2 * 255).clamp(0, 255).byte().numpy()

    # Determine prompt timeline (rough: ~8 frames per chunk)
    swap_at_frame = (swap["at"] * 8) if swap else T

    burned = []
    for t in range(T):
        frame = frames_uint8[t]  # [C, H, W]
        frame = frame.transpose(1, 2, 0)  # [H, W, C]

        img = Image.fromarray(frame, mode="RGB")
        draw = ImageDraw.Draw(img)

        # Determine active prompt
        if swap and t >= swap_at_frame:
            prompt_text = swap["prompt"][:50]
            color = (100, 255, 100)  # Bright green
        else:
            prompt_text = base_prompt[:50]
            color = (255, 255, 100)  # Bright yellow

        # Draw text with black background for visibility
        text_y = H - 50
        text_x = 10
        # Black background box
        draw.rectangle([text_x - 2, text_y - 2, text_x + 400, text_y + 20], fill=(0, 0, 0))
        # White text (use default font)
        draw.text((text_x, text_y), prompt_text, fill=color)

        burned.append(torch.from_numpy(np.array(img)).permute(2, 0, 1).float() / 255 * 2 - 1)

    return torch.stack(burned).to(device)


def main() -> None:
    hdmap_path, frame_path, clip_prompt = _sample_paths(UUID)
    total_frames = 5 + (N_CHUNKS - 1) * 8
    print(f"clip {UUID}\n  prompt: {clip_prompt}\n  edits:  {', '.join(EDIT_KEYS)}")
    print(f"  chunks={N_CHUNKS} swap_at={SWAP_AT} frames={total_frames}")

    device = torch.device("cuda")
    hdmap = load_video_tensor(
        hdmap_path,
        pixel_height=VIDEO_HEIGHT,
        pixel_width=VIDEO_WIDTH,
        device=device,
        dtype=torch.bfloat16,
    )[:total_frames][None, None]
    first = load_first_frame_tensor(
        frame_path,
        pixel_height=VIDEO_HEIGHT,
        pixel_width=VIDEO_WIDTH,
        device=device,
        dtype=torch.bfloat16,
    )[None, None]  # [B=1, V=1, 1, C, H, W]

    pipe = _build_pipeline()

    # control + one guided swap per swept prompt (weather + actor-class text).
    variants: dict[str, dict | None] = {"control": None}
    for key in EDIT_KEYS:
        variants[key] = {
            "at": SWAP_AT,
            "prompt": SWEEP_PROMPTS[key],
            "scale": GUIDE_SCALE,
            "chunks": GUIDE_CHUNKS,
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    videos: dict[str, Tensor] = {}
    for name, swap in variants.items():
        print(f"rolling out {name} ...", flush=True)
        videos[name] = _rollout(
            pipe, hdmap=hdmap, first=first, base_prompt=clip_prompt, swap=swap
        )
        write_video_tensor(videos[name], OUT_DIR / f"{name}.mp4", fps=30, layout="tchw")

        # Save annotated version with prompts burned on
        annotated = _burn_prompts(videos[name], clip_prompt, swap)
        write_video_tensor(annotated, OUT_DIR / f"{name}_annotated.mp4", fps=30, layout="tchw")

    control = videos["control"]
    report: dict[str, list[float]] = {}
    for name in EDIT_KEYS:
        gaps = _per_chunk_gap(videos[name], control)
        report[name] = gaps
        pre = max(gaps[:SWAP_AT])
        post = gaps[SWAP_AT:]
        print(
            f"{name:>13}: pre-swap max gap {pre:6.3f}  "
            f"post-swap per-chunk {' '.join(f'{g:6.2f}' for g in post)}"
        )

    # Side-by-side [control | first two edits] for eyeballing.
    sbs = torch.cat(
        [control, *(videos[k] for k in EDIT_KEYS[:2])], dim=3
    )  # widths concat
    write_video_tensor(sbs, OUT_DIR / "sbs.mp4", fps=30, layout="tchw")

    meta = {
        "uuid": UUID,
        "clip_prompt": clip_prompt,
        "edit_prompts": {k: SWEEP_PROMPTS[k] for k in EDIT_KEYS},
        "n_chunks": N_CHUNKS,
        "swap_at": SWAP_AT,
        "guide_scale": GUIDE_SCALE,
        "guide_chunks": GUIDE_CHUNKS,
        "seed": SEED,
        "per_chunk_gap_uint8": report,
    }
    (OUT_DIR / "report.json").write_text(json.dumps(meta, indent=2))
    print(f"videos + report under {OUT_DIR}/")


if __name__ == "__main__":
    main()
