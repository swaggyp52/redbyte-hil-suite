import numpy as np

from src.file_ingestion import ImportedDataset
from src.dataset_converter import dataset_to_session, MAX_REPLAY_FRAMES


def test_decimation_caps_frames():
    # Create a synthetic dataset larger than the MAX_REPLAY_FRAMES cap
    n = 10_000
    t = np.linspace(0.0, 1.0, n)
    channels = {
        'v_an': np.sin(2 * np.pi * 50.0 * t),
        'freq': np.full(n, 50.0),
    }
    ds = ImportedDataset(
        source_type='rigol_csv',
        source_path='RigolDS0.csv',
        channels=channels,
        time=t,
        sample_rate=float(n),
        duration=1.0,
        raw_headers=['Time', 'CH1(V)', 'CH2', 'CH3'],
    )

    capsule = dataset_to_session(ds, session_id='test_decimation')
    assert capsule['meta']['original_row_count'] == n
    assert capsule['meta']['frame_count'] <= MAX_REPLAY_FRAMES
    assert 'v_an' in capsule['meta']['channels']
"""
Tests for src/dataset_converter.py

Validates:
  - dataset_to_session() decimation logic
  - Frame dicts contain only channels present in the dataset (no fabrication)
  - Missing canonical fields are absent (not filled with 0)
  - session meta fields are correct
  - save_session() / load_session() round-trip
  - available_channels() statistics
  - Full resolution access via get_channel_full_res()
"""
import json
import os
import tempfile

import numpy as np
import pytest

from src.dataset_converter import (
    MAX_REPLAY_FRAMES,
    available_channels,
    dataset_to_session,
    get_channel_full_res,
    load_session,
    save_session,
)
from src.file_ingestion import ImportedDataset


# ──────────────────────────────────────────────────────────────────────────────
# Fixture helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_dataset(n: int, channels: dict | None = None) -> ImportedDataset:
    t = np.linspace(0, float(n - 1) / 1000.0, n)
    if channels is None:
        channels = {
            "v_an": np.sin(2 * np.pi * 60 * t),
            "v_bn": np.sin(2 * np.pi * 60 * t - 2.094),
        }
    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/fake/test.csv",
        channels=channels,
        time=t,
        sample_rate=1000.0,
        duration=float(t[-1] - t[0]) if len(t) > 1 else 0.0,
        raw_headers=list(channels.keys()),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Decimation tests
# ──────────────────────────────────────────────────────────────────────────────

def test_decimation_reduces_large_dataset():
    n = MAX_REPLAY_FRAMES * 10  # 10x the cap
    ds = _make_dataset(n)
    capsule = dataset_to_session(ds)
    assert capsule["meta"]["frame_count"] <= MAX_REPLAY_FRAMES
    assert capsule["meta"]["frame_count"] > 0


def test_small_dataset_not_over_decimated():
    n = 50  # well below MIN_REPLAY_FRAMES cap
    ds = _make_dataset(n)
    capsule = dataset_to_session(ds)
    assert capsule["meta"]["frame_count"] == n


def test_decimation_factor_recorded():
    n = MAX_REPLAY_FRAMES * 5
    ds = _make_dataset(n)
    capsule = dataset_to_session(ds)
    assert capsule["meta"]["decimation_factor"] >= 1.0
    assert capsule["meta"]["original_row_count"] == n


# ──────────────────────────────────────────────────────────────────────────────
# Frame content tests
# ──────────────────────────────────────────────────────────────────────────────

