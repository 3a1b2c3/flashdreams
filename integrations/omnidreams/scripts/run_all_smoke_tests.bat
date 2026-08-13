@echo off
REM SPDX-License-Identifier: Apache-2.0
REM Master smoke test orchestrator: runs all test modes in sequence
REM Generates comprehensive benchmark report for prompt editing evaluation

setlocal enableextensions enabledelayedexpansion
cd /d %~dp0\..\..\..

set "VENV=.venv"
set "PYEXE=%VENV%\Scripts\python.exe"
set "OUT_BASE=integrations\omnidreams\scripts\outputs\text_edit_smoke"

if not exist "!PYEXE!" (
  echo ERROR: venv not found at %VENV%
  exit /b 1
)

echo.
echo ===================================================================
echo OMNIDREAMS SMOKE TEST SUITE - FULL EVALUATION
echo ===================================================================
echo.
echo This will run a comprehensive test of prompt editing capabilities:
echo   - Timing variation (when edits happen)
echo   - Guidance strength sweep (edit intensity)
echo   - Sequential edits (A -^> B -^> C)
echo   - Determinism verification (bit-clean reproducibility)
echo.
echo TOTAL DURATION: ~2 hours
echo OUTPUT: videos + structured JSON report
echo.

set "TIMESTAMP=%date:~-4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "RUN_DIR=%OUT_BASE%\run_%TIMESTAMP%"

echo Creating output directory: %RUN_DIR%
mkdir "%RUN_DIR%" 2>nul

echo.
echo ===================================================================
echo TEST 1: BASELINE CONTROL (reference, ~10 min)
echo ===================================================================
echo.
set "OUT_DIR=%RUN_DIR%\1_baseline"
mkdir "!OUT_DIR!" 2>nul
"!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py
if %ERRORLEVEL% neq 0 (
  echo ERROR: Baseline test failed
  exit /b 1
)
echo ✓ Baseline complete

echo.
echo ===================================================================
echo TEST 2: TIMING VARIATION (chunks 4, 8, 12 - ~30 min)
echo ===================================================================
echo.
set "OUT_DIR=%RUN_DIR%\2_timing_sweep"
mkdir "!OUT_DIR!" 2>nul
set "SWAP_AT=4,8,12"
"!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py
if %ERRORLEVEL% neq 0 (
  echo ERROR: Timing sweep failed
  exit /b 1
)
echo ✓ Timing sweep complete

echo.
echo ===================================================================
echo TEST 3: GUIDANCE STRENGTH SWEEP (s=1.0,2.5,5.0 - ~30 min)
echo ===================================================================
echo.
set "OUT_DIR=%RUN_DIR%\3_guidance_sweep"
mkdir "!OUT_DIR!" 2>nul
set "SWAP_AT=8"
set "GUIDE_SCALES=1.0,2.5,5.0"
"!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py
if %ERRORLEVEL% neq 0 (
  echo ERROR: Guidance sweep failed
  exit /b 1
)
echo ✓ Guidance sweep complete

echo.
echo ===================================================================
echo TEST 4: SEQUENTIAL EDITS (A -^> B -^> C - ~15 min)
echo ===================================================================
echo.
set "OUT_DIR=%RUN_DIR%\4_sequential"
mkdir "!OUT_DIR!" 2>nul
set "SWAP_AT=8"
set "GUIDE_SCALES=2.5"
set "SEQUENTIAL_PROMPTS=Driving scene in heavy rain with wet road and windshield droplets,Driving scene at night with streetlights and vehicle lights,Driving scene in heavy snowstorm with thick snow cover"
"!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py
if %ERRORLEVEL% neq 0 (
  echo ERROR: Sequential edits test failed
  exit /b 1
)
echo ✓ Sequential edits complete

echo.
echo ===================================================================
echo TEST 5: DETERMINISM CHECK (bit-clean reproducibility - ~20 min)
echo ===================================================================
echo.
set "OUT_DIR=%RUN_DIR%\5_determinism"
mkdir "!OUT_DIR!" 2>nul
set "SWAP_AT=8"
set "GUIDE_SCALES=2.5"
set "CHECK_DETERMINISM=1"
"!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py
if %ERRORLEVEL% neq 0 (
  echo ERROR: Determinism check failed
  exit /b 1
)
echo ✓ Determinism check complete

echo.
echo ===================================================================
echo TEST 6: COMBINED SWEEP (timing x guidance matrix - ~90 min)
echo ===================================================================
echo.
set "OUT_DIR=%RUN_DIR%\6_combined"
mkdir "!OUT_DIR!" 2>nul
set "SWAP_AT=4,8,12"
set "GUIDE_SCALES=1.0,2.5,5.0"
set "SEQUENTIAL_PROMPTS="
set "CHECK_DETERMINISM="
"!PYEXE!" integrations/omnidreams/scripts/smoke_text_edit.py
if %ERRORLEVEL% neq 0 (
  echo ERROR: Combined sweep failed
  exit /b 1
)
echo ✓ Combined sweep complete

echo.
echo ===================================================================
echo ALL TESTS COMPLETE
echo ===================================================================
echo.
echo Results saved to: %RUN_DIR%
echo.
echo Test outputs:
echo   1_baseline\        - Reference control video + single swap
echo   2_timing_sweep\    - Swaps at chunks 4, 8, 12 (when edits happen)
echo   3_guidance_sweep\  - Guidance scales 1.0, 2.5, 5.0 (edit strength)
echo   4_sequential\      - Multiple edits A -^> B -^> C
echo   5_determinism\     - Bit-clean reproducibility check
echo   6_combined\        - Timing x guidance matrix (3x3 = 9 variants)
echo.
echo Each test directory contains:
echo   - *.mp4           Videos for visual inspection
echo   - report.json     Quantitative metrics (pixel divergence, etc)
echo.
echo Next steps:
echo   1. Review JSON reports for pixel-gap metrics
echo   2. Watch videos to verify visual quality
echo   3. Compare timing (when do edits take effect?)
echo   4. Identify best (swap_at, guidance_scale) pair for your use
echo.

pause
