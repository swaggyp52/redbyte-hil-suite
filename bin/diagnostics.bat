@echo off
:: Quick Launch - VSM Evidence Workbench Diagnostics (demo adapter mode)

cd /d "%~dp0.."
python src\launchers\launch_diagnostics.py %*
if errorlevel 1 pause
