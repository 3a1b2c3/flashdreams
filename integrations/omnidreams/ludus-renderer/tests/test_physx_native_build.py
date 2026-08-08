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

"""CPU-only contracts for the first-use PhysX CMake build."""

from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from ludus_renderer import _physx_native

pytestmark = pytest.mark.ci_cpu


def test_load_native_physx_runs_cmake_path_once_per_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module_path = tmp_path / "ludus_physx_native.pyd"
    module_path.touch()
    loaded_module = ModuleType(_physx_native._MODULE_NAME)
    configure_calls: list[tuple[Path, Path]] = []

    @contextmanager
    def fake_build_lock(cache_root: Path) -> Any:
        yield

    def fake_configure(cache_root: Path, physx_root: Path) -> Path:
        configure_calls.append((cache_root, physx_root))
        return module_path

    loader = SimpleNamespace(exec_module=lambda module: None)
    spec = SimpleNamespace(loader=loader)
    monkeypatch.setattr(_physx_native, "_CACHED_MODULE", None)
    monkeypatch.setattr(_physx_native, "_cache_root", lambda: tmp_path)
    monkeypatch.setattr(_physx_native, "_build_lock", fake_build_lock)
    monkeypatch.setattr(
        _physx_native, "_download_source", lambda cache_root: tmp_path / "physx"
    )
    monkeypatch.setattr(_physx_native, "_configure_and_build", fake_configure)
    monkeypatch.setattr(
        _physx_native.importlib.util,
        "spec_from_file_location",
        lambda name, path: spec,
    )
    monkeypatch.setattr(
        _physx_native.importlib.util,
        "module_from_spec",
        lambda loaded_spec: loaded_module,
    )
    monkeypatch.delitem(
        _physx_native.sys.modules, _physx_native._MODULE_NAME, raising=False
    )

    first = _physx_native.load_native_physx()
    second = _physx_native.load_native_physx()

    assert first is loaded_module
    assert second is loaded_module
    assert configure_calls == [(tmp_path, tmp_path / "physx")]


def test_configure_and_build_delegates_freshness_to_cmake(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    existing_module = tmp_path / "module" / "ludus_physx_native.pyd"
    existing_module.parent.mkdir()
    existing_module.touch()
    commands: list[list[str]] = []

    monkeypatch.setattr(_physx_native.shutil, "which", lambda command: "cmake")
    monkeypatch.setattr(
        _physx_native,
        "_module_path",
        lambda output_dir: existing_module,
    )
    monkeypatch.setattr(
        _physx_native.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command),
    )

    result = _physx_native._configure_and_build(tmp_path, tmp_path / "physx")

    assert result == existing_module
    assert len(commands) == 2
    assert commands[0][:2] == ["cmake", "-S"]
    assert "-B" in commands[0]
    assert commands[1][:2] == ["cmake", "--build"]
    assert "--target" in commands[1]
    assert _physx_native._MODULE_NAME in commands[1]
