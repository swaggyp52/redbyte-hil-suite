@echo off
echo.
echo ========================================
echo   VSM Evidence Workbench — Test Suite
echo ========================================
echo.

cd /d "%~dp0.."
set PYTHONPATH=.
python -m pytest tests/ -v --tb=short ^
    --ignore=tests/manual_ux_validation.py ^
    --ignore=tests/quick_diagnostic.py

echo.
pause
