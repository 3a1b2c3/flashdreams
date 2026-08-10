# SPDX-License-Identifier: Apache-2.0
"""Runtime obstacle injection for OmniDreams interactive-drive.

Place 3D boxes (cars / trucks / pedestrians / cyclists) on the map WITHOUT
editing the scene's ``clipgt/obstacle.parquet``. Obstacles are already a
first-class, per-frame-rendered part of a scene (``SceneBundle.vehicle_bbox_tracks``,
each a :class:`WorldVehicleBBoxTrack` that ``render_chunk`` interpolates every
frame), so "adding a box" is just building a track and appending it to the
(frozen) bundle via :func:`dataclasses.replace`.

Two entry points:
  * :func:`boxes_from_env` + :func:`inject_into_bundle` -- seed boxes at scene
    load from the ``IDRIVE_ROAD_CUBOIDS_AHEAD`` env var (the previously-unwired
    launcher knob), e.g. ``IDRIVE_ROAD_CUBOIDS_AHEAD="30:-2:car;60:3:truck"``.
  * :func:`inject_into_bundle` with a programmatic ``[RuntimeBox(...)]`` -- used
    by a runtime keypress ("drop a box ahead of the ego").

Placement is relative to the ego START pose (``initial_rig_to_world`` /
``initial_yaw_rad``), converted to the scene's WORLD frame.

TWO ASSUMPTIONS to confirm on first launch with a box (both easy to flip if the
box lands wrong):
  1. Ego heading: forward = ``(cos(initial_yaw_rad), sin(initial_yaw_rad))`` in
     world XY (yaw about +Z, 0 == +X). If the box shows up behind/beside the
     ego, the yaw convention differs -- adjust ``_forward_left``.
  2. Ground height: box center z = ``ground_z + height/2`` with ``ground_z``
     defaulting to 0 (matching the parquet convention where obstacle centers are
     absolute world z ~= half-height). If boxes float/sink, set ``ground_z``.
"""
from __future__ import annotations

import dataclasses
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from omnidreams.interactive_drive.types import SceneBundle, WorldVehicleBBoxTrack

ENV_VAR = "IDRIVE_ROAD_CUBOIDS_AHEAD"

# category -> (default size (length, width, height) m, bbox object_type for color).
# object_type must be one of _VALID_BBOX_TYPES or it falls back to "Others".
_CATEGORY_DEFAULTS: dict[str, tuple[tuple[float, float, float], str]] = {
    "car": ((4.7, 2.0, 1.6), "Car"),
    "truck": ((9.0, 2.6, 3.5), "Truck"),
    "pedestrian": ((0.6, 0.6, 1.8), "Pedestrian"),
    "ped": ((0.6, 0.6, 1.8), "Pedestrian"),
    "cyclist": ((1.8, 0.6, 1.6), "Cyclist"),
}
_DEFAULT_CATEGORY = "car"
_VALID_BBOX_TYPES = {"Car", "Truck", "Pedestrian", "Cyclist", "Others"}

# BEV object_type (color bucket) -> a REAL clipgt obstacle category string. The
# model conditions on the rasterized clipgt cubes, whose color/type comes from
# ``CATEGORY_TO_OBJECT_TYPE`` (ludus_renderer.clipgt): only these lowercase
# category strings map to a recognised vehicle/person type; anything else falls
# to 'Other'. So the parquet MUST carry a real category, not "Car"/"Truck".
_BBOX_TYPE_TO_CLIPGT_CATEGORY: dict[str, str] = {
    "Car": "automobile",
    "Truck": "heavy_truck",
    "Pedestrian": "person",
    "Cyclist": "bicycle",
    "Others": "automobile",
}

# A static box present for the whole rollout: two identical samples spanning a
# wide window around the scene start, with generous extrapolation, so
# ``interpolate_at_timestamp`` resolves at every render frame regardless of how
# far the rollout advances.
_WINDOW_US = 600_000_000  # +/- 600 s around scene start
_MAX_EXTRAPOLATION_US = 600_000_000.0


@dataclasses.dataclass(frozen=True)
class RuntimeBox:
    """A box to drop, positioned relative to the ego start pose."""

    ahead_m: float = 30.0
    lateral_m: float = 0.0  # +left, -right (world XY, relative to ego heading)
    category: str = _DEFAULT_CATEGORY
    yaw_deg: float = 0.0  # box heading relative to the ego heading
    size_lwh: tuple[float, float, float] | None = None  # override category default
    ground_z: float = 0.0  # world z of the ground plane under the box


