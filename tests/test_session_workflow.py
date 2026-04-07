"""
Integration tests for the imported-dataset → active-session workflow.

Validates the complete data pipeline from file ingestion through channel
mapping and session conversion to the ActiveSession descriptor that powers
the UI.  No Qt required — all tests run against the Python backend.

Covers:
  - End-to-end: ingest → map → dataset_to_session → ActiveSession
  - ActiveSession correctly reflects channel mapping results
  - Warnings propagate from ingest to ActiveSession
  - Unmapped channels stay unmapped (no fabrication)
  - Partial datasets (only a subset of canonical channels) remain partial
  - Session bar data methods receive correct arguments
  - ActiveSession from a saved (plain) capsule works for reloaded sessions
"""

import json
import os
import tempfile

import numpy as np
import pytest

from src.channel_mapping import UNMAPPED, ChannelMapper, auto_suggest_mapping
from src.dataset_converter import dataset_to_session
from src.file_ingestion import ImportedDataset, ingest_file
from src.session_state import ActiveSession


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_dataset(n: int, channels: dict | None = None,
                  sample_rate: float = 1000.0) -> ImportedDataset:
    t = np.linspace(0, float(n - 1) / sample_rate, n)
    if channels is None:
        channels = {"CH1(V)": np.sin(2 * np.pi * 60 * t)}
    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/fake/RigolDS0.csv",
        channels=channels,
        time=t,
        sample_rate=sample_rate,
        duration=float(t[-1] - t[0]) if len(t) > 1 else 0.0,
        warnings=[],
        raw_headers=list(channels.keys()),
    )


def _write_rigol_csv(path: str, n_rows: int = 200):
    with open(path, "w") as f:
        f.write("Time(s),CH1(V),CH2(V)\n")
        t = 0.0
        for _ in range(n_rows):
            f.write(f"{t:.6f},{np.sin(60 * t):.4f},{np.cos(60 * t):.4f}\n")
            t += 1e-4


# ──────────────────────────────────────────────────────────────────────────────
# End-to-end: ingest → map → convert → ActiveSession
# ──────────────────────────────────────────────────────────────────────────────

def test_e2e_rigol_ingest_to_active_session():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tf:
        path = tf.name
    try:
        _write_rigol_csv(path, n_rows=200)
        ds = ingest_file(path)

        # Map CH1(V) → v_an, leave CH2(V) unmapped
        mapping = auto_suggest_mapping(ds.raw_headers)
        mapping["CH1(V)"] = "v_an"
        # CH2(V) stays UNMAPPED (auto_suggest leaves it that way)
        assert mapping.get("CH2(V)") == UNMAPPED

        mapper = ChannelMapper()
        ds_mapped = mapper.apply(ds, mapping)
        capsule = dataset_to_session(ds_mapped, session_id="rigol_test")

        session = ActiveSession.from_capsule(capsule, label="rigol_test")

        assert session.source_type == "rigol_csv"
        assert session.label == "rigol_test"
        assert session.row_count > 0
        assert session.is_imported is True
        assert "v_an" in session.mapped_channels
        assert "CH2(V)" in session.unmapped_channels
    finally:
        os.unlink(path)


def test_e2e_session_metadata_matches_dataset():
    """Session sample rate and duration track the underlying dataset."""
    ds = _make_dataset(1000, sample_rate=10_000.0)
    mapping = {"CH1(V)": "v_an"}
    mapper = ChannelMapper()
    ds_mapped = mapper.apply(ds, mapping)
    capsule = dataset_to_session(ds_mapped, session_id="rate_test")

    session = ActiveSession.from_capsule(capsule)

    # Sample rate is preserved from the original dataset
    assert session.sample_rate == pytest.approx(10_000.0, rel=0.01)
    # Duration is reasonable (0.099s for 1000 rows at 10kHz)
    assert session.duration > 0.0


def test_e2e_warnings_propagate_to_active_session():
    """Warnings from ingestion/mapping appear on the ActiveSession."""
    # Build a dataset with warnings already attached
    n = 50
    t = np.linspace(0, 0.049, n)
    arr_with_nan = np.ones(n)
    arr_with_nan[10] = np.nan

    ds = ImportedDataset(
        source_type="rigol_csv",
        source_path="/fake/warn.csv",
        channels={"CH1(V)": arr_with_nan},
        time=t,
        sample_rate=1000.0,
        duration=0.049,
        warnings=["Channel 'CH1(V)': 1 NaN value (Rigol fill row)."],
        raw_headers=["CH1(V)"],
    )

    mapper = ChannelMapper()
    ds_mapped = mapper.apply(ds, {"CH1(V)": "v_an"})
    capsule = dataset_to_session(ds_mapped)

    session = ActiveSession.from_capsule(capsule)

    assert session.has_warnings
    assert any("NaN" in w or "nan" in w.lower() for w in session.warnings)


# ──────────────────────────────────────────────────────────────────────────────
# Channel mapping honesty
# ──────────────────────────────────────────────────────────────────────────────

