# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

"""Shared metadata + helpers for the ``omni-dreams-scenes`` Hugging Face dataset.

Both demo paths in this package consume the same source of scene data
(the ``omni-dreams-scenes`` HF dataset at ``scenes/clipgt-<uuid>.usdz``)
but differ in what they do with it after download:

* ``omnidreams.interactive_drive`` (desktop demo) keeps the USDZ archive
  intact under ``omnidreams/interactive_drive/assets/scenes/`` and reads
  prompts / first-images out of it via ``zipfile.ZipFile``.
* ``omnidreams.webrtc.session`` extracts the USDZ into a per-uuid
  directory under ``FLASHDREAMS_CACHE_DIR/omnidreams-scenes/`` and reads
  ``clipgt/first_image.*`` + ``clipgt/prompt.txt`` directly from disk.

This module owns the pieces that *are* shared -- the dataset name, the
archive path template, the file-suffix conventions, the variant-suffix
parser (interactive-drive supports multiple prompt / first_image
variants via ``prompt_<N>.txt`` etc.; this convention is documented
here even though webrtc currently only ships single-variant scenes),
and a ``list_available_scene_uuids`` helper that walks the HF dataset.
Centralising them here keeps the two demos in lock-step on what a
"clipgt scene" looks like and what HF repo to fetch from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from omnidreams.hf_org import hf_repo


# ---------------------------------------------------------------------------
# Hugging Face dataset metadata
# ---------------------------------------------------------------------------

# Filename suffixes accepted as the scene's first-frame image. Both demo
# paths normalise to lowercase before comparison.
SCENE_IMAGE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".bmp", ".jpeg", ".jpg", ".png", ".webp"}
)

# Canonical filename for the per-scene prompt inside an extracted clipgt
# bundle. The interactive-drive demo also supports ``prompt_<N>.txt`` for
# multiple variants of the same scene (parsed via ``variant_from_stem``
# below); the webrtc session pipeline only uses the canonical name.
SCENE_PROMPT_FILENAME: Final[str] = "prompt.txt"

# Conventional subdirectory under which a USDZ archive's payload is
# unpacked by the webrtc session pipeline (``FLASHDREAMS_CACHE_DIR/
# omnidreams-scenes/<uuid>/clipgt/...``).
SCENE_CLIPGT_DIRNAME: Final[str] = "clipgt"

# Convenience link to the canonical NVIDIA-hosted dataset browser. The
# resolver below honours OMNI_DREAMS_HF_ORG when picking the actual repo
# id; this URL is intentionally fixed at ``nvidia/`` because the public
# docs always point there.
HF_DATASET_BROWSER_URL: Final[str] = (
    "https://huggingface.co/datasets/nvidia/omni-dreams-scenes/tree/main/scenes"
)


def hf_scenes_repo_id(org: str | None = None) -> str:
    """Return ``<resolved-org>/omni-dreams-scenes`` for HF lookups.

    Delegates to :func:`omnidreams.hf_org.hf_repo` so the
    ``OMNI_DREAMS_HF_ORG`` env var / ``--hf-org`` CLI flag flow through
    here too, keeping the webrtc server in lock-step with
    interactive-drive once the env var is set.
    """
    return hf_repo(kind="scenes", org=org)


def scene_archive_filename(scene_uuid: str) -> str:
    """Path inside the HF dataset for one scene's USDZ archive."""
    return f"scenes/clipgt-{scene_uuid.strip()}.usdz"


# ---------------------------------------------------------------------------
# Filename convention helpers
# ---------------------------------------------------------------------------


def variant_from_stem(stem: str, prefix: str) -> str | None:
    """Canonical scene-variant name parser.

    Maps a file *stem* (no extension) to the variant slug used by
    ``--variant`` / the HUD's variant selector. The convention, matching
    what ``nvidia/omni-dreams-scenes`` ships:

    * ``<prefix>``           -> ``"default"``  (e.g. ``prompt.txt``, ``first_image.png``)
    * ``<prefix>_<X>``       -> ``<X>``        (e.g. ``prompt_1.txt`` -> ``"1"``)
    * anything else          -> ``None``       (rejected; caller skips it)

    The trailing-suffix-without-underscore form (``prompt1.txt``,
    ``first_image1.png``) is **rejected** so the HUD's selector and the
    scene-loader's prompt dict agree on the variant key. Previously a
    naive ``stem.replace(prefix, "")`` quietly mapped ``prompt_1`` to
    ``_1`` while the HUD displayed ``1``, so the selector silently fell
    back to the default prompt on real scenes.

    Used by every discovery path that walks clipgt asset names:

    * ``omnidreams.interactive_drive.scene_loader._discover_prompts``
      and ``._discover_first_images`` (USDZ archive entries).
    * ``omnidreams.interactive_drive.demo._discover_variants``
      (HUD variant-selector dropdown).
    * ``omnidreams.interactive_drive.assets.scene_bundle._discover_prompts``
      and ``._discover_first_frames`` (unpacked scene directories).
    """
    if stem == prefix:
        return "default"
    if stem.startswith(prefix + "_"):
        return stem[len(prefix) + 1 :]
    return None


# ---------------------------------------------------------------------------
# Dataset enumeration
# ---------------------------------------------------------------------------


def list_available_scene_uuids() -> list[str]:
    """Enumerate every ``scenes/clipgt-<uuid>.usdz`` file in the HF dataset.

    Returns a sorted list of ``clipgt-<uuid>`` strings (the stem, i.e.
    no ``scenes/`` prefix or ``.usdz`` suffix). Requires ``HF_TOKEN`` to
    be set because the dataset is gated. The exact repo id is resolved
    via :func:`hf_scenes_repo_id`, so the function honours
    ``OMNI_DREAMS_HF_ORG`` / the ``--hf-org`` CLI flag.

    Imported lazily by callers (e.g. ``interactive-drive-prepare``) so
    the ``huggingface_hub`` dependency only matters when this function
    is actually used.
    """
    try:
        from huggingface_hub import HfApi
    except Exception as exc:  # pragma: no cover - huggingface_hub must be installed
        raise RuntimeError(
            "Unable to import huggingface_hub.HfApi; run "
            "`uv sync --package flashdreams-omnidreams` from the flashdreams "
            "workspace root first."
        ) from exc

    repo_id = hf_scenes_repo_id()
    files = HfApi().list_repo_files(repo_id=repo_id, repo_type="dataset")
    prefix = "scenes/"
    suffix = ".usdz"
    uuids = [
        path[len(prefix) : -len(suffix)]
        for path in files
        if path.startswith(prefix) and path.endswith(suffix)
    ]
    return sorted(uuids)


def hf_hub_download_scene(scene_uuid: str) -> Path:
    """Download one scene's USDZ archive from the resolved HF dataset.

    Returns the local cache path (from ``huggingface_hub``'s default
    cache, typically ``~/.cache/huggingface/hub/...``). Callers are
    responsible for copying / extracting that file into wherever they
    actually consume it from -- ``interactive_drive.prepare`` copies it
    into the package's ``assets/scenes/`` dir, while
    ``omnidreams.webrtc.session`` extracts it under
    ``FLASHDREAMS_CACHE_DIR``. Returning the cached archive lets each
    caller own its post-download policy.
    """
    try:
        from huggingface_hub import hf_hub_download
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Unable to import huggingface_hub; run "
            "`uv sync --package flashdreams-omnidreams` from the flashdreams "
            "workspace root first."
        ) from exc

    cached = hf_hub_download(
        repo_id=hf_scenes_repo_id(),
        repo_type="dataset",
        filename=scene_archive_filename(scene_uuid),
    )
    return Path(cached)
