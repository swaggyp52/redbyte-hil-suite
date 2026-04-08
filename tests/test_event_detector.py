"""
Tests for src/event_detector.py — batch event detection on ImportedDataset.

TDD: these tests were written BEFORE implementation.

Covers:
  - Voltage sag detection
  - Voltage swell detection
  - Frequency excursion / drift
  - Flatline / missing-data / constant-channel detection
  - Abrupt step-change / discontinuity detection
  - Clipping / saturation detection
  - Duplicate/identical channel detection
  - Graceful no-op on partial / unsupported datasets
  - DetectedEvent dataclass field contract
  - Detection metrics (duration, worst value, etc.)
  - Clean synthetic signal produces no false positives
"""

import numpy as np
import pytest

from src.file_ingestion import ImportedDataset
from src.event_detector import DetectedEvent, detect_events


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ds(n: int, channels: dict, sample_rate: float = 1000.0) -> ImportedDataset:
    t = np.linspace(0.0, float(n - 1) / sample_rate, n)
    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/fake/test.csv",
        channels={k: np.asarray(v, dtype=np.float64) for k, v in channels.items()},
        time=t,
        sample_rate=sample_rate,
        duration=float(t[-1] - t[0]),
        warnings=[],
        raw_headers=list(channels.keys()),
    )


def _clean_sine(n: int = 2000, freq: float = 60.0, sr: float = 10_000.0,
                amplitude: float = 169.7) -> np.ndarray:
    """Clean 60 Hz sinusoid — should produce no false-positive events."""
    t = np.linspace(0.0, float(n - 1) / sr, n)
    return amplitude * np.sin(2 * np.pi * freq * t)


# ---------------------------------------------------------------------------
# DetectedEvent dataclass contract
# ---------------------------------------------------------------------------

def test_detected_event_has_required_fields():
    e = DetectedEvent(
        kind="voltage_sag",
        ts_start=0.1,
        ts_end=0.3,
        channel="v_an",
        severity="warning",
        description="Voltage sag detected",
        metrics={"depth_pct": 25.0, "duration_s": 0.2},
        confidence=0.95,
    )
    assert e.kind == "voltage_sag"
    assert e.ts_start == 0.1
    assert e.ts_end == 0.3
    assert e.channel == "v_an"
    assert e.severity in ("info", "warning", "critical")
    assert isinstance(e.description, str) and e.description
    assert isinstance(e.metrics, dict)
    assert 0.0 <= e.confidence <= 1.0


def test_detected_event_to_dict():
    e = DetectedEvent(
        kind="flatline",
        ts_start=1.0,
        ts_end=2.0,
        channel="freq",
        severity="info",
        description="Constant value",
        metrics={},
        confidence=0.8,
    )
    d = e.to_dict()
    assert d["type"] == "flatline"
    assert d["ts"] == e.ts_start
    assert "description" in d
    assert "severity" in d
    assert "metrics" in d


# ---------------------------------------------------------------------------
# Voltage sag detection
# ---------------------------------------------------------------------------

def test_detects_voltage_sag():
    """Short sag window: v_an drops to 50% of nominal for 0.2s."""
    sr = 5000.0
    n = int(sr * 2)  # 2 seconds
    sig = _clean_sine(n, sr=sr)
    # Inject a sag: drop to 50% amplitude for samples 5000..5999 (1.0 - 1.2s)
    sig[5000:6000] *= 0.5
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    sag_events = [e for e in events if e.kind == "voltage_sag"]
    assert len(sag_events) >= 1
    sag = sag_events[0]
    assert sag.channel == "v_an"
    assert sag.ts_start < sag.ts_end
    assert "depth" in sag.metrics or "depth_pct" in sag.metrics


def test_no_sag_on_clean_signal():
    """Clean undisturbed sinusoid → no sag events."""
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    sag_events = [e for e in events if e.kind == "voltage_sag"]
    assert sag_events == []


def test_sag_severity_critical_for_deep_sag():
    """Sag below 50% nominal is critical."""
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    sig[5000:7000] *= 0.3    # 30% of nominal – very deep
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    sag_events = [e for e in events if e.kind == "voltage_sag"]
    assert any(e.severity == "critical" for e in sag_events)


