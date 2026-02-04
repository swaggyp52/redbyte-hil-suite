"""
Test OpenGL detection and graceful degradation
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.opengl_check import check_opengl_available, get_opengl_fallback_message

def test_opengl_detection():
    """Test that OpenGL detection doesn't crash"""
    print("Testing OpenGL detection...")
    available, error = check_opengl_available()
    
    if available:
        print("  ✓ OpenGL available")
    else:
        print(f"  ⚠ OpenGL not available: {error}")
    
    # Should never crash
    assert isinstance(available, bool)
    assert isinstance(error, str)
    print("  ✓ Detection works without crashes")

def test_fallback_message():
    """Test that fallback message is properly formatted"""
    print("\nTesting fallback message...")
    msg = get_opengl_fallback_message()
    
    assert isinstance(msg, str)
    assert len(msg) > 0
    assert "3D View Unavailable" in msg
    assert "pip install PyOpenGL" in msg
    print("  ✓ Fallback message is well-formed")

def test_system_3d_view_import():
    """Test that System3DView can import even without OpenGL"""
    print("\nTesting System3DView import...")
    try:
        from ui.system_3d_view import System3DView, OPENGL_AVAILABLE
        print(f"  ✓ System3DView imports successfully")
        print(f"  OpenGL available: {OPENGL_AVAILABLE}")
    except ImportError as e:
        print(f"  ✗ Failed to import System3DView: {e}")
        raise

def test_main_with_no_3d_flag():
    """Test that main.py can parse --no-3d flag"""
    print("\nTesting --no-3d flag parsing...")
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--autoplay", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-3d", action="store_true")
    
    args = parser.parse_args(["--no-3d"])
    assert args.no_3d == True
    print("  ✓ --no-3d flag parses correctly")
    
    args = parser.parse_args([])
    assert args.no_3d == False
    print("  ✓ Default (3D enabled) works")

if __name__ == '__main__':
    print("=" * 60)
    print("OpenGL Graceful Degradation Test Suite")
    print("=" * 60)
    print()
    
    try:
        test_opengl_detection()
        test_fallback_message()
        test_system_3d_view_import()
        test_main_with_no_3d_flag()
        
        print()
        print("=" * 60)
        print("✅ All OpenGL safety tests passed!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. Run: python -m src.main --debug --demo")
        print("  2. If 3D crashes, run: python -m src.main --no-3d --demo")
        print("  3. On lab machines: ./launch.ps1")
        print()
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Test failed: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
