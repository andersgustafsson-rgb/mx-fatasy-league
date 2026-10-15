@echo off
REM Oppna lokal MX Fantasy i webblasare (Chrome om finns, annars Windows standard).
set "LOCAL_URL=%~1"
if "%LOCAL_URL%"=="" set "LOCAL_URL=http://127.0.0.1:5000/"

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
  start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" "%LOCAL_URL%"
  exit /b 0
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
  start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" "%LOCAL_URL%"
  exit /b 0
)
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
  start "" "%LocalAppData%\Google\Chrome\Application\chrome.exe" "%LOCAL_URL%"
  exit /b 0
)
REM Edge / standardwebblasare
start "" "%LOCAL_URL%"
exit /b 0
