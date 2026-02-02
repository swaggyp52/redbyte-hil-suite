"""
Simple diagnostic test - no GUI
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

print("\n" + "="*60)
print("RedByte v2.0 - Quick Diagnostic Test")
print("="*60 + "\n")

# Test 1: Core imports
print("Testing Core Imports...")
try:
    from hil_core.session import SessionContext
    from hil_core.signals import SignalEngine
    from hil_core.faults import FaultEngine
    from hil_core.insights import InsightEngine
    print("  ✓ All core modules import successfully")
except Exception as e:
    print(f"  ✗ Core import failed: {e}")
    sys.exit(1)

# Test 2: UI imports
print("\nTesting UI Imports...")
try:
    from ui.app_themes import get_diagnostics_style, APP_ACCENTS
    from ui.style import get_global_stylesheet
    print("  ✓ All UI modules import successfully")
except Exception as e:
    print(f"  ✗ UI import failed: {e}")
    sys.exit(1)

# Test 3: Core functionality
print("\nTesting Core Functionality...")
try:
    ctx = SessionContext()
    ctx.set_scenario("diagnostic_test", fault_type="test")
    assert ctx.scenario.name == "diagnostic_test"
    
    engine = SignalEngine(buffer_size=100)
    engine.push_sample({'Va': 120.0}, timestamp=0.0)
    
    print("  ✓ Core functionality works")
except Exception as e:
    print(f"  ✗ Functionality test failed: {e}")
    sys.exit(1)

# Test 4: Launcher files
print("\nChecking Launcher Files...")
launchers = [
    'src/launchers/launch_diagnostics.py',
    'src/launchers/launch_replay.py',
    'src/launchers/launch_compliance.py',
    'src/launchers/launch_insights.py',
    'src/launchers/launch_sculptor.py',
    'src/redbyte_launcher.py'
]

all_exist = True
for launcher in launchers:
    path = project_root / launcher
    if path.exists():
        print(f"  ✓ {launcher}")
    else:
        print(f"  ✗ {launcher} - MISSING")
        all_exist = False

if not all_exist:
    sys.exit(1)

# Test 5: Batch files
print("\nChecking Batch Files...")
batch_files = [
    'bin/launch_redbyte.bat',
    'bin/diagnostics.bat',
    'bin/replay.bat'
]

for batch in batch_files:
    path = project_root / batch
    if path.exists():
        print(f"  ✓ {batch}")
    else:
        print(f"  ✗ {batch} - MISSING")

print("\n" + "="*60)
print("✅ ALL CRITICAL SYSTEMS OPERATIONAL")
print("="*60)
print("\nReady to launch:")
print("  • Main Launcher: bin\\launch_redbyte.bat")
print("  • Diagnostics:   bin\\diagnostics.bat")
print("  • Replay Studio: bin\\replay.bat")
print("\n")
