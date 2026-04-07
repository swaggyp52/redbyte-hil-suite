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
