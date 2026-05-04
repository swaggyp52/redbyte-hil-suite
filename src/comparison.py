"""
Comparison engine for RedByte GFM HIL Suite.

Compares two ImportedDataset objects channel-by-channel:
  - Finds the canonical-name intersection (unmapped originals never compared)
  - Optionally aligns datasets via cross-correlation to remove timing skew
  - Computes RMS error, peak absolute error, Pearson correlation
  - Generates delta (difference) traces on a common time grid

All comparisons operate on the full-resolution numpy arrays stored in
ImportedDataset.channels — NOT on decimated capsule frames.

Usage::
    from src.comparison import compare_datasets, align_datasets

    result = compare_datasets(dataset_a, dataset_b,
                              label_a="Measured", label_b="Simulated",
                              timing_offset_s=0.0)
    for ch, r in result.channels.items():
        print(f"{ch}: RMS={r.rms_error:.4f}  r={r.correlation:.4f}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.file_ingestion import ImportedDataset
from src.signal_processing import compute_rms, compute_thd

logger = logging.getLogger(__name__)

# Maximum points to interpolate onto when computing delta traces.
_DEFAULT_MAX_POINTS = 2_000


def _unit_for_channel(channel: str) -> str:
    if channel.startswith("v_"):
        return "V"
    if channel.startswith("i_"):
        return "A"
    if channel == "freq":
        return "Hz"
    if channel in {"p_mech", "q"}:
        return "W"
    return ""


# ---------------------------------------------------------------------------
# Capsule → ImportedDataset bridge
# ---------------------------------------------------------------------------

def dataset_from_capsule(capsule: dict, label: str = "") -> "ImportedDataset":
    """
    Build a lightweight ImportedDataset from a Data Capsule dict.

    Uses the (decimated) frame list embedded in the capsule.  Suitable for
    comparison and plotting; not a replacement for the full-resolution data
    that comes from file ingestion.

    Args:
        capsule:  Data Capsule dict with 'frames' and 'meta' keys.
        label:    Optional label / source_path substitution.

    Returns:
        ImportedDataset with numpy arrays built from the frame list.

    Raises:
        ValueError if the capsule has no frames or no time column.
    """
    frames = capsule.get("frames", [])
    if not frames:
        raise ValueError("Capsule has no frames — cannot build dataset")

    # Build time array
    t = np.array([f.get("ts", float(i)) for i, f in enumerate(frames)],
                 dtype=np.float64)
    t -= t[0]  # normalise to start at 0

    # Collect all channel keys (exclude 'ts')
    all_keys: set[str] = set()
    for f in frames:
        for k, v in f.items():
            if k in {"ts", "display_time_s"}:
                continue
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                all_keys.add(k)

    channels: dict[str, np.ndarray] = {}
    for key in sorted(all_keys):
        channels[key] = np.array(
            [
                float(v)
                if isinstance((v := f.get(key, float("nan"))), (int, float, np.integer, np.floating))
                and not isinstance(v, bool)
                else float("nan")
                for f in frames
            ],
            dtype=np.float64,
        )

    meta = capsule.get("meta", {})
    sample_rate = float(meta.get("sample_rate", meta.get("sample_rate_estimate", 0.0)))
    if sample_rate == 0.0 and len(t) >= 2:
        dt = float(np.median(np.diff(t)))
        sample_rate = 1.0 / dt if dt > 0 else 0.0

    duration = float(t[-1] - t[0]) if len(t) > 1 else 0.0

    return ImportedDataset(
        source_type=meta.get("source_type", "data_capsule_json"),
        source_path=label or meta.get("source_path", ""),
        channels=channels,
        time=t,
        sample_rate=sample_rate,
        duration=duration,
        warnings=[],
        raw_headers=list(channels.keys()),
    )


# ---------------------------------------------------------------------------
# Duplicate dataset detection
# ---------------------------------------------------------------------------

_DUPLICATE_CORR_THRESHOLD = 0.9999


def detect_duplicate_datasets(
    dataset_a: "ImportedDataset",
    dataset_b: "ImportedDataset",
    channel: str,
) -> Optional[str]:
    """
    Return a warning string if the named channel appears identical in both datasets.

    Uses Pearson correlation on a 500-point interpolated overlap.  A correlation
    >= 0.9999 is treated as "same data", which catches cases like
    VSGFrequency_Simulation.xlsx being a mislabelled duplicate of
    InverterPower_Simulation.xlsx.

    Returns None if:
    - the channel is absent from either dataset
    - datasets have no time overlap
    - the channel is constant (std < 1e-12)
    - correlation is below the threshold (datasets differ meaningfully)
    """
    if channel not in dataset_a.channels or channel not in dataset_b.channels:
        return None

    t_a = dataset_a.time
    t_b = dataset_b.time
    t_start = max(float(t_a[0]), float(t_b[0]))
    t_end   = min(float(t_a[-1]), float(t_b[-1]))
    if t_start >= t_end:
        return None

    n_grid = min(500, min(len(t_a), len(t_b)))
    t_grid = np.linspace(t_start, t_end, n_grid)
    a_i = np.interp(t_grid, t_a, dataset_a.channels[channel])
    b_i = np.interp(t_grid, t_b, dataset_b.channels[channel])

    a_std = float(a_i.std())
    b_std = float(b_i.std())
    if a_std < 1e-12 or b_std < 1e-12:
        return None  # constant channels — correlation undefined; skip

    corr = float(np.corrcoef(a_i, b_i)[0, 1])
    if corr >= _DUPLICATE_CORR_THRESHOLD:
        return (
            f"Both sessions appear to contain identical '{channel}' data "
            f"(r={corr:.4f}). The delta trace will be near-zero."
        )
    return None


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ChannelComparisonResult:
    """Comparison metrics for a single channel between two datasets."""
    rms_error:          float
    peak_abs_error:     float
    correlation:        float          # Pearson r; NaN if constant signal
    mean_delta:         float = float("nan")
    timing_offset_s:    float = 0.0    # applied timing offset (A − B)
    overlap_duration_s: float = 0.0    # duration of the compared region
    n_samples_compared: int = 0
    alignment_confidence: float = 0.0  # 0..1; 1 = perfect cross-corr peak
    ref_rms:            float = float("nan")
    test_rms:           float = float("nan")
    delta_rms:          float = float("nan")
    ref_thd_pct:        float = float("nan")
    test_thd_pct:       float = float("nan")
    delta_thd_pct:      float = float("nan")
    units:              str = ""
    warnings:           list[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Top-level result for a full two-dataset comparison."""
    label_a:                str
    label_b:                str
    timing_offset_s:        float
    overlap_duration_s:     float
    channels:               dict[str, ChannelComparisonResult] = field(default_factory=dict)
    overlapping_channel_names: list[str]                       = field(default_factory=list)
    skipped_channels:       list[str]                          = field(default_factory=list)
    warnings:               list[str]                          = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_overlapping_channels(
    dataset_a: ImportedDataset,
    dataset_b: ImportedDataset,
    unmapped_a: Optional[set[str]] = None,
    unmapped_b: Optional[set[str]] = None,
) -> list[str]:
    """
    Return the sorted list of channel names that exist in both datasets
    and are NOT in either unmapped set.

    Only canonical engineering names (e.g. 'v_an', 'freq') are considered
    valid overlap candidates.  Original oscilloscope header names (CH1(V),
    CH2(V) …) are excluded via the unmapped sets — comparing them would be
    semantically wrong because the same label in two files does not imply
    the same physical signal.

    Args:
        dataset_a:   First dataset.
        dataset_b:   Second dataset.
        unmapped_a:  Set of channel names in A that were never renamed to a
                     canonical name (and must therefore be excluded).
        unmapped_b:  Set of channel names in B that were never renamed.

    Returns:
        Sorted list of shared canonical channel names.
    """
    excl_a = unmapped_a or set()
    excl_b = unmapped_b or set()

    keys_a = {k for k in dataset_a.channels if k not in excl_a}
    keys_b = {k for k in dataset_b.channels if k not in excl_b}

    return sorted(keys_a & keys_b)


