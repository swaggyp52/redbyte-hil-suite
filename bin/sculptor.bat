@echo off
cd /d "%~dp0.."
python src\launchers\launch_sculptor.py %*
if errorlevel 1 pause
