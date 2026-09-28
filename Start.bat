@echo off
rem ============================================================
rem  YT Video Downloader - Start
rem  Launches the local server and opens the app in your browser.
rem
rem  Developer: Muhammad Abdullah Awais (www.abdullahawais.com)
rem ============================================================
setlocal EnableExtensions
title YT Video Downloader
cd /d "%~dp0"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo.
    echo  The app is not set up yet. Please run Setup.bat first.
    echo.
    pause
    exit /b 1
)

"%~dp0.venv\Scripts\python.exe" "%~dp0app.py" --open
if errorlevel 1 pause
