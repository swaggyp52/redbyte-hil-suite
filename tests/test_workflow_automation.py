import math
import sys
import time
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

from io_adapter import DemoAdapter
from launchers.launch_compliance import ComplianceRunnerPanel
from launchers.launch_diagnostics import DiagnosticsWindow
from launchers.launch_replay import ReplayWindow
from replayer import Replayer


def _make_frame(idx: int, ts0: float) -> dict:
    ts = ts0 + idx * 0.02
    freq = 60.0
    v_scale = 1.0
    fault_type = None

    # Inject sag and drift periods so compliance sees meaningful variation.
    if 50 <= idx < 100:
        v_scale = 0.5
        fault_type = "sag"
    if 180 <= idx < 240:
        freq = 61.5
        fault_type = "drift"

    w = 2 * math.pi * freq
    v_peak = 120.0 * math.sqrt(2) * v_scale
    i_peak = 5.0 * math.sqrt(2)

    frame = {
        "ts": ts,
        "v_an": v_peak * math.sin(w * ts),
        "v_bn": v_peak * math.sin(w * ts - 2 * math.pi / 3),
        "v_cn": v_peak * math.sin(w * ts + 2 * math.pi / 3),
        "i_a": i_peak * math.sin(w * ts - 0.1),
        "i_b": i_peak * math.sin(w * ts - 2 * math.pi / 3 - 0.1),
        "i_c": i_peak * math.sin(w * ts + 2 * math.pi / 3 - 0.1),
        "freq": freq,
        "p_mech": 1000.0,
        "fault_type": fault_type,
    }
    return frame


def test_diagnostics_to_replay_to_compliance_pipeline(qapp, tmp_path, monkeypatch):
    diag = DiagnosticsWindow()
    diag.recorder.data_dir = str(tmp_path)

    diag.start_recording()
    ts0 = time.time()
    for idx in range(260):
        diag._on_frame(_make_frame(idx, ts0))
    diag.stop_recording()

    session_files = sorted(tmp_path.glob("session_*.json"))
    assert session_files, "Expected Diagnostics recording to create a session JSON"
    session_path = session_files[-1]

    # Replay load check
    replayer = Replayer()
    assert replayer.load_file(str(session_path)) is True
    assert replayer.total_frames >= 200

    # Compliance run + export
    panel = ComplianceRunnerPanel()
    panel.load_from_path(str(session_path))
    panel._run_checks()
    assert panel.table.rowCount() >= 3

    import launchers.launch_compliance as launch_compliance

    real_generate_report = launch_compliance.generate_report
    monkeypatch.setattr(
        launch_compliance,
        "generate_report",
        lambda p: real_generate_report(p, output_dir=str(tmp_path)),
    )
    opened_urls = []
    monkeypatch.setattr(
        launch_compliance.webbrowser,
        "open_new_tab",
        lambda url: opened_urls.append(url),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    panel._export_report()

    reports = list(tmp_path.glob("session_report_*.html"))
    assert reports, "Expected Compliance export to generate a timestamped HTML report"
    assert opened_urls and opened_urls[0].startswith("file://")

    panel.close()
    diag.close()


def test_demo_adapter_fault_injection_changes_voltage_magnitude():
    adapter = DemoAdapter()
    assert adapter.connect({}) is True

    baseline = [abs(adapter.read_frame()["v_an"]) for _ in range(25)]

    assert adapter.write_command("fault_sag", {"duration": 0.8}) is True
    sag = [abs(adapter.read_frame()["v_an"]) for _ in range(25)]

    baseline_avg = sum(baseline) / len(baseline)
    sag_avg = sum(sag) / len(sag)
    assert sag_avg < baseline_avg * 0.8

    assert adapter.write_command("clear_fault") is True
    recovered = [abs(adapter.read_frame()["v_an"]) for _ in range(25)]
    recovered_avg = sum(recovered) / len(recovered)
    assert recovered_avg > sag_avg

    adapter.disconnect()


def test_replay_window_controls_operate(qapp):
    win = ReplayWindow()

    win.seek(245)
    assert win.playback_position == 245
    assert ":" in win.pos_label.text()

    win.play()
    assert win.playing is True

    win.pause()
    assert win.playing is False

    win.stop()
    assert win.playback_position == 0

    win.close()


def test_redbyte_launcher_direct_app_cli_passes_mock_and_load(monkeypatch):
    import redbyte_launcher

    class DummyApp:
        def __init__(self, *args, **kwargs):
            pass

    launched = {}

    def fake_popen(cmd, cwd=None):
        launched["cmd"] = cmd
        launched["cwd"] = cwd

        class _Proc:
            pass

        return _Proc()

    monkeypatch.setattr(redbyte_launcher, "QApplication", DummyApp)
    monkeypatch.setattr(redbyte_launcher.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "redbyte_launcher.py",
            "--mock",
            "--app",
            "diagnostics",
            "--load",
            "demo_session.json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        redbyte_launcher.main()

    assert exc.value.code == 0
    assert "--mock" in launched["cmd"]
    assert "--load" in launched["cmd"]
