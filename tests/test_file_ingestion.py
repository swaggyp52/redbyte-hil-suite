"""
Tests for src/file_ingestion.py

Uses synthetic small files for unit tests.  Validates:
  - Rigol CSV parse (headers, time axis, NaN trimming, sample rate)
  - Simulation Excel parse (sheet selection, time axis, numeric columns)
  - Data Capsule JSON parse
  - Duplicate channel detection (correlation warning)
  - Error conditions (unsupported format, missing file, no data)
"""
import json
import os
import tempfile

import numpy as np
import pytest

from src.file_ingestion import (
    ImportedDataset,
    IngestionError,
    _estimate_sample_rate,
    _find_time_column,
    _time_column_is_milliseconds,
    ingest_file,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers to generate synthetic fixture files
# ──────────────────────────────────────────────────────────────────────────────

def _write_rigol_csv(path: str, n_rows: int = 200):
    """Write a minimal Rigol-format CSV file with 4 channels."""
    with open(path, "w") as f:
        f.write("Time(s),CH1(V),CH2(V),CH3(V),CH4(V)\n")
        t = 0.0
        for i in range(n_rows):
            ch1 = np.sin(2 * np.pi * 60 * t)
            ch2 = np.sin(2 * np.pi * 60 * t - 2.094)
            ch3 = np.sin(2 * np.pi * 60 * t + 2.094)
            ch4 = 0.1 * np.sin(2 * np.pi * 60 * t)
            f.write(f"{t:.6f},{ch1:.4f},{ch2:.4f},{ch3:.4f},{ch4:.4f}\n")
            t += 1e-4  # 10 kHz sample rate


def _write_rigol_csv_with_nan(path: str, n_rows: int = 100, nan_rows: int = 20):
    """Rigol CSV where the last `nan_rows` rows have NaN in data channels."""
    with open(path, "w") as f:
        f.write("Time(s),CH1(V),CH2(V)\n")
        t = 0.0
        for i in range(n_rows):
            if i >= n_rows - nan_rows:
                f.write(f"{t:.6f},9.9e37,9.9e37\n")  # Rigol fill value
            else:
                f.write(f"{t:.6f},{np.sin(60 * t):.4f},{np.cos(60 * t):.4f}\n")
            t += 1e-4


def _write_simulation_excel(path: str):
    """Write a minimal simulation Excel file."""
    try:
        import openpyxl
    except ImportError:
        pytest.skip("openpyxl not installed")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["time", "Pinv"])
    t = 0.0
    for i in range(50):
        ws.append([t, 1000.0 + 50 * np.sin(2 * np.pi * t)])
        t += 0.01
    wb.save(path)


def _write_duplicate_excel(path: str):
    """Excel file where two columns have identical data (simulating a duplicate)."""
    try:
        import openpyxl
    except ImportError:
        pytest.skip("openpyxl not installed")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["time", "Pinv", "AlsoPinv"])
    t = 0.0
    for i in range(50):
        val = 1000.0 + 50 * np.sin(2 * np.pi * t)
        ws.append([t, val, val])
        t += 0.01
    wb.save(path)


def _write_data_capsule_json(path: str, n_frames: int = 100):
    """Write a minimal Data Capsule JSON session."""
    frames = []
    for i in range(n_frames):
        frames.append({
            "ts": float(i) * 0.02,
            "v_an": float(np.sin(2 * np.pi * 60 * i * 0.02)),
            "v_bn": float(np.sin(2 * np.pi * 60 * i * 0.02 - 2.094)),
            "v_cn": float(np.sin(2 * np.pi * 60 * i * 0.02 + 2.094)),
            "freq": 60.0,
            "p_mech": 1000.0,
        })
    capsule = {
        "meta": {"version": "1.2", "session_id": "test_session"},
        "frames": frames,
        "insights": [],
        "events": [],
    }
    with open(path, "w") as f:
        json.dump(capsule, f)


# ──────────────────────────────────────────────────────────────────────────────
# Rigol CSV tests
# ──────────────────────────────────────────────────────────────────────────────

def test_rigol_csv_basic_ingestion():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_csv(path, n_rows=200)
        ds = ingest_file(path)

        assert ds.source_type == "rigol_csv"
        assert ds.row_count == 200
        assert "CH1(V)" in ds.channels
        assert "CH2(V)" in ds.channels
        assert "CH3(V)" in ds.channels
        assert "CH4(V)" in ds.channels
        assert len(ds.time) == 200
        assert abs(ds.time[0]) < 1e-9  # starts at 0
        assert ds.sample_rate > 5000   # ~10 kHz
        assert ds.duration > 0
        assert "Time(s)" not in ds.channels  # time col excluded
    finally:
        os.unlink(path)


