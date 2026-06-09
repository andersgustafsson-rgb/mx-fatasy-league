@echo off
REM MX Fantasy League — lokal utveckling (samma app som Render: main.py)
chcp 65001 >nul
cd /d "%~dp0"
title MX Fantasy League (lokal)

echo.
echo   MX Fantasy League - lokal server
echo   ================================
echo.

REM Overstyr .env sa vi inte traffar Render Postgres hemifran
set PYTHONUTF8=1
set FLASK_ENV=development
set HOST=127.0.0.1
set PORT=5000
set DATABASE_URL=sqlite:///fantasy_mx_local.db
set RENDER=

set PY=py -3
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

if not exist instance mkdir instance
if not exist data mkdir data
if not exist .pip-cache mkdir .pip-cache
set PIP_CACHE_DIR=%CD%\.pip-cache

echo Kontrollerar Python-paket...
"%PY%" -c "import flask; import dotenv; import flask_sqlalchemy; from PIL import Image" 2>nul
if errorlevel 1 (
    echo Installerar/uppdaterar paket fran requirements.txt...
    "%PY%" -m pip install --upgrade pip --no-cache-dir -q
    "%PY%" -m pip install --no-cache-dir -r requirements-dev-min.txt
    if errorlevel 1 (
        echo.
        echo FEL: pip-installation misslyckades.
        echo Prova: installera_venv.bat
        pause
        exit /b 1
    )
    "%PY%" -c "import flask; import dotenv; import flask_sqlalchemy" 2>nul
    if errorlevel 1 (
        echo FEL: Paket saknas fortfarande efter pip install.
        pause
        exit /b 1
    )
    echo Paket installerade.
) else (
    echo Paket OK.
)

echo.
echo Forbereder lokal testanvandare...
"%PY%" scripts\ensure_local_test_user.py
if errorlevel 1 (
    echo VARNING: Kunde inte skapa testanvandare. Prova http://127.0.0.1:%PORT%/fix_user_roles
)
echo.
echo   INLOGGNING:
echo     Efter hamta_prod_data.bat: samma konto som pa Render (t.ex. spliffan)
echo     Annars test: test / password
echo     Tom databas: http://127.0.0.1:%PORT%/register
echo.

echo.
echo Startar servern...
echo   Oppna:  http://127.0.0.1:%PORT%/
echo   Stopp:  Ctrl+C i detta fonster
echo.

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%PORT%/"

"%PY%" main.py
if errorlevel 1 (
    echo.
    echo FEL: Servern startade inte.
)

echo.
echo Servern stoppad.
pause
