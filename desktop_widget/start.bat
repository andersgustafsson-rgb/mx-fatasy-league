@echo off
cd /d "%~dp0"
if not exist node_modules (
  echo Installerar dependencies...
  call npm install
)
echo Startar MX Fantasy Widget...
call npm start
