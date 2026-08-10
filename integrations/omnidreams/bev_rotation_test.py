#!/usr/bin/env python3
"""Headless BEV rotation/translation test.

Loads the scene + Ludus rasterizer ONCE, renders the top-down BEV at several
poses, saves each PNG, and reports the pixel-diff vs the yaw=0 baseline. This
isolates whether the rendered map actually responds to yaw (rotation) and x/y
(translation) -- i.e. whether the rig pose reaches the BEV camera.

Run with the native-Windows venv (real Vulkan):
  C:\\workspace\\world\\flashdream_public\\.venv\\Scripts\\python.exe bev_rotation_test.py
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from omnidreams.interactive_drive.config import AppConfig, BevConfig
from omnidreams.interactive_drive.rasterizer import LudusConditionRasterizer
from omnidreams.interactive_drive.scene_loader import load_scene_bundle
from omnidreams.interactive_drive.math3d import rig_pose_from_state
from omnidreams.scenes import scenes_cache_root

OUT = Path(r"C:\tmp\bevtest_t0")   # tilt=0 (pure top-down, ego-centered)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # "default" does NOT normalise to the real UUID, so glob the staged base
    # scene (clipgt-<uuid>.usdz, excluding -rain/-snow) from the scenes cache.
    root = Path(scenes_cache_root())
    cands = sorted(p for p in root.glob("clipgt-*.usdz")
                   if "-rain" not in p.name and "-snow" not in p.name)
    if not cands:
        print("SCENE_MISSING in", root)
        return 1
    scene_path = cands[0]
    print("scene:", scene_path)

    cfg = AppConfig(scene_path=scene_path)
    bundle = load_scene_bundle(
        scene_path=scene_path,
        camera_name=cfg.camera_name,
        variant="default",
        prompt_override=None,
        raster=cfg.raster,
    )
    raster = LudusConditionRasterizer(cfg.raster, bev=BevConfig(tilt_deg=0.0))
    raster.load_scene(bundle)

    def render(x, y, yaw):
        pose = rig_pose_from_state(x_m=float(x), y_m=float(y), z_m=0.0,
                                   yaw_rad=math.radians(yaw))
        chunk = raster.render_chunk(
            np.array([pose], dtype=np.float32), np.array([0], dtype=np.int64)
        )
        f = chunk.frames[0]
        return None if f.bev_host_uint8 is None else np.asarray(f.bev_host_uint8)

    poses = [
        ("yaw000", 0, 0, 0), ("yaw090", 0, 0, 90), ("yaw180", 0, 0, 180),
        ("posX+20", 20, 0, 0), ("posY+20", 0, 20, 0),
    ]
    imgs = {}
    for name, x, y, yaw in poses:
        a = render(x, y, yaw)
        if a is None:
            print("NO_FRAME:", name)
            continue
        imgs[name] = a
        Image.fromarray(a, "RGB").save(OUT / f"{name}.png")
        print("saved", name, a.shape)

    def pct_changed(a, b):
        if a is None or b is None or a.shape != b.shape:
            return -1.0
        return float(np.mean(np.abs(a.astype(int) - b.astype(int)) > 8) * 100.0)

    base = imgs.get("yaw000")
    print("=== % pixels changed vs yaw000 ===")
    for k in ("yaw090", "yaw180", "posX+20", "posY+20"):
        print(f"  {k:8s}: {pct_changed(base, imgs.get(k)):6.1f}%")
    print("INTERPRET: yaw090/yaw180 high => map ROTATES with heading; "
          "posX/posY high => map PANS with position; ~0 => that input is IGNORED.")
    print("OUT_DIR:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
