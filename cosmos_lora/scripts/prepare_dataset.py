#!/usr/bin/env python
"""Build and validate a Cosmos LoRA dataset (datasets/videos + datasets/metas)."""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

RESOLUTION = (1280, 720)  # width, height, 720p per README
FPS = 24
DURATION_S = 4
FRAME_COUNT = FPS * DURATION_S

SAMPLE_SHAPES = [
    {"name": "video1", "color_bgr": (180, 180, 40), "color_name": "teal", "shape": "circle", "path": "left-to-right"},
    {"name": "video2", "color_bgr": (60, 60, 220), "color_name": "red", "shape": "square", "path": "top-to-bottom"},
    {"name": "video3", "color_bgr": (60, 200, 60), "color_name": "green", "shape": "triangle", "path": "diagonal"},
    {"name": "video4", "color_bgr": (200, 120, 40), "color_name": "blue", "shape": "circle", "path": "circular"},
]


def _position(path, frame_idx, width, height, margin=120):
    t = frame_idx / (FRAME_COUNT - 1)
    if path == "left-to-right":
        return int(margin + t * (width - 2 * margin)), height // 2
    if path == "top-to-bottom":
        return width // 2, int(margin + t * (height - 2 * margin))
    if path == "diagonal":
        return int(margin + t * (width - 2 * margin)), int(margin + t * (height - 2 * margin))
    if path == "circular":
        cx, cy, r = width // 2, height // 2, min(width, height) // 3
        angle = t * 2 * np.pi
        return int(cx + r * np.cos(angle)), int(cy + r * np.sin(angle))
    raise ValueError(f"unknown path: {path}")


def _draw_shape(frame, shape, center, color_bgr, size=60):
    x, y = center
    if shape == "circle":
        cv2.circle(frame, (x, y), size, color_bgr, thickness=-1)
    elif shape == "square":
        cv2.rectangle(frame, (x - size, y - size), (x + size, y + size), color_bgr, thickness=-1)
    elif shape == "triangle":
        pts = np.array(
            [[x, y - size], [x - size, y + size], [x + size, y + size]],
            dtype=np.int32,
        )
        cv2.fillPoly(frame, [pts], color_bgr)
    else:
        raise ValueError(f"unknown shape: {shape}")


def make_synthetic_video(out_path, color_bgr, shape, path, background_bgr=(30, 30, 30)):
    width, height = RESOLUTION
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, FPS, (width, height))
    try:
        for frame_idx in range(FRAME_COUNT):
            frame = np.full((height, width, 3), background_bgr, dtype=np.uint8)
            center = _position(path, frame_idx, width, height)
            _draw_shape(frame, shape, center, color_bgr)
            writer.write(frame)
    finally:
        writer.release()


def create_sample_dataset(data_dir: Path, prompt_override: str = None):
    videos_dir = data_dir / "videos"
    metas_dir = data_dir / "metas"
    videos_dir.mkdir(parents=True, exist_ok=True)
    metas_dir.mkdir(parents=True, exist_ok=True)

    for spec in SAMPLE_SHAPES:
        video_path = videos_dir / f"{spec['name']}.mp4"
        make_synthetic_video(video_path, spec["color_bgr"], spec["shape"], spec["path"])

        if prompt_override:
            prompt = prompt_override
        else:
            prompt = (
                f"A video of a {spec['color_name']} {spec['shape']} moving "
                f"{spec['path'].replace('-', ' ')} against a dark background. "
                "High quality, cinematic lighting."
            )
        (metas_dir / f"{spec['name']}.txt").write_text(prompt + "\n", encoding="utf-8")
        print(f"Wrote {video_path} ({FRAME_COUNT} frames @ {FPS}fps) and matching prompt")

    sample_prompts_path = metas_dir / "sample_prompts.txt"
    sample_prompts_path.write_text(
        "\n".join(
            f"{spec['name']}.mp4: A video of a {spec['color_name']} {spec['shape']} "
            f"moving {spec['path'].replace('-', ' ')} against a dark background. "
            "High quality, cinematic lighting."
            for spec in SAMPLE_SHAPES
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {sample_prompts_path}")


def apply_prompt_template(data_dir: Path, prompt: str):
    videos_dir = data_dir / "videos"
    metas_dir = data_dir / "metas"
    metas_dir.mkdir(parents=True, exist_ok=True)

    videos = sorted(videos_dir.glob("*.mp4"))
    if not videos:
        print(f"No videos found in {videos_dir}", file=sys.stderr)
        return 1

    for video_path in videos:
        meta_path = metas_dir / f"{video_path.stem}.txt"
        meta_path.write_text(prompt + "\n", encoding="utf-8")
        print(f"Wrote {meta_path}")
    return 0


def validate_dataset(data_dir: Path) -> bool:
    videos_dir = data_dir / "videos"
    metas_dir = data_dir / "metas"

    if not videos_dir.is_dir():
        print(f"Missing directory: {videos_dir}")
        return False
    if not metas_dir.is_dir():
        print(f"Missing directory: {metas_dir}")
        return False

    videos = sorted(videos_dir.glob("*.mp4"))
    prompts = {p.stem for p in metas_dir.glob("*.txt") if p.stem != "sample_prompts"}

    print(f"Found {len(videos)} videos")
    print(f"Found {len(prompts)} prompt files")

    ok = True
    if len(videos) < 4:
        print(f"WARNING: minimum recommended is 4-5 videos, found {len(videos)}")

    for video_path in videos:
        if video_path.stem not in prompts:
            print(f"MISSING prompt for {video_path.name} (expected metas/{video_path.stem}.txt)")
            ok = False
            continue
        meta_path = metas_dir / f"{video_path.stem}.txt"
        if not meta_path.read_text(encoding="utf-8").strip():
            print(f"EMPTY prompt file: {meta_path}")
            ok = False

    if ok and videos:
        print("✓ Dataset is valid")
    elif not videos:
        print("No videos found - nothing to validate")
        ok = False
    else:
        print("✗ Dataset is invalid")

    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("datasets"))
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Generate 4 synthetic MP4 clips + matching prompts under --data-dir",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Write this prompt to a metas/<name>.txt file for every existing video in --data-dir/videos",
    )
    parser.add_argument("--validate", action="store_true", help="Check that every video has a matching prompt file")
    args = parser.parse_args()

    if not any([args.create_sample, args.prompt, args.validate]):
        parser.error("one of --create-sample, --prompt, or --validate is required")

    if args.create_sample:
        create_sample_dataset(args.data_dir, prompt_override=None)

    if args.prompt and not args.create_sample:
        rc = apply_prompt_template(args.data_dir, args.prompt)
        if rc:
            return rc

    if args.validate:
        return 0 if validate_dataset(args.data_dir) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
