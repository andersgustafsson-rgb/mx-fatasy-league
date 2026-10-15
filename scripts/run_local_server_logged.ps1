# Run main.py; append output to a new log under instance\logs\ (avoids locked local_server.log).
# Flask writes warnings to stderr — must not treat as terminating errors.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logDir = Join-Path $root "instance\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("local_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

$latest = Join-Path $root "instance\local_server_latest.txt"
Set-Content -Path $latest -Value $log -Encoding UTF8

Add-Content -Path $log -Value ("===== MX Fantasy start {0} =====" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

$py = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $py) {
    & $py "main.py" *>> $log
    exit $LASTEXITCODE
}

& py -3 "main.py" *>> $log
exit $LASTEXITCODE
