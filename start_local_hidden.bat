@echo off
REM Dolld start — anropas av genvagen / start_local_hidden.vbs
cd /d "%~dp0"
set MX_LOCAL_HIDDEN=1
if not exist instance mkdir instance
call "%~dp0start_local.bat" > "%~dp0instance\local_server.log" 2>&1
