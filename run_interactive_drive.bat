@echo off
setlocal

REM Launch the NVIDIA OmniDreams interactive-drive demo (HUD mode by default).
REM Pass extra flags through to interactive-drive, e.g.:
REM   run_interactive_drive.bat --no-hud
REM   run_interactive_drive.bat --stream-mjpeg 8080
REM   run_interactive_drive.bat --synthetic-scene

cd /d C:\workspace\world\flashdream_public

REM The Ludus HD-map renderer JIT-compiles a CUDA/C++ torch extension on first
REM launch, so the MSVC + Windows SDK toolchain (INCLUDE / LIB) must be on the
REM environment or the build fails with C1083 (missing assert.h / crtdbg.h).
set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if exist "%VCVARS%" (
    call "%VCVARS%" >nul
) else (
    echo WARNING: vcvars64.bat not found at "%VCVARS%"; the Ludus extension build may fail with missing CRT/SDK headers.
)

REM torch in this venv is the cu130 build, so the extension must compile against
REM the CUDA 13.0 toolkit (cudart64_13.dll, which torch ships) -- not v12.8, or
REM the .pyd depends on cudart64_12.dll and import fails with "DLL load failed".
REM torch keys off CUDA_HOME, which can otherwise point at v12.8.
set "CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
set "PATH=%CUDA_HOME%\bin;%PATH%"

REM Pull HF_TOKEN from the cached token file if it isn't already set in the env.
if "%HF_TOKEN%"=="" if exist "C:\Users\kschmid\.cache\omni-dreams\huggingface\token" set /p HF_TOKEN=<"C:\Users\kschmid\.cache\omni-dreams\huggingface\token"
if "%HF_TOKEN%"=="" echo WARNING: HF_TOKEN is not set; scene and text-encoder downloads from nvidia/omni-dreams-scenes will fail.

REM Cosmos-Reason1-7B is already fully cached (~15.5 GiB), so the default 20 GiB
REM free-space preflight is a false blocker (it checks free space before noticing
REM the repo is complete). Skip it -- no download happens. Set back to unset/20
REM if you clear the cache and need a real re-download headroom check.
set "FLASHDREAMS_MIN_CACHE_FREE_GB=0"

REM Resolve/install the interactive-drive runtime (fast no-op once synced).
uv sync --package flashdreams-omnidreams --extra interactive-drive
if errorlevel 1 exit /b 1

REM Force inductor to autotune among ATen (cuDNN/cuBLAS) backends only, not
REM Triton templates. compile_net: false does NOT gate the lightVAE compile,
REM whose Triton mm/conv templates request >99 KB shared memory and crash this
REM GPU with "No valid triton configs. OutOfMemoryError". ATen kernels always
REM fit, so this removes the crash regardless of manifest.
set "TORCHINDUCTOR_MAX_AUTOTUNE_GEMM_BACKENDS=ATEN"
set "TORCHINDUCTOR_MAX_AUTOTUNE_CONV_BACKENDS=ATEN"
REM Also turn off max-autotune outright so inductor uses default cuDNN/cuBLAS
REM kernels with no benchmarking sweep -- much lower startup GPU churn.
set "TORCHINDUCTOR_MAX_AUTOTUNE=0"
set "TORCHINDUCTOR_MAX_AUTOTUNE_GEMM=0"

REM Persist the compile caches in the repo (NOT %TEMP%, which gets cleaned and
REM forces a full recompile every launch). First run still compiles; later runs
REM reuse these and start fast. Inductor (lightVAE kernels), the cross-process FX
REM graph cache, and Triton's kernel cache:
set "TORCHINDUCTOR_CACHE_DIR=%~dp0.cache\torchinductor"
set "TORCHINDUCTOR_FX_GRAPH_CACHE=1"
set "TRITON_CACHE_DIR=%~dp0.cache\triton"
if not exist "%~dp0.cache" mkdir "%~dp0.cache"

REM This GPU has 32 GB; the model's nominal minimum is ~48 GB, so cut VRAM:
REM expandable_segments reduces allocator fragmentation (helps fit / avoid OOM).
set "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True"

REM Use the eager manifest (compile_net: false) by default: torch.compile's
REM max-autotune emits Triton conv/mm kernels whose big-block configs exceed
REM this GPU's ~99 KB shared-mem limit and crash ("No valid triton configs.
REM OutOfMemoryError"). Eager mode sidesteps autotune and gives a faster first
REM chunk for GUI bring-up. Pass your own --manifest after to override (the
REM later value wins), e.g. ...perf.yaml once you want the compiled path.
set "MANIFEST=C:\workspace\world\flashdream_public\integrations\omnidreams\omnidreams\interactive_drive\configs\example_world_model_lowres.yaml"

REM --- interactive-drive HUD goal-marker / logging knobs --------------------
REM Pin the goal (viewport cylinder + BEV minimap dot) a fixed distance
REM straight ahead of spawn so it's always visible for testing. Set to 0 to
REM use the real first-intersection-from-clipgt search instead.
set "IDRIVE_TEST_MARKER_AHEAD_M=50"
REM Marker stays visible for the whole rollout by default. Uncomment to restore
REM the old behaviour of hiding it once the ego drives over it.
REM set "IDRIVE_MARKER_HIDE_ON_PASS=1"
REM Mirror the loguru session log to a file so it can be tailed live.
set "IDRIVE_LOG_FILE=C:\tmp\idrive.log"
REM Drop obstacle cuboids in the middle of the road, at these distances (metres)
REM straight ahead of spawn. Empty = none. Composed live (no scene rebuild).
REM Re-enabled: the earlier "crash at render start" was the Cosmos-Reason1-7B
REM disk-space preflight (now skipped above), NOT the cuboid CubePool -- the log
REM shows road-cuboid uploads succeeding ("road cuboids=N -> dynamic scene_id=N").
REM Empty = no auto-seeded cubes at launch. Press the 'c' hotkey in the demo to
REM drop an obstacle cuboid ~14 m ahead of the car on demand instead.
set "IDRIVE_ROAD_CUBOIDS_AHEAD="

REM Launch. %* forwards any flags you pass to this .bat.
REM --offload-text-encoder moves Cosmos-Reason1-7B (~14-15 GB) to CPU after it
REM embeds the prompt once, freeing that VRAM for the world model (32 GB card vs
REM ~48 GB nominal min). Override by passing --offload-text-encoder again or not.
REM BEV minimap as a zoomed-out, pure top-down bird's-eye:
REM   --bev-tilt-deg 0  -> straight down (no Google-Maps forward lean)
REM   --bev-height-m 700 + --bev-fov-deg 70 -> ~980 m ground coverage (vs ~87 m default)
REM Override by passing your own --bev-* after (later value wins).
REM Default: capture ALL demo console output (incl. [hud] key events, [rasterizer]
REM road-cuboid drops, [viewport-marker], tracebacks) to a log file so it can be
REM tailed/checked. The demo window still opens normally. Edit the path to change.
if not exist "C:\tmp" mkdir "C:\tmp"
set "IDRIVE_CONSOLE_LOG=C:\tmp\idrive_console.log"
echo Console log -^> %IDRIVE_CONSOLE_LOG%
uv run --no-sync --package flashdreams-omnidreams interactive-drive --manifest "%MANIFEST%" --offload-text-encoder --bev-tilt-deg 0 --bev-height-m 700 --bev-fov-deg 70 %* > "%IDRIVE_CONSOLE_LOG%" 2>&1

endlocal
