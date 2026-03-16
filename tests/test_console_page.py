"""
Tests for ui/pages/console_page.py

Verifies that ConsolePage, _ConsoleHeaderBar, and _CompactIEEEPanel
instantiate cleanly and respond correctly to data updates.
"""
import json
import sys

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


# ── Minimal fakes ──────────────────────────────────────────────────────────────

class FakeSerialMgr(QObject):
    frame_received = pyqtSignal(dict)
    connection_status = pyqtSignal(bool, str)


class FakeInsightEngine(QObject):
    insight_emitted = pyqtSignal(dict)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_console_page_instantiates(qapp):
    """ConsolePage should construct without errors given fake managers."""
    from ui.pages.console_page import ConsolePage

    serial_mgr = FakeSerialMgr()
    insight_engine = FakeInsightEngine()

    page = ConsolePage(serial_mgr, insight_engine)

    assert page is not None
    assert page.scope is not None
    assert page.phasor is not None
    assert page.insights is not None

    page.close()


def test_header_bar_updates_on_frame(qapp):
    """_ConsoleHeaderBar should update metric chip text when on_frame is called."""
    from ui.pages.console_page import _ConsoleHeaderBar

    header = _ConsoleHeaderBar()

    frame = {
        "freq":       60.03,
        "v_rms":     119.8,
        "thd":         3.5,
        "p_mech":    995.0,
        "fault_type": None,
    }
    header.on_frame(frame)
    header._apply_pending()      # force immediate apply, bypassing 250ms timer

    assert "60.03" in header._chip_freq._value.text()
    assert "119.8" in header._chip_rms._value.text()
    assert "3.5"   in header._chip_thd._value.text()
    assert "995"   in header._chip_power._value.text()

    header.close()


def test_header_bar_fault_badge(qapp):
    """Header badge should switch to FAULT ACTIVE when fault_type is set, then clear."""
    from ui.pages.console_page import _ConsoleHeaderBar

    header = _ConsoleHeaderBar()

    # Trigger fault
    header.on_frame({"freq": 59.9, "v_rms": 60.0, "thd": 8.1,
                     "p_mech": 500.0, "fault_type": "sag"})
    header._apply_pending()

    assert header._current_status == "fault"
    assert "FAULT" in header._badge.text()

    # Clear fault — should return to stable
    header.on_frame({"freq": 60.0, "v_rms": 120.0, "thd": 3.5,
                     "p_mech": 1000.0, "fault_type": None})
    header._apply_pending()

    assert header._current_status == "stable"
    assert "STABLE" in header._badge.text()

    header.close()


def test_ieee_panel_set_results(qapp):
    """_CompactIEEEPanel.set_results should update rule row chips to PASS/FAIL."""
    from ui.pages.console_page import _CompactIEEEPanel

    panel = _CompactIEEEPanel()

    results = [
        {"name": "Ride-through 50% sag", "passed": True,  "details": "min 101V"},
        {"name": "Freq ±0.5Hz",          "passed": True,  "details": "59.5–60.5"},
        {"name": "Voltage recovery",     "passed": False, "details": "undervolt window"},
    ]
    panel.set_results(results)

    assert panel._rows[0]._chip.text() == "PASS"
    assert panel._rows[1]._chip.text() == "PASS"
    assert panel._rows[2]._chip.text() == "FAIL"
    assert "101V" in panel._rows[0]._detail_lbl.text()

    panel.close()


def test_console_page_load_session(qapp, tmp_path):
    """load_session should enable the 'Run Tests' button in the IEEE panel."""
    from ui.pages.console_page import ConsolePage

    serial_mgr = FakeSerialMgr()
    insight_engine = FakeInsightEngine()
    page = ConsolePage(serial_mgr, insight_engine)

    # IEEE Run Tests button starts disabled
    assert not page._ieee._run_btn.isEnabled()

    # Write a minimal session file
    session = {
        "meta": {
            "version": "1.2",
            "session_id": "test_session_001",
            "frame_count": 10,
            "sample_rate_estimate": 50.0,
        },
        "frames": [
            {"ts": float(i), "v_an": 120.0, "v_bn": -60.0, "v_cn": -60.0,
             "i_a": 5.0, "i_b": -2.5, "i_c": -2.5, "freq": 60.0, "p_mech": 1000.0}
            for i in range(10)
        ],
        "insights": [],
        "events": [],
    }
    path = tmp_path / "test_session_001.json"
    path.write_text(json.dumps(session))

    page.load_session(str(path))
    assert page._ieee._run_btn.isEnabled()

    page.close()