def align_datasets(
    dataset_a: ImportedDataset,
    dataset_b: ImportedDataset,
    channel: str,
    max_offset_s: float = 0.5,
) -> tuple[float, float]:
    """
    Estimate the timing offset between two datasets using cross-correlation
    on the named channel.

    Returns (offset_s, confidence) where:
      offset_s   — how many seconds dataset B lags behind dataset A
                   (positive → B starts later; apply as ``t_b - offset_s``
                   to align to A's timeline).
      confidence — normalised peak correlation height [0, 1].  Values below
                   ~0.3 indicate that the two channels may not be the same
                   physical signal; the offset should not be trusted blindly.

    If ``channel`` is missing from either dataset the function returns
    (0.0, 0.0) so callers can degrade gracefully.

    Args:
        dataset_a:    First (reference) dataset.
        dataset_b:    Second dataset.
        channel:      Name of the channel to correlate.
        max_offset_s: Maximum absolute offset to search (symmetric).
    """
    if channel not in dataset_a.channels or channel not in dataset_b.channels:
        logger.debug("align_datasets: channel '%s' missing from one dataset", channel)
        return 0.0, 0.0

    a = dataset_a.channels[channel].copy()
    b = dataset_b.channels[channel].copy()

    # Normalise both signals to zero-mean / unit-variance to make correlation
    # independent of amplitude differences.
    def _norm(x: np.ndarray) -> np.ndarray:
        std = x.std()
        if std < 1e-12:
            return np.zeros_like(x)
        return (x - x.mean()) / std

    a_n = _norm(a)
    b_n = _norm(b)

    # Use the sample rate of dataset A as the reference.
    sr = dataset_a.sample_rate if dataset_a.sample_rate > 0 else 1000.0
    max_lag_samples = int(max_offset_s * sr)

    # Full cross-correlation — scipy gives better results but numpy is
    # sufficient and avoids an optional dependency.
    try:
        from scipy.signal import correlate as _correlate, correlation_lags as _lags
        corr = _correlate(a_n, b_n, mode="full")
        lags = _lags(len(a_n), len(b_n), mode="full")
    except ImportError:
        corr = np.correlate(a_n, b_n, mode="full")
        lags = np.arange(-(len(b_n) - 1), len(a_n))

    # Restrict search to ±max_lag_samples
    mask     = np.abs(lags) <= max_lag_samples
    corr_win = corr[mask]
    lags_win = lags[mask]

    if len(corr_win) == 0:
        return 0.0, 0.0

    best_idx    = int(np.argmax(np.abs(corr_win)))
    best_lag    = int(lags_win[best_idx])
    best_corr   = float(corr_win[best_idx])

    # Normalise confidence: peak / max-possible (sqrt(N_a * N_b))
    denom = np.sqrt(len(a_n) * len(b_n))
    confidence = float(np.clip(abs(best_corr) / denom if denom > 0 else 0.0, 0.0, 1.0))

    offset_s = float(best_lag) / sr
    # Clamp to declared max
    offset_s = float(np.clip(offset_s, -max_offset_s, max_offset_s))
    return offset_s, confidence


