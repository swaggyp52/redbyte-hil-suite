import sys
import pytest
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.inverter_scope import InverterScope
from ui.fault_injector import FaultInjector
from ui.validation_dashboard import ValidationDashboard

def test_mainwindow_load(qapp):
    """Verifies that the main window initializes without error."""
    window = MainWindow()
    assert window is not None
    assert "Verifier Suite" in window.windowTitle()
    
    # Check sub-windows exist
    assert isinstance(window.scope, InverterScope)
    assert isinstance(window.injector, FaultInjector)
    assert isinstance(window.dashboard, ValidationDashboard)
    assert window.phasor_view is not None
    assert window.view_3d is not None
    assert window.replay_studio is not None
    assert window.sculptor is not None
    
    window.close()
