@echo off
REM MX Fantasy League - Windows startup (samma app som Render)
cd /d "%~dp0"

echo Starting MX Fantasy League...
echo Open: http://127.0.0.1:5000
echo For lokal SQLite-test: start_local.bat
echo.

if not exist .env (
    echo .env saknas — kopierar fran env.example ...
    copy env.example .env
    echo Redigera .env och kor igen.
    pause
    exit /b 1
)

if not exist instance mkdir instance
if not exist static\uploads\leagues mkdir static\uploads\leagues
if not exist static\images mkdir static\images
if not exist static\sfx mkdir static\sfx
if not exist static\brand_logos mkdir static\brand_logos
if not exist data mkdir data
if not exist backups mkdir backups

set PYTHONUTF8=1

py -3 -m pip install -r requirements.txt -q
py -3 wsgi.py

pause
