@echo off
setlocal enableextensions enabledelayedexpansion

echo.
echo ========================================
echo OmniDreams Interactive Drive - Manga Night
echo ========================================
echo.

cd /d "%~dp0"

REM Launch with manga_night variant
python -m omnidreams.interactive_drive.cli ^
  --scene-path 0d404ff7-2b66-498c-b047-1ed8cded60d4 ^
  --variant manga_night

pause
