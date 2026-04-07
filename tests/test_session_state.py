"""
Tests for src/session_state.py

Validates:
  - ActiveSession.from_capsule() for imported files (with import_meta block)
  - ActiveSession.from_capsule() for plain saved sessions (no import_meta)
  - Channel classification: mapped vs unmapped
  - Warnings extraction
  - is_imported flag
  - Computed properties: has_warnings, channel_count, source_filename,
    source_type_display, duration_display, sample_rate_display, row_count_display
  - Label override
  - Duration fallback derivation from frame timestamps
"""

import time

import pytest

from src.session_state import ActiveSession


# ──────────────────────────────────────────────────────────────────────────────
# Fixture helpers
# ──────────────────────────────────────────────────────────────────────────────

def _import_capsule(
    n_frames: int = 100,
    source_type: str = "rigol_csv",
    source_path: str = "/fake/RigolDS0.csv",
    sample_rate: float = 1000.0,
    mapped: dict | None = None,
    unmapped: dict | None = None,
    warnings: list | None = None,
) -> dict:
    """Return a minimal imported Data Capsule dict (has import_meta block)."""
    if mapped is None:
        mapped = {"CH1(V)": "v_an", "CH2(V)": "v_bn"}
    if unmapped is None:
        unmapped = {"CH3(V)": "__unmapped__"}
    if warnings is None:
        warnings = []

    all_mapping = {**mapped, **unmapped}
    all_channels = sorted(
        [v for v in mapped.values()]
        + [k for k, v in unmapped.items() if v == "__unmapped__"]
    )

    duration = (n_frames - 1) * 0.001
    frames = [
        {"ts": round(i * 0.001, 6), "v_an": 1.0, "v_bn": -0.5}
        for i in range(n_frames)
    ]

    return {
        "meta": {
            "version": "1.2",
            "session_id": "test_session",
            "frame_count": n_frames,
            "channels": all_channels,
            "decimation_factor": 1.0,
            "duration": duration,
            "original_row_count": n_frames,
        },
        "import_meta": {
            "source_type": source_type,
            "source_path": source_path,
            "original_row_count": n_frames,
            "original_sample_rate": sample_rate,
            "applied_mapping": all_mapping,
            "raw_headers": list(all_mapping.keys()),
            "warnings": warnings,
        },
        "frames": frames,
    }


def _plain_capsule(
    n_frames: int = 50,
    channels: list | None = None,
) -> dict:
    """Return a plain saved session dict (no import_meta)."""
    if channels is None:
        channels = ["v_an", "freq"]
    frames = [{"ts": i * 0.02, "v_an": 1.0, "freq": 60.0} for i in range(n_frames)]
    duration = (n_frames - 1) * 0.02
    return {
        "meta": {
            "version": "1.2",
            "session_id": "saved_sess",
            "frame_count": n_frames,
            "channels": sorted(channels),
            "duration": duration,
        },
        "frames": frames,
    }


# ──────────────────────────────────────────────────────────────────────────────
# from_capsule — imported file
# ──────────────────────────────────────────────────────────────────────────────

def test_from_capsule_source_type_extracted():
    s = ActiveSession.from_capsule(_import_capsule(source_type="rigol_csv"))
    assert s.source_type == "rigol_csv"


def test_from_capsule_row_count_from_import_meta():
    s = ActiveSession.from_capsule(_import_capsule(n_frames=250))
    assert s.row_count == 250


def test_from_capsule_sample_rate_from_import_meta():
    s = ActiveSession.from_capsule(_import_capsule(sample_rate=10_000.0))
    assert s.sample_rate == 10_000.0


def test_from_capsule_label_uses_session_id_by_default():
    s = ActiveSession.from_capsule(_import_capsule())
    assert s.label == "test_session"


def test_from_capsule_label_override_wins():
    s = ActiveSession.from_capsule(_import_capsule(), label="custom_label")
    assert s.label == "custom_label"


def test_from_capsule_source_path_extracted():
    s = ActiveSession.from_capsule(_import_capsule(source_path="/data/RigolDS0.csv"))
    assert s.source_path == "/data/RigolDS0.csv"


def test_from_capsule_is_imported_true():
    s = ActiveSession.from_capsule(_import_capsule())
    assert s.is_imported is True


def test_from_capsule_mapped_channels_extracted():
    s = ActiveSession.from_capsule(
        _import_capsule(mapped={"CH1(V)": "v_an", "CH2(V)": "v_bn"}, unmapped={})
    )
    assert "v_an" in s.mapped_channels
    assert "v_bn" in s.mapped_channels


def test_from_capsule_unmapped_channels_extracted():
    s = ActiveSession.from_capsule(
        _import_capsule(
            mapped={"CH1(V)": "v_an"},
            unmapped={"CH3(V)": "__unmapped__", "CH4(V)": "__unmapped__"},
        )
    )
    assert "CH3(V)" in s.unmapped_channels
    assert "CH4(V)" in s.unmapped_channels


