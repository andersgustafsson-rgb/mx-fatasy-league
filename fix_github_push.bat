@echo off
echo Fixing GitHub push conflict...
echo.

cd /d "C:\projects\MittFantasySpel"

echo 1. Removing old remote...
git remote remove origin

echo.
echo 2. Adding correct remote for mx-fatasy-league...
git remote add origin https://github.com/andersgustafsson-rgb/mx-fatasy-league.git

echo.
echo 3. Force pushing to overwrite remote...
git push -f origin main

echo.
echo Done! Check your repository at:
echo https://github.com/andersgustafsson-rgb/mx-fatasy-league
echo.
pause
