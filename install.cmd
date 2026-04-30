@echo off
cd /d "%~dp0"
echo ============================================
echo  RedByte GFM HIL Suite - Setup
echo ============================================
echo.

call scripts\bootstrap.cmd --dev
if errorlevel 1 (
    echo.
    echo [ERROR] Setup failed. Check the error above.
    pause
    exit /b 1
)

echo [Optional] Installing Playwright Chromium (for browser UI tests)...
"%REDBYTE_PYTHON%" -m playwright install chromium >nul 2>&1
if errorlevel 1 (
    echo [WARN] Playwright browser install skipped or unavailable.
    echo        Core app setup is complete. Browser-based tests may require:
    echo        .venv\Scripts\python.exe -m playwright install chromium
)

echo.
echo ============================================
echo  Setup complete!
echo.
echo  Launch:  run.bat  (double-click)
echo    or     .venv\Scripts\python.exe run.py
echo.
echo  Test:    bin\test.bat
echo ============================================
pause
