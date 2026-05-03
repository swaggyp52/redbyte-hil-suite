"""
Event detector for RedByte GFM HIL Suite.

Batch-scans an ImportedDataset for common power-quality and data-quality
anomalies:

  - Voltage sag / swell     — per-cycle RMS vs estimated nominal
  - Frequency excursion     — freq channel deviation from 60 Hz nominal
  - Flatline / constant     — zero variation in a channel window
  - Abrupt step change      — single-sample derivative spike
  - Clipping / saturation   — consecutive identical extreme samples
  - Duplicate channels      — near-perfect Pearson correlation
  - THD spike               — FFT-based total harmonic distortion > 10%

Usage::

    from src.event_detector import detect_events

    events = detect_events(dataset)
    for e in events:
        print(f"{e.ts_start:.3f}s  {e.kind:20s}  {e.severity}  {e.description}")
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from src.file_ingestion import ImportedDataset
from src.signal_processing import compute_rms, compute_thd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_VOLTAGE_PREFIXES = ("v_", "vdc", "v_ab", "v_bc", "v_ca", "v_rms", "voltage")
_FREQ_NAMES = frozenset({"freq", "frequency", "f_grid", "f_hz", "f"})
_CURRENT_PREFIXES = ("i_", "current")

# Explicit non-voltage unit suffixes to prevent false positives on CH1(A), time(s), etc.
_NON_VOLTAGE_UNIT_SUFFIXES = frozenset({
    "(a)", "(amp)", "(ampere)", "(hz)", "(w)", "(var)", "(s)", "(sec)", "(ms)"
})

# Canonical AC phase-voltage channels — these are periodic sinusoids whose
# per-sample derivative naturally exceeds the step-change threshold at normal
# power-system frequencies.  Suppress _detect_step_change on these channels
# to avoid flooding the event log with spurious "step change" events.
_AC_VOLTAGE_CHANNELS = frozenset({
    "v_an", "v_bn", "v_cn",
    "v_ab", "v_bc", "v_ca",
})
_SAG_WARN_THRESH   = 0.90   # < 90% nominal  → warning
_SAG_CRIT_THRESH   = 0.50   # < 50% nominal  → critical
_SWELL_WARN_THRESH = 1.10   # > 110% nominal → warning

# Frequency excursion
_FREQ_NOMINAL_HZ       = 60.0
_FREQ_EXCURSION_HZ     = 0.5    # deviation threshold
_FREQ_EXCURSION_MIN_S  = 0.1    # must persist ≥ 100 ms

# Flatline
_FLATLINE_STD_FRAC     = 0.001  # std < 0.1% of signal range
_FLATLINE_MIN_DUR_S    = 0.05   # must persist ≥ 50 ms

# Step change: |Δ| > 20% of signal range in one sample (raised to suppress
# noisy step spam on oscillating waveforms)
_STEP_RANGE_FRAC = 0.20
# Minimum gap (seconds) between reported step-change events on the same channel
_STEP_MERGE_GAP_S = 0.05
# Maximum step-change events per channel before the detector stops
_STEP_MAX_PER_CH = 20

# Clipping: consecutive samples at extreme value
_CLIP_MIN_DUR_S   = 0.005   # 5 ms
_CLIP_TOL_FRAC    = 0.001   # within 0.1% of max/min counts as clipped

# Duplicate channels
_DUP_CORR_THRESH = 0.999

# THD
_THD_THRESHOLD_PCT = 10.0
_THD_MIN_SAMPLES   = 100

# Overcurrent
_OVERCURRENT_MULTIPLIER = 1.20
_OVERCURRENT_MIN_S = 0.05

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "nominal_v_rms": 120.0,
    "nominal_freq": 60.0,
    "sag_v_ratio": 0.90,
    "rms_window_s": 0.1,
    "min_window_s": 0.05,
}


# ---------------------------------------------------------------------------
# DetectedEvent dataclass
# ---------------------------------------------------------------------------

@dataclass
class DetectedEvent:
    """A single detected event on an ImportedDataset channel."""

    kind:        str
    ts_start:    float
    ts_end:      float
    channel:     str
    severity:    str          # "info" | "warning" | "critical"
    description: str
    metrics:     dict = field(default_factory=dict)
    confidence:  float = 1.0

    def to_dict(self) -> dict:
        return {
            "type":        self.kind,
            "ts":          self.ts_start,
            "description": self.description,
            "severity":    self.severity,
            "metrics":     self.metrics,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rms(arr: np.ndarray) -> float:
    if len(arr) == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr.astype(np.float64) ** 2)))


def _find_runs(flags: np.ndarray) -> list[tuple[int, int]]:
    """Return (start, end) index pairs for every contiguous True region."""
    flags = np.asarray(flags, dtype=bool)
    if not np.any(flags):
        return []
    padded = np.empty(len(flags) + 2, dtype=bool)
    padded[0] = False
    padded[1:-1] = flags
    padded[-1] = False
    diff = padded[1:].astype(np.int8) - padded[:-1].astype(np.int8)
    starts = np.where(diff == 1)[0]
    ends   = np.where(diff == -1)[0] - 1
    return list(zip(starts.tolist(), ends.tolist()))


def _is_voltage_channel(name: str) -> bool:
    nl = name.lower()
    if nl.startswith(_VOLTAGE_PREFIXES) or "voltage" in nl:
        return True
    # Reject explicit non-voltage unit suffixes like CH1(A), time(s), CH1(Hz)
    if any(nl.endswith(suf) for suf in _NON_VOLTAGE_UNIT_SUFFIXES):
        return False
    # Match parenthetical voltage unit suffix: "CH1(V)", "CH2(Volt)", etc.
    return "(v)" in nl or "(volt" in nl


def _is_freq_channel(name: str) -> bool:
    return name.lower() in _FREQ_NAMES


def _is_current_channel(name: str) -> bool:
    nl = name.lower()
    return nl.startswith(_CURRENT_PREFIXES) or "(a)" in nl


def _looks_periodic_ac_voltage(signal: np.ndarray, sample_rate: float) -> bool:
    """Heuristic: True when *signal* resembles a steady AC waveform.

    Used to suppress generic point-to-point step detection on channels like
    v_an/v_bn/v_cn for normal sinusoidal operation, while still allowing
    step detection on non-periodic voltage traces (e.g. DC-like jumps).
    """
    n = int(signal.size)
    if n < 128 or sample_rate <= 0:
        return False

    centered = signal.astype(np.float64) - float(np.mean(signal))
    std = float(np.std(centered))
    if std < 1e-9:
        return False

    # Moderate threshold to ignore tiny noise crossings around zero.
    zc = int(np.sum((centered[:-1] <= 0.0) & (centered[1:] > 0.0)))
    duration_s = n / float(sample_rate)
    if duration_s <= 0:
        return False
    est_freq = zc / duration_s
    if not (40.0 <= est_freq <= 80.0):
        return False

    # Confirm that 45–75 Hz dominates the spectrum.
    spectrum = np.fft.rfft(centered)
    freqs = np.fft.rfftfreq(n, d=1.0 / float(sample_rate))
    mags = np.abs(spectrum)
    total = float(np.sum(mags[1:]))
    if total <= 0:
        return False
    band = (freqs >= 45.0) & (freqs <= 75.0)
    band_energy = float(np.sum(mags[band]))
    return (band_energy / total) >= 0.35


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

def _detect_voltage_sag_swell(
    channel: str,
    signal: np.ndarray,
    time: np.ndarray,
    sample_rate: float,
) -> list[DetectedEvent]:
    """Per-cycle RMS compared to nominal estimated from first 20% of signal."""
    n = len(signal)
    # Need at least 4 full cycles of input
    min_n = max(int(sample_rate / 60.0 * 4), 40)
    if n < min_n:
        return []

    # Nominal: RMS of first 20%, at least 2 cycles
    ref_n = max(n // 5, int(sample_rate / 60.0 * 2))
    ref_n = min(ref_n, n)
    nominal_rms = _rms(signal[:ref_n])
    if nominal_rms < 1e-6:
        return []

    cycle_n   = max(int(sample_rate / 60.0), 4)
    n_windows = n // cycle_n
    if n_windows < 2:
        return []

    win_rms = np.array([_rms(signal[i * cycle_n:(i + 1) * cycle_n])
                        for i in range(n_windows)])

    sag_flags   = win_rms < _SAG_WARN_THRESH   * nominal_rms
    swell_flags = win_rms > _SWELL_WARN_THRESH  * nominal_rms

    events: list[DetectedEvent] = []
    for flags, kind in [(sag_flags, "voltage_sag"), (swell_flags, "voltage_swell")]:
        for ws, we in _find_runs(flags):
            seg    = win_rms[ws:we + 1]
            worst  = float(seg.min() if kind == "voltage_sag" else seg.max())
            depth  = abs(worst - nominal_rms) / nominal_rms * 100.0

            ts_s = float(time[ws * cycle_n])
            ts_e = float(time[min((we + 1) * cycle_n - 1, n - 1)])

            if kind == "voltage_sag":
                sev  = "critical" if worst < _SAG_CRIT_THRESH * nominal_rms else "warning"
                desc = (
                    f"Voltage sag on '{channel}': RMS ≈ {worst:.2f} V "
                    f"({depth:.1f}% below nominal {nominal_rms:.2f} V)"
                )
            else:
                sev  = "warning"
                desc = (
                    f"Voltage swell on '{channel}': RMS ≈ {worst:.2f} V "
                    f"({depth:.1f}% above nominal {nominal_rms:.2f} V)"
                )

            events.append(DetectedEvent(
                kind=kind, ts_start=ts_s, ts_end=ts_e,
                channel=channel, severity=sev, description=desc,
                metrics={
                    "depth_pct":   round(depth, 2),
                    "worst_rms":   round(worst, 4),
                    "nominal_rms": round(nominal_rms, 4),
                    "duration_s":  round(ts_e - ts_s, 6),
                },
                confidence=0.90,
            ))

    return events


def _detect_freq_excursion(
    channel: str,
    signal: np.ndarray,
    time: np.ndarray,
    sample_rate: float,
) -> list[DetectedEvent]:
    """Frequency deviation beyond ±0.5 Hz from 60 Hz nominal."""
    n = len(signal)
    min_samples = max(int(_FREQ_EXCURSION_MIN_S * sample_rate), 5)
    if n < min_samples:
        return []

    deviation  = np.abs(signal - _FREQ_NOMINAL_HZ)
    exc_flags  = deviation > _FREQ_EXCURSION_HZ

    events: list[DetectedEvent] = []
    for rs, re in _find_runs(exc_flags):
        if re - rs + 1 < min_samples:
            continue
        seg       = signal[rs:re + 1]
        idxmax    = int(np.argmax(np.abs(seg - _FREQ_NOMINAL_HZ)))
        worst_dev = float(abs(seg[idxmax] - _FREQ_NOMINAL_HZ))
        worst_hz  = float(seg[idxmax])
        sev       = "critical" if worst_dev >= 1.0 else "warning"
        events.append(DetectedEvent(
            kind="freq_excursion",
            ts_start=float(time[rs]),
            ts_end=float(time[re]),
            channel=channel,
            severity=sev,
            description=(
                f"Frequency excursion on '{channel}': {worst_hz:.3f} Hz "
                f"({worst_dev:.3f} Hz from {_FREQ_NOMINAL_HZ} Hz nominal)"
            ),
            metrics={
                "deviation_hz": round(worst_dev, 4),
                "worst_hz":     round(worst_hz, 4),
                "duration_s":   round(float(time[re] - time[rs]), 6),
            },
            confidence=0.95,
        ))

    return events


def _detect_flatline(
    channel: str,
    signal: np.ndarray,
    time: np.ndarray,
    sample_rate: float,
) -> list[DetectedEvent]:
    """Detect windows where std ≈ 0 (signal stuck at constant value)."""
    n = len(signal)
    if n < 10:
        return []

    # Entire channel is constant
    if signal.std() < 1e-9:
        return [DetectedEvent(
            kind="flatline",
            ts_start=float(time[0]),
            ts_end=float(time[-1]),
            channel=channel,
            severity="warning",
            description=f"Channel '{channel}' is entirely constant (value={float(signal[0]):.4g})",
            metrics={
                "duration_s": round(float(time[-1] - time[0]), 6),
                "value":      float(signal[0]),
            },
            confidence=1.0,
        )]

    signal_range = float(signal.max() - signal.min())
    std_thresh   = max(1e-9, _FLATLINE_STD_FRAC * signal_range)
    min_samples  = max(int(_FLATLINE_MIN_DUR_S * sample_rate), 10)
    window_n     = min_samples
    step_n       = max(window_n // 2, 1)

    flat_flags = np.zeros(n, dtype=bool)
    for i in range(0, n - window_n + 1, step_n):
        if signal[i:i + window_n].std() < std_thresh:
            flat_flags[i:i + window_n] = True

    events: list[DetectedEvent] = []
    for rs, re in _find_runs(flat_flags):
        if re - rs + 1 < min_samples:
            continue
        dur = float(time[re] - time[rs])
        events.append(DetectedEvent(
            kind="flatline",
            ts_start=float(time[rs]),
            ts_end=float(time[re]),
            channel=channel,
            severity="warning",
            description=f"Flatline in '{channel}': constant for {dur:.3f}s",
            metrics={
                "duration_s":  round(dur, 6),
                "stuck_value": round(float(np.mean(signal[rs:re + 1])), 6),
            },
            confidence=0.95,
        ))

    return events


def _detect_step_change(
    channel: str,
    signal: np.ndarray,
    time: np.ndarray,
    sample_rate: float,
) -> list[DetectedEvent]:
    """Detect abrupt step changes: |Δ| > threshold of total signal range.

    Adjacent events within ``_STEP_MERGE_GAP_S`` are merged into a single
    event to prevent thousands of per-sample detections on oscillating
    waveforms.  Output is capped at ``_STEP_MAX_PER_CH`` per channel.
    """
    n = len(signal)
    if n < 4:
        return []

    signal_range = float(signal.max() - signal.min())
    if signal_range < 1e-9:
        return []

    diff      = np.diff(signal)
    threshold = _STEP_RANGE_FRAC * signal_range
    flags     = np.abs(diff) > threshold

    raw_runs = _find_runs(flags)
    if not raw_runs:
        return []

    # ── Merge runs that are within _STEP_MERGE_GAP_S of each other ──
    merge_gap_samples = max(int(_STEP_MERGE_GAP_S * sample_rate), 1)
    merged: list[tuple[int, int]] = [raw_runs[0]]
    for rs, re in raw_runs[1:]:
        prev_rs, prev_re = merged[-1]
        if rs - prev_re <= merge_gap_samples:
            merged[-1] = (prev_rs, re)
        else:
            merged.append((rs, re))

    events: list[DetectedEvent] = []
    for rs, re in merged:
        if len(events) >= _STEP_MAX_PER_CH:
            break
        step_sz = float(np.max(np.abs(diff[rs:min(re + 1, len(diff))])))
        pct     = step_sz / signal_range * 100.0
        sev     = "critical" if pct > 50.0 else "warning"
        events.append(DetectedEvent(
            kind="step_change",
            ts_start=float(time[rs]),
            ts_end=float(time[min(re + 1, n - 1)]),
            channel=channel,
            severity=sev,
            description=(
                f"Abrupt step in '{channel}': {step_sz:.4g} "
                f"({pct:.1f}% of signal range)"
            ),
            metrics={
                "step_size":  round(step_sz, 6),
                "range_pct":  round(pct, 2),
            },
            confidence=0.85,
        ))

    return events


def _detect_clipping(
    channel: str,
    signal: np.ndarray,
    time: np.ndarray,
    sample_rate: float,
) -> list[DetectedEvent]:
    """Detect saturation: many consecutive samples at the signal min or max."""
    n = len(signal)
    min_samples = max(int(_CLIP_MIN_DUR_S * sample_rate), 5)
    if n < min_samples * 2:
        return []

    signal_range = float(signal.max() - signal.min())
    if signal_range < 1e-9:
        return []

    tol = max(_CLIP_TOL_FRAC * signal_range, 1e-12)
    edges = [
        (signal >= signal.max() - tol, "high"),
        (signal <= signal.min() + tol, "low"),
    ]

    events: list[DetectedEvent] = []
    for flags, direction in edges:
        for rs, re in _find_runs(flags):
            n_run = re - rs + 1
            if n_run < min_samples:
                continue
            clip_val = float(signal[rs])
            events.append(DetectedEvent(
                kind="clipping",
                ts_start=float(time[rs]),
                ts_end=float(time[re]),
                channel=channel,
                severity="warning",
                description=(
                    f"Clipping ({direction}) in '{channel}': "
                    f"{n_run} consecutive samples at {clip_val:.4g}"
                ),
                metrics={
                    "clip_value": round(clip_val, 6),
                    "n_samples":  n_run,
                    "direction":  direction,
                },
                confidence=0.80,
            ))

    return events


def _detect_thd_spike(
    channel: str,
    signal: np.ndarray,
    time: np.ndarray,
    sample_rate: float,
) -> list[DetectedEvent]:
    """Detect high THD using FFT on the full channel buffer."""
    if len(signal) < _THD_MIN_SAMPLES:
        return []

    thd_pct = compute_thd(signal, fundamental_freq=60.0, fs=sample_rate)
    if thd_pct <= _THD_THRESHOLD_PCT:
        return []

    sev = "critical" if thd_pct >= 25.0 else "warning"
    return [DetectedEvent(
        kind="thd_spike",
        ts_start=float(time[0]),
        ts_end=float(time[-1]),
        channel=channel,
        severity=sev,
        description=(
            f"High THD in '{channel}': {thd_pct:.1f}% "
            f"(threshold {_THD_THRESHOLD_PCT:.0f}%)"
        ),
        metrics={
            "thd_pct":       round(thd_pct, 2),
            "threshold_pct": _THD_THRESHOLD_PCT,
            "duration_s":    round(float(time[-1] - time[0]), 6),
        },
        confidence=0.85,
    )]


def _detect_overcurrent(
    channel: str,
    signal: np.ndarray,
    time: np.ndarray,
    sample_rate: float,
) -> list[DetectedEvent]:
    if len(signal) < 16:
        return []

    baseline_n = max(8, int(len(signal) * 0.2))
    baseline_rms = _rms(signal[:baseline_n])
    if baseline_rms < 1e-9:
        return []

    window_n = max(int(_OVERCURRENT_MIN_S * sample_rate), 8)
    if len(signal) < window_n:
        return []

    rms_vals = np.array(
        [_rms(signal[i:i + window_n]) for i in range(0, len(signal) - window_n + 1)]
    )
    threshold = baseline_rms * _OVERCURRENT_MULTIPLIER
    flags = rms_vals > threshold
    if not np.any(flags):
        return []

    events: list[DetectedEvent] = []
    for rs, re in _find_runs(flags):
        start_i = rs
        end_i = min(re + window_n - 1, len(signal) - 1)
        peak_rms = float(np.max(rms_vals[rs:re + 1]))
        events.append(DetectedEvent(
            kind="overcurrent",
            ts_start=float(time[start_i]),
            ts_end=float(time[end_i]),
            channel=channel,
            severity="warning",
            description=(
                f"Overcurrent on '{channel}': RMS ≈ {peak_rms:.3f} A "
                f"(threshold {threshold:.3f} A)"
            ),
            metrics={
                "baseline_rms_a": round(baseline_rms, 6),
                "threshold_a": round(threshold, 6),
                "peak_rms_a": round(peak_rms, 6),
            },
            confidence=0.85,
        ))

    return events


def _detect_duplicate_channels(dataset: ImportedDataset) -> list[DetectedEvent]:
    """Flag channel pairs with Pearson correlation ≥ 0.999."""
    names = list(dataset.channels.keys())
    events: list[DetectedEvent] = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            ch_a, ch_b = names[i], names[j]
            sig_a = dataset.channels[ch_a]
            sig_b = dataset.channels[ch_b]

            if len(sig_a) != len(sig_b):
                continue
            if sig_a.std() < 1e-9 or sig_b.std() < 1e-9:
                continue

            corr = float(np.corrcoef(sig_a, sig_b)[0, 1])
            if corr < _DUP_CORR_THRESH:
                continue

            events.append(DetectedEvent(
                kind="duplicate_channel",
                ts_start=float(dataset.time[0]),
                ts_end=float(dataset.time[-1]),
                channel=f"{ch_a},{ch_b}",
                severity="info",
                description=(
                    f"Channels '{ch_a}' and '{ch_b}' are nearly identical "
                    f"(r={corr:.4f}) — possible duplicate or wiring error"
                ),
                metrics={
                    "channel_a":   ch_a,
                    "channel_b":   ch_b,
                    "correlation": round(corr, 6),
                },
                confidence=corr,
            ))

    return events


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _detect_dataset_events(dataset: ImportedDataset) -> list[DetectedEvent]:
    """
    Run all batch event detectors on *dataset*.

    Returns a list of :class:`DetectedEvent` objects sorted by ``ts_start``.
    Gracefully returns an empty list if the dataset is empty or too short.

    Args:
        dataset: The ImportedDataset to scan.

    Returns:
        Sorted list of DetectedEvent objects (may be empty).
    """
    if not dataset.channels:
        return []

    sr = dataset.sample_rate if dataset.sample_rate and dataset.sample_rate > 0 else 1000.0

    events: list[DetectedEvent] = []

    for ch_name, signal in dataset.channels.items():
        if len(signal) < 4:
            continue

        time = dataset.time
        if time is None or len(time) != len(signal):
            time = np.linspace(0.0, (len(signal) - 1) / sr, len(signal))

        signal = np.asarray(signal, dtype=np.float64)

        if _is_voltage_channel(ch_name):
            events.extend(_detect_voltage_sag_swell(ch_name, signal, time, sr))
            events.extend(_detect_thd_spike(ch_name, signal, time, sr))

        if _is_freq_channel(ch_name):
            events.extend(_detect_freq_excursion(ch_name, signal, time, sr))

        if _is_current_channel(ch_name):
            events.extend(_detect_overcurrent(ch_name, signal, time, sr))

        # Universal detectors — suppress step-change only when a canonical
        # phase/line voltage channel looks like periodic AC.  This prevents
        # false "abrupt step" events on healthy sinusoids while preserving
        # true discontinuity detection for non-periodic voltage traces.
        events.extend(_detect_flatline(ch_name, signal, time, sr))
        periodic_ac = (
            ch_name in _AC_VOLTAGE_CHANNELS
            and _looks_periodic_ac_voltage(signal, sr)
        )
        if not periodic_ac:
            events.extend(_detect_step_change(ch_name, signal, time, sr))
        events.extend(_detect_clipping(ch_name, signal, time, sr))

    events.extend(_detect_duplicate_channels(dataset))
    events.sort(key=lambda e: e.ts_start)

    # ── Global noise reduction: merge same-kind events on the same channel
    # that overlap or are within a tiny gap. ────────────────────────────────
    events = _merge_nearby_events(events, gap_s=0.02)

    return events


def _session_frames_to_arrays(frames: List[Dict]) -> Dict[str, np.ndarray]:
    if not frames:
        return {k: np.array([]) for k in ("ts", "t_rel", "v_an", "v_bn", "v_cn", "freq")}
    ts = np.array([f.get("ts", 0.0) for f in frames], dtype=float)
    return {
        "ts": ts,
        "t_rel": ts - ts[0] if ts.size else ts,
        "v_an": np.array([f.get("v_an", 0.0) for f in frames], dtype=float),
        "v_bn": np.array([f.get("v_bn", 0.0) for f in frames], dtype=float),
        "v_cn": np.array([f.get("v_cn", 0.0) for f in frames], dtype=float),
        "freq": np.array([f.get("freq", 60.0) for f in frames], dtype=float),
    }


def _rolling_rms_session(x: np.ndarray, window_n: int) -> np.ndarray:
    if x.size == 0 or window_n < 1:
        return x.copy()
    window_n = min(window_n, x.size)
    kernel = np.ones(window_n) / window_n
    return np.sqrt(np.maximum(np.convolve(x * x, kernel, mode="same"), 0.0))


def _bool_segments(mask: np.ndarray, t_rel: np.ndarray, min_len_s: float) -> List[Dict]:
    segments: List[Dict] = []
    if mask.size == 0 or t_rel.size == 0:
        return segments
    start = None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        if (not flag or i == mask.size - 1) and start is not None:
            end = i if flag and i == mask.size - 1 else i - 1
            dur = float(t_rel[end] - t_rel[start]) if end > start else 0.0
            if dur >= min_len_s:
                segments.append({"start_i": start, "end_i": end, "start_s": float(t_rel[start]), "end_s": float(t_rel[end])})
            start = None
    return segments


def _detect_session_events(session_data: Dict, thresholds: Optional[Dict] = None) -> List[Dict]:
    frames = session_data.get("frames", [])
    arr = _session_frames_to_arrays(frames)
    if arr["ts"].size < 4:
        return []

    cfg = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        cfg.update(thresholds)

    dt = float(np.median(np.diff(arr["t_rel"]))) if arr["t_rel"].size >= 2 else 0.01
    if dt <= 0:
        dt = 0.01
    window_n = max(2, int(round(cfg["rms_window_s"] / dt)))
    v_rms = {
        "v_an": _rolling_rms_session(arr["v_an"], window_n),
        "v_bn": _rolling_rms_session(arr["v_bn"], window_n),
        "v_cn": _rolling_rms_session(arr["v_cn"], window_n),
    }
    avg_rms = (v_rms["v_an"] + v_rms["v_bn"] + v_rms["v_cn"]) / 3.0
    sag_mask = avg_rms < cfg["sag_v_ratio"] * cfg["nominal_v_rms"]

    events: List[Dict] = []
    for seg in _bool_segments(sag_mask, arr["t_rel"], cfg["min_window_s"]):
        window = avg_rms[seg["start_i"]:seg["end_i"] + 1]
        min_v = float(np.min(window)) if window.size else 0.0
        events.append({
            "ts": seg["start_s"],
            "t_rel": seg["start_s"],
            "type": "voltage_sag_start",
            "details": f"Three-phase RMS dropped to {min_v:.2f} V.",
            "meta": {"min_v_rms": min_v, "threshold_v": cfg["sag_v_ratio"] * cfg["nominal_v_rms"]},
        })
        events.append({
            "ts": seg["end_s"],
            "t_rel": seg["end_s"],
            "type": "voltage_sag_end",
            "details": "Three-phase RMS recovered above sag threshold.",
            "meta": {"duration_s": seg["end_s"] - seg["start_s"]},
        })
    return events


def run_summary(session_data: Dict) -> Dict:
    frames = session_data.get("frames", [])
    arr = _session_frames_to_arrays(frames)
    if arr["ts"].size == 0:
        return {"frames": 0, "duration_s": 0.0, "thd_van_pct": 0.0, "v_rms_per_phase": {"a": 0.0, "b": 0.0, "c": 0.0}}
    duration = float(arr["t_rel"][-1] - arr["t_rel"][0]) if arr["t_rel"].size >= 2 else 0.0
    return {
        "frames": int(arr["ts"].size),
        "duration_s": duration,
        "freq_min": float(np.min(arr["freq"])),
        "freq_max": float(np.max(arr["freq"])),
        "thd_van_pct": float(compute_thd(arr["v_an"].tolist(), time_data=arr["ts"].tolist())),
        "v_rms_per_phase": {
            "a": float(compute_rms(arr["v_an"].tolist())),
            "b": float(compute_rms(arr["v_bn"].tolist())),
            "c": float(compute_rms(arr["v_cn"].tolist())),
        },
    }


def detect_events(data, thresholds: Optional[Dict] = None):
    if isinstance(data, ImportedDataset):
        return _detect_dataset_events(data)
    if isinstance(data, dict):
        return _detect_session_events(data, thresholds=thresholds)
    return []


def _merge_nearby_events(
    events: list[DetectedEvent], gap_s: float = 0.02,
) -> list[DetectedEvent]:
    """Merge events of the same kind+channel that overlap or are within *gap_s*."""
    if not events:
        return events

    merged: list[DetectedEvent] = []
    for e in events:
        if (
            merged
            and merged[-1].kind == e.kind
            and merged[-1].channel == e.channel
            and (e.ts_start - merged[-1].ts_end) <= gap_s
        ):
            prev = merged[-1]
            # Extend the previous event to cover this one, keep worst severity
            worse = (
                e.severity
                if _sev_rank(e.severity) > _sev_rank(prev.severity)
                else prev.severity
            )
            merged[-1] = DetectedEvent(
                kind=prev.kind,
                ts_start=prev.ts_start,
                ts_end=max(prev.ts_end, e.ts_end),
                channel=prev.channel,
                severity=worse,
                description=prev.description,
                metrics=prev.metrics,
                confidence=min(prev.confidence, e.confidence),
            )
        else:
            merged.append(e)
    return merged


def _sev_rank(sev: str) -> int:
    return {"info": 0, "warning": 1, "critical": 2}.get(sev, 0)
