@echo off
REM Launch GFM HIL Demo without console window
cd /d "%~dp0"
start "" .venv\Scripts\pythonw.exe src\main.py --demo
