@echo off
setlocal

REM Download OmniDreams scene USDZs into the shared scenes cache
REM (%FLASHDREAMS_CACHE_DIR%\omnidreams-scenes, default ~\.cache\flashdreams).
REM Wraps omnidreams-prepare; skips the model / text-encoder prewarm so this
REM ONLY stages scenes. Pass selector flags through, e.g.:
REM   download_scenes.bat                                          (ALL scenes, ALL variants -- large)
REM   download_scenes.bat --scene-uuid clipgt-0d404ff7-2b66-498c-b047-1ed8cded60d4
REM   download_scenes.bat --scene-uuid clipgt-XXXX --scene-variant rain
REM   download_scenes.bat --scene-uuid clipgt-XXXX --force          (re-download)
REM Browse available UUIDs: https://huggingface.co/datasets/nvidia/omni-dreams-scenes/tree/main/scenes

cd /d C:\workspace\world\flashdream_public

REM gates nvidia/omni-dreams-scenes; pull from the cached token file if unset.
if "%HF_TOKEN%"=="" if exist "C:\Users\kschmid\.cache\omni-dreams\huggingface\token" set /p HF_TOKEN=<"C:\Users\kschmid\.cache\omni-dreams\huggingface\token"
if "%HF_TOKEN%"=="" echo WARNING: HF_TOKEN is not set; downloads from gated nvidia/omni-dreams-scenes will 403.

uv run --no-sync --package flashdreams-omnidreams omnidreams-prepare --skip-hf-prewarm --skip-text-encoder %*

endlocal
