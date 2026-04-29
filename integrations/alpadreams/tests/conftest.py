from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_SCENE_ZIP = REPO_ROOT / "assets" / "example_data" / "alpadreams" / "clipgt.zip"


@pytest.fixture(scope="session")
def example_scene_zip_path() -> Path:
    if not EXAMPLE_SCENE_ZIP.exists():
        raise FileNotFoundError(
            f"Missing integration-test scene archive at {EXAMPLE_SCENE_ZIP}."
        )
    return EXAMPLE_SCENE_ZIP


@pytest.fixture(scope="session")
def example_scene_zip_bytes(example_scene_zip_path: Path) -> bytes:
    return example_scene_zip_path.read_bytes()
