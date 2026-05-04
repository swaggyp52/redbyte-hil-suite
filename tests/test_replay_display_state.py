import json

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from src.dataset_converter import dataset_to_session
from src.file_ingestion import ImportedDataset
from src.recorder import Recorder
from ui.replay_studio import ReplayStudio


class _FakeSerialMgr(QObject):
    frame_received = pyqtSignal(dict)


def _make_dataset(duration_s: float = 0.1, n: int = 2000) -> ImportedDataset:
    t = np.linspace(0.0, duration_s, n, endpoint=False)
    v_an = 120.0 * np.sin(2 * np.pi * 60.0 * t)
    v_bn = 120.0 * np.sin(2 * np.pi * 60.0 * t - 2 * np.pi / 3)
    v_cn = 120.0 * np.sin(2 * np.pi * 60.0 * t + 2 * np.pi / 3)
    channels = {"v_an": v_an, "v_bn": v_bn, "v_cn": v_cn}
    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/tmp/rigol.csv",
        channels=channels,
        time=t,
        sample_rate=float(1.0 / np.median(np.diff(t))),
        duration=duration_s,
        warnings=[],
        meta={"time_column": "Time(s)"},
        raw_headers=["Time(s)", "CH1(V)", "CH2(V)", "CH3(V)"],
    )


def test_dataset_converter_emits_display_time_field():
    ds = _make_dataset(duration_s=0.1, n=2000)
    capsule = dataset_to_session(ds, session_id="display_time_test")
    frames = capsule["frames"]
    assert frames
    assert "display_time_s" in frames[0]
    assert abs(frames[0]["display_time_s"] - 0.0) < 1e-9
    assert 0.095 <= frames[-1]["display_time_s"] <= 0.1001


def test_replay_import_resets_cursor_and_range(tmp_path, qapp):
    _ = qapp
    ds = _make_dataset(duration_s=0.1, n=2000)
    capsule = dataset_to_session(ds, session_id="replay_range_test")

    studio = ReplayStudio(Recorder(), _FakeSerialMgr())
    studio.load_session_from_dict(capsule, label="replay_range_test", is_primary=True)

    assert studio.play_idx == 0
    assert abs(studio.scrubber.value()) < 1e-9

    x_min, x_max = studio.plot_wave.viewRange()[0]
    assert x_min <= 0.01
    assert x_max >= 0.08

    # Move cursor and zoom away, then verify reset returns to full session span.
    studio.play_idx = min(100, len(studio._ts_arr) - 1)
    studio._update_ui(studio.play_idx)
    studio.plot_wave.setXRange(0.04, 0.06, padding=0.0)
    studio._reset_zoom()

    x_min_reset, x_max_reset = studio.plot_wave.viewRange()[0]
    assert x_min_reset <= 0.01
    assert x_max_reset >= 0.08


def test_primary_load_replaces_prior_session(tmp_path, qapp):
    _ = qapp
    studio = ReplayStudio(Recorder(), _FakeSerialMgr())

    ds_a = _make_dataset(duration_s=0.2, n=1000)
    capsule_a = dataset_to_session(ds_a, session_id="session_a")
    path_a = tmp_path / "session_a.json"
    path_a.write_text(json.dumps(capsule_a))

    ds_b = _make_dataset(duration_s=0.05, n=600)
    capsule_b = dataset_to_session(ds_b, session_id="session_b")
    path_b = tmp_path / "session_b.json"
    path_b.write_text(json.dumps(capsule_b))

    studio._load_session(str(path_a), is_primary=True)
    assert len(studio.sessions) == 1

    studio._load_session(str(path_b), is_primary=True)
    assert len(studio.sessions) == 1
    assert studio.sessions[0]["label"] == "session_b"
