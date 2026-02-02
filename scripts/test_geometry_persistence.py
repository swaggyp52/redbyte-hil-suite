"""
Test script for verifying geometry persistence and layout stability
Tests the fixes for phasor view snapping and UI lag
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QRect
from ui.main_window import MainWindow
import time

def test_geometry_persistence():
    """Test that panel positions persist across layout changes"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    print("\n=== Testing Geometry Persistence ===\n")
    
    # Give window time to initialize
    QApplication.processEvents()
    time.sleep(0.5)
    
    # Step 1: Set custom position for phasor view
    phasor_sub = window.phasor_view.parent()
    initial_geometry = QRect(500, 200, 400, 350)
    phasor_sub.setGeometry(initial_geometry)
    
    # Simulate user moving the panel by triggering moveEvent
    phasor_sub.move(500, 200)
    QApplication.processEvents()
    time.sleep(0.2)
    
    print(f"✓ Set phasor view to custom position: {initial_geometry}")
    print(f"  User-moved panels: {window.user_moved_panels}")
    print(f"  Saved geometries: {list(window.saved_geometries.keys())}")
    
    # Step 2: Switch to different layouts
    layouts = ["Diagnostics Matrix", "Engineer View", "Analyst View", "3D Ops View"]
    
    for layout in layouts:
        window.combo_layout.setCurrentText(layout)
        QApplication.processEvents()
        time.sleep(0.3)
        
        # Check if phasor is visible in this layout
        if phasor_sub.isVisible():
            current_geometry = phasor_sub.geometry()
            print(f"\n  Layout: {layout}")
            print(f"    Phasor geometry: {current_geometry}")
            
            # Verify it's near the user-set position (allowing for small variations)
            if "Phasor" in window.user_moved_panels:
                dx = abs(current_geometry.x() - initial_geometry.x())
                dy = abs(current_geometry.y() - initial_geometry.y())
                if dx < 10 and dy < 10:
                    print(f"    ✓ Position preserved (Δx={dx}, Δy={dy})")
                else:
                    print(f"    ✗ Position changed! (Δx={dx}, Δy={dy})")
            else:
                print(f"    → New preset position (panel not marked as user-moved)")
        else:
            print(f"\n  Layout: {layout} - Phasor not visible")
    
    # Step 3: Test debouncing
    print("\n=== Testing Auto-Pin Debouncing ===\n")
    
    # Trigger auto-pin multiple times rapidly
    window._auto_pin_panel("Phasor", "Test Event 1")
    time1 = window.last_auto_pin_time.get(("Phasor", "Test Event 1"), 0)
    print(f"  First auto-pin timestamp: {time1:.3f}")
    
    time.sleep(0.5)
    window._auto_pin_panel("Phasor", "Test Event 1")
    time2 = window.last_auto_pin_time.get(("Phasor", "Test Event 1"), 0)
    print(f"  Second auto-pin (0.5s later): {time2:.3f}")
    print(f"    → Should be blocked (delta < 3s): {time2 == time1}")
    
    time.sleep(3.1)
    window._auto_pin_panel("Phasor", "Test Event 2")
    time3 = window.last_auto_pin_time.get(("Phasor", "Test Event 2"), 0)
    print(f"  Third auto-pin (3.1s later, different event): {time3:.3f}")
    print(f"    → Should succeed (delta > 3s or new event): {time3 > time2}")
    
    # Step 4: Test Quick Jump tabs
    print("\n=== Testing Quick Jump Navigation ===\n")
    
    quick_jump_tabs = [
        ("⚡ Live", "Engineer View"),
        ("📊 Analyze", "Analyst View"),
        ("🌈 Phasor", "Diagnostics Matrix"),
        ("🎛️ 3D Ops", "3D Ops View"),
        ("🎯 Dash", "Diagnostics Matrix")
    ]
    
    for tab_name, expected_layout in quick_jump_tabs:
        # Find and click the Quick Jump button
        for child in window.findChildren(type(window.combo_layout)):
            if hasattr(child, 'text') and tab_name in child.text():
                print(f"  Clicking {tab_name}...")
                child.click()
                QApplication.processEvents()
                time.sleep(0.2)
                current = window.combo_layout.currentText()
                print(f"    → Layout changed to: {current}")
                break
    
    print("\n=== Test Complete ===\n")
    print("Summary:")
    print(f"  • User-moved panels tracked: {len(window.user_moved_panels)}")
    print(f"  • Saved geometries: {len(window.saved_geometries)}")
    print(f"  • Auto-pin timestamps: {len(window.last_auto_pin_time)}")
    print("\nPlease manually verify:")
    print("  1. Drag phasor to a custom position")
    print("  2. Switch layouts using dropdown or Quick Jump tabs")
    print("  3. Verify phasor stays in your custom position")
    print("  4. Check that UI remains smooth with no lag")
    
    # Keep window open for manual inspection
    sys.exit(app.exec())

if __name__ == '__main__':
    test_geometry_persistence()