def test_from_capsule_warnings_extracted():
    warns = ["Channel has NaN values", "Duplicate detected"]
    s = ActiveSession.from_capsule(_import_capsule(warnings=warns))
    assert s.warnings == warns


def test_from_capsule_no_warnings():
    s = ActiveSession.from_capsule(_import_capsule(warnings=[]))
    assert s.warnings == []


def test_from_capsule_duration_from_meta():
    capsule = _import_capsule(n_frames=100)
    s = ActiveSession.from_capsule(capsule)
    assert s.duration > 0


# ──────────────────────────────────────────────────────────────────────────────
# from_capsule — plain saved session
# ──────────────────────────────────────────────────────────────────────────────

def test_plain_session_not_imported():
    s = ActiveSession.from_capsule(_plain_capsule())
    assert s.is_imported is False


def test_plain_session_source_type_default():
    s = ActiveSession.from_capsule(_plain_capsule())
    assert s.source_type == "data_capsule_json"


def test_plain_session_row_count_from_frame_count():
    s = ActiveSession.from_capsule(_plain_capsule(n_frames=50))
    assert s.row_count == 50


def test_plain_session_label_from_session_id():
    s = ActiveSession.from_capsule(_plain_capsule())
    assert s.label == "saved_sess"


def test_plain_session_channels_in_mapped():
    s = ActiveSession.from_capsule(_plain_capsule(channels=["v_an", "freq"]))
    assert "v_an" in s.mapped_channels
    assert "freq" in s.mapped_channels


def test_plain_session_no_unmapped():
    s = ActiveSession.from_capsule(_plain_capsule())
    assert s.unmapped_channels == []


def test_plain_session_duration_from_frame_timestamps_fallback():
    capsule = _plain_capsule(n_frames=10)
    capsule["meta"].pop("duration", None)  # remove duration from meta
    s = ActiveSession.from_capsule(capsule)
    # 10 frames × 0.02s per frame = 0.18s (9 intervals)
    assert s.duration > 0


# ──────────────────────────────────────────────────────────────────────────────
# Properties
# ──────────────────────────────────────────────────────────────────────────────

def test_has_warnings_true():
    s = ActiveSession.from_capsule(_import_capsule(warnings=["w1"]))
    assert s.has_warnings is True


def test_has_warnings_false():
    s = ActiveSession.from_capsule(_import_capsule(warnings=[]))
    assert s.has_warnings is False


def test_channel_count_sums_mapped_and_unmapped():
    s = ActiveSession.from_capsule(
        _import_capsule(
            mapped={"CH1(V)": "v_an", "CH2(V)": "v_bn"},
            unmapped={"CH3(V)": "__unmapped__"},
        )
    )
    assert s.channel_count == 3


def test_source_filename_from_path():
    s = ActiveSession.from_capsule(_import_capsule(source_path="/data/capture/run1.csv"))
    assert s.source_filename == "run1.csv"


def test_source_filename_falls_back_to_label():
    capsule = _import_capsule()
    capsule["import_meta"]["source_path"] = ""
    s = ActiveSession.from_capsule(capsule, label="fallback_label")
    assert s.source_filename == "fallback_label"


def test_source_type_display_rigol():
    s = ActiveSession.from_capsule(_import_capsule(source_type="rigol_csv"))
    assert s.source_type_display == "Rigol CSV"


def test_source_type_display_excel():
    s = ActiveSession.from_capsule(_import_capsule(source_type="simulation_excel"))
    assert s.source_type_display == "Simulation Excel"


def test_source_type_display_capsule():
    s = ActiveSession.from_capsule(_plain_capsule())
    assert s.source_type_display == "Data Capsule"


def test_source_type_display_unknown_passes_through():
    s = ActiveSession.from_capsule(_import_capsule(source_type="opal_rt_hdf5"))
    assert s.source_type_display == "opal_rt_hdf5"


def test_duration_display():
    capsule = _import_capsule()
    capsule["meta"]["duration"] = 1.234
    s = ActiveSession.from_capsule(capsule)
    assert s.duration_display == "1.234 s"


def test_sample_rate_display_with_rate():
    s = ActiveSession.from_capsule(_import_capsule(sample_rate=10_000.0))
    assert "10,000" in s.sample_rate_display or "10000" in s.sample_rate_display


def test_sample_rate_display_unknown():
    s = ActiveSession.from_capsule(_import_capsule(sample_rate=0.0))
    assert "—" in s.sample_rate_display


def test_row_count_display_uses_thousands_separator():
    s = ActiveSession.from_capsule(_import_capsule(n_frames=1_000_000))
    assert "1,000,000" in s.row_count_display


def test_imported_at_is_recent():
    before = time.time()
    s = ActiveSession.from_capsule(_import_capsule())
    after = time.time()
    assert before <= s.imported_at <= after
