@echo off
rem ============================================================
rem  YT Video Downloader - Setup
rem  Installs every dependency inside this project folder only.
rem  Existing global tools (Python, Node, Deno, ffmpeg) are reused.
rem  Nothing is ever installed globally.
rem
rem  Developer: Muhammad Abdullah Awais (www.abdullahawais.com)
rem ============================================================
setlocal EnableExtensions
title YT Video Downloader - Setup
cd /d "%~dp0"

set "PY_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20260924/cpython-3.12.14%%2B20260924-x86_64-pc-windows-msvc-install_only.tar.gz"
set "PY_CHECK=import sys; sys.exit(sys.version_info[:2] < (3, 10))"
set "RUNTIME_DIR=%~dp0runtime"
set "LOCAL_PY=%RUNTIME_DIR%\python\python.exe"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "PYTHON_EXE="
set "PYTHON_ARGS="

echo.
echo  YT Video Downloader - Setup
echo  ---------------------------
echo.

rem ---- 1. Python environment -------------------------------------------
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "%PY_CHECK%" >nul 2>&1 && (
        echo [1/4] Using existing local environment .venv
        goto :install_packages
    )
    echo [1/4] Existing .venv is broken, recreating it...
    rmdir /s /q "%~dp0.venv"
)

call :find_python
if not defined PYTHON_EXE call :download_python
if not defined PYTHON_EXE goto :fail

echo [1/4] Creating local environment .venv
"%PYTHON_EXE%" %PYTHON_ARGS% -m venv "%~dp0.venv"
if errorlevel 1 (
    echo ERROR: Could not create the virtual environment.
    goto :fail
)

:install_packages
rem ---- 2. Python packages (local to .venv) -----------------------------
echo [2/4] Installing Python packages into .venv
"%VENV_PY%" -m pip install --upgrade pip --disable-pip-version-check --retries 10 --timeout 60 --quiet
if errorlevel 1 goto :fail_pip
"%VENV_PY%" -m pip install --upgrade -r "%~dp0requirements.txt" --disable-pip-version-check --retries 10 --timeout 60 --quiet
if errorlevel 1 goto :fail_pip

rem ---- 3. JavaScript runtime (needed by yt-dlp for YouTube) ------------
set "HAS_JS="
where deno >nul 2>&1 && set "HAS_JS=Deno"
if not defined HAS_JS (
    node -e "process.exit(parseInt(process.versions.node, 10) < 20 ? 1 : 0)" >nul 2>&1 && set "HAS_JS=Node.js"
)
if defined HAS_JS (
    echo [3/4] JavaScript runtime found: %HAS_JS%
) else (
    echo [3/4] No JavaScript runtime found, installing Deno into .venv
    "%VENV_PY%" -m pip install --upgrade deno --disable-pip-version-check --retries 10 --timeout 60 --quiet
    if errorlevel 1 goto :fail_pip
)

rem ---- 4. ffmpeg (needed to merge video + audio and to create MP3) -----
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [4/4] ffmpeg not found, installing a local copy into .venv
    "%VENV_PY%" -m pip install --upgrade imageio-ffmpeg --disable-pip-version-check --retries 10 --timeout 60 --quiet
    if errorlevel 1 goto :fail_pip
) else (
    echo [4/4] ffmpeg found on this system
)

if not exist "%~dp0output" mkdir "%~dp0output"

echo.
echo  Setup complete. Run Start.bat to launch the app.
echo.
pause
exit /b 0


rem ======================================================================
:find_python
py -3 -c "%PY_CHECK%" >nul 2>&1 && (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    echo [1/4] Using Python from the py launcher
    exit /b 0
)
python -c "%PY_CHECK%" >nul 2>&1 && (
    set "PYTHON_EXE=python"
    echo [1/4] Using Python found on PATH
    exit /b 0
)
if exist "%LOCAL_PY%" (
    "%LOCAL_PY%" -c "%PY_CHECK%" >nul 2>&1 && (
        set "PYTHON_EXE=%LOCAL_PY%"
        echo [1/4] Using local Python in runtime\python
        exit /b 0
    )
)
exit /b 0


:download_python
echo [1/4] Python 3.10+ not found. Downloading a portable Python into runtime\
where curl.exe >nul 2>&1 || (
    echo ERROR: curl.exe is not available. Install Python 3.10+ manually and run Setup.bat again.
    exit /b 1
)
where tar.exe >nul 2>&1 || (
    echo ERROR: tar.exe is not available. Install Python 3.10+ manually and run Setup.bat again.
    exit /b 1
)
if exist "%RUNTIME_DIR%\python" rmdir /s /q "%RUNTIME_DIR%\python"
if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%"
rem A leftover python.tar.gz is always a partial download, so resume it.
curl.exe -L --fail --retry 10 --retry-all-errors --retry-delay 3 -C - --progress-bar -o "%RUNTIME_DIR%\python.tar.gz" "%PY_URL%"
if errorlevel 1 (
    echo ERROR: Download failed. Check your internet connection and run Setup.bat again, it will resume.
    exit /b 1
)
tar.exe -xzf "%RUNTIME_DIR%\python.tar.gz" -C "%RUNTIME_DIR%"
if errorlevel 1 (
    echo ERROR: Could not extract the Python archive. Run Setup.bat again to download it fresh.
    del /q "%RUNTIME_DIR%\python.tar.gz"
    if exist "%RUNTIME_DIR%\python" rmdir /s /q "%RUNTIME_DIR%\python"
    exit /b 1
)
del /q "%RUNTIME_DIR%\python.tar.gz"
if not exist "%LOCAL_PY%" (
    echo ERROR: Portable Python was not found after extraction.
    exit /b 1
)
set "PYTHON_EXE=%LOCAL_PY%"
echo       Portable Python installed in runtime\python
exit /b 0


:fail_pip
echo ERROR: Package installation failed. Check your internet connection and try again.

:fail
echo.
echo  Setup did not complete.
echo.
pause
exit /b 1