def test_frames_contain_only_present_channels():
    """Frames must not contain channels that were not in the source dataset."""
    ds = _make_dataset(100, channels={"CH1(V)": np.ones(100)})
    capsule = dataset_to_session(ds)
    sample_frame = capsule["frames"][0]
    assert "CH1(V)" in sample_frame
    # Canonical names not in the source must be absent
    for absent in ("v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "p_mech"):
        assert absent not in sample_frame, (
            f"Frame fabricated absent channel '{absent}'"
        )


def test_frames_have_ts_starting_near_zero():
    ds = _make_dataset(100)
    capsule = dataset_to_session(ds)
    t0 = capsule["frames"][0]["ts"]
    assert abs(t0) < 1e-6  # relative time starting at 0


def test_nan_values_excluded_from_frames():
    """NaN channel values must not appear in frame dicts."""
    n = 50
    arr = np.ones(n)
    arr[10] = np.nan
    ds = _make_dataset(n, channels={"v_an": arr})
    capsule = dataset_to_session(ds)
    for frame in capsule["frames"]:
        if "v_an" in frame:
            assert not np.isnan(frame["v_an"]), "NaN leaked into frame dict"


def test_missing_canonical_fields_are_absent_not_zero():
    """
    If v_bn, v_cn are not in the source, they must be ABSENT from frames,
    not silently filled with 0.0.
    """
    ds = _make_dataset(100, channels={"v_an": np.ones(100)})
    capsule = dataset_to_session(ds)
    for frame in capsule["frames"]:
        assert "v_bn" not in frame
        assert "v_cn" not in frame
        assert "p_mech" not in frame


# ──────────────────────────────────────────────────────────────────────────────
# Metadata tests
# ──────────────────────────────────────────────────────────────────────────────

def test_session_meta_version():
    ds = _make_dataset(10)
    capsule = dataset_to_session(ds)
    assert capsule["meta"]["version"] == "1.2"


def test_session_meta_channels_sorted():
    ds = _make_dataset(10, channels={"z_ch": np.ones(10), "a_ch": np.zeros(10)})
    capsule = dataset_to_session(ds)
    channels_in_meta = capsule["meta"]["channels"]
    assert channels_in_meta == sorted(channels_in_meta)


def test_session_id_defaults_to_filename_stem():
    ds = _make_dataset(10)
    capsule = dataset_to_session(ds)
    assert capsule["meta"]["session_id"] == "test"  # stem of "/fake/test.csv"


def test_session_id_override():
    ds = _make_dataset(10)
    capsule = dataset_to_session(ds, session_id="my_run_001")
    assert capsule["meta"]["session_id"] == "my_run_001"


def test_import_meta_block_present():
    ds = _make_dataset(10)
    capsule = dataset_to_session(ds)
    assert "import_meta" in capsule
    assert "source_type" in capsule["import_meta"]
    assert "original_row_count" in capsule["import_meta"]


# ──────────────────────────────────────────────────────────────────────────────
# Persistence tests
# ──────────────────────────────────────────────────────────────────────────────

def test_save_and_load_session_round_trip():
    with tempfile.TemporaryDirectory() as tmpdir:
        ds = _make_dataset(100)
        capsule = dataset_to_session(ds, session_id="roundtrip_test")
        path = save_session(capsule, out_dir=tmpdir)

        assert os.path.isfile(path)
        loaded = load_session(path)
        assert loaded["meta"]["session_id"] == "roundtrip_test"
        assert len(loaded["frames"]) == capsule["meta"]["frame_count"]


# ──────────────────────────────────────────────────────────────────────────────
# Analysis helper tests
# ──────────────────────────────────────────────────────────────────────────────

def test_get_channel_full_res_present():
    n = 500
    arr = np.sin(np.linspace(0, 2 * np.pi, n))
    ds = _make_dataset(n, channels={"v_an": arr})
    t, data = get_channel_full_res(ds, "v_an")
    assert len(t) == n
    assert len(data) == n
    assert np.array_equal(data, arr)


def test_get_channel_full_res_absent_returns_none():
    ds = _make_dataset(10, channels={"v_an": np.ones(10)})
    result = get_channel_full_res(ds, "v_bn")
    assert result is None


def test_available_channels_statistics():
    n = 100
    arr = np.linspace(0.0, 1.0, n)
    ds = _make_dataset(n, channels={"v_an": arr})
    info = available_channels(ds)
    assert "v_an" in info
    assert abs(info["v_an"]["min"] - 0.0) < 1e-9
    assert abs(info["v_an"]["max"] - 1.0) < 1e-9
    assert not info["v_an"]["has_nan"]


def test_available_channels_nan_flag():
    arr = np.array([1.0, np.nan, 2.0])
    ds = _make_dataset(3, channels={"v_an": arr})
    info = available_channels(ds)
    assert info["v_an"]["has_nan"]


# ──────────────────────────────────────────────────────────────────────────────
# Error tests
# ──────────────────────────────────────────────────────────────────────────────

def test_empty_dataset_raises():
    ds = _make_dataset(0, channels={})
    with pytest.raises(ValueError, match="no data rows"):
        dataset_to_session(ds)
