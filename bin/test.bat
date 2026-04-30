@echo off
echo.
echo ========================================
echo   VSM Evidence Workbench — Test Suite
echo ========================================
echo.

cd /d "%~dp0.."
call scripts\bootstrap.cmd --dev
if errorlevel 1 (
    echo.
    echo [ERROR] Test setup failed.
    pause
    exit /b 1
)
"%REDBYTE_PYTHON%" -m pytest tests/ -v --tb=short ^
    --ignore=tests/manual_ux_validation.py ^
    --ignore=tests/quick_diagnostic.py

echo.
pause
