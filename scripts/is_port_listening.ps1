param([int]$Port = 5000)
$ok = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($ok) { exit 0 }
exit 1
