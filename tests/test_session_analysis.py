import json
import math

import numpy as np

from src.compliance_checker import evaluate_session
from src.dataset_converter import dataset_to_session
from src.derived_channels import compute_line_to_line_channels
from src.file_ingestion import ImportedDataset
from src.report_generator import generate_evidence_package
from src.session_analysis import build_dataset_overview, compute_session_metrics


def _three_phase_dataset(include_current: bool = False) -> ImportedDataset:
    sample_rate = 1000.0
    n = 1200
    time = np.arange(n, dtype=np.float64) / sample_rate
    peak = 120.0 * math.sqrt(2.0)
    omega = 2.0 * math.pi * 60.0

    channels = {
        "v_an": peak * np.sin(omega * time),
        "v_bn": peak * np.sin(omega * time - 2.0 * math.pi / 3.0),
        "v_cn": peak * np.sin(omega * time + 2.0 * math.pi / 3.0),
    }
    if include_current:
        channels.update(
            {
                "i_a": 5.0 * np.sin(omega * time),
                "i_b": 5.0 * np.sin(omega * time - 2.0 * math.pi / 3.0),
                "i_c": 5.0 * np.sin(omega * time + 2.0 * math.pi / 3.0),
            }
        )

    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/fake/three_phase.csv",
        channels=channels,
        time=time,
        sample_rate=sample_rate,
        duration=float(time[-1] - time[0]),
        raw_headers=list(channels.keys()),
    )


def _generic_dataset(n: int = 600) -> ImportedDataset:
    sample_rate = 100.0
    time = np.arange(n, dtype=np.float64) / sample_rate
    channels = {
        "signal_a": np.linspace(0.0, 5.0, n, dtype=np.float64),
        "signal_b": np.cos(2.0 * math.pi * 1.5 * time),
    }
    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/fake/generic.csv",
        channels=channels,
        time=time,
        sample_rate=sample_rate,
        duration=float(time[-1] - time[0]),
        raw_headers=["time", *channels.keys()],
        meta={"time_column": "time"},
    )


def _p_mech_only_dataset(n: int = 600) -> ImportedDataset:
    sample_rate = 2000.0
    time = np.arange(n, dtype=np.float64) / sample_rate
    channels = {
        "p_mech": 100.0 + 15.0 * np.sin(2.0 * math.pi * 4.0 * time),
    }
    return ImportedDataset(
        source_type="simulation_excel",
        source_path="/fake/p_mech_only.xlsx",
        channels=channels,
        time=time,
        sample_rate=sample_rate,
        duration=float(time[-1] - time[0]),
        raw_headers=["Pinv"],
        meta={"scale_factors": {"p_mech": 1.0}},
    )


def test_compute_line_to_line_channels_matches_phase_differences():
    dataset = _three_phase_dataset()
    derived = compute_line_to_line_channels(dataset.channels)

    assert np.allclose(derived["v_ab"], dataset.channels["v_an"] - dataset.channels["v_bn"])
    assert np.allclose(derived["v_bc"], dataset.channels["v_bn"] - dataset.channels["v_cn"])
    assert np.allclose(derived["v_ca"], dataset.channels["v_cn"] - dataset.channels["v_an"])


def test_session_metrics_include_line_to_line_values():
    capsule = dataset_to_session(_three_phase_dataset())
    summary = compute_session_metrics(capsule)

    assert summary["line_voltage"]["v_ab"]["available"] is True
    assert summary["line_voltage"]["v_bc"]["available"] is True
    assert summary["line_voltage"]["v_ca"]["available"] is True
    assert "v_ab" in summary["session"]["derived_channels"]
    assert summary["current_thresholds"]["available"] is False


