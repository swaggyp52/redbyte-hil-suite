"""
Manual UX Validation Script - Tests CLI flows and launcher behaviors
Run this to manually verify end-to-end user experience
"""

import subprocess
import sys
from pathlib import Path
import time

project_root = Path(__file__).parent.parent
bin_dir = project_root / "bin"
data_dir = project_root / "data"

print("=" * 70)
print("RedByte HIL Verifier Suite - UX Validation Manual Test Script")
print("=" * 70)
print()

# Test data files
baseline_context = data_dir / "demo_context_baseline.json"
fault_context = data_dir / "demo_context_fault_sag.json"

if not baseline_context.exists():
    print("❌ Missing demo_context_baseline.json")
    sys.exit(1)

if not fault_context.exists():
    print("❌ Missing demo_context_fault_sag.json")
    sys.exit(1)

print("✅ Demo context files found")
print()

# CLI Validation Tests
print("🧪 CLI & Batch UX Validation")
print("-" * 70)

tests = [
    {
        "name": "Diagnostics - Mock mode",
        "cmd": [str(bin_dir / "diagnostics.bat"), "--mock"],
        "expected": "Should launch with mock serial data (no hardware required)",
        "auto_close": True
    },
    {
        "name": "Diagnostics - Load baseline context",
        "cmd": [str(bin_dir / "diagnostics.bat"), "--load", str(baseline_context), "--mock"],
        "expected": "Should load baseline demo, panels populate, serial in mock mode",
        "auto_close": True
    },
    {
        "name": "Replay - Load baseline context",
        "cmd": [str(bin_dir / "replay.bat"), "--load", str(baseline_context)],
        "expected": "ReplayStudio should show scrollable frames, PhasorView renders",
        "auto_close": True
    },
    {
        "name": "Compliance - Load baseline context",
        "cmd": [str(bin_dir / "compliance.bat"), "--load", str(baseline_context)],
        "expected": "ValidationDashboard shows scenario name and checks",
        "auto_close": True
    },
    {
        "name": "Insights - Load fault context",
        "cmd": [str(bin_dir / "insights.bat"), "--load", str(fault_context)],
        "expected": "Insight timeline loads with tooltips, color-coded events",
        "auto_close": True
    },
    {
        "name": "Sculptor - Mock mode",
        "cmd": [str(bin_dir / "sculptor.bat"), "--mock"],
        "expected": "Opens without crash, shows default view with helpful overlay",
        "auto_close": True
    }
]

print("\nℹ️  Instructions:")
print("   - Each launcher will open with specific context/mode")
print("   - Verify the expected behavior is visible")
print("   - Close the window to continue to the next test")
print("   - Press Ctrl+C to abort testing at any time")
print()
input("Press Enter to start manual testing...")
print()

for i, test in enumerate(tests, 1):
    print(f"\n[{i}/{len(tests)}] {test['name']}")
    print(f"    Expected: {test['expected']}")
    print(f"    Command: {' '.join(str(x) for x in test['cmd'])}")
    print()
    
    try:
        # Launch the application
        proc = subprocess.Popen(
            test['cmd'],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"    🚀 Launched (PID: {proc.pid})")
        print(f"    👀 Verify expected behavior, then close the window")
        
        # Wait for user to close the app
        proc.wait()
        
        if proc.returncode == 0:
            print(f"    ✅ Exited cleanly (code {proc.returncode})")
        else:
            print(f"    ⚠️  Exit code: {proc.returncode}")
            stderr = proc.stderr.read().decode('utf-8', errors='ignore')
            if stderr:
                print(f"    Error output: {stderr[:200]}")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing aborted by user")
        sys.exit(0)
    except Exception as e:
        print(f"    ❌ Failed to launch: {e}")
    
    print()

print()
print("=" * 70)
print("✅ Manual UX Testing Complete")
print("=" * 70)
print()
print("Next steps:")
print("  1. Test context export/import round-trip manually:")
print("     - Open Diagnostics with --load demo_context_baseline.json")
print("     - Click 📤 Export Context button, save as 'test_export.json'")
print("     - Open Replay with --load test_export.json")
print("     - Verify frames load correctly")
print()
print("  2. Test layout persistence:")
print("     - Open any launcher, drag panels to new positions")
print("     - Close and reopen - panels should be in same spots")
print()
print("  3. Test error resilience:")
print("     - Try loading an invalid JSON file")
print("     - Should show error overlay, not crash")
print()
print("  4. Verify visual consistency:")
print("     - Each app should have distinct theme color")
print("     - Tooltips present on toolbar buttons")
print("     - Status bar shows connection status")
print()
