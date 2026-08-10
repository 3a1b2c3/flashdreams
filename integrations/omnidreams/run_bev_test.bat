@echo off
REM run_bev_test.bat - run the headless BEV rotation test with the SAME env as
REM run_interactive_drive.bat (vcvars + CUDA v13.0 + .venv\Scripts on PATH so
REM torch's cpp_extension JIT finds ninja.exe / cl.exe for the Ludus plugin).
setlocal enableextensions
set "VENV=C:\workspace\world\flashdream_public\.venv"
set "CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
set "CUDA_PATH=%CUDA_HOME%"
set "PATH=%CUDA_HOME%\bin;%VENV%\Scripts;%PATH%"
set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if exist "%VCVARS%" call "%VCVARS%" >nul

if "%HF_TOKEN%"=="" if exist "%~dp0.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0.env") do (
        if /I "%%A"=="HF_TOKEN" set "HF_TOKEN=%%B"
    )
)

cd /d "%~dp0"
"%VENV%\Scripts\python.exe" bev_rotation_test.py
exit /b %ERRORLEVEL%
