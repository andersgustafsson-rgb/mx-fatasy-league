@echo off
REM Hamtar en kopia av Render-databasen till fantasy_mx_local.db (read-only mot prod)
chcp 65001 >nul
cd /d "%~dp0"
title Hamta prod-data

echo.
echo  MX Fantasy - hamta produktionsdata lokalt
echo  ==========================================
echo.
echo  Kraver PRODUCTION_DATABASE_URL i .env
echo  (Render - PostgreSQL - External Database URL)
echo.

set PY=py -3
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

if not exist .pip-cache mkdir .pip-cache
set PIP_CACHE_DIR=%CD%\.pip-cache

"%PY%" -c "import dotenv, sqlalchemy, psycopg2" 2>nul
if errorlevel 1 (
    echo Installerar sync-beroenden...
    "%PY%" -m pip install --no-cache-dir python-dotenv psycopg2-binary SQLAlchemy -q
)

"%PY%" scripts\sync_production_to_local.py %*
echo.
pause
