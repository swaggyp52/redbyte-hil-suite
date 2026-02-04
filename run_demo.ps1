#!/usr/bin/env pwsh
# run_demo.ps1 - Launch the GFM HIL Verifier Suite demo

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "  GFM HIL VERIFIER SUITE - DEMO LAUNCHER           " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Check if venv exists
if (-not (Test-Path ".venv")) {
    Write-Host "[X] Virtual environment not found. Run launch.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "[*] Starting demo application..." -ForegroundColor Green
Write-Host "[?] Button Controls:" -ForegroundColor Yellow
Write-Host "    RUN    - Start 20 Hz telemetry stream" -ForegroundColor Yellow
Write-Host "    PAUSE  - Trigger stale detection (watch for red warning after 2s)" -ForegroundColor Yellow
Write-Host "    RESUME - Restart data flow and clear warning" -ForegroundColor Yellow
Write-Host "    STOP   - Stop cleanly" -ForegroundColor Yellow
Write-Host ""

# Activate venv and set PYTHONPATH
& .venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."

# Launch the app with demo mode enabled
python src\main.py --demo