def _yaw_to_quat_xyzw(yaw_rad: float) -> list[float]:
    """Quaternion (x, y, z, w) for a rotation of ``yaw_rad`` about world +Z."""
    half = 0.5 * yaw_rad
    return [0.0, 0.0, math.sin(half), math.cos(half)]


def _forward_left(yaw_rad: float) -> tuple[np.ndarray, np.ndarray]:
    """World-XY forward and left unit vectors for an ego heading of ``yaw_rad``.

    Forward = ``(cos, sin)`` (world +X at yaw=0, which is "up" on the north-up BEV
    and the ego arrow's direction), left = ``(-sin, cos)``. Verified from the
    debug log: ego arrow points +X, so boxes at +X land ahead.
    """
    fwd = np.array([math.cos(yaw_rad), math.sin(yaw_rad), 0.0])
    left = np.array([-math.sin(yaw_rad), math.cos(yaw_rad), 0.0])
    return fwd, left


def build_box_track(bundle: SceneBundle, box: RuntimeBox, track_id: str) -> WorldVehicleBBoxTrack:
    """Build a static :class:`WorldVehicleBBoxTrack` for ``box`` ahead of the ego."""
    ego_world = np.asarray(bundle.initial_rig_to_world, dtype=np.float64)[:3, 3].copy()
    yaw = float(bundle.initial_yaw_rad)
    fwd, left = _forward_left(yaw)

    size, cat_type = _CATEGORY_DEFAULTS.get(
        box.category.strip().lower(), _CATEGORY_DEFAULTS[_DEFAULT_CATEGORY]
    )
    size = tuple(box.size_lwh) if box.size_lwh else size
    object_type = cat_type if cat_type in _VALID_BBOX_TYPES else "Others"

    center = ego_world + box.ahead_m * fwd + box.lateral_m * left
    center[2] = box.ground_z + 0.5 * float(size[2])
    quat = _yaw_to_quat_xyzw(yaw + math.radians(box.yaw_deg))

    t_mid = int(bundle.initial_timestamp_us)
    timestamps = np.asarray([t_mid - _WINDOW_US, t_mid + _WINDOW_US], dtype=np.int64)
    print(
        f"[runtime-obstacle] {track_id} {object_type}: ego=({ego_world[0]:.1f},{ego_world[1]:.1f}) "
        f"yaw={math.degrees(yaw):.0f}deg  ahead={box.ahead_m} lateral={box.lateral_m}  "
        f"-> box_center=({center[0]:.1f},{center[1]:.1f},{center[2]:.1f})  fwd=({fwd[0]:.2f},{fwd[1]:.2f})",
        flush=True,
    )
    return WorldVehicleBBoxTrack(
        track_id=track_id,
        object_type=object_type,
        timestamps_us=timestamps,
        centers_world=np.asarray([center, center], dtype=np.float32),
        dimensions_lwh=np.asarray([size, size], dtype=np.float32),
        orientations_xyzw=np.asarray([quat, quat], dtype=np.float32),
        max_extrapolation_us=_MAX_EXTRAPOLATION_US,
    )


def inject_into_bundle(bundle: SceneBundle, boxes: list[RuntimeBox]) -> SceneBundle:
    """Return a new bundle with ``boxes`` appended to ``vehicle_bbox_tracks``.

    The bundle is frozen, so this replaces it; the extra tracks render every
    frame exactly like scene-authored obstacles. Returns ``bundle`` unchanged
    when ``boxes`` is empty.
    """
    if not boxes:
        return bundle
    tracks = list(bundle.vehicle_bbox_tracks)
    base = len(tracks)
    for i, box in enumerate(boxes):
        tracks.append(build_box_track(bundle, box, track_id=f"runtime-obstacle-{base + i:03d}"))
    return dataclasses.replace(bundle, vehicle_bbox_tracks=tuple(tracks))