def test_sag_metrics_include_duration():
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    sig[5000:6000] *= 0.5
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    sag = next((e for e in events if e.kind == "voltage_sag"), None)
    assert sag is not None
    duration = sag.ts_end - sag.ts_start
    assert duration > 0.0


# ---------------------------------------------------------------------------
# Voltage swell detection
# ---------------------------------------------------------------------------

def test_detects_voltage_swell():
    """v_an rises to 130% of nominal for 0.2s."""
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    sig[5000:6000] *= 1.3
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    swell_events = [e for e in events if e.kind == "voltage_swell"]
    assert len(swell_events) >= 1


# ---------------------------------------------------------------------------
# Frequency excursion
# ---------------------------------------------------------------------------

def test_detects_frequency_excursion():
    """freq drops below 59.0 Hz for a window."""
    sr = 1000.0
    n = int(sr * 5)
    freq_sig = np.ones(n) * 60.0
    freq_sig[2000:3000] = 58.5
    ds = _ds(n, {"freq": freq_sig}, sample_rate=sr)
    events = detect_events(ds)
    exc_events = [e for e in events if e.kind == "freq_excursion"]
    assert len(exc_events) >= 1


def test_frequency_excursion_has_worst_deviation_metric():
    sr = 1000.0
    n = int(sr * 3)
    freq_sig = np.ones(n) * 60.0
    freq_sig[1000:2000] = 58.0     # -2 Hz excursion
    ds = _ds(n, {"freq": freq_sig}, sample_rate=sr)
    events = detect_events(ds)
    exc = next((e for e in events if e.kind == "freq_excursion"), None)
    assert exc is not None
    assert "deviation" in exc.metrics or "worst_hz" in exc.metrics or "deviation_hz" in exc.metrics


def test_no_frequency_excursion_on_steady_60hz():
    sr = 1000.0
    n = int(sr * 2)
    ds = _ds(n, {"freq": np.ones(n) * 60.0}, sample_rate=sr)
    events = detect_events(ds)
    exc_events = [e for e in events if e.kind == "freq_excursion"]
    assert exc_events == []


# ---------------------------------------------------------------------------
# Flatline / missing-data / constant-value detection
# ---------------------------------------------------------------------------

def test_detects_flatline_region():
    """Channel stuck at a constant value for a noticeable window."""
    sr = 1000.0
    n = int(sr * 3)
    sig = np.sin(np.linspace(0, 6 * np.pi, n))
    sig[1000:2000] = sig[999]   # stuck value
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    flat_events = [e for e in events if e.kind == "flatline"]
    assert len(flat_events) >= 1


def test_flatline_start_and_end_in_correct_range():
    sr = 1000.0
    n = 3000
    sig = np.sin(np.linspace(0, 6 * np.pi, n))
    sig[1000:2000] = 0.0      # flat to zero
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    flat = next((e for e in events if e.kind == "flatline"), None)
    assert flat is not None
    # Flatline window should start near t = 1.0s (±10 samples)
    assert 0.9 < flat.ts_start < 1.1
    assert flat.ts_end > flat.ts_start


def test_fully_constant_channel_is_flagged():
    """A channel that is identically zero throughout → flagged as constant."""
    sr = 1000.0
    n = 2000
    ds = _ds(n, {"v_bn": np.zeros(n), "v_an": np.sin(np.linspace(0, 4*np.pi, n))},
             sample_rate=sr)
    events = detect_events(ds)
    # Either flagged as flatline or "constant_channel" — kind contains "flat" or "constant"
    flagged = [e for e in events if "flat" in e.kind or "constant" in e.kind]
    channels_flagged = {e.channel for e in flagged}
    assert "v_bn" in channels_flagged


# ---------------------------------------------------------------------------
# Step change / discontinuity detection
# ---------------------------------------------------------------------------

