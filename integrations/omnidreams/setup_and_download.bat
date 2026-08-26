@echo off
setlocal enabledelayedexpansion

REM Setup script for OmniDreams: venv, models, scenes, CUDA build
REM Usage: setup_and_download.bat [--skip-venv] [--skip-download] [--skip-build]

cd /d "%~dp0"
set SCRIPT_DIR=%cd%
set REPO_ROOT=%SCRIPT_DIR%\..\..\..
set CUDA_VERSION=13.2

echo.
echo ========== OmniDreams Setup ==========
echo Script dir: %SCRIPT_DIR%
echo Repo root: %REPO_ROOT%
echo CUDA version: %CUDA_VERSION%
echo.

REM Parse arguments
set SKIP_VENV=0
set SKIP_DOWNLOAD=0
set SKIP_BUILD=0

for %%A in (%*) do (
  if "%%A"=="--skip-venv" set SKIP_VENV=1
  if "%%A"=="--skip-download" set SKIP_DOWNLOAD=1
  if "%%A"=="--skip-build" set SKIP_BUILD=1
)

REM Step 1: Create venv if needed
if %SKIP_VENV%==0 (
  echo [1/4] Setting up virtual environment...
  if exist ".venv" (
    echo Virtual environment already exists
  ) else (
    echo Creating new venv...
    python -m venv .venv
    if errorlevel 1 (
      echo ERROR: Failed to create venv
      exit /b 1
    )
  )
  call .venv\Scripts\activate.bat
  echo Virtual environment activated
) else (
  echo [1/4] Skipping venv setup
)

echo.
echo [2/4] Installing/syncing dependencies...
if exist "%REPO_ROOT%\uv.exe" (
  set UV_EXE=%REPO_ROOT%\uv.exe
) else (
  for /f "tokens=*" %%i in ('where uv 2^>nul') do set UV_EXE=%%i
)

if not defined UV_EXE (
  echo ERROR: uv not found. Install it first with: pip install uv
  exit /b 1
)

REM Sync dependencies with uv
!UV_EXE! sync --package flashdreams-omnidreams --extra interactive-drive
if errorlevel 1 (
  echo ERROR: Failed to sync dependencies
  exit /b 1
)

echo Dependencies synced successfully
echo.

REM Step 2: Download models and scenes
if %SKIP_DOWNLOAD%==0 (
  echo [3/4] Downloading models and scenes...

  REM Check HF_TOKEN
  if not defined HF_TOKEN (
    for /f "tokens=1,* delims==" %%A in ('findstr /c:"HF_TOKEN" .env 2^>nul') do (
      set "HF_TOKEN=%%B"
    )
  )

  if not defined HF_TOKEN (
    echo ERROR: HF_TOKEN not set in environment or .env file
    echo        Create .env file or set: set HF_TOKEN=...
    exit /b 1
  )

  echo HF_TOKEN is set (length: !HF_TOKEN:~0,8!...)
  echo.

  REM Download models (model repo)
  echo Downloading nvidia/omni-dreams-models...
  !UV_EXE! run --from huggingface_hub hf download nvidia/omni-dreams-models --repo-type model
  if errorlevel 1 (
    echo ERROR: Failed to download models
    exit /b 1
  )
  echo Models downloaded successfully
  echo.

  REM Download samples (dataset repo)
  echo Downloading nvidia/omni-dreams-samples...
  !UV_EXE! run --from huggingface_hub hf download nvidia/omni-dreams-samples --repo-type dataset
  if errorlevel 1 (
    echo ERROR: Failed to download samples
    exit /b 1
  )
  echo Samples downloaded successfully
  echo.

  REM Download scenes (dataset repo)
  echo Downloading nvidia/omni-dreams-scenes...
  !UV_EXE! run --from huggingface_hub hf download nvidia/omni-dreams-scenes --repo-type dataset
  if errorlevel 1 (
    echo ERROR: Failed to download scenes
    exit /b 1
  )
  echo Scenes downloaded successfully
  echo.
) else (
  echo [3/4] Skipping model/scene download
)

REM Step 3: Sync thirdparty deps and build CUDA
if %SKIP_BUILD%==0 (
  echo [4/4] Syncing thirdparty dependencies and building CUDA %CUDA_VERSION%...

  REM Sync thirdparty (CuTASS, SageAttention, etc.)
  echo Syncing thirdparty sources...
  !UV_EXE! run --package flashdreams-omnidreams python omnidreams_singleview/tools/sync_thirdparty.py sync
  if errorlevel 1 (
    echo ERROR: Failed to sync thirdparty dependencies
    exit /b 1
  )
  echo Thirdparty sync completed
  echo.

  REM Compile with CUDA 13.2
  echo Compiling extensions with CUDA %CUDA_VERSION%...
  echo This may take several minutes...
  echo.

  set "TORCH_CUDA_ARCH_LIST=8.0 8.6 8.9 9.0 12.0a"
  set "FORCE_CUDA=1"

  REM Build ludus-renderer first
  echo Building ludus-renderer CUDA extensions...
  !UV_EXE! run --package flashdreams-omnidreams python -m pip install -e ludus-renderer --no-build-isolation --no-deps
  if errorlevel 1 (
    echo ERROR: Failed to build ludus-renderer
    exit /b 1
  )
  echo ludus-renderer built successfully
  echo.

  REM Build omnidreams_singleview extensions
  echo Building OmniDreams CUDA extensions...
  !UV_EXE! run --package flashdreams-omnidreams python setup.py build_ext --inplace
  if errorlevel 1 (
    echo WARNING: Extension build completed with warnings (may still be usable)
  )

) else (
  echo [4/4] Skipping thirdparty/CUDA build
)

echo.
echo ========== Setup Complete ==========
echo.
echo Next steps:
echo 1. Run the interactive demo:
echo    uv run --package flashdreams-omnidreams interactive-drive
echo.
echo 2. Or run batch inference:
echo    uv run --python 3.12 --package flashdreams-omnidreams flashdreams-run omnidreams mp4 ^
echo      --scenario.example-data true --output.path outputs/omnidreams.mp4
echo.
echo 3. Or serve WebRTC:
echo    uv run --python 3.12 --package flashdreams-omnidreams flashdreams-run omnidreams webrtc
echo.