def drop_truck_into_env(base_ahead: float = 30.0, step_m: float = 12.0) -> str:
    """Append a truck to :data:`ENV_VAR`, spaced past any existing boxes.

    Shared by the native HUD (``t`` key) and the streaming/browser control
    handler so both drop the same accumulating trucks (30 m, then 42 m, ...).
    Returns the ``ahead:lateral:category`` spec that was appended.
    """
    existing = (os.environ.get(ENV_VAR) or "").strip().strip(";")
    count = (existing.count(";") + 1) if existing else 0
    spec = f"{base_ahead + step_m * count:g}:0:truck"
    os.environ[ENV_VAR] = f"{existing};{spec}" if existing else spec
    return spec


def toggle_truck_in_env(spec: str = "30:0:truck") -> bool:
    """Toggle a single truck in :data:`ENV_VAR`.

    Shows ``spec`` if the env var is currently empty, hides (clears) it if set.
    Shared by the ``t`` key in the native HUD and the streaming control handler.
    Returns True if the truck is now shown, False if hidden.
    """
    if (os.environ.get(ENV_VAR) or "").strip():
        os.environ[ENV_VAR] = ""
        return False
    os.environ[ENV_VAR] = spec
    return True


def rebuild_runtime_obstacles(scene: SceneBundle) -> SceneBundle:
    """Return ``scene`` with its runtime obstacle tracks rebuilt from the CURRENT
    :data:`ENV_VAR` value.

    Strips any existing ``runtime-obstacle-*`` tracks, then re-injects from
    :func:`boxes_from_env`. Used by the live-refresh path (the ``t``/``y`` keys):
    a keypress mutates ``IDRIVE_ROAD_CUBOIDS_AHEAD`` and the rasterizer re-reads
    the resulting tracks WITHOUT a full scene reload. An empty env var yields no
    runtime tracks (obstacles hidden). Idempotent -- old runtime tracks are
    always stripped first, so repeated refreshes never duplicate.
    """
    base_tracks = tuple(
        t
        for t in scene.vehicle_bbox_tracks
        if not str(getattr(t, "track_id", "")).startswith("runtime-obstacle-")
    )
    base = dataclasses.replace(scene, vehicle_bbox_tracks=base_tracks)
    return inject_into_bundle(base, boxes_from_env())


def parse_boxes(spec: str) -> list[RuntimeBox]:
    """Parse ``IDRIVE_ROAD_CUBOIDS_AHEAD``-style spec into :class:`RuntimeBox` list.

    Format: semicolon-separated boxes; each box is
    ``ahead[:lateral[:category[:yaw_deg]]]`` (missing fields use defaults).
    Examples:
      "30"                     -> one car 30 m ahead, centered
      "30:-2:car;60:3:truck"   -> car 30 m ahead 2 m right; truck 60 m ahead 3 m left
      "15:0:pedestrian"        -> pedestrian 15 m ahead
    Whitespace and empty entries are ignored; unparseable entries are skipped.
    """
    boxes: list[RuntimeBox] = []
    for entry in spec.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        parts = [p.strip() for p in entry.split(":")]
        try:
            ahead = float(parts[0])
            lateral = float(parts[1]) if len(parts) > 1 and parts[1] else 0.0
            category = parts[2] if len(parts) > 2 and parts[2] else _DEFAULT_CATEGORY
            yaw_deg = float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
        except (ValueError, IndexError):
            continue
        boxes.append(RuntimeBox(ahead_m=ahead, lateral_m=lateral, category=category, yaw_deg=yaw_deg))
    return boxes


def boxes_from_env(environ: dict[str, str] | None = None) -> list[RuntimeBox]:
    """Read :data:`ENV_VAR` from ``environ`` (default ``os.environ``) -> boxes.

    Empty/unset -> ``[]`` (no-op), so the load hook is free to always call this.
    """
    env = os.environ if environ is None else environ
    spec = (env.get(ENV_VAR) or "").strip()
    return parse_boxes(spec) if spec else []


