# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Compatibility exports for camera controls now owned by ``cam2v``."""

try:
    from cam2v.controls import CameraPoseIntegrator, KeyboardResampler, PoseSegment
except (ImportError, AttributeError):
    CameraPoseIntegrator = None
    KeyboardResampler = None
    PoseSegment = None

__all__ = ["CameraPoseIntegrator", "KeyboardResampler", "PoseSegment"]
