@echo off
REM Installerar alla Python-paket i .venv (kor kors om start_local strular)
chcp 65001 >nul
cd /d "%~dp0"

echo Installerar MX Fantasy League dependencies...
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Skapar virtuell miljo...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo FEL: Kunde inte skapa .venv. Installera Python 3.11+ fran python.org
        pause
        exit /b 1
    )
)

set PY=.venv\Scripts\python.exe
if not exist .pip-cache mkdir .pip-cache
set PIP_CACHE_DIR=%CD%\.pip-cache

"%PY%" -m pip install --upgrade pip --no-cache-dir
echo ^(minimal lista — utan Pillow, funkar pa Python 3.14^)
"%PY%" -m pip install --no-cache-dir -r requirements-dev-min.txt
if errorlevel 1 (
    echo.
    echo FEL: Installation misslyckades.
    pause
    exit /b 1
)

echo.
echo Klart! Kor start_local.bat for att starta servern.
pause
