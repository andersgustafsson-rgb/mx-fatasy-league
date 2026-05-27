@echo off
REM Lokal utveckling — SQLite, samma app som Render (create_app via wsgi.py)
cd /d "%~dp0"

echo Starting MX Fantasy League (local SQLite)...
echo Open: http://127.0.0.1:5000
echo.

if not exist .env (
    echo .env saknas — kopierar fran env.example ...
    copy env.example .env
    echo Redigera .env vid behov, kor sedan igen.
    pause
    exit /b 1
)

if not exist instance mkdir instance
if not exist data mkdir data

set PYTHONUTF8=1
set FLASK_ENV=development
set DATABASE_URL=sqlite:///fantasy_mx.db
set PORT=5000

py -3 -m pip install -r requirements.txt -q
py -3 wsgi.py

pause
