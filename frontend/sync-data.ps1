# PowerShell script to sync data from main project
# Run this after the pipeline generates new data

$sourcePath = "..\App-Review-Insights-Analyser\data\processed"
$destPath = "public\data\processed"

Write-Host "Syncing data from $sourcePath to $destPath..." -ForegroundColor Cyan

if (Test-Path $sourcePath) {
    if (Test-Path $destPath) {
        Remove-Item $destPath -Recurse -Force
    }
    Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force
    Write-Host "Data synced successfully!" -ForegroundColor Green
} else {
    Write-Host "Source path not found: $sourcePath" -ForegroundColor Red
    Write-Host "Please ensure the main project has generated data." -ForegroundColor Yellow
}

