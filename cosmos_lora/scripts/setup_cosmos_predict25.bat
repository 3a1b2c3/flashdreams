@echo off
setlocal enabledelayedexpansion

rem Clones nvidia-cosmos/cosmos-predict2.5, installs it into its own venv,
rem and downloads the Cosmos-Predict2.5-2B checkpoint.
rem Requires HF_TOKEN to be set in your own shell first:
rem   $env:HF_TOKEN = "hf_..."   (PowerShell)
rem   set HF_TOKEN=hf_...        (cmd)

if "%HF_TOKEN%"=="" (
    echo ERROR: HF_TOKEN is not set. Set it in your shell before running this script.
    exit /b 1
)

set "ROOT=%~dp0.."
set "REPO_DIR=%ROOT%\cosmos-predict2.5"

set "UV_EXE=uv"
where uv >nul 2>nul
if errorlevel 1 (
    if exist "%USERPROFILE%\.local\bin\uv.exe" (
        set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
    ) else (
        echo ERROR: uv not found on PATH or at %USERPROFILE%\.local\bin\uv.exe
        exit /b 1
    )
)

echo === Disk space check ===
for /f "tokens=3" %%a in ('dir /-c "%ROOT%" ^| findstr /C:"bytes free"') do set FREEBYTES=%%a
set "FREEBYTES=!FREEBYTES:,=!"
set /a FREEGB=!FREEBYTES:~0,-9! 2>nul
echo Free space on target drive: ~!FREEGB! GB
echo Repo clone + deps: ~1 GB. Cosmos-Predict2.5-2B checkpoint: ~15-20 GB. Recommend 30+ GB free.
if !FREEGB! LSS 30 (
    echo WARNING: less than 30 GB free. Continuing in 5 seconds, Ctrl+C to abort.
    timeout /t 5
)

if exist "%REPO_DIR%\.git" (
    echo Repo already present at %REPO_DIR%, skipping clone.
) else (
    echo === Cloning nvidia-cosmos/cosmos-predict2.5 ===
    git clone --depth 1 https://github.com/nvidia-cosmos/cosmos-predict2.5.git "%REPO_DIR%"
    if errorlevel 1 (
        echo ERROR: git clone failed.
        exit /b 1
    )
    if not exist "%REPO_DIR%\.git\HEAD" (
        echo ERROR: %REPO_DIR%\.git is missing or not a real repo dir - aliasing to a parent repo. Aborting, do not train against this checkout.
        exit /b 1
    )
)

echo === Creating venv and installing cosmos-predict2.5 ===
cd /d "%REPO_DIR%"
if not exist ".venv" (
    "!UV_EXE!" venv --python 3.11
)
call .venv\Scripts\activate.bat

"!UV_EXE!" pip install torch --index-url https://download.pytorch.org/whl/cu130
if errorlevel 1 (
    echo ERROR: torch install failed.
    exit /b 1
)

"!UV_EXE!" pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: requirements install failed.
    exit /b 1
)

"!UV_EXE!" pip install -e .
if errorlevel 1 (
    echo ERROR: editable install failed.
    exit /b 1
)

rem cosmos-predict2.5 auto-downloads the base checkpoint on first training run
rem (via HF_TOKEN, already validated above) into HF_HOME / IMAGINAIRE_OUTPUT_ROOT.
rem No manual huggingface-cli download step needed or wanted here -- a manual
rem download would land the checkpoint at a path the training script doesn't
rem look at, since it resolves the checkpoint itself.
if "%HF_HOME%"=="" (
    echo NOTE: HF_HOME not set - checkpoint will download to the default %%USERPROFILE%%\.cache\huggingface
)
if "%IMAGINAIRE_OUTPUT_ROOT%"=="" (
    echo NOTE: IMAGINAIRE_OUTPUT_ROOT not set - training artifacts will default to /tmp/imaginaire4-output
)

echo.
echo === Done ===
echo Repo: %REPO_DIR%
echo Venv: %REPO_DIR%\.venv
echo Next: run training - the 2B checkpoint downloads automatically on first launch:
echo   torchrun --nproc_per_node=1 scripts/train.py --config=cosmos_predict2/_src/predict2/configs/video2world/config.py -- experiment=predict2_lora_training_2b_cosmos_lora_sample

endlocal
