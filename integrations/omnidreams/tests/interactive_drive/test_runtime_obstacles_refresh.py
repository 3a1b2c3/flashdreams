# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

"""Unit tests for the live obstacle-refresh logic (the ``t``/``y`` keys).

These cover ``rebuild_runtime_obstacles`` -- the pure-Python core the live
refresh runs on the worker thread -- without a GPU or the world model: it must
add obstacles from the cuboids env var, hide them when the var is cleared, and
never duplicate on repeated refreshes.
"""

from __future__ import annotations

import os

from omnidreams.interactive_drive._pipeline_fakes import minimal_scene
from omnidreams.interactive_drive.runtime_obstacles import (
    ENV_VAR,
    rebuild_runtime_obstacles,
    toggle_truck_in_env,
)


def _set_env(value: str | None) -> None:
    if value is None:
        os.environ.pop(ENV_VAR, None)
    else:
        os.environ[ENV_VAR] = value


def _runtime_tracks(scene: object) -> list:
    return [
        t
        for t in scene.vehicle_bbox_tracks
        if str(t.track_id).startswith("runtime-obstacle-")
    ]


def test_rebuild_adds_obstacle_from_env() -> None:
    prev = os.environ.get(ENV_VAR)
    try:
        _set_env("30:0:truck")
        out = rebuild_runtime_obstacles(minimal_scene())
        rt = _runtime_tracks(out)
        assert len(rt) == 1
        assert rt[0].object_type == "Truck"
        # Ego starts at world (0,0) facing +X, so the box sits 30 m ahead,
        # centered on the ego's lane.
        cx, cy = float(rt[0].centers_world[0][0]), float(rt[0].centers_world[0][1])
        assert abs(cx - 30.0) < 0.5
        assert abs(cy) < 0.5
    finally:
        _set_env(prev)


def test_rebuild_hides_when_env_cleared() -> None:
    prev = os.environ.get(ENV_VAR)
    try:
        _set_env("30:0:truck")
        with_box = rebuild_runtime_obstacles(minimal_scene())
        assert len(_runtime_tracks(with_box)) == 1

        # ``y`` hide: clear the env var and rebuild from the already-injected
        # scene -> the runtime track is stripped and not re-added.
        _set_env("")
        hidden = rebuild_runtime_obstacles(with_box)
        assert len(_runtime_tracks(hidden)) == 0
    finally:
        _set_env(prev)


def test_toggle_truck_in_env() -> None:
    prev = os.environ.get(ENV_VAR)
    try:
        _set_env(None)  # start with no obstacle
        assert toggle_truck_in_env() is True  # 1st press -> show
        assert os.environ[ENV_VAR] == "30:0:truck"
        assert toggle_truck_in_env() is False  # 2nd press -> hide
        assert os.environ[ENV_VAR] == ""
        assert toggle_truck_in_env() is True  # 3rd press -> show again
        assert os.environ[ENV_VAR] == "30:0:truck"
    finally:
        _set_env(prev)


def test_toggle_visibility_end_to_end() -> None:
    """The ``t`` visibility toggle: ``toggle_truck_in_env`` flips the env, and
    ``rebuild_runtime_obstacles`` reflects it in the scene the model conditions
    on -- so the rendered obstacle appears/disappears in lockstep with each press.
    """
    prev = os.environ.get(ENV_VAR)
    try:
        _set_env(None)
        scene = minimal_scene()
        # Starts hidden.
        assert len(_runtime_tracks(rebuild_runtime_obstacles(scene))) == 0
        # Press 1 -> shown: one obstacle in the conditioned scene.
        toggle_truck_in_env()
        shown = rebuild_runtime_obstacles(scene)
        assert len(_runtime_tracks(shown)) == 1
        # Press 2 -> hidden: rebuild from the already-injected scene, obstacle gone.
        toggle_truck_in_env()
        assert len(_runtime_tracks(rebuild_runtime_obstacles(shown))) == 0
        # Press 3 -> shown again.
        toggle_truck_in_env()
        assert len(_runtime_tracks(rebuild_runtime_obstacles(scene))) == 1
    finally:
        _set_env(prev)


def test_rebuild_is_idempotent_no_duplication() -> None:
    prev = os.environ.get(ENV_VAR)
    try:
        _set_env("30:0:truck;50:0:car")
        once = rebuild_runtime_obstacles(minimal_scene())
        # Rebuild again on the already-injected scene (what repeated t/y presses
        # do): old runtime tracks are stripped first, so the count stays put.
        twice = rebuild_runtime_obstacles(once)
        assert len(_runtime_tracks(once)) == 2
        assert len(_runtime_tracks(twice)) == 2
    finally:
        _set_env(prev)
