@echo off
setlocal enableextensions

echo.
echo ===================================================================
echo FLASHDREAM INTERACTIVE-DRIVE: COMPLETE SETUP
echo ===================================================================
echo This script downloads all models and precompiles C++ extensions (Ludus + PhysX).
echo Run this ONCE. Then just use: .\run_interactive_drive_perf.bat
echo.
echo ===================================================================
echo.

cd /d C:\workspace\world\flashdream_public

set "VENV=C:\workspace\world\flashdream_public\.venv"
set "PYEXE=%VENV%\Scripts\python.exe"

if not exist "%PYEXE%" (
    echo ERROR: .venv not found at %VENV%
    exit /b 1
)

set "VIRTUAL_ENV="
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "FLASHDREAMS_MIN_CACHE_FREE_GB=0"
set "TORCHINDUCTOR_COMPILE_THREADS=1"

echo [1/3] Checking Python version...
"%PYEXE%" --version
echo.

echo [2/3] Downloading all models (Cosmos-Reason1, LightWave, OmniDreams)...
"%PYEXE%" -B -c "from transformers import AutoModel; AutoModel.from_pretrained('nvidia/Cosmos-Reason1-7B')" >nul 2>&1 && echo [OK] Cosmos-Reason1 || (echo [ERROR] Cosmos-Reason1 failed & "%PYEXE%" -B -c "from transformers import AutoModel; AutoModel.from_pretrained('nvidia/Cosmos-Reason1-7B')" & exit /b 1)
"%PYEXE%" -B -c "import torch; torch.hub.load_state_dict_from_url('https://huggingface.co/lightx2v/Autoencoders/resolve/main/lightvaew2_1.pth')" >nul 2>&1 && echo [OK] LightWave VAE || (echo [ERROR] LightWave VAE failed & "%PYEXE%" -B -c "import torch; torch.hub.load_state_dict_from_url('https://huggingface.co/lightx2v/Autoencoders/resolve/main/lightvaew2_1.pth')" & exit /b 1)
"%PYEXE%" -B -c "import torch; torch.hub.load_state_dict_from_url('https://huggingface.co/lightx2v/Autoencoders/resolve/main/lighttaew2_1.pth')" >nul 2>&1 && echo [OK] LightWave TAE || (echo [ERROR] LightWave TAE failed & "%PYEXE%" -B -c "import torch; torch.hub.load_state_dict_from_url('https://huggingface.co/lightx2v/Autoencoders/resolve/main/lighttaew2_1.pth')" & exit /b 1)
"%PYEXE%" -B -c "from huggingface_hub import hf_hub_download; hf_hub_download('nvidia/omni-dreams-models', 'single_view/2b_res720p_30fps_i2v_hdmap_distilled.pt')" >nul 2>&1 && echo [OK] OmniDreams I2V || (echo [ERROR] OmniDreams I2V failed - set HF_TOKEN or login with: huggingface-cli login & exit /b 1)
echo.

echo [3/3] Precompiling Ludus C++ extension with MSVC...
echo Calling vcvarsall.bat x64...
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64

set "CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0"
set "PATH=%CUDA_HOME%\bin;%CUDA_HOME%\lib\x64;%PATH%"
set "TORCH_CUDA_ARCH_LIST=12.0a"

echo Clearing old Ludus build cache...
if exist "%LocalAppData%\torch_extensions\torch_extensions\Cache\py311_cu128\ludus_renderer_plugin" (
    rmdir /s /q "%LocalAppData%\torch_extensions\torch_extensions\Cache\py311_cu128\ludus_renderer_plugin"
    echo Cache cleared.
)

echo Ensuring build directory exists...
if not exist "%LocalAppData%\torch_extensions\torch_extensions\Cache\py311_cu128" (
    mkdir "%LocalAppData%\torch_extensions\torch_extensions\Cache\py311_cu128"
)

echo Building Ludus C++ extension (this may take 2-5 minutes)...
"%PYEXE%" -B -c "import sys; sys.path.insert(0, 'integrations/omnidreams'); from ludus_renderer._ops._plugin import _get_plugin; _get_plugin(); print('[OK] Ludus precompiled')" || (
    echo.
    echo ===================================================================
    echo Ludus precompile FAILED
    echo ===================================================================
    echo Check the error above for details (likely MSVC/CUDA/compiler issue).
    exit /b 1
)
echo.

echo [4/4] Rebuilding PhysX...
"%PYEXE%" -B -c "import sys; sys.path.insert(0, 'integrations/omnidreams'); from ludus_renderer.physx import load_native_physx; m = load_native_physx(); print('[OK] PhysX loaded')" && (
    echo.
    echo ===================================================================
    echo SETUP COMPLETE!
    echo ===================================================================
    echo.
    echo ✓ Models downloaded
    echo ✓ Ludus C++ extension precompiled
    echo ✓ PhysX rebuilt for your Python version
    echo.
    echo Next step:
    echo   .\run_interactive_drive_perf.bat
    echo.
    echo ===================================================================
) || (
    echo.
    echo ===================================================================
    echo SETUP FAILED at PhysX rebuild
    echo ===================================================================
    echo Try running: .\rebuild_physx_python311.bat
    exit /b 1
)

endlocal
