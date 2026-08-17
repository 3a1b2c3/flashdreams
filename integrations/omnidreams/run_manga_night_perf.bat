@echo off
setlocal enableextensions enabledelayedexpansion

echo.
echo ========================================
echo OmniDreams - Manga Night (Performance)
echo ========================================
echo.

cd /d "%~dp0"

python -m omnidreams.interactive_drive.cli ^
  --scene 0d404ff7-2b66-498c-b047-1ed8cded60d4 ^
  --variant manga_night ^
  --pipeline omnidreams-sv-2steps-perf

pause
