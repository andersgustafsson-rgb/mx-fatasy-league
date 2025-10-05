# Dedupe track maps in static\trackmaps\2026 by grouping variants
# Keeps one preferred file per base name, moves the rest to a backup folder.

param(
  [string]$Root = "static\trackmaps\2026",
  [string]$Backup = "static\trackmaps\2026_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
)

Write-Host "Root:" (Resolve-Path $Root) -ForegroundColor Cyan

if (!(Test-Path $Root)) {
  Write-Host "Mappen hittas inte:" (Resolve-Path .) "\" $Root -ForegroundColor Red
  exit 1
}

# Skapa backupmapp
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
Write-Host "Backupmapp:" (Resolve-Path $Backup) -ForegroundColor Yellow

# Regex för suffix att strippa
$SuffixPatterns = @(
  '-1024x768$',
  '-1$','-2$','-3$','-4$','-5$'
)

function Get-BaseKey([string]$fileName) {
  # Returnerar ett "basnamn" (lowercase, utan kända suffix, behåller extension)
  $lower = $fileName.ToLower()
  $name = [System.IO.Path]::GetFileNameWithoutExtension($lower)
  $ext  = [System.IO.Path]::GetExtension($lower)

  foreach ($pat in $SuffixPatterns) {
    $name = [regex]::Replace($name, $pat, "")
  }

  return "$name$ext"
}

function Get-PreferScore([string]$fileName) {
  # Högre = bättre. Utan suffix (-1024x768, -N) får +2, annars +1
  $lower = $fileName.ToLower()
  $score = 1
  if ($lower -notmatch '-1024x768(\.[a-z0-9]+)$' -and $lower -notmatch '-[1-9](\.[a-z0-9]+)$') {
    $score += 1
  }
  return $score
}

# Grupp: BaseKey -> [filer]
$files = Get-ChildItem -Path $Root -File
if ($files.Count -eq 0) {
  Write-Host "Inga filer hittades i" (Resolve-Path $Root) -ForegroundColor DarkYellow
  exit 0
}

$groups = @{}
foreach ($f in $files) {
  # Hoppa över uppenbart icke-kartfiler (ex. logo etc) men kommentera ut vid behov
  if ($f.Name -notmatch '^(\d+_)?Rd\d{2}_') { continue }

  $key = Get-BaseKey $f.Name
  if (-not $groups.ContainsKey($key)) { $groups[$key] = New-Object System.Collections.ArrayList }
  [void]$groups[$key].Add($f)
}

$moveCount = 0

foreach ($key in $groups.Keys) {
  $group = $groups[$key]

  if ($group.Count -le 1) { continue }

  # Välj bästa fil
  $best = $null
  $bestScore = -1
  foreach ($f in $group) {
    $score = Get-PreferScore $f.Name
    if ($score -gt $bestScore) {
      $bestScore = $score
      $best = $f
    }
  }

  # Flytta alla andra
  foreach ($f in $group) {
    if ($f.FullName -ne $best.FullName) {
      $dest = Join-Path $Backup $f.Name
      Move-Item -Force -Path $f.FullName -Destination $dest
      $moveCount++
      Write-Host ("[MOVE] {0} -> {1}" -f $f.Name, $dest) -ForegroundColor DarkGray
    }
  }

  Write-Host ("[KEEP] {0}" -f $best.Name) -ForegroundColor Green
}

Write-Host ("KLART. Flyttade {0} dubbletter till {1}" -f $moveCount, (Resolve-Path $Backup)) -ForegroundColor Cyan
Write-Host "Kör nu assign_trackmaps_multi.py igen om du vill börja om DB-koppling baserat på den rensade mappen."