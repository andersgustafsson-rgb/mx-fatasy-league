@echo off
echo Adding all changes...
git add .

echo Committing changes...
git commit -m "Add Track Maps functionality and improve fallback message

- Added Track Maps link to navigation in index.html
- Modified setup_trackmaps.py to select only one image per track
- Updated trackmaps.html with better fallback message
- Track maps work locally but images are too large for GitHub deployment"

echo Pushing to GitHub...
git push origin main

echo Done! Changes pushed to GitHub.
pause
