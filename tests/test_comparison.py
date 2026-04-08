"""
Tests for src/comparison.py — run comparison between two ImportedDatasets.

TDD: these tests were written BEFORE the implementation.

Covers:
  - find_overlapping_channels: only canonical/mapped channel names overlap
  - align_datasets: cross-correlation finds timing offset; confidence reflects quality
  - compare_channels: RMS error, peak error, correlation; correct with timing offset
  - generate_delta_trace: time/delta arrays; identical signals → zeros
  - Unmapped channels (original header names) are never compared
  - ChannelComparisonResult and ComparisonResult dataclasses
  - compare_datasets: full two-dataset pipeline
"""

import numpy as np
import pytest

from src.file_ingestion import ImportedDataset
from src.comparison import (
    ChannelComparisonResult,
    ComparisonResult,
    align_datasets,
    compare_channels,
    compare_datasets,
    dataset_from_capsule,
    find_overlapping_channels,
    generate_delta_trace,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ds(n: int, channels: dict, sample_rate: float = 1000.0) -> ImportedDataset:
    """Build a minimal ImportedDataset."""
    t = np.linspace(0.0, float(n - 1) / sample_rate, n)
    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/fake/a.csv",
        channels={k: np.asarray(v, dtype=np.float64) for k, v in channels.items()},
        time=t,
        sample_rate=sample_rate,
        duration=float(t[-1] - t[0]),
        warnings=[],
        raw_headers=list(channels.keys()),
    )


def _sine(n: int, freq: float = 60.0, sr: float = 1000.0,
          offset: float = 0.0) -> np.ndarray:
    t = np.linspace(0.0, float(n - 1) / sr, n)
    return np.sin(2 * np.pi * freq * (t + offset))


# ---------------------------------------------------------------------------
# find_overlapping_channels
# ---------------------------------------------------------------------------

def test_overlap_both_have_v_an():
    a = _ds(100, {"v_an": np.ones(100)})
    b = _ds(100, {"v_an": np.ones(100) * 0.9})
    assert "v_an" in find_overlapping_channels(a, b)


def test_overlap_multiple_channels():
    a = _ds(100, {"v_an": np.ones(100), "v_bn": np.ones(100), "freq": np.ones(100)})
    b = _ds(100, {"v_an": np.ones(100), "v_bn": np.ones(100)})
    result = find_overlapping_channels(a, b)
    assert set(result) == {"v_an", "v_bn"}


def test_overlap_unmapped_channel_excluded():
    """CH1(V) in both datasets must NOT count as an overlap — name ≠ physical signal."""
    a = _ds(100, {"CH1(V)": np.ones(100), "v_an": np.ones(100)})
    b = _ds(100, {"CH1(V)": np.ones(100)})
    # Only v_an is canonical — CH1(V) is an original header that was left unmapped
    result = find_overlapping_channels(a, b, unmapped_a={"CH1(V)"}, unmapped_b={"CH1(V)"})
    assert "CH1(V)" not in result


def test_overlap_no_shared_channels():
    a = _ds(100, {"v_an": np.ones(100)})
    b = _ds(100, {"v_bn": np.ones(100)})
    assert find_overlapping_channels(a, b) == []


def test_overlap_both_datasets_only_unmapped():
    """If both datasets consist entirely of unmapped channels, no overlap."""
    a = _ds(50, {"CH1(V)": np.ones(50)})
    b = _ds(50, {"CH1(V)": np.ones(50)})
    result = find_overlapping_channels(
        a, b, unmapped_a={"CH1(V)"}, unmapped_b={"CH1(V)"}
    )
    assert result == []


def test_overlap_returns_sorted_list():
    a = _ds(100, {"freq": np.ones(100), "v_an": np.ones(100), "v_bn": np.ones(100)})
    b = _ds(100, {"freq": np.ones(100), "v_an": np.ones(100), "v_bn": np.ones(100)})
    result = find_overlapping_channels(a, b)
    assert result == sorted(result)


# ---------------------------------------------------------------------------
# align_datasets
# ---------------------------------------------------------------------------

def test_align_identical_signals_offset_near_zero():
    sig = _sine(2000, sr=1000.0)
    a = _ds(2000, {"v_an": sig}, sample_rate=1000.0)
    b = _ds(2000, {"v_an": sig.copy()}, sample_rate=1000.0)
    offset, confidence = align_datasets(a, b, channel="v_an", max_offset_s=0.1)
    assert abs(offset) < 0.005          # within half a cycle at 60 Hz
    assert confidence > 0.9


