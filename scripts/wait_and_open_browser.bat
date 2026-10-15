@echo off
REM Vantar tills Flask lyssnar, oppnar sedan webblasaren (kor i bakgrunden fran start_local.bat).
set "PORT=%~1"
if "%PORT%"=="" set "PORT=5000"
set "LOCAL_URL=http://127.0.0.1:%PORT%/"
set /a TRIES=0

:loop
ping 127.0.0.1 -n 2 >nul
set /a TRIES+=1
if %TRIES% gtr 240 exit /b 1

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0local_health_ok.ps1" -Port %PORT% >nul 2>&1
if errorlevel 1 goto loop

call "%~dp0open_local_url.bat" "%LOCAL_URL%"
exit /b 0