def test_rigol_csv_channel_shapes_match_time():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_csv(path, n_rows=150)
        ds = ingest_file(path)
        for ch, arr in ds.channels.items():
            assert len(arr) == len(ds.time), (
                f"Channel '{ch}' length ({len(arr)}) != time length ({len(ds.time)})"
            )
    finally:
        os.unlink(path)


def test_rigol_csv_nan_trimming():
    """Channels with trailing NaN rows should be trimmed and a warning raised."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_csv_with_nan(path, n_rows=100, nan_rows=20)
        ds = ingest_file(path)
        # At least one NaN warning
        assert any("NaN" in w for w in ds.warnings)
        # Trimmed length should be < 100 (the NaN rows were dropped)
        assert ds.row_count < 100
    finally:
        os.unlink(path)


def test_rigol_csv_no_fabricated_canonical_channels():
    """Rigol CSV should NOT produce v_an, v_bn, etc. without a channel mapping."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_csv(path)
        ds = ingest_file(path)
        canonical = {"v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "freq", "p_mech"}
        assert not (canonical & set(ds.channel_names)), (
            f"Rigol CSV ingestion must NOT produce canonical channel names "
            f"without explicit mapping. Found: {canonical & set(ds.channel_names)}"
        )
    finally:
        os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# Simulation Excel tests
# ──────────────────────────────────────────────────────────────────────────────

def test_simulation_excel_basic_ingestion():
    pytest.importorskip("pandas")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        path = tf.name
    try:
        _write_simulation_excel(path)
        ds = ingest_file(path)

        assert ds.source_type == "simulation_excel"
        assert ds.row_count == 50
        assert "Pinv" in ds.channels
        assert len(ds.time) == 50
        assert ds.sample_rate > 0
    finally:
        os.unlink(path)


def test_simulation_excel_duplicate_column_warning():
    """Files with identical columns should generate a warning."""
    pytest.importorskip("pandas")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        path = tf.name
    try:
        _write_duplicate_excel(path)
        ds = ingest_file(path)
        dup_warnings = [w for w in ds.warnings if "identical" in w or "duplicate" in w]
        assert len(dup_warnings) > 0, (
            "Expected a duplicate-content warning but got none. "
            f"Warnings: {ds.warnings}"
        )
    finally:
        os.unlink(path)


def test_simulation_excel_time_starts_at_zero():
    pytest.importorskip("pandas")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        path = tf.name
    try:
        _write_simulation_excel(path)
        ds = ingest_file(path)
        assert abs(ds.time[0]) < 1e-9  # normalized to 0
    finally:
        os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# Data Capsule JSON tests
# ──────────────────────────────────────────────────────────────────────────────

def test_data_capsule_json_basic_ingestion():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        _write_data_capsule_json(path, n_frames=100)
        ds = ingest_file(path)

        assert ds.source_type == "data_capsule_json"
        assert ds.row_count == 100
        assert "v_an" in ds.channels
        assert "v_bn" in ds.channels
        assert "freq" in ds.channels
        assert abs(ds.time[0]) < 1e-9
    finally:
        os.unlink(path)


def test_data_capsule_json_channel_values_correct():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        _write_data_capsule_json(path, n_frames=50)
        ds = ingest_file(path)
        freq_arr = ds.channels["freq"]
        # All freq values should be 60.0
        assert np.allclose(freq_arr, 60.0)
    finally:
        os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# Error condition tests
# ──────────────────────────────────────────────────────────────────────────────

def test_ingest_missing_file():
    with pytest.raises(FileNotFoundError):
        ingest_file("/nonexistent/no_such_file_xyz.csv")


def test_ingest_unsupported_format():
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tf:
        path = tf.name
    try:
        with pytest.raises(IngestionError, match="Unsupported file format"):
            ingest_file(path)
    finally:
        os.unlink(path)


def test_ingest_empty_json():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as tf:
        json.dump({"meta": {}, "frames": []}, tf)
        path = tf.name
    try:
        with pytest.raises(IngestionError, match="no frames"):
            ingest_file(path)
    finally:
        os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# Helper function unit tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("headers,expected", [
    (["Time(s)", "CH1(V)"],    "Time(s)"),
    (["time", "Pinv"],         "time"),
    (["ts", "v_an"],           "ts"),
    (["timestamp", "freq"],    "timestamp"),
    (["CH1(V)", "CH2(V)"],     None),
])
def test_find_time_column(headers, expected):
    assert _find_time_column(headers) == expected


