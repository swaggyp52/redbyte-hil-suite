"""
End-to-end tests for the evidence pipeline:
event detection, comparison, compliance profiles, report export.
"""
import json
import math
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest


# --------------------------------------------------------------------------
# Synthetic data helpers
# --------------------------------------------------------------------------
def _make_session(duration_s=2.0, fs=200.0, sag_start=None, sag_end=None,
                  sag_ratio=0.5, v_rms=120.0, freq=60.0, thd_inject=0.0,
                  imbalance=(1.0, 1.0, 1.0)):
    """Make a synthetic Data Capsule with optional sag / THD / imbalance."""
    n = int(duration_s * fs)
    t = np.arange(n) / fs
    peak = v_rms * math.sqrt(2)
    omega = 2 * math.pi * freq

    scale = np.ones(n)
    if sag_start is not None and sag_end is not None:
        mask = (t >= sag_start) & (t <= sag_end)
        scale[mask] = sag_ratio

    v_an = peak * imbalance[0] * scale * np.sin(omega * t)
    v_bn = peak * imbalance[1] * scale * np.sin(omega * t - 2 * math.pi / 3)
    v_cn = peak * imbalance[2] * scale * np.sin(omega * t + 2 * math.pi / 3)

    if thd_inject > 0:
        # Add a 5th harmonic of the given magnitude ratio
        v_an = v_an + peak * thd_inject * np.sin(5 * omega * t)

    i_a = 5 * np.sin(omega * t)
    i_b = 5 * np.sin(omega * t - 2 * math.pi / 3)
    i_c = 5 * np.sin(omega * t + 2 * math.pi / 3)
    freq_arr = np.full(n, freq)

    frames = []
    for k in range(n):
        frames.append({
            "ts": float(t[k]),
            "v_an": float(v_an[k]), "v_bn": float(v_bn[k]), "v_cn": float(v_cn[k]),
            "i_a": float(i_a[k]),  "i_b": float(i_b[k]),  "i_c": float(i_c[k]),
            "freq": float(freq_arr[k]),
            "p_mech": 1000.0,
            "status": 0,
        })

    return {
        "meta": {"session_id": "synthetic", "frame_count": n, "duration_s": duration_s},
        "events": [],
        "frames": frames,
    }


# --------------------------------------------------------------------------
# Event detection
# --------------------------------------------------------------------------
def test_event_detector_finds_sag():
    from src.event_detector import detect_events
    session = _make_session(duration_s=2.0, fs=500.0, sag_start=0.5, sag_end=1.0, sag_ratio=0.3)
    events = detect_events(session)
    types = [e["type"] for e in events]
    assert any("voltage_sag_start" in t for t in types)
    assert any("voltage_sag_end" in t for t in types)


def test_run_summary_basic_shape():
    from src.event_detector import run_summary
    s = run_summary(_make_session(duration_s=1.0, fs=200.0))
    assert s["frames"] > 0
    assert "thd_van_pct" in s
    assert "v_rms_per_phase" in s
    assert set(s["v_rms_per_phase"].keys()) == {"a", "b", "c"}


# --------------------------------------------------------------------------
# Compliance profiles
# --------------------------------------------------------------------------
def test_nominal_session_passes_project_profile():
    from src.compliance_checker import evaluate_session
    session = _make_session(duration_s=1.0, fs=500.0)
    results = evaluate_session(session, profile="project_demo")
    assert all(r["passed"] for r in results), \
        "Nominal session should pass project_demo profile: " + \
        str([(r["name"], r["details"]) for r in results if not r["passed"]])


def test_severe_sag_fails_ride_through():
    from src.compliance_checker import evaluate_session
    session = _make_session(duration_s=1.0, fs=500.0,
                            sag_start=0.3, sag_end=0.6, sag_ratio=0.1)
    results = evaluate_session(session, profile="ieee_2800_inspired")
    ride = next(r for r in results if "Ride-through" in r["name"])
    assert not ride["passed"]
    assert "inspired subset" in ride["source"].lower() or "IEEE 2800" in ride["source"]


