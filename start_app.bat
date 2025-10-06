@echo off
echo Starting MX Fantasy League...
echo.
cd /d "C:\projects\MittFantasySpel"
echo Current directory: %CD%
echo.
echo Starting Flask app...
python app.py
echo.
echo App stopped. Press any key to exit...
pause
