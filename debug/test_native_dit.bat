@echo off
setlocal enableextensions enabledelayedexpansion

cd /d C:\workspace\world\flashdream_public

set "VENV=C:\workspace\world\flashdream_public\.venv"
set "PYEXE=%VENV%\Scripts\python.exe"

echo.
echo ===================================================================
echo NATIVE DIT EXTENSION LOAD TEST
echo ===================================================================
echo.
echo This test will attempt to load the native DIT extension separately.
echo If it hangs, the issue is definitely in native DIT on Windows.
echo If it completes quickly, the app should work now.
echo.
echo Press Ctrl+C to cancel at any time.
echo.

"%PYEXE%" test_native_dit_minimal.py

echo.
echo Test completed.
echo.
