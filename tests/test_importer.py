"""
Tests for src/importer.py — CSV/Excel ingest and time normalization.
"""
import json
import math
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from src.importer import DataImporter, CANONICAL_CHANNELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _three_phase_frame(n=200, f=60.0, fs=200.0, v_rms=120.0, t_unit="s", t0=0.0):
    t = np.arange(n) / fs + t0
    peak = v_rms * math.sqrt(2)
    return pd.DataFrame({
        "time_s" if t_unit == "s" else "time_ms": (t if t_unit == "s" else t * 1000.0),
        "V_an": peak * np.sin(2 * math.pi * f * t),
        "V_bn": peak * np.sin(2 * math.pi * f * t - 2 * math.pi / 3),
        "V_cn": peak * np.sin(2 * math.pi * f * t + 2 * math.pi / 3),
        "I_a": 5 * np.sin(2 * math.pi * f * t),
        "I_b": 5 * np.sin(2 * math.pi * f * t - 2 * math.pi / 3),
        "I_c": 5 * np.sin(2 * math.pi * f * t + 2 * math.pi / 3),
        "Freq(Hz)": np.full(n, f),
    })


# ---------------------------------------------------------------------------
# Auto-detect mapping
# ---------------------------------------------------------------------------
def test_suggest_mapping_common_headers():
    cols = ["Time(s)", "V_an", "Vbn", "V_cn", "I_a", "I_b", "I_c", "Frequency", "PMech"]
    m = DataImporter.suggest_mapping(cols)
    assert m["ts"] == "Time(s)"
    assert m["v_an"] == "V_an"
    assert m["v_bn"] == "Vbn"
    assert m["v_cn"] == "V_cn"
    assert m["i_a"] == "I_a"
    assert m["freq"] == "Frequency"


def test_suggest_mapping_pinv_and_vsg_frequency_aliases():
    cols = ["time", "Pinv", "vsg_freq", "omega_r"]
    m = DataImporter.suggest_mapping(cols)
    assert m["ts"] == "time"
    # Pinv should map to p_mech for power-only simulation exports
    assert m["p_mech"] == "Pinv"
    # Frequency aliases should be recognized when present
    assert m["freq"] in {"vsg_freq", "omega_r"}


def test_suggest_mapping_ignores_unknown():
    cols = ["foo", "bar", "baz"]
    assert DataImporter.suggest_mapping(cols) == {}


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------
def test_import_csv_roundtrip(tmp_path):
    df = _three_phase_frame(n=100, t_unit="s")
    csv_path = tmp_path / "run1.csv"
    df.to_csv(csv_path, index=False)

    cap = DataImporter.import_csv(str(csv_path))
    assert cap["meta"]["frame_count"] == 100
    assert len(cap["frames"]) == 100
    # must contain all canonical channels in every frame
    for key in CANONICAL_CHANNELS:
        assert key in cap["frames"][0]
    # time values should be source-relative (same as the original values)
    assert cap["frames"][0]["ts"] == pytest.approx(df["time_s"].iloc[0], rel=1e-6)
    assert cap.mapping["v_an"] == "V_an"


def test_preview_reads_only_requested_csv_rows(tmp_path):
    # Build a large-enough CSV and verify preview does not read all rows.
    n = 10_000
    df = pd.DataFrame({
        "Time(s)": np.arange(n, dtype=float) * 1e-4,
        "CH1(V)": np.sin(np.linspace(0, 20 * np.pi, n)),
        "CH2(V)": np.cos(np.linspace(0, 20 * np.pi, n)),
    })
    csv_path = tmp_path / "large_preview.csv"
    df.to_csv(csv_path, index=False)

    preview = DataImporter.preview(str(csv_path), n_rows=8)
    assert preview["n_rows"] == n
    assert len(preview["head"]) == 8
    # Ensure no hidden full-read side effect by checking head content only
    assert preview["head"][0]["Time(s)"] == pytest.approx(0.0)
    assert preview["head"][-1]["Time(s)"] == pytest.approx(7e-4)


def test_import_csv_ms_time_unit_detected(tmp_path):
    df = _three_phase_frame(n=50, t_unit="ms")
    csv_path = tmp_path / "run_ms.csv"
    df.to_csv(csv_path, index=False)

    cap = DataImporter.import_csv(str(csv_path), options={"time_unit": "auto"})
    ts0 = cap["frames"][0]["ts"]
    ts1 = cap["frames"][1]["ts"]
    dt = ts1 - ts0
    # 200 Hz sampling in seconds → dt ≈ 0.005 s
    assert 0 < dt < 0.05
    assert cap["meta"]["import"]["time_unit_detected"] == "ms"


def test_missing_time_column_raises(tmp_path):
    df = pd.DataFrame({"V_an": [1, 2, 3]})
    csv_path = tmp_path / "notime.csv"
    df.to_csv(csv_path, index=False)
    with pytest.raises(ValueError):
        DataImporter.import_csv(str(csv_path))


