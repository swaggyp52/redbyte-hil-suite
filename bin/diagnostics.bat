@echo off
:: Quick Launch - RedByte Diagnostics

cd /d "%~dp0.."
python src\launchers\launch_diagnostics.py %*
if errorlevel 1 pause
