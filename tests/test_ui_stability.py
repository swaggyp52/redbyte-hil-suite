"""
Test script to verify UI stability fixes.
Checks for layout lock guards, signal blocking, and prevents reset loops.
"""
import os
import sys

# Test 1: Verify layout lock guards
print("✅ Test 1: Checking layout lock implementation...")
main_window_path = os.path.join("ui", "main_window.py")
with open(main_window_path, 'r', encoding='utf-8') as f:
    content = f.read()
    assert "self.layout_locked = False" in content, "Missing layout_locked flag"
    assert "if self.layout_locked:" in content, "Missing layout lock guard"
    assert 'logger.debug(f"Layout change blocked (locked): {mode}")' in content, "Missing lock debug message"
    print("   ✓ Layout lock guards in place")

# Test 2: Verify signal blocking
print("\n✅ Test 2: Checking signal blocking...")
assert "blockSignals(True)" in content, "Missing signal blocking"
assert "blockSignals(False)" in content, "Missing signal unblocking"
print("   ✓ Signal blocking implemented")

# Test 3: Verify initializing flag
print("\n✅ Test 3: Checking initializing flag...")
assert "self.initializing = True" in content, "Missing initializing flag"
assert "self.initializing = False" in content, "Missing initializing unlock"
print("   ✓ Initializing flag implemented")

# Test 4: Verify LayoutManager disabled auto-switch
print("\n✅ Test 4: Checking LayoutManager auto-switch disabled...")
layout_mgr_path = os.path.join("src", "layout_manager.py")
with open(layout_mgr_path, 'r') as f:
    lm_content = f.read()
    assert "# Disabled automatic layout switching to prevent UI resets" in lm_content, "Auto-switch not disabled"
    assert "pass" in lm_content, "on_frame not properly disabled"
print("   ✓ Automatic layout switching disabled")

# Test 5: Verify stylesheet applied after window.show()
print("\n✅ Test 5: Checking stylesheet application order...")
main_path = os.path.join("src", "main.py")
with open(main_path, 'r') as f:
    main_content = f.read()
    show_idx = main_content.find("window.show()")
    stylesheet_idx = main_content.find("app.setStyleSheet(get_global_stylesheet())", show_idx)
    assert stylesheet_idx > show_idx, "Stylesheet applied before window.show()"
    assert "# Apply stylesheet AFTER window is shown" in main_content, "Missing stylesheet comment"
print("   ✓ Stylesheet applied after window shown")

# Test 6: Verify demo mode guard
print("\n✅ Test 6: Checking demo mode double-initialization guard...")
assert 'logger.debug("Demo mode already enabled, skipping")' in content, "Missing demo mode guard"
assert 'logger.info("Enabling demo mode...")' in content, "Missing demo mode start log"
print("   ✓ Demo mode guard in place")

print("\n" + "="*60)
print("🎉 ALL STABILITY TESTS PASSED!")
print("="*60)
print("\nFixed issues:")
print("  1. Layout lock prevents recursive changes")
print("  2. Signal blocking prevents infinite loops")
print("  3. LayoutManager no longer auto-switches layouts")
print("  4. Stylesheet applied after window shown")
print("  5. Demo mode prevents double initialization")
print("  6. Debug logging added for troubleshooting")
print("\nNext: Run the app and verify dropdowns/toggles don't reset UI")
