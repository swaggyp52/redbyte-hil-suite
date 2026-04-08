#!/usr/bin/env python3
"""
RedByte GFM HIL Suite — entry point.

Usage:
    python run.py              # launch (windowed, overview/import-first)
    python run.py --demo       # demo telemetry mode (windowed)
    python run.py --demo --fullscreen # fullscreen demo
    python run.py --live       # live hardware mode (reads port from system_config.json)
    python run.py --live --port COM5  # live hardware on explicit port
    python run.py --no-3d      # disable 3D view if OpenGL unavailable
"""
import sys
import os

# Ensure project root is on the path regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main


def resolve_startup_args(argv: list[str]) -> list[str]:
    """Normalize convenience flags into args accepted by src.main."""
    resolved = list(argv)

    # Product default: open windowed on Overview so the first action is
    # real-data import. Demo mode is opt-in via --demo.
    defaults = ["--windowed"]

    # Back-compat convenience flag: main parser does not expose --live,
    # but users may pass it to mean "not demo; use configured/explicit port".
    if "--live" in resolved:
        resolved.remove("--live")

    if "--fullscreen" in resolved:
        resolved.remove("--fullscreen")
        defaults = []

    for d in defaults:
        if d not in resolved:
            resolved.append(d)

    return resolved

if __name__ == "__main__":
    sys.argv = resolve_startup_args(sys.argv)
    main()
