@echo off
cd /d "%~dp0.."
python src\launchers\launch_insights.py %*
if errorlevel 1 pause