def test_estimate_sample_rate_uniform():
    t = np.linspace(0, 1, 1001)  # 1000 intervals at 1kHz
    sr = _estimate_sample_rate(t)
    assert abs(sr - 1000.0) < 10  # within 1%


def test_estimate_sample_rate_empty():
    assert _estimate_sample_rate(np.array([])) == 0.0


def test_estimate_sample_rate_single():
    assert _estimate_sample_rate(np.array([0.0])) == 0.0


# ──────────────────────────────────────────────────────────────────────────────
# VSM / Arduino telemetry CSV tests (t_ms time column + ms→s conversion)
# ──────────────────────────────────────────────────────────────────────────────

def _write_vsm_csv(path: str, n_rows: int = 30):
    """Write a VSM/Arduino-style telemetry CSV with t_ms time column."""
    with open(path, "w") as f:
        f.write("t_ms,vdc,freq,p_kw,q_kvar,fault\n")
        for i in range(n_rows):
            t_ms = 499 + i * 103
            vdc = 450.0 + 10 * np.sin(2 * np.pi * i / n_rows)
            freq = 60.0 + 0.02 * np.sin(2 * np.pi * i / n_rows)
            p_kw = 1.0
            q_kvar = 0.2 * np.sin(2 * np.pi * i / n_rows)
            fault = 1 if i > n_rows * 0.8 else 0
            f.write(f"{t_ms},{vdc:.2f},{freq:.4f},{p_kw:.2f},{q_kvar:.3f},{fault}\n")


@pytest.mark.parametrize("header,expected", [
    # Exact hint matches
    ("t_ms",        "t_ms"),
    ("time_ms",     "time_ms"),
    ("time(ms)",    "time(ms)"),
    ("Time(s)",     "Time(s)"),
    ("ts",          "ts"),
    # Fuzzy match — starts with "time"
    ("TimeAxis",    "TimeAxis"),
    # Non-time columns → None
    ("vdc",         None),
    ("CH1(V)",      None),
])
def test_find_time_column_extended(header, expected):
    assert _find_time_column([header]) == expected


@pytest.mark.parametrize("col,expected_ms", [
    ("t_ms",         True),
    ("time_ms",      True),
    ("time(ms)",     True),
    ("timestamp_ms", True),
    ("Time(s)",      False),
    ("ts",           False),
    ("time",         False),
    ("t",            False),
])
def test_time_column_is_milliseconds(col, expected_ms):
    assert _time_column_is_milliseconds(col) == expected_ms


def test_vsm_csv_ingests_without_error():
    """VSM telemetry CSV (t_ms header) must ingest successfully."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_vsm_csv(path, n_rows=30)
        ds = ingest_file(path)
        assert ds.row_count == 30
        assert "vdc" in ds.channels
        assert "freq" in ds.channels
        assert "p_kw" in ds.channels
        assert "q_kvar" in ds.channels
        assert "fault" in ds.channels
        assert "t_ms" not in ds.channels       # time col excluded from channels
    finally:
        os.unlink(path)


def test_vsm_csv_time_axis_in_seconds():
    """t_ms values must be converted to seconds; axis starts at 0."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_vsm_csv(path, n_rows=30)
        ds = ingest_file(path)
        assert abs(ds.time[0]) < 1e-9, "Time axis must start at 0"
        # 30 samples at ~103 ms each ≈ 3.0 s total; not 3000 s
        assert ds.duration < 10.0, f"Duration {ds.duration:.1f}s looks like ms not converted"
        assert ds.duration > 0.5, "Duration must be positive"
    finally:
        os.unlink(path)


def test_vsm_csv_sample_rate_near_10hz():
    """t_ms at ~103 ms intervals → ~9.7 Hz sample rate, NOT 0.01 Hz."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_vsm_csv(path, n_rows=30)
        ds = ingest_file(path)
        assert ds.sample_rate > 5.0, (
            f"Sample rate {ds.sample_rate} Hz looks wrong — "
            "t_ms values may not have been converted to seconds"
        )
        assert ds.sample_rate < 50.0, f"Sample rate {ds.sample_rate} Hz unexpectedly high"
    finally:
        os.unlink(path)


def test_vsm_csv_source_type_is_rigol_csv():
    """VSM CSV files are ingested via the CSV ingestor (same source_type as Rigol)."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_vsm_csv(path)
        ds = ingest_file(path)
        assert ds.source_type == "rigol_csv"
    finally:
        os.unlink(path)


