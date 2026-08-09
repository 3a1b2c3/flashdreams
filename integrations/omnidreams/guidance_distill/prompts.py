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

"""Edit prompt bank (v1) for guidance self-distillation.

The weather/lighting set from ``scripts/sweep_text_edit.py`` — copied
verbatim rather than imported, because the sweep is a script with heavy
module-level setup (env reads, pipeline imports) that a constants consumer
should not execute — plus a :data:`NO_OP` entry. The no-op edit swaps to
the sampled clip's OWN prompt: the guidance combine then degenerates to
the plain flow (``kv_old == kv_new``), so its distillation target is the
unedited network — a regularizer against drift on non-edits (``PLAN.md``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EditPrompt:
    """One edit-prompt bank entry."""

    name: str
    """Stable key: names the precomputed embedding and eval report rows."""

    text: str | None
    """Prompt text; ``None`` marks the no-op entry, resolved at sample
    time to the current clip's own prompt (keyed via :func:`clip_key`)."""


def clip_key(uuid: str) -> str:
    """Return the embedding-dict key of a sample clip's own prompt.

    Args:
        uuid: ``nvidia/omni-dreams-samples`` single-view clip UUID.

    Returns:
        The key under which ``precompute_embeddings.py`` stores the clip
        prompt's text embeddings.
    """
    return f"clip:{uuid}"


# The scene bundle's own weather phrasings (training-distribution wording),
# lightly de-scene-specified — verbatim from ``scripts/sweep_text_edit.py``.
SNOW_NATIVE = (
    "A dashcam perspective from inside a vehicle driving down a wide suburban "
    "residential street during a snowstorm. The road is heavily covered in "
    "white snow with visible parallel tire tracks. Vehicles parked along the "
    "curb are coated in a layer of snow. The surrounding houses, lawns, and "
    "large trees are completely blanketed in winter snow. The sky is overcast "
    "and gray with snowflakes visibly falling. In the foreground, the bottom "
    "of the windshield and the car's hood are visible, with snow accumulating "
    "around the windshield wipers."
)
SNOW_MINE = (
    "Driving scene from a front-facing car camera at night in a heavy "
    "snowstorm. Thick snow falling, snow-covered road and buildings, "
    "headlights and streetlights glowing through the snow. Photorealistic "
    "dashcam footage."
)
RAIN_NIGHT_NATIVE = (
    "A deep night sky of dark blue and grey is heavy with persistent, visible "
    "rain streaks. The overall atmosphere is dark and thoroughly wet. An "
    "asphalt road, marked by double yellow center lines, extends into the "
    "distance, its surface completely saturated with sheeting water, creating "
    "a glossy mirror that breaks and complexifies the reflections of multiple "
    "warm-toned overhead streetlights. In the immediate lower foreground, the "
    "car's wet hood is covered with rain droplets and reflecting light."
)
FOG = (
    "A dashcam perspective of a suburban street in extremely dense fog. "
    "Visibility is very low; buildings and trees fade into a uniform white-"
    "gray haze within tens of meters. Faint silhouettes of parked cars line "
    "the curb, headlights diffuse into soft glows. Muted, desaturated colors."
)
NIGHT = (
    "A dashcam perspective of a suburban street late at night. Dark sky, the "
    "road lit by warm streetlights and the car's headlights, parked cars in "
    "shadow along the curb, illuminated house windows, deep shadows under the "
    "trees. Photorealistic night dashcam footage."
)
SUNSET = (
    "A dashcam perspective of a suburban street at golden-hour sunset. Warm "
    "orange low sun ahead near the horizon, long shadows across the road, "
    "golden light on the trees and house facades, glowing warm sky with a few "
    "pink clouds. Photorealistic dashcam footage."
)

NO_OP = EditPrompt(name="no_op", text=None)
"""Swap to the clip's own prompt: teacher == plain flow (regularizer)."""

PROMPT_BANK: tuple[EditPrompt, ...] = (
    EditPrompt(name="snow_native", text=SNOW_NATIVE),
    EditPrompt(name="snow_mine", text=SNOW_MINE),
    EditPrompt(name="rain_night", text=RAIN_NIGHT_NATIVE),
    EditPrompt(name="fog", text=FOG),
    EditPrompt(name="night", text=NIGHT),
    EditPrompt(name="sunset", text=SUNSET),
    NO_OP,
)
"""Full v1 bank: six real weather/lighting edits + the no-op entry."""

EDIT_PROMPTS: tuple[EditPrompt, ...] = tuple(
    p for p in PROMPT_BANK if p.text is not None
)
"""The real (non-no-op) edits — the entries that get precomputed embeddings."""
