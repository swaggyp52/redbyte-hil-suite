@echo off
cd /d "%~dp0.."
python src\launchers\launch_compliance.py %*
if errorlevel 1 pause