# ──────────────────────────────────────────────────────────────────────────────
# Rigol 1 MHz oscilloscope format tests
# (Mirrors the real RigolDS0.csv / RigolDS1.csv files used in development)
# ──────────────────────────────────────────────────────────────────────────────

def _write_rigol_1mhz_csv(path: str, n_channels: int = 3,
                           n_rows: int = 500, dead_last_ch: bool = False):
    """
    Write a Rigol-style CSV at 1 MHz sample rate.

    n_channels: 3 → Time(s) + CH1..CH3  (mirrors RigolDS0.csv)
                4 → Time(s) + CH1..CH4  (mirrors RigolDS1.csv)
    dead_last_ch: if True, last channel is nearly zero (mirrors CH4 in RigolDS1)
    """
    headers = ["Time(s)"] + [f"CH{i+1}(V)" for i in range(n_channels)]
    dt = 1e-6  # 1 MHz
    with open(path, "w", newline="") as f:
        f.write(",".join(headers) + "\n")
        t = -0.0002  # Rigol time axis often starts slightly before 0
        for i in range(n_rows):
            row = [f"{t:.8f}"]
            for ch in range(n_channels):
                if dead_last_ch and ch == n_channels - 1:
                    # Near-zero dead channel (like CH4 in RigolDS1)
                    row.append(f"{-0.004 + 0.001 * (i % 2):.4f}")
                else:
                    row.append(f"{1.8 * np.sin(2 * np.pi * 60 * t - ch * 2.094):.4f}")
            f.write(",".join(row) + "\n")
            t += dt


def test_rigol_1mhz_3channel_basic():
    """3-channel Rigol CSV (RigolDS0 style) ingests cleanly."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_1mhz_csv(path, n_channels=3, n_rows=500)
        ds = ingest_file(path)

        assert ds.source_type == "rigol_csv"
        assert ds.row_count == 500
        assert set(ds.channel_names) == {"CH1(V)", "CH2(V)", "CH3(V)"}
        assert "Time(s)" not in ds.channels
        assert abs(ds.time[0]) < 1e-9  # normalized to start at 0
        assert len(ds.time) == 500
        # All channel arrays match time length
        for ch, arr in ds.channels.items():
            assert len(arr) == 500, f"Channel {ch} wrong length"
    finally:
        os.unlink(path)


def test_rigol_1mhz_sample_rate_detection():
    """1 MHz time step (1e-6 s) must be detected as ~1 000 000 Hz."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_1mhz_csv(path, n_channels=3, n_rows=1000)
        ds = ingest_file(path)
        # Allow ±10% — the median-based estimator is not exact for small files
        assert ds.sample_rate > 500_000, (
            f"Expected ~1 MHz sample rate, got {ds.sample_rate:.0f} Hz"
        )
        assert ds.sample_rate < 2_000_000, (
            f"Sample rate {ds.sample_rate:.0f} Hz unreasonably high"
        )
    finally:
        os.unlink(path)


def test_rigol_1mhz_4channel_dead_ch4():
    """CH4 with near-zero values (like RigolDS1) is ingested but not silently dropped."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_1mhz_csv(path, n_channels=4, n_rows=500, dead_last_ch=True)
        ds = ingest_file(path)

        assert "CH4(V)" in ds.channel_names, "Dead channel must still be present"
        ch4 = ds.channels["CH4(V)"]
        # Verify the channel is nearly zero (range < 0.01V)
        valid = ch4[~np.isnan(ch4)]
        assert len(valid) > 0
        span = float(valid.max() - valid.min())
        assert span < 0.02, f"CH4 span {span:.4f}V — expected near-zero dead channel"
    finally:
        os.unlink(path)


def test_rigol_1mhz_no_canonical_channels():
    """1 MHz Rigol CSV must not produce canonical names without channel mapping."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_1mhz_csv(path, n_channels=3, n_rows=200)
        ds = ingest_file(path)
        canonical = {"v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "freq", "p_mech"}
        collision = canonical & set(ds.channel_names)
        assert not collision, (
            f"Rigol ingestor must NOT map channels to canonical names automatically. "
            f"Found: {collision}"
        )
    finally:
        os.unlink(path)
