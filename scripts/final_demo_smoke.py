"""
final_demo_smoke.py — headless pre-presentation smoke test.

Verifies the core demo workflow without a GUI or committed raw data files.
Run before the presentation to confirm nothing is broken:

    python scripts/final_demo_smoke.py

Checks:
  1. DS0-like 3-phase dataset: metrics (RMS, THD, frequency), derived v_ab/v_bc/v_ca.
  2. InverterPower-like dataset: p_mech generic stats, step-change event detection.
  3. VSGFrequency truth: Pinv-only file has no freq column.
  4. Evidence export: 7 mandatory artifacts (no compliance) + 8 with compliance.
  5. Compliance applicability: 3-phase dataset gets applicable checks; power-only
     gets all-N/A.

Exit code 0 = all passed. Exit code 1 = one or more failures.
"""

from __future__ import annotations

import csv
import math
import os
import sys
import tempfile
import traceback
from pathlib import Path

# Ensure project root is on path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

# Force UTF-8 stdout so Unicode in compliance labels renders on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

PASS_MARK = "[PASS]"
FAIL_MARK = "[FAIL]"

_failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"{PASS_MARK} {label}")
    else:
        msg = f"{label}{': ' + detail if detail else ''}"
        print(f"{FAIL_MARK} {msg}")
        _failures.append(msg)


# ─── Dataset builders ────────────────────────────────────────────────────────

def _make_three_phase_dataset(rows: int = 2000, v_rms: float = 120.0, fs: float = 10_000.0):
    """Return ImportedDataset with canonical channel names (post-mapping, post-scale)."""
    from src.file_ingestion import ImportedDataset
    t = np.arange(rows) / fs
    peak = v_rms * math.sqrt(2)
    omega = 2 * math.pi * 60
    channels = {
        "v_an": peak * np.sin(omega * t),
        "v_bn": peak * np.sin(omega * t - 2 * math.pi / 3),
        "v_cn": peak * np.sin(omega * t + 2 * math.pi / 3),
    }
    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/smoke/DS0_synthetic.csv",
        channels=channels,
        time=t,
        sample_rate=fs,
        duration=float(t[-1] - t[0]),
        raw_headers=["Time(s)", "CH1(V)", "CH2(V)", "CH3(V)"],
        meta={
            "applied_mapping": {"CH1(V)": "v_an", "CH2(V)": "v_bn", "CH3(V)": "v_cn"},
            "scale_factors": {"v_an": 100.0, "v_bn": 100.0, "v_cn": 100.0},
            "row_count": rows,
        },
    )


def _make_power_dataset(rows: int = 500, fs: float = 20_000.0):
    """Return ImportedDataset with p_mech only (simulates InverterPower)."""
    from src.file_ingestion import ImportedDataset
    t = np.arange(rows) / fs
    p = 200.0 + 50.0 * np.sin(2 * math.pi * 2 * t)
    # Inject a step at row 200
    p[200:220] = 450.0
    channels = {"p_mech": p}
    return ImportedDataset(
        source_type="simulation_excel",
        source_path="/smoke/InverterPower_synthetic.xlsx",
        channels=channels,
        time=t,
        sample_rate=fs,
        duration=float(t[-1] - t[0]),
        raw_headers=["time", "Pinv"],
        meta={
            "applied_mapping": {"Pinv": "p_mech"},
            "scale_factors": {},
            "row_count": rows,
        },
    )


def _write_rigol_csv(path: str, rows: int = 200) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Time(s)", "CH1(V)", "CH2(V)", "CH3(V)"])
        dt = 1.0 / 10_000_000
        omega = 2 * math.pi * 60
        peak = 1.2
        for i in range(rows):
            t = i * dt
            w.writerow([
                f"{t:.9f}",
                f"{peak * math.sin(omega * t):.6f}",
                f"{peak * math.sin(omega * t - 2*math.pi/3):.6f}",
                f"{peak * math.sin(omega * t + 2*math.pi/3):.6f}",
            ])


def _write_power_xlsx(path: str, rows: int = 200) -> None:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["time", "Pinv"])
    dt = 1.0 / 20_000
    for i in range(rows):
        ws.append([i * dt, 200.0 + 50.0 * math.sin(2 * math.pi * 2 * i * dt)])
    wb.save(path)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: DS0-like 3-phase metrics and derived channels
