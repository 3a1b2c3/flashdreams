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

"""Precompute the guidance-distillation text + image embeddings (one shot).

Loads the pipeline WITH the one-shot encoders once, encodes every prompt-bank
entry and every sample clip's own prompt through the Cosmos-Reason1 text
encoder, encodes every clip's first frame through the Wan VAE image encoder,
saves CPU tensors, and exits — so the ~14 GB text encoder is never resident
during training or eval (``pipeline.precompute_embeddings`` pattern,
``PLAN.md``).

Outputs (under ``guidance_distill/outputs/``):

- ``prompt_embeddings.pt``: ``{name: [1, 1, 512, 100352] bf16}`` — bank
  entries under their bank names, clip prompts under ``clip:<uuid>``.
- ``clip_assets.pt``: ``{"uuids": [...], "prompts": {uuid: str},
  "image_embeddings": {uuid: [1, 1, 1, Cl, Hl, Wl] bf16}}`` — the clip
  index that ``train_guidance.py`` / ``eval_guidance.py`` split into
  train / held-out sets.

Run from the flashdreams repo root (set ``SAMPLE_UUIDS`` to skip the HF
listing API — the shared IP rate limit, ``build_pairs.py`` note)::

    N_CLIPS=10 .venv/bin/python \
        integrations/omnidreams/guidance_distill/precompute_embeddings.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Must land before the first CUDA allocation (co-tenant VRAM share).
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drift_correction"))

import torch
from _host import build_pipeline
from build_pairs import _clip_prompt, _list_sample_uuids, _sample_files
from omnidreams.runner import (
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
    _load_first_frame,
)
from prompts import EDIT_PROMPTS, clip_key

## Configuration

OUT_DIR = Path(
    os.environ.get("OUT_DIR", "integrations/omnidreams/guidance_distill/outputs")
)
"""Embedding files consumed by ``train_guidance.py`` / ``eval_guidance.py``."""

N_CLIPS = int(os.environ.get("N_CLIPS", "10"))
"""Sample clips to encode (first ``N_CLIPS`` of the dataset, sorted).
Downstream, the last ``HOLDOUT`` of these are the eval's held-out set."""


def main() -> None:
    """Encode the bank + clip prompts and first frames; save CPU tensors."""
    torch.set_grad_enabled(False)
    dtype = torch.bfloat16

    # Load every first frame BEFORE any model work: image decode may fork,
    # which fails silently once this process has grown to model size (the
    # build_pairs.py ffmpeg note; first frames are cheap, so front-load them).
    uuids = _list_sample_uuids(N_CLIPS)
    firsts: list[torch.Tensor] = []
    prompts_by_uuid: dict[str, str] = {}
    for uuid in uuids:
        _, (frame_path,) = _sample_files(uuid)
        firsts.append(
            _load_first_frame(
                frame_path,
                pixel_height=DEFAULT_VIDEO_HEIGHT,
                pixel_width=DEFAULT_VIDEO_WIDTH,
                device="cpu",
                dtype=dtype,
            )[None, :, None]  # [1, V=1, 1, C, H, W]
        )
        prompts_by_uuid[uuid] = _clip_prompt(uuid)
        print(f"loaded inputs for clip {uuid}", flush=True)

    pipe = build_pipeline(with_oneshot_encoders=True)
    device = pipe.device
    assert pipe.text_encoder is not None  # with_oneshot_encoders=True

    prompt_embeddings: dict[str, torch.Tensor] = {}
    for entry in EDIT_PROMPTS:
        emb = torch.stack([pipe.text_encoder([entry.text])], dim=0)  # [1, 1, L, D]
        prompt_embeddings[entry.name] = emb.to("cpu", dtype)
        print(f"encoded bank prompt {entry.name}: {tuple(emb.shape)}", flush=True)

    image_embeddings: dict[str, torch.Tensor] = {}
    for uuid, first in zip(uuids, firsts):
        emb = pipe.precompute_embeddings(
            text=[[prompts_by_uuid[uuid]]], image=first.to(device)
        )
        text_emb = emb["text_embeddings"]
        image_emb = emb["image_embeddings"]
        assert text_emb is not None and image_emb is not None
        prompt_embeddings[clip_key(uuid)] = text_emb.to("cpu", dtype)
        image_embeddings[uuid] = image_emb.to("cpu", dtype)
        print(
            f"encoded clip {uuid}: text {tuple(text_emb.shape)} "
            f"image {tuple(image_emb.shape)}",
            flush=True,
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(prompt_embeddings, OUT_DIR / "prompt_embeddings.pt")
    torch.save(
        {
            "uuids": uuids,
            "prompts": prompts_by_uuid,
            "image_embeddings": image_embeddings,
        },
        OUT_DIR / "clip_assets.pt",
    )
    print(
        f"PRECOMPUTE-DONE | {len(prompt_embeddings)} prompt embeddings "
        f"({len(EDIT_PROMPTS)} bank + {len(uuids)} clips) -> {OUT_DIR}/",
        flush=True,
    )


if __name__ == "__main__":
    main()