def append_runtime_obstacles_to_clipgt(clipgt_dir, tracks) -> int:
    """Append runtime-injected obstacle tracks to the extracted clipgt
    ``obstacle.parquet`` so the rasterizer's ClipGT GPU scene (and thus the model
    conditioning) includes them.

    The model only conditions on obstacles read from this parquet -- NOT from
    ``SceneBundle.vehicle_bbox_tracks`` (which only the HUD/BEV overlay reads). So
    boxes injected via :func:`inject_into_bundle` must also be written here or the
    model never sees them. Idempotent per load: the rasterizer extracts a fresh
    clipgt dir each ``load_scene``.

    THREE things the parquet format requires (each one, if wrong, silently drops
    the box from the render):
      1. **Timestamps must land on the clip's real grid.** ``_obstacles_to_pool``
         builds its global timeline from ``unique(all obstacle timestamps)`` and
         the GPU cube is only active at timestamps it actually has a sample for.
         A box sampled at ``t0 +/- 600s`` (outside the ~1..101 s clip window)
         never coincides with a rendered frame -> invisible. So we write the box
         at EVERY unique timestamp already present in the parquet (the exact grid
         the model conditions on), holding it static.
      2. **Category must be a real clipgt category string** ("automobile",
         "heavy_truck", "person", ...). ``CATEGORY_TO_OBJECT_TYPE`` maps only
         those to a vehicle/person colour; "Car"/"Truck" (the BEV type) fall to
         'Other'. We map the track's ``object_type`` via
         :data:`_BBOX_TYPE_TO_CLIPGT_CATEGORY`.
      3. **Struct schema must match** the existing rows or ``to_parquet`` fails to
         unify the ``obstacle`` struct. We copy a base obstacle row and override
         only ``trackline_id/center/size/orientation/category``.

    Returns the number of obstacle tracks appended. Best-effort: logs and returns 0
    on any failure rather than breaking scene load.
    """
    runtime = [t for t in tracks if str(getattr(t, "track_id", "")).startswith("runtime-obstacle-")]
    if not runtime:
        return 0
    try:
        d = Path(clipgt_dir)
        pq_path = d / "obstacle.parquet"
        if not pq_path.exists():
            cands = list(d.glob("*obstacle*.parquet"))
            pq_path = cands[0] if cands else pq_path
        if not pq_path.exists():
            logger.warning(f"[runtime-obstacle] no obstacle parquet under {d}; skipping append")
            return 0
        existing = pd.read_parquet(pq_path)
        if len(existing) == 0:
            logger.warning("[runtime-obstacle] obstacle parquet empty; skipping append")
            return 0

        # Clip metadata + real timestamp grid, straight from the existing rows.
        base_key = dict(existing.iloc[0]["key"])
        base_obs = dict(existing.iloc[0]["obstacle"])
        clip_id = base_key.get("clip_id", "runtime-clip")
        label_class_id = base_key.get("label_class_id", "scene:obstacles:autolabels:v2")
        grid = sorted({int(k["timestamp_micros"]) for k in existing["key"]})

        rows = []
        summary = []
        for t in runtime:
            c = t.centers_world[0]
            s = t.dimensions_lwh[0]
            q = t.orientations_xyzw[0]
            category = _BBOX_TYPE_TO_CLIPGT_CATEGORY.get(str(t.object_type), "automobile")
            center = {"x": float(c[0]), "y": float(c[1]), "z": float(c[2])}
            size = {"x": float(s[0]), "y": float(s[1]), "z": float(s[2])}
            orient = {"x": float(q[0]), "y": float(q[1]), "z": float(q[2]), "w": float(q[3])}
            for ts in grid:
                obs = dict(base_obs)  # inherit every extra field + its type
                obs.update(
                    trackline_id=str(t.track_id),
                    center=center,
                    size=size,
                    orientation=orient,
                    category=category,
                )
                key = dict(base_key)
                key.update(
                    clip_id=clip_id,
                    timestamp_micros=int(ts),
                    label_class_id=label_class_id,
                    label_id=f"{t.track_id}:{ts}",
                )
                rows.append({"key": key, "obstacle": obs, "version": 1})
            summary.append(f"{t.track_id}={category}@({center['x']:.1f},{center['y']:.1f})")

        new_df = pd.DataFrame(rows)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined.to_parquet(pq_path)
        logger.info(
            f"[runtime-obstacle] appended {len(runtime)} box(es) x {len(grid)} grid samples "
            f"({len(rows)} rows) -> {pq_path.name}  [{', '.join(summary)}]  "
            f"grid=[{grid[0]}..{grid[-1]}]us"
        )
        return len(runtime)
    except Exception as exc:  # noqa: BLE001 - never break scene load over an overlay box
        logger.warning(f"[runtime-obstacle] failed to append to clipgt obstacle.parquet: {exc}")
        return 0
