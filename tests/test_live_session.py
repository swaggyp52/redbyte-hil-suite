"""
Tests for the live telemetry session unification layer.

Covers:
- present_canonical_keys() — distinguishing measured vs zero-filled channels
- Recorder.to_capsule() — in-memory capsule without disk write
- Partial live session truthfulness (DC-bus-only hardware → no 3-phase fabrication)
- ActiveSession.from_capsule() with live source_type
- LiveStats dataclass
- SerialManager stats helpers (no threading required)
"""

import time
import threading
from src.models import normalize_frame, present_canonical_keys
from src.recorder import Recorder
from src.session_state import ActiveSession
from src.serial_reader import SerialManager, LiveStats


# ──────────────────────────────────────────────────────────────────────────────
# present_canonical_keys
# ──────────────────────────────────────────────────────────────────────────────

def test_present_canonical_keys_full_3phase():
    raw = {
        "ts": 1.0,
        "v_an": 120.0, "v_bn": -60.0, "v_cn": -60.0,
        "i_a": 5.0, "i_b": -2.5, "i_c": -2.5,
        "freq": 60.0, "p_mech": 1000.0,
    }
    keys = present_canonical_keys(raw)
    assert "v_an" in keys
    assert "v_bn" in keys
    assert "v_cn" in keys
    assert "i_a" in keys
    assert "freq" in keys
    assert "p_mech" in keys
    # ts is excluded — it is metadata, not a measured channel
    assert "ts" not in keys


def test_present_canonical_keys_arduino_partial():
    """Arduino breadboard only sends DC bus voltage — no 3-phase waveforms."""
    raw = {
        "t_ms": 1523,          # Arduino millis()
        "vdc": 450.0,          # DC bus
        "freq": 60.02,
        "p_kw": 0.99,
        "q_kvar": 0.20,
        "fault": 0,
    }
    keys = present_canonical_keys(raw)
    # DC bus aliases → v_dc
    assert "v_dc" in keys
    assert "freq" in keys
    assert "p_mech" in keys   # p_kw → p_mech via alias
    assert "q" in keys        # q_kvar → q via alias
    assert "status" in keys   # fault → status via alias
    # 3-phase channels are NOT in the raw frame
    assert "v_an" not in keys
    assert "v_bn" not in keys
    assert "v_cn" not in keys
    assert "i_a" not in keys
    # ts excluded
    assert "ts" not in keys


def test_present_canonical_keys_excludes_ts():
    raw = {"timestamp": 999.0, "freq": 60.0}
    keys = present_canonical_keys(raw)
    assert "ts" not in keys
    assert "freq" in keys


def test_present_canonical_keys_returns_frozenset():
    keys = present_canonical_keys({"freq": 60.0})
    assert isinstance(keys, frozenset)


# ──────────────────────────────────────────────────────────────────────────────
# Recorder.to_capsule()
# ──────────────────────────────────────────────────────────────────────────────

def _make_test_frames(n: int = 15) -> list[dict]:
    t0 = time.time()
    return [
        {
            "ts": t0 + i * 0.02,
            "v_an": 120.0, "v_bn": -60.0, "v_cn": -60.0,
            "i_a": 5.0, "i_b": -2.5, "i_c": -2.5,
            "freq": 60.0, "p_mech": 1000.0,
        }
        for i in range(n)
    ]


def test_recorder_to_capsule_after_start():
    rec = Recorder(data_dir="data/test_sessions")
    rec.start()
    for f in _make_test_frames(15):
        rec.log_frame(f)

    capsule = rec.to_capsule()
    assert "meta" in capsule
    assert "frames" in capsule
    assert len(capsule["frames"]) == 15
    assert capsule["meta"]["frame_count"] == 15
    assert capsule["meta"]["source_type"] == "live"


def test_recorder_to_capsule_does_not_stop_recording():
    rec = Recorder(data_dir="data/test_sessions")
    rec.start()
    for f in _make_test_frames(5):
        rec.log_frame(f)

    _ = rec.to_capsule()
    # Recording should still be active
    assert rec.is_recording is True
    # We can still log more frames
    rec.log_frame(_make_test_frames(1)[0])
    assert len(rec.buffer) == 6


def test_recorder_to_capsule_returns_copy_not_reference():
    rec = Recorder(data_dir="data/test_sessions")
    rec.start()
    for f in _make_test_frames(5):
        rec.log_frame(f)

    capsule = rec.to_capsule()
    # Mutating the capsule frames list must not mutate the recorder buffer
    capsule["frames"].clear()
    assert len(rec.buffer) == 5


def test_recorder_to_capsule_detects_channels():
    rec = Recorder(data_dir="data/test_sessions")
    rec.start()
    for f in _make_test_frames(5):
        rec.log_frame(f)

    capsule = rec.to_capsule()
    channels = capsule["meta"]["channels"]
    assert "v_an" in channels
    assert "freq" in channels


def test_recorder_to_capsule_before_start():
    """to_capsule on a never-started recorder returns empty capsule."""
    rec = Recorder(data_dir="data/test_sessions")
    capsule = rec.to_capsule()
    assert capsule["meta"]["frame_count"] == 0
    assert capsule["frames"] == []


