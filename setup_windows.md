# FlashDreams Interactive-Drive Setup Guide

Complete setup workflow for `flashdream_public` on Windows with RTX 5090.

## Prerequisites

### Hardware
- **GPU:** RTX 5090 (32 GB VRAM)
- **Disk:** 100+ GB free (models + cache)
- **RAM:** 32+ GB

### Software
- **Python:** 3.11 (NOT 3.12 — causes torch segfaults)
- **CUDA:** 13.0 (cu130)
- **uv:** installed at `C:\Users\kschmid\.local\bin\uv.exe`
- **Git:** configured with `core.longpaths = true`
- **Ninja:** build system for torch.compile (auto-installed by setup.bat)

### Disk Space
- **Minimum:** 20 GB free for HF cache downloads
- **Check first:** `Get-Volume | Select-Object DriveLetter, SizeRemaining`
- **⚠️ Critical:** If < 20 GB free, run `download_models.bat` on a different machine first

## Setup Workflow

### Step 1: Verify Environment

```powershell
cd C:\workspace\world\flashdream_public
python --version  # Should be 3.11.x
Get-Volume       # Check free space (need 20+ GB)
```

### Step 2: Create venv (Python 3.11 only)

```powershell
Remove-Item .venv -Recurse -Force -ErrorAction SilentlyContinue
uv venv --python 3.11
uv sync --package flashdreams-omnidreams --extra interactive-drive
```

### Step 3: Pre-download Models (Optional but Recommended)

If disk space is tight or on slow connection:

```powershell
.\download_models.bat
```

This downloads all HF models to `~/.cache/huggingface` (~50-100 GB, takes 1-2 hours).

### Step 4: Run Full Setup

```powershell
.\setup.bat
```

This script:
1. Syncs dependencies
2. Syncs third-party sources (CUTLASS, SageAttention, etc.)
3. Runs `omnidreams-prepare --perf` (downloads scenes, builds extensions)
4. **Optionally precompiles torch.compile cache** (speeds up first chunk by 1-2 min)

**Duration:** 10-20 minutes (first run includes extension builds)

### Step 5: Launch Interactive-Drive

```powershell
$env:FLASHDREAMS_MIN_CACHE_FREE_GB = '0'
.\run_interactive_drive_perf.bat
```

**Game-mode is ON by default** (physics, collisions, speed limits, visual flare on impact).

To disable game-mode:
```powershell
.\run_interactive_drive_perf.bat --no-game-mode
```

**Important: torch.compile on first launch**
- **First launch:** You'll see "Optimizing world model..." with a black screen (~1-2 min)
  - This is torch.compile building CUDA kernels (normal, one-time cost)
  - **Do NOT kill it** — wait for HUD to appear
  - Requires `ninja` to be installed (see Troubleshooting)
- **After compilation:** ~30 sec per launch (uses cached compiles)
- Once HUD appears, you can drive immediately

## Helper Scripts

### `setup.bat`
Full setup: dependencies → third-party sync → omnidreams-prepare → optional torch.compile precompile.

### `download_models.bat`
Pre-download all HuggingFace models to `~/.cache/huggingface`. Use when disk is tight.

### `precompile_cache.bat`
Pre-warm torch.compile cache. Called automatically by `setup.bat` (optional).

### `run_interactive_drive_perf.bat`
Launch the app. **Game-mode is ON by default** (physics, collisions, speed limits, visual flare).
Pass `--no-game-mode` to disable physics.

## Controls & Features

### Driving
- **WASD** — move forward/back/left/right
- **Mouse** — look around
- **C** — place obstacle
- **R** — restart session (clears KV cache)
- **Esc** — quit

### Live Prompt Editing (PR #431 / omnidreams-live-edit-pr)
While driving:
- **Scene Prompt panel** — type new scene description, press Enter to swap prompts mid-stream
- **/spawn car 30 5** — spawn a vehicle at 30m ahead, 5 m/s speed
- **/clear-actors** — remove all spawned actors
- **Two-prompt guidance** (optional) — amplify edits by comparing old/new prompt flows

#### Testing Live Prompt Editing
1. **Start the app:**
   ```powershell
   .\run_interactive_drive_perf.bat
   ```

2. **Drive forward** for 10-20 seconds to warm up (get past first chunk compile)

3. **Swap the scene prompt mid-stream:**
   - Locate "Scene Prompt" text input panel on the left side of the UI
   - Type a new scene: `"rainy highway with traffic, dark clouds, wet pavement"`
   - Press **Enter** to apply
   - Watch the scene transition smoothly mid-drive (no restart needed, KV cache preserved)

4. **Spawn actors:**
   - In the **Scene Prompt panel** (same text input area where you edit prompts), type:
     ```
     /spawn car 50 10 0
     ```
   - **Parameters:** `/spawn <type> <distance_m> <speed_mps> <lateral_m>`
     - `car` = vehicle type
     - `50` = distance ahead (meters, world-frame, relative to initial vehicle)
     - `10` = forward speed (m/s)
     - `0` = lateral offset (0 = same lane, -5 = left, +5 = right)
   - Press **Enter** to spawn
   - Vehicle appears in the HDMap conditioning immediately
   - Can spawn multiple actors at different distances/speeds

5. **Test two-prompt guidance** (if enabled in config):
   - Swap prompt while guidance is active
   - Compare strength of the edit (should be more pronounced than without guidance)

