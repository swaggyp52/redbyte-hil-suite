#!/usr/bin/env pwsh
# run_demo.ps1 - Launch the GFM HIL Verifier Suite demo

Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   GFM HIL VERIFIER SUITE - DEMO LAUNCHER             ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Check if venv exists
if (-not (Test-Path ".venv")) {
    Write-Host "❌ Virtual environment not found. Run launch.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "🚀 Starting demo application..." -ForegroundColor Green
Write-Host "💡 Click buttons to:" -ForegroundColor Yellow
Write-Host "   ▶️  Run    - Start telemetry stream" -ForegroundColor Yellow
Write-Host "   ⏸ Pause   - Trigger stale detection (watch for red warning)" -ForegroundColor Yellow
Write-Host "   🔁 Resume  - Restart data flow" -ForegroundColor Yellow
Write-Host "   ⏹ Stop    - Stop cleanly" -ForegroundColor Yellow
Write-Host ""

# Launch the app
.venv\Scripts\python.exe -m ui.main
