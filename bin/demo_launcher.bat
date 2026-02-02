@echo off
set DEMO_MODE=1
set DEMO_AUTOPLAY=1
set PYTHONPATH=.
python src/main.py --demo --autoplay
if not exist exports mkdir exports
if not exist snapshots mkdir snapshots
if not exist data\insights_log.json echo {}> data\insights_log.json
powershell -Command "Compress-Archive -Path exports\*,snapshots\*,data\insights_log.json -DestinationPath demo_output.zip -Force"
pause
