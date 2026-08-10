#!/usr/bin/env python3
"""Build a `mario` scene variant for OmniDreams interactive-drive.

Creates a sibling USDZ (clipgt-<uuid>-mario.usdz) that is a byte copy of the base
scene EXCEPT the seed first frame and the 3 caption prompts, which are replaced with
a Mario Kart image + Mario Kart prompts. The road GEOMETRY (ClipGT parquets) is kept
from the base -- only the appearance seed + text conditioning change. Launch with:
  C:\\workspace\\world\\flashdream_public\\run_interactive_drive_perf.bat --variant mario

All members are written STORED (uncompressed) to match the USDZ layout. pxr isn't
installed, so nothing mmaps the USD; the pipeline reads png/jpeg/txt/parquet via zipfile.
"""
import io
import zipfile
from pathlib import Path

from PIL import Image

BASE = Path(r"C:\Users\kschmid\.cache\flashdreams\omnidreams-scenes\clipgt-0d404ff7-2b66-498c-b047-1ed8cded60d4.usdz")
OUT = BASE.with_name(BASE.stem + "-mario.usdz")
MARIO = Path(r"C:\Users\kschmid\Downloads\1785728834.png")

# The two seed members (loader prefers the frames/*.jpeg, falls back to first_image.png).
JPEG_MEMBER = "frames/camera_front_wide_120fov/1201111.jpeg"
PNG_MEMBER = "first_image.png"
PROMPT_MEMBERS = ["prompt1.txt", "prompt2.txt", "prompt3.txt"]

PROMPTS = {
    # short / medium / long, matching OmniDreams' 3-length captioning, but describing
    # a Mario-Kart-style go-kart racing game so the text conditioning pushes appearance.
    "prompt1.txt": (
        "A colorful cartoon go-kart racing game, bright saturated colors, arcade racetrack, "
        "third-person view behind the kart."
    ),
    "prompt2.txt": (
        "A vibrant, cartoon-style go-kart racing game seen from behind the kart. Bright "
        "saturated primary colors, a cheerful paved racetrack with striped curbs and green "
        "grass, a clear blue sky, a playful arcade racing aesthetic."
    ),
    "prompt3.txt": (
        "A wide third-person view of a vibrant, cartoon-style go-kart racing game in the "
        "spirit of Mario Kart. The player's kart is centered in the lower foreground on a "
        "smooth paved track bordered by red-and-white striped curbs. Bright, highly saturated "
        "primary colors, rounded low-poly scenery -- rolling green hills, cartoon trees, "
        "checkered banners and floating item boxes -- under a clear blue sky with fluffy "
        "clouds. Flat, cheerful lighting; a fast, arcade racing feel."
    ),
}


def main() -> int:
    for p in (BASE, MARIO):
        if not p.is_file():
            print(f"ERROR: missing {p}")
            return 1

    # Resize Mario to the base seed's dimensions, encode as PNG + JPEG.
    with zipfile.ZipFile(BASE) as z:
        base_png = Image.open(io.BytesIO(z.read(PNG_MEMBER)))
        target = base_png.size  # (W, H) e.g. (1924, 1084)
    mario = Image.open(MARIO).convert("RGB").resize(target, Image.Resampling.LANCZOS)
    png_bytes = io.BytesIO(); mario.save(png_bytes, format="PNG"); png_bytes = png_bytes.getvalue()
    jpg_bytes = io.BytesIO(); mario.save(jpg_bytes, format="JPEG", quality=95); jpg_bytes = jpg_bytes.getvalue()

    replace = {JPEG_MEMBER: jpg_bytes, PNG_MEMBER: png_bytes}
    for name, text in PROMPTS.items():
        replace[name] = text.encode("utf-8")

    with zipfile.ZipFile(BASE) as zin, zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED) as zout:
        for info in zin.infolist():
            data = replace.get(info.filename, zin.read(info.filename))
            zout.writestr(info.filename, data)

    print(f"wrote mario variant -> {OUT}")
    print(f"  seed replaced: {JPEG_MEMBER} + {PNG_MEMBER}")
    print(f"  prompts replaced: {', '.join(PROMPT_MEMBERS)}")
    print("\nLaunch it:")
    print(r"  C:\workspace\world\flashdream_public\run_interactive_drive_perf.bat --variant mario")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
