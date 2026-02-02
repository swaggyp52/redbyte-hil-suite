import pytest
import sys
from PyQt6.QtWidgets import QApplication
from src.config_manager import ConfigManager
from ui.inverter_scope import InverterScope

# Manually init qapp for test context
qapp = QApplication.instance()
if not qapp:
    qapp = QApplication(sys.argv)

def test_config_loading():
    ConfigManager.load()
    channels = ConfigManager.get_channel_config()
    assert "v_an" in channels
    assert "i_a" in channels
    assert ConfigManager.get_limits()["v_max"] == 132.0

def test_scope_init():
    from src.serial_reader import SerialManager
    mgr = SerialManager()
    scope = InverterScope(mgr)
    assert scope is not None
    # Check trace creation
    assert "v_an" in scope.traces
