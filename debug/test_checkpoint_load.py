#!/usr/bin/env python3
"""Test loading a checkpoint independently."""

import sys
import torch

checkpoint_path = r"C:\Users\kschmid\.cache\huggingface\hub\models--nvidia--omni-dreams-models\snapshots\253701787e2f99efec31aaab665d0d9e0cc1eb4a\single_view\2b_res720p_30fps_i2v_hdmap_distilled.pt"

print(f"Loading checkpoint: {checkpoint_path}")
print(f"File exists: {__import__('os').path.exists(checkpoint_path)}")
print()

try:
    ckpt = torch.load(checkpoint_path, map_location="cpu")
    print("✓ Checkpoint loaded successfully")
    print(f"Type: {type(ckpt)}")

    if isinstance(ckpt, dict):
        print(f"Keys: {list(ckpt.keys())}")
        for key, val in ckpt.items():
            if isinstance(val, torch.Tensor):
                print(f"  {key}: {val.dtype} {val.shape}")
            else:
                print(f"  {key}: {type(val)}")
    else:
        print(f"Content: {ckpt}")

except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
