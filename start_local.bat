@echo off
REM MX Fantasy League - lokal utveckling (samma app som Render: main.py)
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
REM Prod-liknande pick-las lokalt. Satt =1 tillfalligt for att testa alla omgangar:
set PICKS_UNLOCK_ALL_LOCAL=0
set FLASK_USE_RELOADER=0
REM Visuell preview av sasongsteam-promo (glow/CTA). Combined: SEASON_TEAM_COMBINED_LIVE=1
set SEASON_TEAM_PROMO_LIVE=1

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

set "LOCAL_URL=http://127.0.0.1:%PORT%/"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\is_port_listening.ps1" -Port %PORT% >nul 2>&1
if not errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local_health_ok.ps1" -Port %PORT% >nul 2>&1
  if not errorlevel 1 (
    echo.
    echo   Servern kor redan pa port %PORT%.
    echo   Oppnar webblasare: %LOCAL_URL%
    call "%~dp0scripts\open_local_url.bat" "%LOCAL_URL%"
    if defined MX_LOCAL_HIDDEN exit /b 0
    echo.
    echo   Stoppa med genvagen "MX Fantasy ^(stopp^)" eller stopp_local.bat
    pause
    exit /b 0
  )
  echo.
  echo   Port %PORT% upptagen men servern svarar inte — rensar och startar om...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_local_server.ps1" -Port %PORT%
)

echo.
echo Startar servern...
echo   Forsta start efter stopp kan ta 30-60 sek ^(DB-init^).
echo   Oppnas automatiskt: %LOCAL_URL%
if defined MX_LOCAL_HIDDEN (
  echo   Dolt fonster — senaste logg: instance\local_server_latest.txt
  echo   ^(sok "Running on http://127.0.0.1:%PORT%" i loggfilen^)
) else (
  echo   Stopp:  Ctrl+C i detta fonster
)
echo.

REM Oppna webblasare forst nar porten lyssnar (DB-init kan ta tid)
start /b "" "%~dp0scripts\wait_and_open_browser.bat" %PORT%

if defined MX_LOCAL_HIDDEN (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_local_server_logged.ps1"
) else (
  "%PY%" main.py
)
if errorlevel 1 (
    echo.
    echo FEL: Servern startade inte.
    if defined MX_LOCAL_HIDDEN echo Se instance\local_server_latest.txt
)

echo.
echo Servern stoppad.
if defined MX_LOCAL_HIDDEN exit /b
pause
