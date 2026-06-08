@echo off
setlocal

REM Run the FlashDreams lingbot-world-fast example.
REM Usage: run_lingbot.bat [extra flashdreams-run args appended/overriding]
REM   run_lingbot.bat --example-idx 1
REM   run_lingbot.bat --total-blocks 42

cd /d C:\workspace\world\flashdream_public

REM MSVC + CUDA 13.0 (matches the cu130 torch) in case anything JIT-compiles.
set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if exist "%VCVARS%" call "%VCVARS%" >nul
set "CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
set "PATH=%CUDA_HOME%\bin;%PATH%"

REM Avoid the Triton autotune shared-mem OOM ("No valid triton configs") and
REM reduce allocator fragmentation on this 32 GB GPU.
set "TORCHINDUCTOR_MAX_AUTOTUNE=0"
set "TORCHINDUCTOR_MAX_AUTOTUNE_GEMM=0"
set "TORCHINDUCTOR_MAX_AUTOTUNE_GEMM_BACKENDS=ATEN"
set "TORCHINDUCTOR_MAX_AUTOTUNE_CONV_BACKENDS=ATEN"
set "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True"

REM HF_TOKEN for any model/asset downloads.
if "%HF_TOKEN%"=="" if exist "C:\Users\kschmid\.cache\omni-dreams\huggingface\token" set /p HF_TOKEN=<"C:\Users\kschmid\.cache\omni-dreams\huggingface\token"

uv run --project integrations/lingbot flashdreams-run lingbot-world-fast --example-data True --example-idx 0 --pixel-height 464 --pixel-width 832 --total-blocks 21 %*

endlocal
