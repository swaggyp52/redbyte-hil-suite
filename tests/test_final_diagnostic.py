"""
RedByte v2.0 - Comprehensive Diagnostic Verification
Tests all launchers and core functionality
"""

import sys
import subprocess
from pathlib import Path
import time

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

def test_imports():
    """Test all critical imports"""
    print("\n" + "="*60)
    print("TESTING MODULE IMPORTS")
    print("="*60)
    
    tests = [
        ("Core: SessionContext", "from hil_core.session import SessionContext"),
        ("Core: SignalEngine", "from hil_core.signals import SignalEngine"),
        ("Core: FaultEngine", "from hil_core.faults import FaultEngine"),
        ("Core: InsightEngine", "from hil_core.insights import InsightEngine"),
        ("Core: ContextExporter", "from hil_core.export_context import ContextExporter"),
        ("UI: app_themes", "from ui.app_themes import get_diagnostics_style"),
        ("UI: style", "from ui.style import get_global_stylesheet"),
        ("UI: main_window", "from ui.main_window import MainWindow"),
        ("UI: phasor_view", "from ui.phasor_view import PhasorView"),
        ("UI: inverter_scope", "from ui.inverter_scope import InverterScope"),
    ]
    
    passed = 0
    failed = 0
    
    for name, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f"  ✓ {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
    
    print(f"\nImport Tests: {passed}/{passed+failed} passed")
    return failed == 0


def test_launcher_files():
    """Verify all launcher files exist and have correct structure"""
    print("\n" + "="*60)
    print("TESTING LAUNCHER FILES")
    print("="*60)
    
    launchers_dir = project_root / 'src' / 'launchers'
    
    launchers = [
        'launch_diagnostics.py',
        'launch_replay.py',
        'launch_compliance.py',
        'launch_insights.py',
        'launch_sculptor.py'
    ]
    
    passed = 0
    failed = 0
    
    for launcher in launchers:
        path = launchers_dir / launcher
        if path.exists():
            # Check if it has proper path setup
            content = path.read_text(encoding='utf-8')
            if 'project_root' in content and 'sys.path.insert' in content:
                print(f"  ✓ {launcher} - exists with proper path setup")
                passed += 1
            else:
                print(f"  ✗ {launcher} - missing path setup")
                failed += 1
        else:
            print(f"  ✗ {launcher} - not found")
            failed += 1
    
    # Check main launcher
    main_launcher = project_root / 'src' / 'redbyte_launcher.py'
    if main_launcher.exists():
        content = main_launcher.read_text(encoding='utf-8')
        if 'project_root' in content and 'sys.path.insert' in content:
            print(f"  ✓ redbyte_launcher.py - exists with proper path setup")
            passed += 1
        else:
            print(f"  ✗ redbyte_launcher.py - missing path setup")
            failed += 1
    
    print(f"\nLauncher Files: {passed}/{passed+failed} passed")
    return failed == 0


def test_batch_files():
    """Verify batch files exist"""
    print("\n" + "="*60)
    print("TESTING BATCH FILES")
    print("="*60)
    
    bin_dir = project_root / 'bin'
    
    batch_files = [
        'launch_redbyte.bat',
        'diagnostics.bat',
        'replay.bat',
        'start.bat'
    ]
    
    passed = 0
    failed = 0
    
    for batch in batch_files:
        path = bin_dir / batch
        if path.exists():
            print(f"  ✓ {batch}")
            passed += 1
        else:
            print(f"  ✗ {batch} - not found")
            failed += 1
    
    print(f"\nBatch Files: {passed}/{passed+failed} passed")
    return failed == 0


def test_core_functionality():
    """Test core backend modules work"""
    print("\n" + "="*60)
    print("TESTING CORE FUNCTIONALITY")
    print("="*60)
    
    try:
        from hil_core.session import SessionContext
        from hil_core.signals import SignalEngine
        from hil_core.faults import FaultEngine
        from hil_core.insights import InsightEngine
        
        # Test SessionContext
        ctx = SessionContext()
        ctx.set_scenario("test", fault_type="test")
        assert ctx.scenario.name == "test"
        print("  ✓ SessionContext works")
        
        # Test SignalEngine
        engine = SignalEngine(buffer_size=100)
        engine.push_sample({'Va': 120.0}, timestamp=0.0)
        time_data, buffer_data = engine.get_channel_data('Va')
        assert len(buffer_data) == 1
        print("  ✓ SignalEngine works")
        
        # Test FaultEngine
        fault_engine = FaultEngine()
        assert hasattr(fault_engine, 'active_fault')
        print("  ✓ FaultEngine works")
        
        # Test InsightEngine
        insight_engine = InsightEngine()
        assert hasattr(insight_engine, 'insights')
        print("  ✓ InsightEngine works")
        
        print("\nCore Functionality: 4/4 passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        print("\nCore Functionality: FAILED")
        return False


def test_documentation():
    """Verify documentation exists"""
    print("\n" + "="*60)
    print("TESTING DOCUMENTATION")
    print("="*60)
    
    docs_dir = project_root / 'docs'
    
    docs = [
        'MODULAR_ARCHITECTURE.md',
        'QUICK_START_MODULAR.md',
        'IMPLEMENTATION_SUMMARY.md',
        'QUICK_REFERENCE_CARD.md',
        'geometry_persistence_fix.md'
    ]
    
    passed = 0
    failed = 0
    
    for doc in docs:
        path = docs_dir / doc
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  ✓ {doc} ({size_kb:.1f} KB)")
            passed += 1
        else:
            print(f"  ✗ {doc} - not found")
            failed += 1
    
    # Check root docs
    root_docs = ['README_MODULAR.md', 'MISSION_COMPLETE.md']
    for doc in root_docs:
        path = project_root / doc
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  ✓ {doc} ({size_kb:.1f} KB)")
            passed += 1
        else:
            print(f"  ✗ {doc} - not found")
            failed += 1
    
    print(f"\nDocumentation: {passed}/{passed+failed} passed")
    return failed == 0


def main():
    """Run all diagnostic tests"""
    print("\n" + "#"*60)
    print("# RedByte v2.0 - Final Diagnostic Sweep")
    print("#"*60)
    
    results = []
    
    # Run all tests
    results.append(("Module Imports", test_imports()))
    results.append(("Launcher Files", test_launcher_files()))
    results.append(("Batch Files", test_batch_files()))
    results.append(("Core Functionality", test_core_functionality()))
    results.append(("Documentation", test_documentation()))
    
    # Summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL SYSTEMS OPERATIONAL - READY FOR LAUNCH")
    else:
        print("⚠️  SOME TESTS FAILED - REVIEW ERRORS ABOVE")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
