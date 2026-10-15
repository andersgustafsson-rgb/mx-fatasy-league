# Exit 0 when local Flask responds on /health within timeout.
param(
    [int]$Port = 5000,
    [int]$TimeoutSec = 2
)

$url = "http://127.0.0.1:$Port/health"
try {
    $res = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $TimeoutSec
    if ($res.StatusCode -eq 200) { exit 0 }
} catch {
    exit 1
}
exit 1
