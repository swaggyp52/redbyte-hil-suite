@echo off
echo.
echo ========================================
echo   VSM Evidence Workbench — Quick Check
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

echo [1/3] Checking Python imports...
"%REDBYTE_PYTHON%" -c "import src.main, src.importer, src.compliance_checker, src.event_detector, src.analysis, src.report_generator; print('  Core imports: OK')"
if errorlevel 1 echo   FAIL: Core imports failed

echo [2/3] Checking optional dependencies...
"%REDBYTE_PYTHON%" -c "import openpyxl; print('  openpyxl (Excel): OK')" 2>nul || echo   openpyxl not installed (Excel import disabled)
"%REDBYTE_PYTHON%" -c "import OpenGL; print('  PyOpenGL (3D view): OK')" 2>nul || echo   PyOpenGL not installed (3D view will show placeholder)

echo [3/3] Running fast unit tests...
"%REDBYTE_PYTHON%" -m pytest tests/test_importer.py tests/test_analysis.py tests/test_evidence_pipeline.py -q --tb=short --ignore=tests/manual_ux_validation.py --ignore=tests/quick_diagnostic.py

echo.
pause
