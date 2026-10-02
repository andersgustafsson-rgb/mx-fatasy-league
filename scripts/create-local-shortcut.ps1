# Skapar genvagar: start (dolt) + stopp — skrivbord och Start-meny
$projectRoot = Split-Path -Parent $PSScriptRoot
$startTarget = Join-Path $projectRoot "start_local_hidden.vbs"
$stopTarget = Join-Path $projectRoot "stop_local.bat"
$icon = Join-Path $projectRoot "static\icons\mx_fantasy_local.ico"
$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"

if (-not (Test-Path $startTarget)) {
    Write-Error "Hittar inte $startTarget"
    exit 1
}

function New-MxFantasyShortcut([string]$lnkPath, [string]$target, [string]$description) {
    $ws = New-Object -ComObject WScript.Shell
    $shortcut = $ws.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $target
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.WindowStyle = 1
    $shortcut.Description = $description
    if (Test-Path $icon) {
        $shortcut.IconLocation = "$icon,0"
    }
    $shortcut.Save()
    Write-Host "  $lnkPath"
}

Write-Host "Genvagar skapade:"
New-MxFantasyShortcut (Join-Path $desktop "MX Fantasy (lokalt).lnk") $startTarget "Starta MX Fantasy lokalt (doltt fonster)"
New-MxFantasyShortcut (Join-Path $startMenu "MX Fantasy (lokalt).lnk") $startTarget "Starta MX Fantasy lokalt (doltt fonster)"
New-MxFantasyShortcut (Join-Path $desktop "MX Fantasy (stopp).lnk") $stopTarget "Stoppa lokal MX Fantasy-server"
New-MxFantasyShortcut (Join-Path $startMenu "MX Fantasy (stopp).lnk") $stopTarget "Stoppa lokal MX Fantasy-server"
Write-Host ""
Write-Host "Start: sok 'MX Fantasy (lokalt)'"
Write-Host "Stopp: sok 'MX Fantasy (stopp)'"