def test_voltage_only_compliance_marks_missing_current_checks_na():
    capsule = dataset_to_session(_three_phase_dataset(include_current=False))
    results = evaluate_session(capsule, profile="ieee_2800_inspired")
    by_name = {row["name"]: row for row in results}

    assert by_name["Overcurrent"]["status"] == "N/A"
    assert by_name["Fault ride-through"]["status"] == "N/A"
    assert by_name["THD"]["status"] in {"PASS", "FAIL"}


def test_evidence_package_exports_line_to_line_metrics_and_metadata(tmp_path):
    capsule = dataset_to_session(_three_phase_dataset())
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps(capsule), encoding="utf-8")

    artifacts = generate_evidence_package(
        session_path=str(session_path),
        output_dir=str(tmp_path / "evidence"),
        profile="ieee_2800_inspired",
    )

    metrics = json.loads((tmp_path / "evidence" / "metrics.json").read_text(encoding="utf-8"))
    compliance = json.loads((tmp_path / "evidence" / "compliance.json").read_text(encoding="utf-8"))
    metadata = json.loads((tmp_path / "evidence" / "metadata.json").read_text(encoding="utf-8"))

    assert metrics["line_voltage"]["v_ab"]["available"] is True
    assert metrics["line_voltage"]["v_bc"]["available"] is True
    assert metrics["line_voltage"]["v_ca"]["available"] is True
    assert "v_ab" in metadata["derived_channels"]
    assert "waveform_overview.png" in artifacts["plot"]
    assert any(
        {"name", "measured", "threshold", "units", "status"}.issubset(check)
        for check in compliance["checks"]
    )


def test_generic_dataset_metrics_are_available_without_canonical_channels():
    capsule = dataset_to_session(_generic_dataset())
    summary = compute_session_metrics(capsule)

    assert summary["session"]["analysis_mode"] == "generic"
    assert summary["session"]["generic_numeric_channels"] == ["signal_a", "signal_b"]
    assert summary["generic_numeric"]["signal_a"]["available"] is True
    assert summary["generic_numeric"]["signal_a"]["peak_to_peak"] == 5.0
    assert summary["phase_voltage"]["v_an"]["available"] is False


def test_generic_dataset_compliance_returns_na_instead_of_false_pass(tmp_path):
    capsule = dataset_to_session(_generic_dataset())
    results = evaluate_session(capsule, profile="ieee_2800_inspired")

    assert results
    assert all(row["status"] == "N/A" for row in results)
    assert any("required" in (row.get("na_reason") or "").lower() for row in results)


def test_p_mech_only_dataset_uses_generic_analysis_mode():
    capsule = dataset_to_session(_p_mech_only_dataset())
    summary = compute_session_metrics(capsule)

    assert summary["session"]["analysis_mode"] == "generic"
    assert summary["session"]["analysis_mode_label"] == "Generic data analysis mode"


def test_dataset_overview_exposes_scale_factors_for_ui_panel():
    capsule = dataset_to_session(_p_mech_only_dataset())
    overview = build_dataset_overview(capsule)

    assert overview["scale_factors"] == {"p_mech": 1.0}


def test_evidence_package_can_downsample_preview_csv(tmp_path):
    capsule = dataset_to_session(_generic_dataset(n=1200))
    session_path = tmp_path / "generic_session.json"
    session_path.write_text(json.dumps(capsule), encoding="utf-8")

    artifacts = generate_evidence_package(
        session_path=str(session_path),
        output_dir=str(tmp_path / "evidence"),
        preview_csv_max_rows=120,
    )

    metadata = json.loads((tmp_path / "evidence" / "metadata.json").read_text(encoding="utf-8"))
    csv_lines = [
        line
        for line in (tmp_path / "evidence" / "normalized_frames.csv").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]

    assert artifacts["csv"].endswith("normalized_frames.csv")
    assert metadata["normalized_csv"]["mode"] == "preview_downsampled"
    assert metadata["normalized_csv"]["rows_written"] <= 120
    assert "metrics computed on full-resolution data" in metadata["normalized_csv"]["note"]
    assert len(csv_lines) <= 121
