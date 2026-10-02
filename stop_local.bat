@echo off
REM Stoppa dold lokal MX Fantasy-server (port 5000)
cd /d "%~dp0"
title Stoppa MX Fantasy (lokal)
echo.
echo   Stoppar lokal server pa port 5000...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$conns = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue;" ^
  "if (-not $conns) { Write-Host '  Ingen server kor pa 5000.'; exit 0 };" ^
  "$pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "foreach ($pid in $pids) { try { Stop-Process -Id $pid -Force -ErrorAction Stop; Write-Host ('  Stoppade PID ' + $pid) } catch { Write-Host ('  Kunde inte stoppa PID ' + $pid + ': ' + $_.Exception.Message) } }"
echo.
timeout /t 2 /nobreak >nul
