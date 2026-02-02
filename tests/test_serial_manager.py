import time

import pytest

import src.serial_reader as serial_reader


class FakeAdapter:
    def __init__(self, frames=None):
        self.frames = frames or []
        self.connected = False
        self.commands = []

    def connect(self, config):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    def read_frame(self):
        if self.frames:
            return self.frames.pop(0)
        return None

    def write_command(self, command_type, payload=None):
        self.commands.append((command_type, payload))
        return True


def test_serial_manager_switch_and_command(monkeypatch):
    fake = FakeAdapter(frames=[{"ts": 1, "v_an": 1, "v_bn": 0, "v_cn": -1}])

    monkeypatch.setattr(serial_reader, "SerialAdapter", lambda: fake)
    monkeypatch.setattr(serial_reader, "DemoAdapter", lambda: fake)
    monkeypatch.setattr(serial_reader, "OpalRTAdapter", lambda: fake)

    mgr = serial_reader.SerialManager()
    received = []
    mgr.frame_received.connect(lambda f: received.append(f))

    mgr.connect_serial("COM_TEST")
    time.sleep(0.05)
    assert mgr.write_command("fault_sag", {"duration": 0.5}) is True

    mgr.stop()
    assert fake.commands
    assert any(cmd[0] == "fault_sag" for cmd in fake.commands)


def test_serial_manager_mock_mode(monkeypatch, qapp):
    """Test mock mode with proper Qt event loop handling"""
    from PyQt6.QtCore import QTimer
    
    fake = FakeAdapter(frames=[{"ts": 2, "v_an": 2, "v_bn": 0, "v_cn": -2}])
    monkeypatch.setattr(serial_reader, "DemoAdapter", lambda: fake)

    mgr = serial_reader.SerialManager()
    received = []
    mgr.frame_received.connect(lambda f: received.append(f))

    mgr.start_mock_mode()
    
    # Process Qt events for up to 500ms to allow signal to fire
    timeout = 500
    elapsed = 0
    while not received and elapsed < timeout:
        qapp.processEvents()
        QTimer.singleShot(10, lambda: None)
        qapp.processEvents()
        elapsed += 10
    
    mgr.stop()
    
    assert len(received) >= 1, "No frames received from mock mode"
    assert "v_an" in received[0]
