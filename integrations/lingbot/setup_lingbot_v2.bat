@echo off
setlocal enabledelayedexpansion

REM Setup script for LingBot-World v2: venv, dependencies, checkpoint
REM Usage: setup_lingbot_v2.bat [--skip-venv] [--skip-download]

cd /d "%~dp0"
set SCRIPT_DIR=%cd%
set REPO_ROOT=%SCRIPT_DIR%\..\..\..

echo.
echo ========== LingBot World v2 Setup ==========
echo Script dir: %SCRIPT_DIR%
echo Repo root: %REPO_ROOT%
echo.

REM Parse arguments
set SKIP_VENV=0
set SKIP_DOWNLOAD=0

for %%A in (%*) do (
  if "%%A"=="--skip-venv" set SKIP_VENV=1
  if "%%A"=="--skip-download" set SKIP_DOWNLOAD=1
)

REM Step 1: Create venv if needed
if %SKIP_VENV%==0 (
  echo [1/3] Setting up virtual environment...
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
  echo [1/3] Skipping venv setup
)

echo.
echo [2/3] Installing/syncing dependencies...
if exist "%REPO_ROOT%\uv.exe" (
  set UV_EXE=%REPO_ROOT%\uv.exe
) else (
  for /f "tokens=*" %%i in ('where uv 2^>nul') do set UV_EXE=%%i
)

if not defined UV_EXE (
  echo uv not found, attempting to use uvx instead...
  for /f "tokens=*" %%i in ('where uvx 2^>nul') do set UV_EXE=%%i --from uv
)

if not defined UV_EXE (
  echo ERROR: Neither 'uv' nor 'uvx' found in PATH
  echo        Install with: pip install uv
  echo        Or: python -m pip install --user uv
  exit /b 1
)

REM Sync dependencies with uv
!UV_EXE! sync --package flashdreams-lingbot
if errorlevel 1 (
  echo ERROR: Failed to sync dependencies
  exit /b 1
)

echo Dependencies synced successfully
echo.

REM Step 2: Download checkpoint and example data
if %SKIP_DOWNLOAD%==0 (
  echo [3/3] Downloading LingBot v2 checkpoint and example data...

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

  REM Download v2 checkpoint
  echo Downloading robbyant/lingbot-world-v2-14b-causal-fast checkpoint...
  !UV_EXE! run --from huggingface_hub hf download robbyant/lingbot-world-v2-14b-causal-fast --repo-type model
  if errorlevel 1 (
    echo ERROR: Failed to download checkpoint
    exit /b 1
  )
  echo Checkpoint downloaded successfully (~200GB)
  echo.

  REM Download example data from GitHub
  echo Downloading example data from GitHub...
  !UV_EXE! run --from huggingface_hub hf download --repo-type dataset robbyant/lingbot-world-v2-examples
  if errorlevel 1 (
    echo WARNING: Failed to download example data from HF mirror
    echo         Examples will download on first run instead
  ) else (
    echo Example data downloaded successfully
  )
  echo.

) else (
  echo [3/3] Skipping checkpoint/example download
)

echo.
echo ========== Setup Complete ==========
echo.
echo Next steps:
echo 1. Test inference with example data:
echo    uv run --python 3.12 --package flashdreams-lingbot flashdreams-run ^
echo      lingbot-world-v2-14b-causal-fast mp4 ^
echo      --scenario.example-idx 0 ^
echo      --scenario.total-blocks 10 ^
echo      --output.path outputs/lingbot-v2-demo.mp4
echo.
echo 2. Or stream with WebRTC:
echo    uv run --python 3.12 --package flashdreams-lingbot flashdreams-run ^
echo      lingbot-world-v2-14b-causal-fast webrtc ^
echo      --host 0.0.0.0 --port 8089 ^
echo      --scenario.example-idx 0
echo.
echo 3. Then open: http://localhost:8089/request_session
echo.