# ──────────────────────────────────────────────────────────────────────────────
# Partial live session truthfulness
# ──────────────────────────────────────────────────────────────────────────────

def test_partial_live_session_no_fabricated_3phase():
    """Arduino partial frames normalize without fabricating non-zero 3-phase values."""
    arduino_raw = {
        "t_ms": 2000,
        "vdc": 450.0,
        "freq": 60.02,
        "p_kw": 0.99,
        "q_kvar": 0.20,
        "fault": 0,
    }
    normalized = normalize_frame(arduino_raw)
    # 3-phase voltages absent in hardware → filled to 0.0 (sentinel, not measured)
    assert normalized["v_an"] == 0.0
    assert normalized["v_bn"] == 0.0
    assert normalized["v_cn"] == 0.0
    assert normalized["i_a"] == 0.0
    # But the actually-measured channels are correct
    assert normalized["v_dc"] == 450.0
    assert normalized["freq"] == pytest.approx(60.02)
    assert normalized["p_mech"] == pytest.approx(990.0)   # kW → W
    assert normalized["q"] == pytest.approx(200.0)        # kVAR → VAR


def test_partial_live_session_present_channels_subset():
    """present_canonical_keys correctly identifies the partial channel set."""
    arduino_raw = {
        "t_ms": 2000,
        "vdc": 450.0,
        "freq": 60.02,
        "p_kw": 0.99,
        "q_kvar": 0.20,
        "fault": 0,
    }
    keys = present_canonical_keys(arduino_raw)
    three_phase = {"v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c"}
    # None of the 3-phase keys should appear
    assert keys.isdisjoint(three_phase)


# ──────────────────────────────────────────────────────────────────────────────
# ActiveSession from live capsule
# ──────────────────────────────────────────────────────────────────────────────

def test_active_session_from_live_capsule():
    rec = Recorder(data_dir="data/test_sessions")
    rec.start()
    for f in _make_test_frames(20):
        rec.log_frame(f)

    capsule = rec.to_capsule()
    session = ActiveSession.from_capsule(capsule)

    assert session.source_type == "live"
    assert session.row_count == 20
    assert session.duration > 0
    assert session.source_type_display == "Recorded Session"
    assert session.is_imported is False  # no import_meta block


def test_active_session_live_channel_count():
    rec = Recorder(data_dir="data/test_sessions")
    rec.start()
    for f in _make_test_frames(10):
        rec.log_frame(f)

    capsule = rec.to_capsule()
    session = ActiveSession.from_capsule(capsule)
    # Channels detected from the full 3-phase test frames
    assert session.channel_count > 0


# ──────────────────────────────────────────────────────────────────────────────
# LiveStats
# ──────────────────────────────────────────────────────────────────────────────

def test_live_stats_defaults():
    stats = LiveStats()
    assert stats.source == "—"
    assert stats.connected is False
    assert stats.fps == 0.0
    assert stats.frame_count == 0
    assert len(stats.present_channels) == 0
    assert stats.warnings == []


def test_serial_manager_initial_stats_disconnected():
    mgr = SerialManager()
    stats = mgr.get_live_stats()
    assert stats.connected is False
    assert stats.fps == 0.0
    assert stats.frame_count == 0


def test_serial_manager_compute_fps_empty():
    mgr = SerialManager()
    assert mgr._compute_fps() == 0.0


def test_serial_manager_compute_fps_with_timestamps():
    from collections import deque
    mgr = SerialManager()
    # Simulate 10 frames over 1 second → 9 fps
    t0 = time.time()
    mgr._ts_window = deque(maxlen=20)
    for i in range(10):
        mgr._ts_window.append(t0 + i * (1.0 / 9.0))
    fps = mgr._compute_fps()
    assert fps == pytest.approx(9.0, abs=0.5)


def test_serial_manager_reset_stats_clears_everything():
    mgr = SerialManager()
    mgr._frame_count = 99
    mgr._warnings = ["test"]
    mgr._present_channels = {"v_an"}
    mgr._reset_stats()
    assert mgr._frame_count == 0
    assert mgr._warnings == []
    assert len(mgr._present_channels) == 0


def test_serial_manager_update_stats_detects_dc_only_warning():
    mgr = SerialManager()
    raw = {"vdc": 450.0, "freq": 60.0, "p_kw": 1.0}
    normalized = normalize_frame(raw)
    mgr._update_stats(raw, normalized)
    assert any("DC bus" in w for w in mgr._warnings)


def test_serial_manager_update_stats_no_warning_for_full_3phase():
    mgr = SerialManager()
    raw = {
        "v_an": 120.0, "v_bn": -60.0, "v_cn": -60.0,
        "i_a": 5.0, "i_b": -2.5, "i_c": -2.5,
        "freq": 60.0, "p_mech": 1000.0,
    }
    normalized = normalize_frame(raw)
    mgr._update_stats(raw, normalized)
    assert mgr._warnings == []


# pytest import needed for approx
import pytest
