#!/usr/bin/env python3
"""Minimal test: just try to load the native DIT extension."""

import sys
import time
import os

os.chdir(r"C:\workspace\world\flashdream_public")
sys.path.insert(0, r"C:\workspace\world\flashdream_public")

print("[TEST] Minimal native DIT extension load test")
print()

try:
    print("[1/3] Importing omnidreams_singleview...")
    start = time.perf_counter()
    from omnidreams.native import omnidreams_singleview
    elapsed = time.perf_counter() - start
    print(f"✓ Imported in {elapsed:.2f}s")
    print()

    print("[2/3] Loading optimized_dit Python module...")
    start = time.perf_counter()
    helper = omnidreams_singleview.load_python_module("optimized_dit")
    elapsed = time.perf_counter() - start
    print(f"✓ Loaded in {elapsed:.2f}s")
    print()

    print("[3/3] Selecting backend (this will compile if not cached)...")
    print("⏳ If this hangs, native DIT compilation has issues on Windows")
    print()
    from omnidreams.native.acceleration import NativeAccelerationConfig
    config = NativeAccelerationConfig(
        mode="required",
        build_root=None,
        max_jobs=None,
        verbose_build=True,
    )
    start = time.perf_counter()
    selection = omnidreams_singleview.select_backend(
        "optimized_dit",
        config,
    )
    elapsed = time.perf_counter() - start
    print()
    print(f"✓ select_backend completed in {elapsed:.2f}s")
    print(f"  Enabled: {selection.enabled}")
    print()

    if selection.enabled:
        print("  → require_extension() needed for actual ext load (skipping, too slow)")

    print("✓ Test passed - no hang in select_backend")

except KeyboardInterrupt:
    print("\n✗ Test interrupted by user (Ctrl+C)")
    sys.exit(1)
except Exception as e:
    print()
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
