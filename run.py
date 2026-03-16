#!/usr/bin/env python3
"""
RedByte GFM HIL Suite — entry point.

Usage:
    python run.py              # launch (windowed, demo mode)
    python run.py --fullscreen # fullscreen demo
    python run.py --live       # live hardware mode (requires serial connection)
    python run.py --no-3d      # disable 3D view if OpenGL unavailable
"""
import sys
import os

# Ensure project root is on the path regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == "__main__":
    # Default: demo mode + windowed (safe for any machine)
    # Override by passing explicit args
    defaults = ["--demo", "--windowed"]
    if "--fullscreen" in sys.argv:
        sys.argv.remove("--fullscreen")
        defaults = ["--demo"]
    if "--live" in sys.argv:
        sys.argv.remove("--live")
        defaults = ["--windowed"]
    if "--no-3d" in sys.argv:
        defaults.append("--no-3d")
        sys.argv.remove("--no-3d")

    # Inject defaults only if no conflicting args present
    for d in defaults:
        if d not in sys.argv:
            sys.argv.append(d)

    main()
