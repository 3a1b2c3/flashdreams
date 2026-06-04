@echo off
setlocal

REM Launch the NVIDIA OmniDreams WebRTC interactive server on port 8089.
REM Connect a browser client to drive the scene in real time.
REM Pass extra flags through, e.g.:
REM   run_webrtc_server.bat --port 8090
REM   run_webrtc_server.bat --scene-uuid <other-uuid>

cd /d C:\workspace\world\flashdream_public

REM Ludus HD-map renderer JIT-compiles a CUDA/C++ torch extension on first
REM launch -- MSVC + Windows SDK (INCLUDE/LIB) must be on the environment.
set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if exist "%VCVARS%" (
    call "%VCVARS%" >nul
) else (
    echo WARNING: vcvars64.bat not found at "%VCVARS%"; the Ludus extension build may fail.
)

REM torch here is the cu130 build; the extension must compile against CUDA 13.0.
set "CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
set "PATH=%CUDA_HOME%\bin;%PATH%"

REM Pull HF_TOKEN from the cached token file if not already set.
if "%HF_TOKEN%"=="" if exist "C:\Users\kschmid\.cache\omni-dreams\huggingface\token" set /p HF_TOKEN=<"C:\Users\kschmid\.cache\omni-dreams\huggingface\token"
if "%HF_TOKEN%"=="" echo WARNING: HF_TOKEN is not set; scene/text-encoder downloads will fail.

REM Keep inductor on ATEN (cuDNN/cuBLAS) backends -- the lightVAE Triton
REM templates request >99 KB shared mem and crash this GPU.
set "TORCHINDUCTOR_MAX_AUTOTUNE_GEMM_BACKENDS=ATEN"
set "TORCHINDUCTOR_MAX_AUTOTUNE_CONV_BACKENDS=ATEN"
set "TORCHINDUCTOR_MAX_AUTOTUNE=0"
set "TORCHINDUCTOR_MAX_AUTOTUNE_GEMM=0"

REM Resolve/install the runtime (fast no-op once synced).
uv sync --package flashdreams-omnidreams --extra interactive-drive
if errorlevel 1 exit /b 1

REM Launch the WebRTC server (single line; %* forwards extra flags).
uv run --no-sync --package flashdreams-omnidreams torchrun --nproc_per_node 1 -m omnidreams.webrtc.server --host 0.0.0.0 --port 8089 --pipeline_config_name omnidreams-sv-2steps-chunk2-loc6-lightvae-lighttae-perf --scene-uuid "0d404ff7-2b66-498c-b047-1ed8cded60d4" %*

endlocal
