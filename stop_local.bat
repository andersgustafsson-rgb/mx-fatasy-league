@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Stoppa MX Fantasy (lokal)
set PORT=5000
if not "%~1"=="" set PORT=%~1
echo.
echo   Stoppar lokal server pa port %PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_local_server.ps1" -Port %PORT%
echo.
if defined MX_LOCAL_HIDDEN exit /b 0
pause