def test_align_detects_shift():
    """B is a window of the signal starting 50 samples later than A.

    Use broadband noise to avoid the periodicity alias problem that pure
    sine waves cause (50 samples = 3 exact 60Hz periods → lag looks like 0).
    """
    n = 2000
    sr = 1000.0
    shift_samples = 50
    rng = np.random.default_rng(7)
    sig_long = rng.standard_normal(n + shift_samples)
    sig_a = sig_long[:n]
    sig_b = sig_long[shift_samples: shift_samples + n]
    a = _ds(n, {"v_an": sig_a}, sample_rate=sr)
    b = _ds(n, {"v_an": sig_b}, sample_rate=sr)
    offset, confidence = align_datasets(a, b, channel="v_an", max_offset_s=0.2)
    # The absolute offset should be ~0.05s; sign depends on convention
    assert abs(abs(offset) - 0.05) < 0.005
    assert confidence > 0.5


def test_align_uncorrelated_signals_low_confidence():
    rng = np.random.default_rng(42)
    a = _ds(1000, {"v_an": rng.standard_normal(1000)}, sample_rate=1000.0)
    b = _ds(1000, {"v_bn": rng.standard_normal(1000)}, sample_rate=1000.0)
    # Different channels — fall back to 0 offset
    offset, confidence = align_datasets(a, b, channel="v_an", max_offset_s=0.1)
    # Confidence should be low because the channels don't match
    assert confidence < 0.5


def test_align_returns_offset_within_max():
    sig = _sine(2000)
    a = _ds(2000, {"v_an": sig})
    b_sig = np.roll(sig, 150)
    b = _ds(2000, {"v_an": b_sig})
    offset, _ = align_datasets(a, b, channel="v_an", max_offset_s=0.05)
    assert abs(offset) <= 0.05 + 1e-9   # clamped to max_offset_s


# ---------------------------------------------------------------------------
# compare_channels
# ---------------------------------------------------------------------------

def test_compare_identical_channels_zero_rms():
    sig = _sine(1000)
    a = _ds(1000, {"v_an": sig})
    b = _ds(1000, {"v_an": sig.copy()})
    result = compare_channels(a, b, channel="v_an", timing_offset_s=0.0)
    assert isinstance(result, ChannelComparisonResult)
    assert result.rms_error < 1e-10
    assert result.correlation > 0.9999


def test_compare_channels_known_constant_offset():
    """B = A + 5.0 — RMS error should be 5.0."""
    sig = _sine(1000)
    a = _ds(1000, {"v_an": sig})
    b = _ds(1000, {"v_an": sig + 5.0})
    result = compare_channels(a, b, channel="v_an", timing_offset_s=0.0)
    assert result.rms_error == pytest.approx(5.0, rel=0.01)
    assert result.peak_abs_error == pytest.approx(5.0, rel=0.01)


def test_compare_channels_correlation_is_one_for_identical():
    sig = _sine(1000)
    a = _ds(1000, {"v_an": sig})
    b = _ds(1000, {"v_an": sig.copy()})
    result = compare_channels(a, b, channel="v_an", timing_offset_s=0.0)
    assert result.correlation == pytest.approx(1.0, abs=1e-8)


def test_compare_channels_returns_overlap_duration():
    sr = 1000.0
    n = 500
    sig = _sine(n, sr=sr)
    a = _ds(n, {"v_an": sig}, sample_rate=sr)
    b = _ds(n, {"v_an": sig.copy()}, sample_rate=sr)
    result = compare_channels(a, b, channel="v_an", timing_offset_s=0.0)
    assert result.overlap_duration_s > 0.0
    assert result.n_samples_compared > 0


def test_compare_channels_anticorrelated():
    sig = _sine(1000)
    a = _ds(1000, {"v_an": sig})
    b = _ds(1000, {"v_an": -sig})
    result = compare_channels(a, b, channel="v_an", timing_offset_s=0.0)
    assert result.correlation < -0.9


def test_compare_channel_missing_from_dataset_b():
    """If channel is absent from dataset B, raise ValueError."""
    sig = _sine(500)
    a = _ds(500, {"v_an": sig})
    b = _ds(500, {"v_bn": sig})
    with pytest.raises((ValueError, KeyError)):
        compare_channels(a, b, channel="v_an", timing_offset_s=0.0)


def test_compare_channels_with_timing_offset_better_than_without():
    """
    With broadband noise, a 50-sample shift makes the signals look uncorrelated
    at lag=0.  Applying the correct alignment via align_datasets should drive
    the RMS very close to zero.
    """
    sr = 1000.0
    n = 1000
    shift_samples = 50
    rng = np.random.default_rng(13)
    sig_long = rng.standard_normal(n + shift_samples)
    sig_a = sig_long[:n]
    sig_b = sig_long[shift_samples: shift_samples + n]

    a = _ds(n, {"v_an": sig_a}, sample_rate=sr)
    b = _ds(n, {"v_an": sig_b}, sample_rate=sr)

    result_no_align = compare_channels(a, b, "v_an", timing_offset_s=0.0)
    offset_s, _ = align_datasets(a, b, channel="v_an", max_offset_s=0.2)
    result_with_align = compare_channels(a, b, "v_an", timing_offset_s=offset_s)
    # Correct alignment should reduce RMS substantially (ideally to near 0)
    assert result_with_align.rms_error < result_no_align.rms_error * 0.5


