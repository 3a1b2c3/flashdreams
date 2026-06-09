# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

from __future__ import annotations

import os
import sys

from loguru import logger

_LOG_FORMAT = "{time:HH:mm:ss.SSS} | {level:<7} | {message}"


def configure_logging() -> None:
    """Use compact Loguru output for interactive-drive CLI sessions."""
    logger.remove()
    level = os.environ.get("LOGURU_LEVEL", "INFO")
    logger.add(
        sys.stderr,
        level=level,
        format=_LOG_FORMAT,
    )
    # Opt-in file sink (IDRIVE_LOG_FILE=path) so the session log can be tailed
    # without shell stderr redirection (PowerShell mangles native-exe stderr).
    log_file = os.environ.get("IDRIVE_LOG_FILE")
    if log_file:
        logger.add(log_file, level=level, format=_LOG_FORMAT, enqueue=True)