# ─────────────────────────────────────────────────────────────────────────────
def test_ds0_metrics() -> None:
    print("\n--- Test 1: DS0-like 3-phase metrics ---")
    from src.dataset_converter import dataset_to_session
    from src.session_analysis import compute_session_metrics

    ds = _make_three_phase_dataset(rows=2000)
    capsule = dataset_to_session(ds, session_id="DS0_smoke")

    frames = capsule.get("frames", [])
    _check("DS0 capsule: has frames", len(frames) > 0, f"got {len(frames)}")

    first = frames[0] if frames else {}
    _check("DS0 capsule: v_an in frame", "v_an" in first)
    # derive_dataset_channels should have added v_ab
    _check("DS0 capsule: v_ab derived (present in frame)", "v_ab" in first)

    metrics = compute_session_metrics(capsule, events=[])
    pv = metrics["phase_voltage"]
    _check("DS0 metrics: v_an available", pv["v_an"]["available"])
    rms = pv["v_an"]["rms"]
    _check("DS0 metrics: v_an RMS ~ 120 V", 80.0 < rms < 160.0, f"got {rms:.1f} V")
    _check("DS0 metrics: v_bn available", pv["v_bn"]["available"])
    _check("DS0 metrics: THD present in v_an", "thd_pct" in pv["v_an"])

    lv = metrics["line_voltage"]
    _check("DS0 metrics: v_ab RMS available", lv["v_ab"]["available"])
    v_ab_rms = lv["v_ab"]["rms"]
    # line-to-line should be ~√3 × phase RMS ≈ 208 V
    _check("DS0 metrics: v_ab RMS ~ 208 V", 140.0 < v_ab_rms < 280.0, f"got {v_ab_rms:.1f} V")

    _check("DS0 metrics: frequency estimated",
           metrics["frequency"]["available"],
           str(metrics["frequency"]))


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: InverterPower-like generic data
# ─────────────────────────────────────────────────────────────────────────────
def test_inverterpower_pipeline() -> None:
    print("\n--- Test 2: InverterPower-like power pipeline ---")
    from src.dataset_converter import dataset_to_session
    from src.session_analysis import compute_session_metrics
    from src.event_detector import detect_events

    ds = _make_power_dataset(rows=500)
    capsule = dataset_to_session(ds, session_id="InverterPower_smoke")

    frames = capsule.get("frames", [])
    _check("InverterPower capsule: has frames", len(frames) > 0)
    _check("InverterPower capsule: p_mech in frame",
           "p_mech" in (frames[0] if frames else {}))

    metrics = compute_session_metrics(capsule, events=[])
    gen = metrics.get("generic_numeric", {})
    _check("InverterPower metrics: p_mech generic channel",
           "p_mech" in gen, f"keys: {list(gen.keys())}")
    _check("InverterPower metrics: phase_voltage empty (no v_an)",
           not metrics["phase_voltage"]["v_an"]["available"])

    # detect_events on ImportedDataset uses the full detector (step_change, clipping, etc.)
    # detect_events on a capsule dict uses the legacy voltage-sag-only path
    events = detect_events(ds)
    _check("InverterPower events: at least one event detected",
           len(events) > 0, f"got {len(events)}")
    kinds = {e.kind for e in events}
    _check("InverterPower events: step_change detected",
           "step_change" in kinds, f"kinds: {kinds}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: VSGFrequency truth — file-based check
# ─────────────────────────────────────────────────────────────────────────────
def test_vsgfrequency_truth() -> None:
    print("\n--- Test 3: VSGFrequency truth (file-based) ---")
    from src.file_ingestion import ingest_file

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        tmp = f.name
    try:
        _write_power_xlsx(tmp, rows=100)
        ds = ingest_file(tmp)
        channel_names = list(ds.channels.keys())
        _check("VSGFrequency: no 'freq' channel when file has only time + Pinv",
               "freq" not in channel_names and "frequency" not in channel_names,
               f"channels: {channel_names}")
        _check("VSGFrequency: Pinv is in channels",
               "Pinv" in channel_names,
               f"channels: {channel_names}")
        _check("VSGFrequency: source_type is simulation_excel",
               ds.source_type == "simulation_excel",
               f"got {ds.source_type}")
    finally:
        os.unlink(tmp)


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Evidence export artifacts
# ─────────────────────────────────────────────────────────────────────────────
def test_evidence_export() -> None:
    print("\n--- Test 4: Evidence export artifacts ---")
    from src.dataset_converter import dataset_to_session
    from src.session_exporter import quick_export
    from src.event_detector import detect_events

    ds = _make_three_phase_dataset(rows=2000)
    capsule = dataset_to_session(ds, session_id="DS0_export_smoke")
    events = detect_events(capsule)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Export without compliance — expect 7 artifacts
        result = quick_export(capsule, events=events, compliance_results=None,
                              base_dir=tmp_dir)
        n = len(result["artifacts"])
        _check("Export (no compliance): 7 mandatory artifacts",
               n == 7, f"got {n}: {[a['name'] for a in result['artifacts']]}")

        names = {a["name"] for a in result["artifacts"]}
        for expected in ("HTML Report", "Phase Voltage PNG",
                         "Line-to-Line Voltage PNG", "Metrics JSON",
                         "Events JSON", "Metadata JSON", "Preview CSV"):
            _check(f"Export artifact present: {expected}", expected in names)

        _check("Export: Compliance JSON absent when not run",
               "Compliance JSON" not in names)

        for a in result["artifacts"]:
            _check(f"Export artifact non-empty: {a['name']}",
                   a["size_bytes"] > 0,
                   f"size={a['size_bytes']}")

        # Export WITH compliance — expect 8 artifacts
        from src.compliance_checker import evaluate_session
        compliance = evaluate_session(capsule, profile="ieee_2800_inspired")
        result2 = quick_export(capsule, events=events, compliance_results=compliance,
                               base_dir=tmp_dir)
        n2 = len(result2["artifacts"])
        _check("Export (with compliance): 8 artifacts", n2 == 8, f"got {n2}")
        names2 = {a["name"] for a in result2["artifacts"]}
        _check("Export: Compliance JSON present when compliance provided",
               "Compliance JSON" in names2)


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Compliance applicability
# ─────────────────────────────────────────────────────────────────────────────
def test_compliance_applicability() -> None:
    print("\n--- Test 5: Compliance applicability ---")
    from src.dataset_converter import dataset_to_session
    from src.compliance_checker import evaluate_session

    # 3-phase: should get applicable checks
    ds3 = _make_three_phase_dataset(rows=2000)
    cap3 = dataset_to_session(ds3, session_id="DS0_compliance_smoke")
    r3 = evaluate_session(cap3, profile="ieee_2800_inspired")
    statuses3 = [r["status"] for r in r3]
    applicable3 = [s for s in statuses3 if s in ("PASS", "FAIL")]
    na3 = [s for s in statuses3 if s == "N/A"]
    _check("DS0 compliance: >=4 applicable checks",
           len(applicable3) >= 4, f"got {len(applicable3)}")
    _check("DS0 compliance: >=1 N/A check (ride-through / recovery)",
           len(na3) >= 1, f"got {len(na3)}")

    # Power-only: all N/A
    dsp = _make_power_dataset(rows=500)
    capp = dataset_to_session(dsp, session_id="InverterPower_compliance_smoke")
    rp = evaluate_session(capp, profile="ieee_2800_inspired")
    all_na = all(r["status"] == "N/A" for r in rp)
    _check("InverterPower compliance: all checks N/A (no voltage/freq)",
           all_na, f"statuses: {[r['status'] for r in rp]}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 60)
    print("VSM Evidence Workbench — Final Demo Smoke Test")
    print("=" * 60)

    for fn in [
        test_ds0_metrics,
        test_inverterpower_pipeline,
        test_vsgfrequency_truth,
        test_evidence_export,
        test_compliance_applicability,
    ]:
        try:
            fn()
        except Exception as exc:
            name = fn.__name__
            msg = f"{name} raised unexpected exception: {exc}"
            print(f"{FAIL_MARK} {msg}")
            traceback.print_exc()
            _failures.append(msg)

    print("\n" + "=" * 60)
    if _failures:
        print(f"RESULT: {len(_failures)} failure(s):")
        for f in _failures:
            print(f"  {FAIL_MARK} {f}")
        print("=" * 60)
        return 1

    print("RESULT: All checks passed — app is ready to demo.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
