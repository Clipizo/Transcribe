@echo off
rem Transcribe installer for Windows. Double-click this file.
rem It downloads "uv" (a small tool that installs Python) into this folder,
rem then runs app\setup_kit.py, which does the rest. Everything goes into this
rem folder (only Microsoft's Visual C++ component, if Windows lacks it, is
rem installed on the computer, after asking).
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Transcribe installer

set "NOPAUSE="
for %%A in (%*) do if /i "%%~A"=="--yes" set "NOPAUSE=1"

set "KIT=%~dp0"
rem Ignore Python settings that other programs may have left on this computer.
set "PYTHONHOME="
set "PYTHONPATH="
rem The uv version this kit was tested with.
set "UV_VERSION=0.13.7"
set "UV_DIR=%KIT%.tools\uv"
set "UV=%UV_DIR%\uv.exe"
if exist "%UV%" goto have_uv
if exist "%UV_DIR%\bin\uv.exe" set "UV=%UV_DIR%\bin\uv.exe"
if exist "%UV%" goto have_uv

echo Downloading uv (a small tool that installs Python for Transcribe)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072; $env:UV_UNMANAGED_INSTALL='%UV_DIR%'; irm https://astral.sh/uv/%UV_VERSION%/install.ps1 | iex"
if exist "%UV_DIR%\uv.exe" set "UV=%UV_DIR%\uv.exe"
if exist "%UV_DIR%\bin\uv.exe" set "UV=%UV_DIR%\bin\uv.exe"
if exist "%UV%" goto have_uv

rem Fall back to a uv that is already installed on this computer.
for /f "delims=" %%U in ('where uv 2^>nul') do set "UV=%%U"
if exist "%UV%" goto have_uv

echo.
echo Could not download uv. Check your internet connection and try again.
echo If it still fails, your network may block astral.sh or github.com.
if not defined NOPAUSE pause
exit /b 1

:have_uv
set "KIT_UV=%UV%"
set "UV_PYTHON_INSTALL_DIR=%KIT%.tools\python"
set "UV_CACHE_DIR=%KIT%.tools\uv-cache"
set "UV_PYTHON_PREFERENCE=only-managed"
set "UV_NO_CONFIG=1"
set "UV_HTTP_TIMEOUT=300"
set "UV_HTTP_CONNECT_TIMEOUT=60"
set "UV_HTTP_RETRIES=8"
"%UV%" run --no-project --python 3.12 "%KIT%app\setup_kit.py" %*
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="2" echo If the text above is about a download, check your internet connection and run the installer again.
if not defined NOPAUSE pause
exit /b %CODE%