def test_detects_abrupt_step_change():
    """A sudden large step in signal amplitude → discontinuity event."""
    sr = 1000.0
    n = 2000
    sig = np.ones(n) * 50.0
    sig[1000:] = 100.0      # instant doubling
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    step_events = [e for e in events if e.kind == "step_change"]
    assert len(step_events) >= 1


def test_no_step_change_on_smooth_ramp():
    sr = 1000.0
    n = 2000
    ds = _ds(n, {"v_an": np.linspace(0, 100, n)}, sample_rate=sr)
    events = detect_events(ds)
    step_events = [e for e in events if e.kind == "step_change"]
    assert step_events == []


# ---------------------------------------------------------------------------
# Clipping / saturation detection
# ---------------------------------------------------------------------------

def test_detects_clipping():
    """Many consecutive identical extreme values → clipping suspected."""
    sr = 5000.0
    n = int(sr * 1)
    sig = _clean_sine(n, sr=sr)
    clip_val = float(sig.max())
    sig[2000:2050] = clip_val   # 50-sample clip at peak
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    clip_events = [e for e in events if e.kind == "clipping"]
    assert len(clip_events) >= 1


# ---------------------------------------------------------------------------
# Duplicate channel detection
# ---------------------------------------------------------------------------

def test_detects_duplicate_channels():
    """Two channels with identical data → flagged as suspicious duplicate."""
    sr = 1000.0
    n = 1000
    sig = np.sin(np.linspace(0, 2 * np.pi, n))
    ds = _ds(n, {"v_an": sig, "v_dup": sig.copy()}, sample_rate=sr)
    events = detect_events(ds)
    dup_events = [e for e in events if e.kind == "duplicate_channel"]
    assert len(dup_events) >= 1


def test_no_duplicate_for_different_channels():
    sr = 1000.0
    n = 500
    t = np.linspace(0, np.pi, n)
    ds = _ds(n, {"v_an": np.sin(t), "v_bn": np.cos(t)}, sample_rate=sr)
    events = detect_events(ds)
    dup_events = [e for e in events if e.kind == "duplicate_channel"]
    assert dup_events == []


# ---------------------------------------------------------------------------
# Graceful degradation on partial / unsupported datasets
# ---------------------------------------------------------------------------

def test_no_sag_event_when_no_voltage_channel():
    """Dataset with only 'freq' channel → no sag detection."""
    sr = 1000.0
    n = 1000
    ds = _ds(n, {"freq": np.ones(n) * 60.0}, sample_rate=sr)
    events = detect_events(ds)
    sag_events = [e for e in events if e.kind == "voltage_sag"]
    assert sag_events == []


def test_no_frequency_event_when_no_freq_channel():
    """Dataset with only voltage → no frequency excursion detected."""
    sr = 5000.0
    n = int(sr * 1)
    sig = _clean_sine(n, sr=sr)
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    exc_events = [e for e in events if e.kind == "freq_excursion"]
    assert exc_events == []


def test_empty_dataset_returns_empty_list():
    sr = 1000.0
    n = 3
    ds = _ds(n, {"v_an": np.ones(3)}, sample_rate=sr)
    events = detect_events(ds)
    assert isinstance(events, list)
    # Very short dataset should return empty or minimal events — no crash
    assert events is not None


def test_detect_events_on_dataset_with_no_channels():
    ds = _ds(10, {}, sample_rate=1000.0)
    events = detect_events(ds)
    assert events == []


# ---------------------------------------------------------------------------
# Harmonic / THD spike detection
# ---------------------------------------------------------------------------

def test_detects_thd_spike_in_distorted_signal():
    """Heavily distorted waveform → THD spike event flagged."""
    sr = 10_000.0
    n = int(sr * 1)   # 1 second
    t = np.linspace(0, 1.0, n, endpoint=False)
    # Add very strong harmonics (THD >> 10%)
    sig = (
        169.7 * np.sin(2 * np.pi * 60 * t)
        + 60.0 * np.sin(2 * np.pi * 180 * t)   # 3rd harmonic at 35%
        + 40.0 * np.sin(2 * np.pi * 300 * t)   # 5th harmonic at 24%
    )
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    thd_events = [e for e in events if "thd" in e.kind.lower() or "harmonic" in e.kind.lower()]
    assert len(thd_events) >= 1


