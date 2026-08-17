@echo off
setlocal enableextensions enabledelayedexpansion

echo.
echo ========================================
echo OmniDreams Interactive Drive - Variants
echo ========================================
echo.
echo Available variants:
echo   1) default       - Original scene
echo   2) rain         - Rainy weather
echo   3) snow         - Snowy weather
echo   4) mario        - Themed variant
echo   5) manga_night  - Anime/manga neon cyberpunk
echo.

set /p choice="Select variant (1-5): "

if "%choice%"=="1" (
    set variant=default
) else if "%choice%"=="2" (
    set variant=rain
) else if "%choice%"=="3" (
    set variant=snow
) else if "%choice%"=="4" (
    set variant=mario
) else if "%choice%"=="5" (
    set variant=manga_night
) else (
    echo Invalid choice. Defaulting to manga_night.
    set variant=manga_night
)

echo.
echo Launching with variant: !variant!
echo.

cd /d "%~dp0"

python -m omnidreams.interactive_drive.cli ^
  --scene-path 0d404ff7-2b66-498c-b047-1ed8cded60d4 ^
  --variant !variant!

pause