def compare_channels(
    dataset_a: ImportedDataset,
    dataset_b: ImportedDataset,
    channel: str,
    timing_offset_s: float = 0.0,
    alignment_confidence: float = 0.0,
) -> ChannelComparisonResult:
    """
    Compute comparison metrics for a single channel between two datasets.

    Interpolates both signals onto a common time grid (the overlap region
    after applying ``timing_offset_s``), then computes:
      - RMS error              sqrt(mean((A − B)²))
      - Peak absolute error    max(|A − B|)
      - Pearson correlation    r(A, B)

    Args:
        dataset_a:          Reference dataset.
        dataset_b:          Dataset being compared.
        channel:            Channel name (must exist in both).
        timing_offset_s:    Offset to apply to B's time axis before comparison
                            (B_time_aligned = B.time + timing_offset_s).
        alignment_confidence: Confidence score from align_datasets (stored in result).

    Raises:
        ValueError: if ``channel`` is absent from either dataset.
        KeyError:   propagated from numpy indexing if channel not in channels dict.
    """
    if channel not in dataset_a.channels:
        raise ValueError(f"Channel '{channel}' not found in dataset A")
    if channel not in dataset_b.channels:
        raise ValueError(f"Channel '{channel}' not found in dataset B")

    t_a = dataset_a.time
    t_b = dataset_b.time + timing_offset_s

    sig_a = dataset_a.channels[channel]
    sig_b = dataset_b.channels[channel]

    # Overlap region
    t_start = max(float(t_a[0]),  float(t_b[0]))
    t_end   = min(float(t_a[-1]), float(t_b[-1]))

    warnings: list[str] = []

    if t_start >= t_end:
        warnings.append(
            f"No temporal overlap for channel '{channel}' "
            f"with offset {timing_offset_s:.4f}s"
        )
        return ChannelComparisonResult(
            rms_error=float("nan"),
            peak_abs_error=float("nan"),
            correlation=float("nan"),
            mean_delta=float("nan"),
            timing_offset_s=timing_offset_s,
            overlap_duration_s=0.0,
            n_samples_compared=0,
            alignment_confidence=alignment_confidence,
            ref_rms=float("nan"),
            test_rms=float("nan"),
            delta_rms=float("nan"),
            ref_thd_pct=float("nan"),
            test_thd_pct=float("nan"),
            delta_thd_pct=float("nan"),
            units=_unit_for_channel(channel),
            warnings=warnings,
        )

    # Build a common time grid with at most 10 000 points for the overlap
    n_grid  = min(10_000, max(len(t_a), len(t_b)))
    t_grid  = np.linspace(t_start, t_end, n_grid)

    a_interp = np.interp(t_grid, t_a, sig_a)
    b_interp = np.interp(t_grid, t_b, sig_b)

    diff  = a_interp - b_interp
    rms   = float(np.sqrt(np.mean(diff ** 2)))
    peak  = float(np.max(np.abs(diff)))
    mean_delta = float(np.mean(diff))

    # Pearson r
    a_std = float(a_interp.std())
    b_std = float(b_interp.std())
    if a_std < 1e-12 or b_std < 1e-12:
        corr = float("nan")
        warnings.append(f"Channel '{channel}': constant signal — correlation undefined")
    else:
        corr = float(np.corrcoef(a_interp, b_interp)[0, 1])
    ref_rms = float(compute_rms(a_interp))
    test_rms = float(compute_rms(b_interp))
    delta_rms = float(test_rms - ref_rms)

    if channel.startswith(("v_", "i_")) and channel != "v_dc":
        ref_thd = float(compute_thd(a_interp, fs=dataset_a.sample_rate or 0.0, time_data=t_grid))
        test_thd = float(compute_thd(b_interp, fs=dataset_a.sample_rate or 0.0, time_data=t_grid))
    else:
        ref_thd = float("nan")
        test_thd = float("nan")

    return ChannelComparisonResult(
        rms_error=rms,
        peak_abs_error=peak,
        correlation=corr,
        mean_delta=mean_delta,
        timing_offset_s=timing_offset_s,
        overlap_duration_s=float(t_end - t_start),
        n_samples_compared=n_grid,
        alignment_confidence=alignment_confidence,
        ref_rms=ref_rms,
        test_rms=test_rms,
        delta_rms=delta_rms,
        ref_thd_pct=ref_thd,
        test_thd_pct=test_thd,
        delta_thd_pct=float(test_thd - ref_thd) if ref_thd == ref_thd and test_thd == test_thd else float("nan"),
        units=_unit_for_channel(channel),
        warnings=warnings,
    )


