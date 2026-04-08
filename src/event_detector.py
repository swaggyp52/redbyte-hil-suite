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
from dataclasses import dataclass, field

import numpy as np

from src.file_ingestion import ImportedDataset
from src.signal_processing import compute_thd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_VOLTAGE_PREFIXES = ("v_", "vdc", "v_ab", "v_bc", "v_ca", "v_rms", "voltage")
_FREQ_NAMES = frozenset({"freq", "frequency", "f_grid", "f_hz", "f"})

# Explicit non-voltage unit suffixes to prevent false positives on CH1(A), time(s), etc.
_NON_VOLTAGE_UNIT_SUFFIXES = frozenset({
    "(a)", "(amp)", "(ampere)", "(hz)", "(w)", "(var)", "(s)", "(sec)", "(ms)"
})

# Sag / swell (fraction of nominal RMS)
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

# Step change: |Δ| > 8% of signal range in one sample
_STEP_RANGE_FRAC = 0.08

# Clipping: consecutive samples at extreme value
_CLIP_MIN_DUR_S   = 0.005   # 5 ms
_CLIP_TOL_FRAC    = 0.001   # within 0.1% of max/min counts as clipped

# Duplicate channels
_DUP_CORR_THRESH = 0.999

# THD
_THD_THRESHOLD_PCT = 10.0
_THD_MIN_SAMPLES   = 100


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
    """Detect abrupt step changes: |Δ| > 8% of total signal range per sample."""
    n = len(signal)
    if n < 4:
        return []

    signal_range = float(signal.max() - signal.min())
    if signal_range < 1e-9:
        return []

    diff      = np.diff(signal)
    threshold = _STEP_RANGE_FRAC * signal_range
    flags     = np.abs(diff) > threshold

    events: list[DetectedEvent] = []
    for rs, re in _find_runs(flags):
        step_sz = float(np.max(np.abs(diff[rs:re + 1])))
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

def detect_events(dataset: ImportedDataset) -> list[DetectedEvent]:
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

        # Universal detectors
        events.extend(_detect_flatline(ch_name, signal, time, sr))
        events.extend(_detect_step_change(ch_name, signal, time, sr))
        events.extend(_detect_clipping(ch_name, signal, time, sr))

    events.extend(_detect_duplicate_channels(dataset))
    events.sort(key=lambda e: e.ts_start)
    return events