def test_no_thd_event_on_pure_sine():
    """Pure 60 Hz sine → THD near zero → no harmonic event."""
    sr = 10_000.0
    n = int(sr * 0.5)
    sig = _clean_sine(n, sr=sr)
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    thd_events = [e for e in events if "thd" in e.kind.lower() or "harmonic" in e.kind.lower()]
    assert thd_events == []


# ---------------------------------------------------------------------------
# Event list metadata
# ---------------------------------------------------------------------------

def test_all_events_have_valid_severity():
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    sig[5000:6000] *= 0.5
    sig[1000:1020] = sig[999]   # flatline
    ds = _ds(n, {"v_an": sig, "freq": np.ones(n) * 59.0}, sample_rate=sr)
    events = detect_events(ds)
    for e in events:
        assert e.severity in ("info", "warning", "critical"), \
            f"Invalid severity '{e.severity}' for {e.kind}"


def test_all_events_have_non_empty_description():
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    sig[5000:6000] *= 0.5
    ds = _ds(n, {"v_an": sig}, sample_rate=sr)
    events = detect_events(ds)
    for e in events:
        assert e.description.strip(), f"{e.kind} has empty description"


def test_all_events_ts_start_lte_ts_end():
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    sig[5000:6000] *= 0.5
    ds = _ds(n, {"v_an": sig, "freq": np.ones(n) * 58.5}, sample_rate=sr)
    events = detect_events(ds)
    for e in events:
        assert e.ts_start <= e.ts_end, f"{e.kind}: ts_start={e.ts_start} > ts_end={e.ts_end}"


# ---------------------------------------------------------------------------
# Rigol oscilloscope channel names (CH1(V), CH2(V), etc.)
# ---------------------------------------------------------------------------

def test_is_voltage_channel_unit_suffix_variants():
    """Oscilloscope-style unit suffix names must be recognised as voltage channels."""
    from src.event_detector import _is_voltage_channel
    # Voltage suffixes — must be True
    assert _is_voltage_channel("CH1(V)"),  "CH1(V) must be treated as voltage"
    assert _is_voltage_channel("ch2(v)"),  "lowercase ch2(v) must be treated as voltage"
    assert _is_voltage_channel("v_an"),    "canonical v_an must still work"
    assert _is_voltage_channel("v_dc"),    "v_dc must still work"
    # Non-voltage suffixes — must be False
    assert not _is_voltage_channel("CH1(A)"),  "ampere unit must NOT be voltage"
    assert not _is_voltage_channel("time(s)"), "time column must NOT be voltage"
    assert not _is_voltage_channel("freq"),    "frequency channel must NOT be voltage"
    assert not _is_voltage_channel("CH1(Hz)"), "Hz unit must NOT be voltage"


def test_rigol_ch1v_triggers_voltage_sag_event():
    """CH1(V) channel with injected voltage sag should yield a voltage_sag event."""
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    sig[5000:6000] *= 0.5   # ~200 ms sag to 50% nominal
    ds = _ds(n, {"CH1(V)": sig}, sample_rate=sr)
    events = detect_events(ds)
    sag_events = [e for e in events if e.kind == "voltage_sag"]
    assert len(sag_events) >= 1, (
        f"Expected voltage_sag event for CH1(V) but got event kinds: "
        f"{[e.kind for e in events]}"
    )
    assert sag_events[0].channel == "CH1(V)"


def test_rigol_ch1a_does_not_trigger_voltage_sag_event():
    """Ampere-unit channel CH1(A) must NOT be treated as voltage."""
    sr = 5000.0
    n = int(sr * 2)
    sig = _clean_sine(n, sr=sr)
    sig[5000:6000] *= 0.5
    ds = _ds(n, {"CH1(A)": sig}, sample_rate=sr)
    events = detect_events(ds)
    sag_events = [e for e in events if e.kind == "voltage_sag"]
    assert sag_events == [], (
        f"CH1(A) should not trigger voltage_sag but got: {sag_events}"
    )
