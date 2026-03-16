@echo off
echo ============================================
echo  RedByte GFM HIL Suite - Setup
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.12 from python.org and rerun.
    pause
    exit /b 1
)

echo [1/3] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [2/3] Installing Python dependencies...
pip install -e ".[dev]" --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed. Check the error above.
    pause
    exit /b 1
)

echo [3/3] Installing Playwright browser...
python -m playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright browser install failed. HTML report tests may be skipped.
)

echo.
echo ============================================
echo  Setup complete!
echo  Run:  python run.py
echo  Test: python -m pytest tests/ -v
echo ============================================
pause