# ---------------------------------------------------------------------------
# generate_delta_trace
# ---------------------------------------------------------------------------

def test_delta_trace_identical_signals_all_zeros():
    sig = _sine(500)
    a = _ds(500, {"v_an": sig})
    b = _ds(500, {"v_an": sig.copy()})
    t, delta = generate_delta_trace(a, b, channel="v_an", timing_offset_s=0.0)
    assert t is not None
    assert len(t) == len(delta)
    assert np.allclose(delta, 0.0, atol=1e-10)


def test_delta_trace_constant_offset():
    sig = _sine(500)
    a = _ds(500, {"v_an": sig})
    b = _ds(500, {"v_an": sig + 3.0})
    _, delta = generate_delta_trace(a, b, channel="v_an", timing_offset_s=0.0)
    assert np.allclose(delta, -3.0, atol=1e-6)


def test_delta_trace_respects_max_points():
    sig = _sine(5000, sr=5000.0)
    a = _ds(5000, {"v_an": sig}, sample_rate=5000.0)
    b = _ds(5000, {"v_an": sig.copy()}, sample_rate=5000.0)
    t, delta = generate_delta_trace(a, b, channel="v_an",
                                     timing_offset_s=0.0, max_points=500)
    assert len(t) <= 500
    assert len(delta) <= 500


def test_delta_trace_time_array_is_monotonic():
    sig = _sine(1000)
    a = _ds(1000, {"v_an": sig})
    b = _ds(1000, {"v_an": sig * 0.9})
    t, _ = generate_delta_trace(a, b, channel="v_an", timing_offset_s=0.0)
    assert np.all(np.diff(t) > 0)


# ---------------------------------------------------------------------------
# compare_datasets — full pipeline
# ---------------------------------------------------------------------------

def test_compare_datasets_basic():
    sig = _sine(1000)
    a = _ds(1000, {"v_an": sig, "v_bn": sig * -0.5})
    b = _ds(1000, {"v_an": sig * 1.05, "v_bn": sig * -0.48})
    result = compare_datasets(a, b,
                               label_a="measured", label_b="simulated",
                               timing_offset_s=0.0)
    assert isinstance(result, ComparisonResult)
    assert result.label_a == "measured"
    assert result.label_b == "simulated"
    assert "v_an" in result.channels
    assert "v_bn" in result.channels


def test_compare_datasets_skips_unmapped():
    """Channels in unmapped sets must be skipped with a warning."""
    sig = _sine(500)
    a = _ds(500, {"v_an": sig, "CH1(V)": sig * 0.1})
    b = _ds(500, {"v_an": sig, "CH1(V)": sig * 0.2})
    result = compare_datasets(
        a, b,
        label_a="A", label_b="B",
        timing_offset_s=0.0,
        unmapped_a={"CH1(V)"},
        unmapped_b={"CH1(V)"},
    )
    assert "CH1(V)" not in result.channels
    assert any("CH1(V)" in w for w in result.skipped_channels)


def test_compare_datasets_channel_not_in_b_goes_to_skipped():
    """Channel in A but absent from B goes to skipped, not channels dict."""
    sig = _sine(500)
    a = _ds(500, {"v_an": sig, "freq": np.ones(500) * 60.0})
    b = _ds(500, {"v_an": sig})
    result = compare_datasets(a, b, label_a="A", label_b="B", timing_offset_s=0.0)
    # freq is only in A — must be skipped
    assert "freq" not in result.channels
    assert "freq" in result.skipped_channels


def test_compare_datasets_result_has_overlap_duration():
    sig = _sine(1000)
    a = _ds(1000, {"v_an": sig})
    b = _ds(1000, {"v_an": sig})
    result = compare_datasets(a, b, label_a="A", label_b="B", timing_offset_s=0.0)
    assert result.overlap_duration_s > 0.0


def test_compare_datasets_empty_overlap():
    """If there are no shared channels, ComparisonResult.channels is empty."""
    a = _ds(100, {"v_an": np.ones(100)})
    b = _ds(100, {"v_bn": np.ones(100)})
    result = compare_datasets(a, b, label_a="A", label_b="B", timing_offset_s=0.0)
    assert result.channels == {}
    assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# ChannelComparisonResult dataclass
# ---------------------------------------------------------------------------