def test_thd_exceedance_fails_519_profile():
    from src.compliance_checker import evaluate_session
    # Large 5th-harmonic injection
    session = _make_session(duration_s=1.0, fs=1000.0, thd_inject=0.20)
    results = evaluate_session(session, profile="ieee_519_thd")
    thd_result = next(r for r in results if "THD" in r["name"])
    assert not thd_result["passed"]
    assert thd_result["measured"] > thd_result["threshold"]


def test_phase_imbalance_detected():
    from src.compliance_checker import evaluate_session
    # 20% higher amplitude on phase a only
    session = _make_session(duration_s=0.5, fs=500.0, imbalance=(1.2, 1.0, 1.0))
    results = evaluate_session(session, profile="project_demo")
    imb = next(r for r in results if "Imbalance" in r["name"])
    assert not imb["passed"]


def test_legacy_evaluate_ieee_2800_returns_shape():
    from src.compliance_checker import evaluate_ieee_2800
    session = _make_session(duration_s=0.5, fs=400.0)
    results = evaluate_ieee_2800(session)
    for r in results:
        assert "name" in r and "passed" in r and "details" in r


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------
def test_comparison_identical_sessions_have_zero_delta():
    from src.analysis import AnalysisEngine
    s = _make_session(duration_s=0.5, fs=400.0)
    c = AnalysisEngine.compare_sessions(s, s, signal_key="v_an")
    assert c["rmse"] == pytest.approx(0.0, abs=1e-6)
    assert c["max_delta"] == pytest.approx(0.0, abs=1e-6)


def test_scorecard_detects_improvement():
    from src.analysis import AnalysisEngine
    # Ref has large sag, Test has small sag — Test should be rated better
    ref = _make_session(duration_s=1.0, fs=500.0,
                        sag_start=0.3, sag_end=0.6, sag_ratio=0.2)
    test = _make_session(duration_s=1.0, fs=500.0,
                         sag_start=0.3, sag_end=0.6, sag_ratio=0.85)
    sc = AnalysisEngine.comparison_scorecard(ref, test)
    assert "Test run performed better" in sc["verdict"] or sc["improvements"] >= sc["regressions"]


def test_scorecard_to_csv(tmp_path):
    from src.analysis import AnalysisEngine
    ref = _make_session(duration_s=0.4, fs=400.0)
    test = _make_session(duration_s=0.4, fs=400.0, sag_start=0.1, sag_end=0.2, sag_ratio=0.5)
    sc = AnalysisEngine.comparison_scorecard(ref, test)
    out = AnalysisEngine.scorecard_to_csv(sc, str(tmp_path / "cmp.csv"))
    assert os.path.exists(out)
    content = Path(out).read_text(encoding="utf-8")
    assert "metric,ref,test,delta" in content
    assert "verdict" in content


# --------------------------------------------------------------------------
# Evidence report
# --------------------------------------------------------------------------
def test_evidence_package_writes_all_artifacts(tmp_path):
    from src.report_generator import generate_evidence_package

    session = _make_session(duration_s=0.8, fs=400.0,
                            sag_start=0.2, sag_end=0.5, sag_ratio=0.6)
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps(session))

    out = generate_evidence_package(
        session_path=str(session_path),
        output_dir=str(tmp_path / "out"),
        profile="project_demo",
    )

    for key in ("html", "plot", "csv", "capsule_json",
                "compliance_json", "events_json", "summary_json"):
        assert os.path.exists(out[key]), f"missing artifact: {key}"

    html = Path(out["html"]).read_text(encoding="utf-8")
    # honesty framing present
    assert "not" in html.lower() and "certif" in html.lower()


def test_evidence_package_with_comparison(tmp_path):
    from src.report_generator import generate_evidence_package

    ref = _make_session(duration_s=0.8, fs=400.0)
    test = _make_session(duration_s=0.8, fs=400.0,
                         sag_start=0.2, sag_end=0.4, sag_ratio=0.4)
    ref_path = tmp_path / "ref.json"
    test_path = tmp_path / "test.json"
    ref_path.write_text(json.dumps(ref))
    test_path.write_text(json.dumps(test))

    out = generate_evidence_package(
        session_path=str(test_path),
        output_dir=str(tmp_path / "out"),
        compare_path=str(ref_path),
    )
    assert "comparison_csv" in out
    assert os.path.exists(out["comparison_csv"])

    html = Path(out["html"]).read_text(encoding="utf-8")
    assert "Run Comparison" in html