def test_rigol_channels_are_unmapped_without_explicit_assignment():
    """CH1–CH4 must never silently appear as canonical phase names."""
    ds = _make_dataset(50, channels={
        "CH1(V)": np.ones(50),
        "CH2(V)": np.ones(50) * -0.5,
        "CH3(V)": np.zeros(50),
    })
    mapping = auto_suggest_mapping(ds.raw_headers)
    # All three must be UNMAPPED
    for ch in ("CH1(V)", "CH2(V)", "CH3(V)"):
        assert mapping[ch] == UNMAPPED, f"{ch} should be UNMAPPED, got {mapping[ch]}"


def test_partial_dataset_session_is_partial():
    """
    A dataset with only one channel must produce a session with only that
    channel — not filled with zeros for missing canonical names.
    """
    ds = _make_dataset(100, channels={"v_an": np.ones(100)})
    capsule = dataset_to_session(ds)
    session = ActiveSession.from_capsule(capsule)

    # Only v_an should be present
    assert "v_an" in session.mapped_channels
    # v_bn, v_cn must not have been fabricated
    frame_keys = set(capsule["frames"][0].keys()) - {"ts"}
    assert "v_bn" not in frame_keys, "v_bn was fabricated in frames"
    assert "v_cn" not in frame_keys, "v_cn was fabricated in frames"
    assert "p_mech" not in frame_keys, "p_mech was fabricated in frames"


def test_unmapped_channels_stay_under_original_names():
    """Channels left as UNMAPPED keep original names in frames."""
    ds = _make_dataset(50, channels={
        "CH1(V)": np.ones(50),
        "CH2(V)": np.ones(50) * 2,
    })
    mapper = ChannelMapper()
    mapping = {"CH1(V)": "v_an", "CH2(V)": UNMAPPED}
    ds_mapped = mapper.apply(ds, mapping)
    capsule = dataset_to_session(ds_mapped)
    session = ActiveSession.from_capsule(capsule)

    frame_keys = set(capsule["frames"][0].keys()) - {"ts"}
    assert "CH2(V)" in frame_keys, "Unmapped channel should appear under original name"
    assert "v_an" in frame_keys
    assert "CH2(V)" in session.unmapped_channels


# ──────────────────────────────────────────────────────────────────────────────
# ActiveSession from reloaded (plain) capsule
# ──────────────────────────────────────────────────────────────────────────────

def test_saved_and_reloaded_session_creates_valid_active_session():
    """Round-trip: save capsule to disk, reload, create ActiveSession."""
    ds = _make_dataset(100, channels={"v_an": np.sin(np.linspace(0, 2 * np.pi, 100))})
    capsule = dataset_to_session(ds, session_id="round_trip")

    with tempfile.TemporaryDirectory() as tmpdir:
        from src.dataset_converter import save_session, load_session
        path = save_session(capsule, out_dir=tmpdir)
        loaded = load_session(path)

    session = ActiveSession.from_capsule(loaded, label="round_trip")
    assert session.label == "round_trip"
    assert session.row_count > 0
    assert session.duration >= 0.0


def test_active_session_from_plain_capsule_is_not_imported():
    """Plain saved capsule (no import_meta) marks is_imported=False."""
    ds = _make_dataset(50)
    capsule = dataset_to_session(ds, session_id="live_session")
    # Strip import_meta to simulate a capsule saved from live recording
    capsule.pop("import_meta", None)

    session = ActiveSession.from_capsule(capsule)
    assert session.is_imported is False


# ──────────────────────────────────────────────────────────────────────────────
# Summary bar data correctness (non-Qt: verify the values that would be shown)
# ──────────────────────────────────────────────────────────────────────────────

def test_summary_bar_data_source_type_display():
    ds = _make_dataset(100)
    capsule = dataset_to_session(ds)
    session = ActiveSession.from_capsule(capsule)
    # For a rigol_csv session the display name should be recognizable
    assert "Rigol" in session.source_type_display or "CSV" in session.source_type_display


def test_summary_bar_data_duration_formatted():
    ds = _make_dataset(1000, sample_rate=1000.0)  # 0.999s
    capsule = dataset_to_session(ds)
    session = ActiveSession.from_capsule(capsule)
    # Duration should mention 's'
    assert "s" in session.duration_display


def test_summary_bar_data_sample_rate_formatted():
    ds = _make_dataset(100, sample_rate=10_000.0)
    capsule = dataset_to_session(ds)
    session = ActiveSession.from_capsule(capsule)
    display = session.sample_rate_display
    assert "Hz" in display
    assert "—" not in display  # should not show unknown


def test_session_channel_count_correct():
    ds = _make_dataset(50, channels={
        "v_an": np.ones(50),
        "v_bn": np.ones(50),
        "v_cn": np.ones(50),
    })
    mapper = ChannelMapper()
    mapping = {"v_an": "v_an", "v_bn": "v_bn", "v_cn": UNMAPPED}
    ds_mapped = mapper.apply(ds, mapping)
    capsule = dataset_to_session(ds_mapped)
    session = ActiveSession.from_capsule(capsule)
    assert session.channel_count == 3
