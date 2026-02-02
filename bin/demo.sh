#!/usr/bin/env bash
set -euo pipefail
export DEMO_MODE=1
export DEMO_AUTOPLAY=1
export PYTHONPATH=.
python src/main.py --demo
