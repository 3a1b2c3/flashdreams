# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Compatibility exports for camera controls now owned by ``cam2v``."""

try:
    from cam2v.controls import CameraPoseIntegrator, KeyboardResampler, PoseSegment
except (ImportError, ModuleNotFoundError, AttributeError):
    class CameraPoseIntegrator:
        def __init__(self):
            pass
        def reset(self):
            pass
        def step(self, *args, **kwargs):
            pass
        def apply(self, *args, **kwargs):
            pass
    class KeyboardResampler:
        def __init__(self):
            pass
        def step(self, *args, **kwargs):
            pass
    class PoseSegment:
        pass

__all__ = ["CameraPoseIntegrator", "KeyboardResampler", "PoseSegment"]
