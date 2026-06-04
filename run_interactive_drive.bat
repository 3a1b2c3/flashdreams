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

REM Launch. %* forwards any flags you pass to this .bat.
REM --offload-text-encoder moves Cosmos-Reason1-7B (~14-15 GB) to CPU after it
REM embeds the prompt once, freeing that VRAM for the world model (32 GB card vs
REM ~48 GB nominal min). Override by passing --offload-text-encoder again or not.
uv run --no-sync --package flashdreams-omnidreams interactive-drive --manifest "%MANIFEST%" --offload-text-encoder %*

endlocal