6. **Clear all actors:**
   - Type: `/clear-actors`
   - All spawned vehicles disappear, scene background continues

**Expected behavior:**
- Prompt swaps take effect at the next chunk boundary (seamless, no frame drops)
- Scene background updates with new prompt
- KV cache (past attention history) carries forward → continuity preserved
- Actors appear/disappear instantly in the HDMap conditioning

### Performance
- **Resolution:** 1168×640 (perf-tuned)
- **Denoising steps:** [1000, 100] (few-step)
- **Native FP8 acceleration:** auto-fallback (requires extension build)
- **Compiled network:** enabled (speeds up subsequent chunks)
- **Current FPS:** ~13.5 (PyTorch); ~23+ (with native FP8, if built)

## Troubleshooting

### Torch.compile Hangs (Black Screen "Optimizing world model...")

**Symptom:** App starts but gets stuck at "Optimizing world model..." with a black screen for >5 min.

**Cause:** Missing `ninja` build system (required for torch.compile on Windows).

**Fix:**
```powershell
.\.venv\Scripts\python.exe -m pip install ninja
.\run_interactive_drive_perf.bat
```

**Or:** Let `setup.bat` auto-install ninja:
```powershell
.\setup.bat  # Installs ninja automatically
.\run_interactive_drive_perf.bat
```

**Why:** torch.compile needs Ninja to compile CUDA kernels. Without it, compilation hangs indefinitely. Installation is one-time; subsequent runs reuse cached compiled kernels.

### Python 3.12 Crash
```
Error: Segfault in c10.dll::Allocator / python312.dll
```
**Fix:** Recreate venv with Python 3.11
```powershell
Remove-Item .venv -Recurse -Force
uv venv --python 3.11
uv sync --package flashdreams-omnidreams --extra interactive-drive
```

### Disk Space Error
```
DiskSpaceError: Not enough free disk for HuggingFace cache (need 20 GB)
```
**Options:**
1. Free up 6+ GB on C: drive
2. Run `download_models.bat` on a machine with more space first
3. Set `HF_HOME` to a drive with more space:
   ```powershell
   $env:HF_HOME = 'D:\.cache\huggingface'
   .\setup.bat
   ```

### CUDA Mismatch Error
```
Cannot find include file: 'crtdbg.h'
```
**Fix:** Run from `run_interactive_drive_perf.bat` environment (sets CUDA_HOME + Windows SDK paths)

### Native FP8 Not Available
PR #431 supports live prompt editing. FP8 acceleration is optional:
- **Required:** Full native extension build (complex, see [[reference_omnidreams_singleview_windows_build]])
- **Current:** Falls back to PyTorch (~13.5 FPS)

## Configuration

### Perf Config
Located at: `integrations/omnidreams/omnidreams/interactive_drive/configs/example_world_model_perf.yaml`

Key settings:
- `resolution_wh: [1168, 640]` — lower resolution for speed
- `denoising_steps: [1000, 100]` — few-step inference
- `compile_net: true` — torch.compile optimization
- `native_dit_acceleration: required` — FP8 (auto-fallback to PyTorch)

## Merging PR #431 (Live Prompt Editing)

```powershell
cd C:\workspace\world\flashdream_public
git fetch origin
git merge origin/main
git checkout --theirs integrations/omnidreams
git add .
git commit -m "Merge PR #431: live prompt editing and actor spawning"
.\setup.bat
.\run_interactive_drive_perf.bat --game-mode
```

**New features:**
- Swap scene prompt mid-stream (full continuity)
- Spawn/despawn actors with `/spawn` and `/clear-actors`
- Two-prompt guidance for amplified edits
- All opt-in; zero overhead if not used

## Performance Tips

### Speed Up First Chunk
Pre-compile torch.compile cache:
```powershell
.\precompile_cache.bat  # ~2-3 min one-time cost
```

### Sustained FPS
Current: **13.5 FPS** (PyTorch backend, perf config)

To reach 20+ FPS:
1. Build native FP8 extension (complex, see build guide)
2. Or reduce resolution: `[896, 496]` (~20 FPS)
3. Or reduce steps: `[1000, 50]` (~18 FPS)

### GPU Memory
- Default: ~28 GB used
- With offload_text_encoder: ~25 GB
- Spare headroom: 4 GB (for compile operations)

## References

- **Ludus renderer build:** [[reference_ludus_windows_build]]
- **OmniDreams single-view native FP8:** [[reference_omnidreams_singleview_windows_build]]
- **Windows torch gotchas:** [[feedback_no_cpu_torch_windows]], [[feedback_never_use_python_312]]
- **CUDA + cuDNN setup:** [[reference_windows_blackwell_arch_cudnn]]
- **Disk space:** [[reference_disk_cleanup]] (C:\recordings is protected)

## Common Commands

```powershell
# Full setup
.\setup.bat

# Launch app
.\run_interactive_drive_perf.bat --game-mode

# Check Python version
python --version

# Check free disk
Get-Volume

# Pre-download models
.\download_models.bat

# Pre-compile torch.compile
.\precompile_cache.bat

# Rebuild extensions only
uv run --package flashdreams-omnidreams omnidreams-prepare --perf
```

---

**Last updated:** 2026-08-11  
**Status:** Setup complete, PR #431 ready to merge
