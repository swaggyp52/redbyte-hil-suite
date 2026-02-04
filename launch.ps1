# launch.ps1 — Robust smart launcher for RedByte HIL app

# Move to script directory
Set-Location -Path $PSScriptRoot

# Prefer python, fall back to py launcher
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Write-Error "Python not found. Install Python 3.10+ and try again."
    exit 1
}

# Use .venv by default to match earlier runs
$venvPath = Join-Path $PSScriptRoot '.venv'
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at .venv..."
    & $pythonCmd.Source -m venv $venvPath
}

# Activate venv for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
$venvActivate = Join-Path $venvPath 'Scripts\Activate.ps1'
if (-not (Test-Path $venvActivate)) {
    Write-Error "Failed to find activation script at $venvActivate"
    exit 1
}
& $venvActivate

# Resolve pip/python inside venv
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
$venvPip = Join-Path $venvPath 'Scripts\pip.exe'
if (-not (Test-Path $venvPython)) { Write-Error "Virtualenv python not found at $venvPython"; exit 1 }

# Clean requirements.txt into requirements_clean.txt (remove fenced code blocks)
if (Test-Path "$PSScriptRoot\requirements.txt") {
    Get-Content "$PSScriptRoot\requirements.txt" | Where-Object {$_ -notmatch '^```'} | Where-Object {$_ -match '\S'} | Set-Content "$PSScriptRoot\requirements_clean.txt"
    Write-Host "Installing dependencies from requirements_clean.txt (this may take several minutes)..."
    & $venvPython -m pip install --upgrade pip setuptools wheel
    & $venvPython -m pip install -r "$PSScriptRoot\requirements_clean.txt"
} else {
    Write-Host "No requirements.txt found; skipping dependency install."
}

# Optionally ensure PyOpenGL (used by 3D view)
try {
    & $venvPython -m pip show PyOpenGL > $null 2>&1
} catch {
    # ignore
}
$hasOpengl = (& $venvPython -m pip show PyOpenGL -q 2>$null)
if (-not $hasOpengl) {
    Write-Host "Installing PyOpenGL (required for 3D view)..." -ForegroundColor Yellow
    Write-Host "  If this fails on your machine, the app will still work without 3D." -ForegroundColor Gray
    try {
        & $venvPython -m pip install PyOpenGL PyOpenGL_accelerate --quiet
        Write-Host "  ✓ PyOpenGL installed successfully" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠ PyOpenGL installation failed - 3D view will be disabled" -ForegroundColor Yellow
        Write-Host "    The app will launch with --no-3d flag automatically" -ForegroundColor Gray
    }
}

# Launch the app
$launcher = Join-Path $PSScriptRoot 'src\redbyte_launcher.py'
if (Test-Path $launcher) {
    Write-Host "Launching RedByte HIL Suite UI..."
    Start-Process -FilePath $venvPython -ArgumentList "`"$launcher`"" -WorkingDirectory $PSScriptRoot
} else {
    Write-Error "Launcher not found at $launcher"
}
