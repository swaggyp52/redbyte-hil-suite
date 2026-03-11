@echo off
echo Running HIL Suite Tests...

python scripts\preflight_check.py
if errorlevel 1 (
	echo Preflight checks failed. Fix environment issues before running tests.
	exit /b 1
)

python -m pytest tests/
pause
