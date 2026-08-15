#!/usr/bin/env python3
"""Prepare video dataset for Cosmos LoRA training."""

import argparse
import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_prompt_file(video_path: Path, prompt: str, output_dir: Path):
    """Create prompt text file for a video."""
    txt_file = output_dir / f"{video_path.stem}.txt"
    with open(txt_file, "w") as f:
        f.write(prompt)
    logger.info(f"Created prompt file: {txt_file}")


def validate_dataset(data_dir: Path):
    """Validate dataset structure."""
    videos_dir = data_dir / "videos"
    metas_dir = data_dir / "metas"

    if not videos_dir.exists():
        raise FileNotFoundError(f"Videos directory not found: {videos_dir}")

    if not metas_dir.exists():
        metas_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created metas directory: {metas_dir}")

    videos = sorted(videos_dir.glob("*.mp4"))
    logger.info(f"Found {len(videos)} videos")

    prompts = list(metas_dir.glob("*.txt"))
    logger.info(f"Found {len(prompts)} prompt files")

    # Check for missing prompts
    video_names = {v.stem for v in videos}
    prompt_names = {p.stem for p in prompts}
    missing = video_names - prompt_names

    if missing:
        logger.warning(f"Missing prompts for: {missing}")
        return False

    return True


def create_batch_prompts(
    data_dir: str,
    prompt_template: str,
    output_dir: str = None,
):
    """Create prompt files for all videos using a template."""

    data_path = Path(data_dir)
    output_path = Path(output_dir) if output_dir else data_path / "metas"
    output_path.mkdir(parents=True, exist_ok=True)

    videos = sorted((data_path / "videos").glob("*.mp4"))
    logger.info(f"Creating prompts for {len(videos)} videos...")

    for video in videos:
        create_prompt_file(video, prompt_template, output_path)

    logger.info(f"Prompt files saved to {output_path}")


def create_sample_dataset(output_dir: str):
    """Create sample dataset structure with example files."""

    data_path = Path(output_dir)
    videos_dir = data_path / "videos"
    metas_dir = data_path / "metas"

    videos_dir.mkdir(parents=True, exist_ok=True)
    metas_dir.mkdir(parents=True, exist_ok=True)

    # Create sample prompt file
    sample_prompts = [
        "A teal robot dancing in a modern office",
        "A robot picking up objects from a table",
        "A robot walking through a hallway",
        "A robot interacting with a human",
    ]

    for i, prompt in enumerate(sample_prompts, 1):
        prompt_file = metas_dir / f"sample_{i}.txt"
        with open(prompt_file, "w") as f:
            f.write(prompt)

    logger.info(f"Created sample dataset in {data_path}")
    logger.info(f"Sample prompts saved to {metas_dir}")
    logger.info("To use: Add .mp4 files to 'videos/' directory")


def main():
    parser = argparse.ArgumentParser(description="Prepare dataset for Cosmos LoRA")
    parser.add_argument("--data-dir", help="Path to dataset directory")
    parser.add_argument("--create-sample", action="store_true", help="Create sample dataset")
    parser.add_argument("--validate", action="store_true", help="Validate existing dataset")
    parser.add_argument("--prompt", help="Text prompt to use for all videos")
    parser.add_argument("--output-dir", help="Output directory for prompts")

    args = parser.parse_args()

    if args.create_sample:
        data_dir = args.data_dir or "datasets"
        create_sample_dataset(data_dir)

    if args.validate:
        if not args.data_dir:
            logger.error("--data-dir required for validation")
            return
        data_path = Path(args.data_dir)
        if validate_dataset(data_path):
            logger.info("✓ Dataset is valid")
        else:
            logger.warning("✗ Dataset has issues")

    if args.prompt:
        if not args.data_dir:
            logger.error("--data-dir required for prompt creation")
            return
        create_batch_prompts(
            args.data_dir,
            args.prompt,
            args.output_dir
        )


if __name__ == "__main__":
    main()
