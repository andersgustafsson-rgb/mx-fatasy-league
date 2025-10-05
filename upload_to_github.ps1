# GitHub Upload Script for MX Fantasy League
$token = "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"
$repo = "andersgustafsson-rgb/fantasyMX"
$baseUrl = "https://api.github.com/repos/$repo/contents"

function Upload-File {
    param($filePath, $relativePath)
    
    $content = [System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes($filePath))
    $body = @{
        message = "Add $relativePath"
        content = $content
    } | ConvertTo-Json
    
    $headers = @{
        Authorization = "token $token"
        "Content-Type" = "application/json"
    }
    
    try {
        $response = Invoke-RestMethod -Uri "$baseUrl/$relativePath" -Method Put -Body $body -Headers $headers
        Write-Host "Uploaded: $relativePath" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "Failed to upload $relativePath : $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

Write-Host "Starting upload to GitHub repository: $repo" -ForegroundColor Cyan

# Upload main files
$mainFiles = @("app.py", "requirements.txt", "Dockerfile", "railway.json", "env.example", "README.md")
foreach ($file in $mainFiles) {
    if (Test-Path $file) {
        Upload-File -filePath $file -relativePath $file
    }
}

# Upload templates directory
if (Test-Path "templates") {
    Write-Host "Uploading templates directory" -ForegroundColor Yellow
    Get-ChildItem -Path "templates" -Recurse | ForEach-Object {
        if (-not $_.PSIsContainer) {
            $fileRelativePath = $_.FullName.Replace((Get-Location).Path + "\", "").Replace("\", "/")
            Upload-File -filePath $_.FullName -relativePath $fileRelativePath
        }
    }
}

# Upload static directory
if (Test-Path "static") {
    Write-Host "Uploading static directory" -ForegroundColor Yellow
    Get-ChildItem -Path "static" -Recurse | ForEach-Object {
        if (-not $_.PSIsContainer) {
            $fileRelativePath = $_.FullName.Replace((Get-Location).Path + "\", "").Replace("\", "/")
            Upload-File -filePath $_.FullName -relativePath $fileRelativePath
        }
    }
}

# Upload scripts directory
if (Test-Path "scripts") {
    Write-Host "Uploading scripts directory" -ForegroundColor Yellow
    Get-ChildItem -Path "scripts" -Recurse | ForEach-Object {
        if (-not $_.PSIsContainer) {
            $fileRelativePath = $_.FullName.Replace((Get-Location).Path + "\", "").Replace("\", "/")
            Upload-File -filePath $_.FullName -relativePath $fileRelativePath
        }
    }
}

Write-Host "Upload completed! Check your repository at: https://github.com/$repo" -ForegroundColor Green