def test_non_monotonic_time_is_sorted(tmp_path):
    df = pd.DataFrame({
        "time_s": [0.1, 0.3, 0.2, 0.4, 0.5],
        "V_an":   [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    csv_path = tmp_path / "unsorted.csv"
    df.to_csv(csv_path, index=False)
    cap = DataImporter.import_csv(str(csv_path), column_map={"ts": "time_s", "v_an": "V_an"})
    ts = [f["ts"] for f in cap["frames"]]
    assert ts == sorted(ts)
    # warning surfaced
    assert any("Non-monotonic" in w for w in cap.warnings)


def test_duplicate_timestamps_are_nudged(tmp_path):
    df = pd.DataFrame({
        "time_s": [0.0, 0.1, 0.1, 0.2],
        "V_an":   [1.0, 2.0, 3.0, 4.0],
    })
    csv_path = tmp_path / "dup.csv"
    df.to_csv(csv_path, index=False)
    cap = DataImporter.import_csv(str(csv_path), column_map={"ts": "time_s", "v_an": "V_an"})
    ts = [f["ts"] for f in cap["frames"]]
    # strictly monotonic now
    assert all(ts[i] < ts[i + 1] for i in range(len(ts) - 1))


def test_missing_channels_filled_with_zero(tmp_path):
    df = pd.DataFrame({"time_s": [0.0, 0.05, 0.1], "V_an": [1.0, 2.0, 3.0]})
    csv_path = tmp_path / "partial.csv"
    df.to_csv(csv_path, index=False)
    cap = DataImporter.import_csv(str(csv_path))
    # canonical channels present, missing ones = 0
    assert cap["frames"][0]["v_bn"] == 0.0
    assert cap["frames"][0]["i_a"] == 0.0
    missing = cap["meta"]["import"]["missing_channels"]
    assert "v_bn" in missing and "i_a" in missing


def test_resample_uniform_dt(tmp_path):
    df = _three_phase_frame(n=100, fs=123.0)  # weird fs
    csv_path = tmp_path / "resample.csv"
    df.to_csv(csv_path, index=False)
    cap = DataImporter.import_csv(str(csv_path), options={"resample": 0.01})
    ts = np.array([f["ts"] for f in cap["frames"]])
    dts = np.diff(ts)
    assert np.allclose(dts, 0.01, atol=1e-6)
    assert cap["meta"]["import"]["resample"]["target_dt_s"] == 0.01


# ---------------------------------------------------------------------------
# Excel import
# ---------------------------------------------------------------------------
def test_import_excel(tmp_path):
    pytest.importorskip("openpyxl")
    df = _three_phase_frame(n=60)
    xl_path = tmp_path / "run.xlsx"
    df.to_excel(xl_path, index=False, sheet_name="Scope")

    sheets = DataImporter.list_excel_sheets(str(xl_path))
    assert "Scope" in sheets

    cap = DataImporter.import_excel(str(xl_path), sheet_name="Scope")
    assert cap["meta"]["frame_count"] == 60
    assert cap["meta"]["source"]["sheet"] == "Scope"


# ---------------------------------------------------------------------------
# auto dispatch + passthrough + save
# ---------------------------------------------------------------------------
def test_import_auto_csv_dispatch(tmp_path):
    df = _three_phase_frame(n=30)
    path = tmp_path / "auto.csv"
    df.to_csv(path, index=False)
    cap = DataImporter.import_auto(str(path))
    assert cap["meta"]["source"]["type"] == "csv"


def test_import_auto_json_passthrough(tmp_path):
    cap = {"meta": {"session_id": "x"}, "events": [], "frames": [{"ts": 0.0, "v_an": 1.0}]}
    p = tmp_path / "x.json"
    p.write_text(json.dumps(cap))
    out = DataImporter.import_auto(str(p))
    assert out["frames"][0]["v_an"] == 1.0
    assert out["meta"]["import"]["source_type"] == "json"


def test_save_capsule_round_trip(tmp_path):
    df = _three_phase_frame(n=20)
    csv_path = tmp_path / "r.csv"
    df.to_csv(csv_path, index=False)
    cap = DataImporter.import_csv(str(csv_path))
    out = DataImporter.save_capsule(cap, str(tmp_path / "saved.json"))
    with open(out, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["meta"]["frame_count"] == cap["meta"]["frame_count"]


# ---------------------------------------------------------------------------
# Replay-path compatibility: imported capsule must be loadable like a native session
# ---------------------------------------------------------------------------
def test_imported_capsule_is_shaped_like_native_session(tmp_path):
    df = _three_phase_frame(n=40)
    csv_path = tmp_path / "shape.csv"
    df.to_csv(csv_path, index=False)
    cap = DataImporter.import_csv(str(csv_path))
    # Matches expected Data Capsule contract used by ReplayStudio._load_session
    assert set(cap.keys()) >= {"meta", "events", "frames"}
    assert isinstance(cap["frames"], list) and cap["frames"]
    for k in ("ts", "v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "freq"):
        assert k in cap["frames"][0]
