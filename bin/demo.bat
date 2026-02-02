@echo off
echo Starting HIL Verifier Suite (Demo Mode)...
set DEMO_MODE=1
set DEMO_AUTOPLAY=1
set PYTHONPATH=.
python src/main.py --demo
pause
