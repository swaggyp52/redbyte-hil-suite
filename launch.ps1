# Simple RedByte HIL Launcher
Set-Location -Path $PSScriptRoot

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Host "Python not found"
    exit 1
}

# Setup venv
$venv = '.venv'
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment..."
    & $python.Source -m venv $venv
}

# Activate venv
$activate = "$venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
}

$pythonExe = "$venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "Python executable not found in venv"
    exit 1
}

# Install requirements
if (Test-Path "requirements.txt") {
    Write-Host "Installing dependencies..."
    & $pythonExe -m pip install -q --upgrade pip setuptools wheel
    Get-Content requirements.txt | Where-Object {$_ -notmatch '^```'} | Where-Object {$_ -match '\S'} | Set-Content requirements_clean.txt
    & $pythonExe -m pip install -q -r requirements_clean.txt
}

# Ensure PyOpenGL
try {
    & $pythonExe -m pip show PyOpenGL | Out-Null 2>&1
} catch {
    Write-Host "Installing PyOpenGL..."
    & $pythonExe -m pip install -q PyOpenGL PyOpenGL_accelerate 2>&1 | Out-Null
}

# Launch
$launcher = "src\redbyte_launcher.py"
if (Test-Path $launcher) {
    Write-Host "Launching RedByte HIL Suite..."
    & $pythonExe $launcher
} else {
    Write-Host "Launcher not found: $launcher"
    exit 1
}
