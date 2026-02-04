"""
Test UI integration of telemetry watchdog and CSV exporter.
Verifies main window has proper wiring and event handlers.
"""

import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for all tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_has_watchdog(qapp):
    """Verify MainWindow instantiates telemetry watchdog"""
    window = MainWindow()
    
    assert hasattr(window, 'telemetry_watchdog'), "MainWindow missing telemetry_watchdog"
    assert hasattr(window, 'csv_exporter'), "MainWindow missing csv_exporter"
    assert hasattr(window, 'telemetry_health_label'), "MainWindow missing telemetry_health_label"
    assert hasattr(window, 'export_format_combo'), "MainWindow missing export_format_combo"
    assert hasattr(window, 'stale_indicator'), "MainWindow missing stale_indicator"
    
    window.close()


def test_watchdog_signal_connections(qapp):
    """Verify watchdog signals are connected to UI handlers"""
    window = MainWindow()
    
    # Check handler methods exist (indirect validation of signal wiring)
    assert callable(window._on_telemetry_stale), "Stale handler not callable"
    assert callable(window._on_telemetry_resumed), "Resumed handler not callable"
    assert callable(window._on_frame_rate_changed), "Frame rate handler not callable"
    
    window.close()


def test_watchdog_ui_handlers_exist(qapp):
    """Verify UI handler methods exist for watchdog events"""
    window = MainWindow()
    
    assert hasattr(window, '_on_telemetry_stale'), "Missing _on_telemetry_stale handler"
    assert hasattr(window, '_on_telemetry_resumed'), "Missing _on_telemetry_resumed handler"
    assert hasattr(window, '_on_frame_rate_changed'), "Missing _on_frame_rate_changed handler"
    assert hasattr(window, '_update_telemetry_health_display'), "Missing _update_telemetry_health_display handler"
    assert hasattr(window, '_export_csv'), "Missing _export_csv handler"
    
    window.close()


def test_csv_export_format_selector(qapp):
    """Verify CSV format combo box has correct options"""
    window = MainWindow()
    
    expected_formats = ["Simple CSV", "Detailed CSV", "Analysis CSV"]
    actual_formats = [window.export_format_combo.itemText(i) 
                     for i in range(window.export_format_combo.count())]
    
    assert actual_formats == expected_formats, f"Format selector mismatch: {actual_formats}"
    
    window.close()


def test_stale_indicator_styling(qapp):
    """Verify stale indicator has proper visual styling"""
    window = MainWindow()
    
    # Should be hidden by default
    assert window.stale_indicator.isHidden(), "Stale indicator should be hidden initially"
    
    # Should have red warning styling
    style = window.stale_indicator.styleSheet()
    assert "220, 38, 38" in style or "#dc2626" in style, "Missing red warning color"
    assert "border-radius" in style, "Missing rounded corners"
    
    window.close()


def test_telemetry_health_label_updates(qapp):
    """Verify telemetry health label responds to watchdog events"""
    window = MainWindow()
    window.show()  # Need to show window for visibility changes
    
    # Simulate stale data
    window._on_telemetry_stale(2.5)
    assert "STALE" in window.telemetry_health_label.text(), "Health label not showing STALE"
    # Note: isVisible() may be unreliable without event loop, check show() was called
    assert not window.stale_indicator.isHidden(), "Stale indicator should not be hidden"
    
    # Simulate data resumed
    window._on_telemetry_resumed()
    assert "OK" in window.telemetry_health_label.text(), "Health label not showing OK"
    assert window.stale_indicator.isHidden(), "Stale indicator should be hidden"
    
    # Simulate frame rate update
    window._on_frame_rate_changed(20.5)
    assert "20.5" in window.telemetry_health_label.text(), "Health label not showing frame rate"
    
    window.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
