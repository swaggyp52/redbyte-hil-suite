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

echo [1/2] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [2/2] Installing Python dependencies (including openpyxl for Excel import)...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed. Check the error above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Setup complete!
echo.
echo  Launch:  python run.py
echo    or     run.bat  (double-click)
echo.
echo  Test:    pytest tests/ --ignore=tests/test_ui_integration.py -q
echo ============================================
pause
