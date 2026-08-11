#!/usr/bin/env python3
"""Warmup torch.compile cache for interactive-drive perf."""
import sys
sys.path.insert(0, 'integrations/omnidreams')

print('[PRECOMPILE] Loading manifest...', flush=True)
from omnidreams.interactive_drive.world_model.manifest import load_world_model_manifest
manifest = load_world_model_manifest(
    r'integrations/omnidreams/omnidreams/interactive_drive/configs/example_world_model_perf.yaml'
)

print('[PRECOMPILE] Creating backend...', flush=True)
from omnidreams.interactive_drive.backends.world_model import WorldModelRenderBackend
from omnidreams.interactive_drive.config import ChunkConfig, RasterConfig

chunk = ChunkConfig(chunk_frames=8, initial_chunk_frames=5, fps=30)
raster = RasterConfig(width=1168, height=640)
backend = WorldModelRenderBackend(manifest=manifest, chunk=chunk, raster=raster, skip_warmup=False)

print('[PRECOMPILE] Warming up model (this triggers torch.compile)...', flush=True)
backend.warmup_model()

print('[PRECOMPILE] ✓ Compile cache populated', flush=True)
