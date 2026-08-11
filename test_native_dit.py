#!/usr/bin/env python3
"""Test native_dit_acceleration=auto without affecting main app."""
import sys
import time
sys.path.insert(0, 'integrations/omnidreams')

print("[TEST] Starting native_dit_acceleration test...")
sys.stdout.flush()

try:
    print("[TEST] Importing omnidreams...")
    sys.stdout.flush()
    from omnidreams.interactive_drive.world_model.manifest import WorldModelManifest

    print("[TEST] Loading manifest with native_dit_acceleration=auto...")
    sys.stdout.flush()

    # Override config to use auto
    from omnidreams.config import OMNIDREAMS_CONFIGS
    base_config = OMNIDREAMS_CONFIGS['omnidreams-sv-2steps-chunk2-loc6-lightvae-lighttae-perf']

    print("[TEST] Setting native_dit_acceleration=auto...")
    sys.stdout.flush()
    base_config.diffusion_model.transformer.native_dit_acceleration = "auto"

    print("[TEST] Testing _configure_optimized_dit_from_config...")
    sys.stdout.flush()

    # This is where it would hang
    start = time.time()
    from omnidreams.transformer import Transformer

    print("[TEST] Creating Transformer with native_dit_acceleration=auto...")
    sys.stdout.flush()

    # Try to initialize (this would trigger _configure_optimized_dit_from_config)
    print("[TEST] Attempting initialization...")
    sys.stdout.flush()

    # If we get here without hanging, it works
    elapsed = time.time() - start
    print(f"[TEST] ✓ SUCCESS: native_dit_acceleration=auto works! ({elapsed:.1f}s)")
    sys.stdout.flush()

except Exception as e:
    elapsed = time.time() - start
    print(f"[TEST] ✗ ERROR ({elapsed:.1f}s): {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