def generate_delta_trace(
    dataset_a: ImportedDataset,
    dataset_b: ImportedDataset,
    channel: str,
    timing_offset_s: float = 0.0,
    max_points: int = _DEFAULT_MAX_POINTS,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build a delta (difference) trace: delta(t) = A(t) − B(t + timing_offset_s).

    Both signals are interpolated onto a common, evenly-spaced time grid
    covering only the overlapping region.  The output is decimated to at most
    ``max_points`` for display.

    Args:
        dataset_a:        Reference dataset.
        dataset_b:        Comparison dataset.
        channel:          Channel name (must exist in both).
        timing_offset_s:  Timing offset to apply to B.
        max_points:       Maximum number of output points.

    Returns:
        (time_array, delta_array) — both 1-D float64 numpy arrays of the same
        length.  Returns (empty, empty) if there is no temporal overlap.
    """
    t_a = dataset_a.time
    t_b = dataset_b.time + timing_offset_s

    t_start = max(float(t_a[0]),  float(t_b[0]))
    t_end   = min(float(t_a[-1]), float(t_b[-1]))

    if t_start >= t_end:
        return np.empty(0), np.empty(0)

    n_grid = min(max_points, max(len(t_a), len(t_b)))
    t_grid = np.linspace(t_start, t_end, n_grid)

    sig_a = dataset_a.channels[channel]
    sig_b = dataset_b.channels[channel]

    a_interp = np.interp(t_grid, t_a, sig_a)
    b_interp = np.interp(t_grid, t_b, sig_b)

    return t_grid, a_interp - b_interp


def compare_datasets(
    dataset_a: ImportedDataset,
    dataset_b: ImportedDataset,
    label_a: str = "Dataset A",
    label_b: str = "Dataset B",
    timing_offset_s: float = 0.0,
    unmapped_a: Optional[set[str]] = None,
    unmapped_b: Optional[set[str]] = None,
) -> ComparisonResult:
    """
    Full two-dataset comparison pipeline.

    Steps:
      1. Find overlapping canonical channel names (excluding unmapped originals).
      2. For each overlapping channel, run compare_channels().
      3. Collect channels present in A but absent from B as skipped.
      4. Emit a top-level warning if there are no overlapping channels.

    Args:
        dataset_a:        Reference (e.g. measured) dataset.
        dataset_b:        Comparison (e.g. simulated) dataset.
        label_a:          Display label for dataset A.
        label_b:          Display label for dataset B.
        timing_offset_s:  Pre-computed timing offset to apply (from align_datasets).
        unmapped_a:       Original header names in A that must not be compared.
        unmapped_b:       Original header names in B that must not be compared.

    Returns:
        ComparisonResult with per-channel metrics and aggregate metadata.
    """
    excl_a = unmapped_a or set()
    excl_b = unmapped_b or set()

    overlapping = find_overlapping_channels(
        dataset_a, dataset_b,
        unmapped_a=excl_a, unmapped_b=excl_b,
    )

    top_warnings: list[str] = []
    skipped:      list[str] = []
    channel_results: dict[str, ChannelComparisonResult] = {}

    # Channels that exist in A (non-unmapped) but not in B (or unmapped in B)
    keys_a_canonical = {k for k in dataset_a.channels if k not in excl_a}
    for ch in sorted(keys_a_canonical):
        if ch in overlapping:
            continue  # will be processed below
        if ch not in dataset_b.channels or ch in excl_b:
            skipped.append(ch)

    # Channels that are in unmapped_a but also in unmapped_b (same original name,
    # different files, no semantic equivalence guaranteed)
    for ch in excl_a & excl_b:
        if ch not in skipped:
            skipped.append(ch)
            top_warnings.append(
                f"'{ch}' appears in both datasets but is unmapped in one or both — "
                "cannot guarantee it represents the same physical signal; skipped."
            )

    for ch in overlapping:
        try:
            result = compare_channels(
                dataset_a, dataset_b, ch,
                timing_offset_s=timing_offset_s,
            )
            channel_results[ch] = result
        except Exception as exc:  # pragma: no cover
            skipped.append(ch)
            top_warnings.append(f"Error comparing '{ch}': {exc}")

    # Compute overall overlap duration from first successful channel result
    overlap_duration_s = 0.0
    for r in channel_results.values():
        if r.overlap_duration_s > 0:
            overlap_duration_s = r.overlap_duration_s
            break

    if not overlapping:
        top_warnings.append(
            "No shared canonical channels found — nothing to compare. "
            "Ensure both datasets have channels mapped to the same engineering names."
        )

    return ComparisonResult(
        label_a=label_a,
        label_b=label_b,
        timing_offset_s=timing_offset_s,
        overlap_duration_s=overlap_duration_s,
        channels=channel_results,
        overlapping_channel_names=overlapping,
        skipped_channels=skipped,
        warnings=top_warnings,
    )
