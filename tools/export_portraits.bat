@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
title Exportera forarportratt till filer

set PY=py -3
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

echo.
echo  MX Fantasy - exportera portratt fran databas till static/riders/portraits
echo  ===========================================================================
echo.
echo  Kraver DATABASE_URL eller PRODUCTION_DATABASE_URL i .env
echo.
echo  1) Test forst:  export_portraits.bat --dry-run
echo  2) Kor pa riktigt: export_portraits.bat --clear-blobs
echo  3) git add static/riders/portraits ^&^& git commit ^&^& git push
echo.

"%PY%" tools\export_db_portraits_to_files.py %*

pause
