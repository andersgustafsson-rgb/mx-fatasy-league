@echo off
REM Dolld start — anropas av genvagen / start_local_hidden.vbs
REM Logg skrivs fran start_local.bat (main.py), inte har — undvik fillas pa loggfil.
cd /d "%~dp0"
set MX_LOCAL_HIDDEN=1
if not exist instance mkdir instance
call "%~dp0start_local.bat"
