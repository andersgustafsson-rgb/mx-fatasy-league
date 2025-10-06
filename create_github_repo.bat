@echo off
echo Creating GitHub repository for MX Fantasy League...
echo.

cd /d "C:\projects\MittFantasySpel"

echo 1. Initializing Git repository...
git init

echo 2. Adding all files...
git add .

echo 3. Creating initial commit...
git commit -m "Initial commit - MX Fantasy League with dark mode fixes and user management"

echo 4. Creating GitHub repository...
echo Please go to https://github.com/new and create a new repository named "mx-fantasy-league"
echo Then copy the repository URL and run the next commands manually:
echo.
echo git remote add origin https://github.com/YOUR_USERNAME/mx-fantasy-league.git
echo git branch -M main
echo git push -u origin main
echo.
echo Repository setup complete!
pause
