@echo off
echo Pushing MX Fantasy League to GitHub...
echo.

cd /d "C:\projects\MittFantasySpel"

echo 1. Checking Git status...
git status

echo.
echo 2. Adding all files...
git add .

echo.
echo 3. Creating commit...
git commit -m "Initial commit - MX Fantasy League with dark mode fixes"

echo.
echo 4. Setting remote origin...
git remote add origin https://github.com/andersgustafsson-rgb/mx-fatasy-league.git

echo.
echo 5. Setting main branch...
git branch -M main

echo.
echo 6. Pushing to GitHub...
git push -u origin main

echo.
echo Done! Check your repository at:
echo https://github.com/andersgustafsson-rgb/mx-fatasy-league
echo.
pause
