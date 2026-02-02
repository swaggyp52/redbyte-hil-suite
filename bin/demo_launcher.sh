#!/usr/bin/env bash
set -euo pipefail
export DEMO_MODE=1
export DEMO_AUTOPLAY=1
export PYTHONPATH=.
python src/main.py --demo --autoplay
mkdir -p exports snapshots
[ -f data/insights_log.json ] || echo '{}' > data/insights_log.json
zip -r demo_output.zip exports snapshots data/insights_log.json
