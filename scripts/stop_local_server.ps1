# Stop whatever is listening on the local dev port (default 5000).
param([int]$Port = 5000)

$conns = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if (-not $conns.Count) {
    Write-Host "Ingen server lyssnar pa port $Port."
    exit 0
}

$procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $procIds) {
    try {
        Stop-Process -Id $procId -Force -ErrorAction Stop
        Write-Host "Stoppade process $procId (port $Port)."
    } catch {
        Write-Host "Kunde inte stoppa PID $procId (${_})"
        exit 1
    }
}
exit 0
