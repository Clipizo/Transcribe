@echo off
rem Transcribe for Windows.
rem   Double-click: opens the menu.
rem   In PowerShell in this folder:  ./transcribe my-video.mp4   (see ./transcribe help)
setlocal
chcp 65001 >nul
set "KIT=%~dp0"
set "PY=%KIT%envs\asr\Scripts\python.exe"
if exist "%PY%" goto run
echo Transcribe isn't installed yet. Double-click install-windows.bat first.
if "%~1"=="" pause
exit /b 1
:run
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONUTF8=1"
"%PY%" "%KIT%app\transcribe.py" %*
set "CODE=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %CODE%
