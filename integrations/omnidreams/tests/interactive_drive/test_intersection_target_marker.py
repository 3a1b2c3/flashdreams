# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

"""Placement tests for the test-marker goal (viewport cylinder + BEV dot).

``_find_first_intersection_world`` pins the goal a fixed distance straight
ahead of spawn when ``IDRIVE_TEST_MARKER_AHEAD_M`` is unset/positive (default
50 m), and falls back to the real intersection search when it is 0. The method
reads only ``scene`` + the env var (never ``self``), so we exercise it on a
bare ``__new__`` instance with a hand-built spawn pose -- no GPU/ludus build.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest
from omnidreams.interactive_drive.rasterizer import _LudusConditionRasterizerImpl


def _scene(rig_to_world: np.ndarray) -> SimpleNamespace:
    # polygon_layers is only read on the env==0 fallback path; empty is fine.
    return SimpleNamespace(initial_rig_to_world=rig_to_world, polygon_layers=[])


def _pose(spawn: tuple[float, float, float], yaw_deg: float = 0.0) -> np.ndarray:
    """4x4 rig->world: column 0 is the rig forward (+X) axis in world xy."""
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    m = np.eye(4, dtype=np.float32)
    m[:2, 0] = (c, s)        # forward (rig +X)
    m[:2, 1] = (-s, c)       # left (rig +Y)
    m[:3, 3] = spawn         # spawn translation
    return m


def _call(scene: SimpleNamespace) -> tuple[float, float, float]:
    impl = _LudusConditionRasterizerImpl.__new__(_LudusConditionRasterizerImpl)
    return impl._find_first_intersection_world(scene)


def test_default_pins_50m_straight_ahead(monkeypatch) -> None:
    monkeypatch.delenv("IDRIVE_TEST_MARKER_AHEAD_M", raising=False)
    target = _call(_scene(_pose((10.0, 20.0, 1.0))))  # forward = +X
    assert target is not None
    assert target == pytest.approx((60.0, 20.0, 1.0))  # 50 m ahead along +X


def test_marker_follows_spawn_heading(monkeypatch) -> None:
    monkeypatch.delenv("IDRIVE_TEST_MARKER_AHEAD_M", raising=False)
    # Yaw 90deg: rig forward now points along world +Y, so the goal is 50 m +Y.
    target = _call(_scene(_pose((10.0, 20.0, 1.0), yaw_deg=90.0)))
    assert target == pytest.approx((10.0, 70.0, 1.0))


def test_env_overrides_distance(monkeypatch) -> None:
    monkeypatch.setenv("IDRIVE_TEST_MARKER_AHEAD_M", "120")
    target = _call(_scene(_pose((0.0, 0.0, 0.0))))
    assert target == pytest.approx((120.0, 0.0, 0.0))


def test_env_zero_falls_back_to_intersection_search(monkeypatch) -> None:
    # 0 disables the test marker; with no intersection polygons the real
    # search returns None (no goal) rather than a fixed-distance point.
    monkeypatch.setenv("IDRIVE_TEST_MARKER_AHEAD_M", "0")
    assert _call(_scene(_pose((5.0, 5.0, 0.0)))) is None
