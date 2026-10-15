@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PORT=5000
if not "%~1"=="" set PORT=%~1
echo Stoppar lokal server pa port %PORT%...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_local_server.ps1" -Port %PORT%
pause
