# Skapar genvag pa skrivbordet till start_local.bat
$projectRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $projectRoot "start_local.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "MX Fantasy (lokalt).lnk"

if (-not (Test-Path $target)) {
    Write-Error "Hittar inte $target"
    exit 1
}

$ws = New-Object -ComObject WScript.Shell
$shortcut = $ws.CreateShortcut($lnk)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $projectRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "Starta MX Fantasy League lokalt (SQLite, main.py)"
$shortcut.Save()

Write-Host "Genvag skapad:"
Write-Host "  $lnk"
