# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

"""Thread-safe channel for live scene edits triggered from the UI.

The keyboard handler runs on the presenter (UI) thread, but Ludus geometry
uploads must happen on the pipeline worker thread (the one that calls
``LudusConditionRasterizer.render_chunk``). So the ``c`` hotkey only *records*
intent here (a counter, guarded by a lock); the rasterizer drains it inside
``render_chunk`` and does the actual ``add_road_cuboid`` upload on the worker,
placing the cuboid ahead of the ego pose it already has for that chunk.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_pending_cuboid_drops = 0

# Metres ahead of the current ego pose to drop the cuboid (middle of the road).
DROP_AHEAD_M = 14.0


def request_drop_cuboid() -> None:
    """Record a 'drop a cuboid ahead of the ego' request (UI thread)."""
    global _pending_cuboid_drops
    with _lock:
        _pending_cuboid_drops += 1


def take_pending_cuboid_drops() -> int:
    """Atomically read and clear the pending-drop count (worker thread)."""
    global _pending_cuboid_drops
    with _lock:
        n = _pending_cuboid_drops
        _pending_cuboid_drops = 0
    return n
