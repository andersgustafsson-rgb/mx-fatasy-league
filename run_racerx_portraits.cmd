@echo off
setlocal

REM Double-click helper: scrape RacerX riders -> import headshots URLs into DB.
REM Runs from repo root regardless of current directory.

cd /d "%~dp0"

echo.
echo ==========================================
echo  MX Fantasy: RacerX portraits importer
echo ==========================================
echo.
echo This will:
echo  1) Scrape RacerX rider list to data\racerx_riders_2026.csv
echo  2) Import headshot URLs into your database (safe default: IMPORT_MODE=url)
echo.

REM You can change this to "download" if you later want local webp files.
if "%IMPORT_MODE%"=="" set IMPORT_MODE=url
echo Using IMPORT_MODE=%IMPORT_MODE%
echo.

echo [1/2] Scraping RacerX riders...
python tools\scrape_racerx_riders.py
if errorlevel 1 (
  echo.
  echo [ERROR] scrape_racerx_riders failed.
  pause
  exit /b 1
)

echo.
echo [2/2] Importing portraits into DB...
python tools\import_racerx_images.py
if errorlevel 1 (
  echo.
  echo [ERROR] import_racerx_images failed.
  echo Tip: ensure DATABASE_URL is set and reachable.
  pause
  exit /b 1
)

echo.
echo [OK] Done. Now refresh your site and check Race Resultat / Race Picks.
echo If it looks good, commit and push your changes (this script only updates DB, not git).
echo.
pause
