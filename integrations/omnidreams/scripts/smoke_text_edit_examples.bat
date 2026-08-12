@echo off
REM SPDX-License-Identifier: Apache-2.0
REM Smoke test runner: various test modes for mid-stream prompt editing
REM
REM This script demonstrates different test configurations for smoke_text_edit.py
REM Uncomment the mode you want to run, or create your own combinations.

setlocal enableextensions enabledelayedexpansion
cd /d %~dp0\..\..\..

set "VENV=.venv"
set "PYEXE=%VENV%\Scripts\python.exe"

if not exist "!PYEXE!" (
  echo ERROR: venv not found at %VENV%
  exit /b 1
)

echo.
echo ===================================================================
echo Smoke Test: Mid-Stream Prompt Swap Test Modes
echo ===================================================================
echo.
echo Available test modes (uncomment one below):
echo.
echo 1. BASELINE         Single swap at chunk 8, guidance scale 2.5
echo 2. TIMING SWEEP     Test swaps at chunks 4, 8, 12 (vary when edit happens)
echo 3. GUIDANCE SWEEP   Test guidance scales 1.0, 2.5, 5.0 (vary edit strength)
echo 4. COMBINED SWEEP   Both timing + guidance variation (comprehensive)
echo 5. SEQUENTIAL       Multiple edits in sequence (A -^> B -^> C)
echo 6. DETERMINISM      Verify determinism (run each variant twice)
echo 7. FULL SUITE       All variations above (long run, ~2 hours)
echo.
echo Uncomment your desired test mode and run this script.
echo.

REM ==========================================================================
REM TEST MODE 1: BASELINE (single swap, ~10 minutes)
REM ==========================================================================
REM set "TEST_MODE=baseline"
REM echo Running: %TEST_MODE%
REM "!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py

REM ==========================================================================
REM TEST MODE 2: TIMING SWEEP (chunks 4, 8, 12 - vary swap position)
REM ==========================================================================
REM set "TEST_MODE=timing_sweep"
REM set "SWAP_AT=4,8,12"
REM echo Running: %TEST_MODE% (SWAP_AT=%SWAP_AT%)
REM "!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py

REM ==========================================================================
REM TEST MODE 3: GUIDANCE STRENGTH SWEEP (scales 1.0, 2.5, 5.0)
REM ==========================================================================
REM set "TEST_MODE=guidance_sweep"
REM set "GUIDE_SCALES=1.0,2.5,5.0"
REM echo Running: %TEST_MODE% (GUIDE_SCALES=%GUIDE_SCALES%)
REM "!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py

REM ==========================================================================
REM TEST MODE 4: COMBINED SWEEP (timing + guidance)
REM ==========================================================================
REM set "TEST_MODE=combined_sweep"
REM set "SWAP_AT=4,8,12"
REM set "GUIDE_SCALES=1.0,2.5,5.0"
REM echo Running: %TEST_MODE%
REM echo   SWAP_AT=%SWAP_AT%
REM echo   GUIDE_SCALES=%GUIDE_SCALES%
REM "!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py

REM ==========================================================================
REM TEST MODE 5: SEQUENTIAL EDITS (A -> B -> C)
REM ==========================================================================
REM set "TEST_MODE=sequential"
REM set "SEQUENTIAL_PROMPTS=Driving scene with heavy rain on the road,Driving scene at night under starlight,Driving scene in a heavy snowstorm"
REM echo Running: %TEST_MODE%
REM "!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py

REM ==========================================================================
REM TEST MODE 6: DETERMINISM CHECK (run each variant twice, ~20 minutes)
REM ==========================================================================
REM set "TEST_MODE=determinism"
REM set "CHECK_DETERMINISM=1"
REM echo Running: %TEST_MODE%
REM "!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py

REM ==========================================================================
REM TEST MODE 7: FULL SUITE (all variations, comprehensive - ~2 hours)
REM ==========================================================================
REM set "TEST_MODE=full_suite"
REM set "SWAP_AT=4,8,12"
REM set "GUIDE_SCALES=1.0,2.5,5.0"
REM set "SEQUENTIAL_PROMPTS=Driving with heavy rain and wet road,Driving at night under streetlights,Driving in snowstorm with thick snow cover"
REM set "CHECK_DETERMINISM=1"
REM echo Running: %TEST_MODE% - COMPREHENSIVE TEST (will take ~2 hours)
REM echo   Timing: chunks 4, 8, 12
REM echo   Guidance: scales 1.0, 2.5, 5.0
REM echo   Sequential: 3 sequential edits
REM echo   Determinism: enabled
REM "!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py

echo.
echo ===================================================================
echo UNCOMMENT YOUR TEST MODE ABOVE AND RUN THIS SCRIPT
echo ===================================================================
echo.
echo Each test generates videos (*.mp4) and a comprehensive report.json
echo Output directory: integrations/omnidreams/scripts/outputs/text_edit_smoke/
echo.

pause
