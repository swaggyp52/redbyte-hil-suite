@echo off
:: Quick Launch - RedByte Replay Studio

cd /d "%~dp0.."
python src\launchers\launch_replay.py %*
if errorlevel 1 pause