def test_channel_comparison_result_fields():
    r = ChannelComparisonResult(
        rms_error=0.5,
        peak_abs_error=1.0,
        correlation=0.97,
        timing_offset_s=0.01,
        overlap_duration_s=0.999,
        n_samples_compared=999,
        alignment_confidence=0.85,
        warnings=[],
    )
    assert r.rms_error == 0.5
    assert r.peak_abs_error == 1.0
    assert r.correlation == 0.97
    assert r.timing_offset_s == 0.01
    assert r.overlap_duration_s == 0.999
    assert r.n_samples_compared == 999
    assert r.alignment_confidence == 0.85
    assert r.warnings == []


# ---------------------------------------------------------------------------
# ComparisonResult dataclass
# ---------------------------------------------------------------------------

def test_comparison_result_overlapping_channel_names():
    sig = _sine(200)
    a = _ds(200, {"v_an": sig, "v_bn": sig * -0.5})
    b = _ds(200, {"v_an": sig, "v_bn": sig * -0.5})
    result = compare_datasets(a, b, label_a="A", label_b="B", timing_offset_s=0.0)
    assert set(result.overlapping_channel_names) == {"v_an", "v_bn"}


def test_comparison_result_timing_offset_stored():
    sig = _sine(500)
    a = _ds(500, {"v_an": sig})
    b = _ds(500, {"v_an": sig})
    result = compare_datasets(a, b, label_a="A", label_b="B", timing_offset_s=0.025)
    assert result.timing_offset_s == pytest.approx(0.025)


# ---------------------------------------------------------------------------
# dataset_from_capsule
# ---------------------------------------------------------------------------

def _make_capsule(n: int = 100, sr: float = 1000.0) -> dict:
    t = np.linspace(0.0, (n - 1) / sr, n)
    return {
        "meta": {
            "session_id": "test_cap",
            "frame_count": n,
            "channels": ["v_an"],
            "duration": float(t[-1]),
            "sample_rate": sr,
        },
        "frames": [{"ts": round(float(t[i]), 6), "v_an": float(np.sin(t[i]))}
                   for i in range(n)],
    }


def test_dataset_from_capsule_creates_importeddataset():
    from src.file_ingestion import ImportedDataset
    caps = _make_capsule(50)
    ds = dataset_from_capsule(caps)
    assert isinstance(ds, ImportedDataset)


def test_dataset_from_capsule_channels():
    caps = _make_capsule(50)
    ds = dataset_from_capsule(caps)
    assert "v_an" in ds.channels
    assert len(ds.channels["v_an"]) == 50


def test_dataset_from_capsule_time_starts_at_zero():
    caps = _make_capsule(50)
    ds = dataset_from_capsule(caps)
    assert ds.time[0] == pytest.approx(0.0)


def test_dataset_from_capsule_sample_rate():
    caps = _make_capsule(100, sr=500.0)
    ds = dataset_from_capsule(caps)
    assert ds.sample_rate == pytest.approx(500.0, rel=0.05)


def test_dataset_from_capsule_empty_raises():
    caps = {"meta": {}, "frames": []}
    with pytest.raises(ValueError, match="no frames"):
        dataset_from_capsule(caps)


# ---------------------------------------------------------------------------
# Duplicate dataset detection
# ---------------------------------------------------------------------------

def test_detect_duplicate_identical_signals_returns_warning():
    """Two datasets with identical channel content must return a warning string."""
    from src.comparison import detect_duplicate_datasets
    sig = np.sin(np.linspace(0, 2 * np.pi, 500))
    a = _ds(500, {"p_mech": sig})
    b = _ds(500, {"p_mech": sig.copy()})
    warning = detect_duplicate_datasets(a, b, channel="p_mech")
    assert warning is not None, "Identical datasets must produce a warning"
    assert ("identical" in warning.lower() or "duplicate" in warning.lower()), (
        f"Warning text unclear: {warning}"
    )


def test_detect_duplicate_different_signals_returns_none():
    """Meaningfully different signal shapes must NOT produce a duplicate warning."""
    from src.comparison import detect_duplicate_datasets
    rng = np.random.default_rng(42)
    sig_a = np.sin(np.linspace(0, 2 * np.pi, 500))
    # Different waveform: add large noise to break correlation below threshold
    sig_b = sig_a + rng.normal(0, 0.5, 500)
    a = _ds(500, {"p_mech": sig_a})
    b = _ds(500, {"p_mech": sig_b})
    assert detect_duplicate_datasets(a, b, channel="p_mech") is None


def test_detect_duplicate_missing_channel_returns_none():
    """When the named channel is absent from dataset B, return None (no crash)."""
    from src.comparison import detect_duplicate_datasets
    sig = np.sin(np.linspace(0, 2 * np.pi, 200))
    a = _ds(200, {"p_mech": sig})
    b = _ds(200, {"v_an": sig.copy()})
    assert detect_duplicate_datasets(a, b, channel="p_mech") is None
