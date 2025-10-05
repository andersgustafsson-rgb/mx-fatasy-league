@echo off
REM MX Fantasy League - Windows Startup Script

echo 🚀 Starting MX Fantasy League...

REM Check if .env exists
if not exist .env (
    echo ⚠️  .env file not found. Creating from template...
    copy env.example .env
    echo 📝 Please edit .env file with your configuration before running again.
    pause
    exit /b 1
)

REM Create necessary directories
if not exist instance mkdir instance
if not exist static\uploads\leagues mkdir static\uploads\leagues
if not exist static\images mkdir static\images
if not exist static\sfx mkdir static\sfx
if not exist static\brand_logos mkdir static\brand_logos
if not exist data mkdir data
if not exist backups mkdir backups

REM Install dependencies
pip install -r requirements.txt

REM Run the application
python app.py

pause
