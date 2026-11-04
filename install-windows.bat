@echo off
rem Transcribe installer for Windows. Double-click this file.
rem It downloads "uv" (a small tool that installs Python) into this folder,
rem then runs app\setup_kit.py, which does the rest. Nothing is installed
rem outside this folder.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Transcribe installer

set "NOPAUSE="
for %%A in (%*) do if /i "%%~A"=="--yes" set "NOPAUSE=1"

set "KIT=%~dp0"
set "UV_DIR=%KIT%.tools\uv"
set "UV=%UV_DIR%\uv.exe"
if exist "%UV%" goto have_uv
if exist "%UV_DIR%\bin\uv.exe" set "UV=%UV_DIR%\bin\uv.exe"
if exist "%UV%" goto have_uv

echo Downloading uv (a small tool that installs Python for Transcribe)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_UNMANAGED_INSTALL='%UV_DIR%'; irm https://astral.sh/uv/install.ps1 | iex"
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
"%UV%" run --no-project --python 3.12 "%KIT%app\setup_kit.py" %*
set "CODE=%ERRORLEVEL%"
echo.
if not defined NOPAUSE pause
exit /b %CODE%
