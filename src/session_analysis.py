"""
Shared offline-analysis helpers for replay, compliance, and export.
"""

from __future__ import annotations

import os
from collections import Counter

import numpy as np

from src.channel_mapping import CANONICAL_SIGNALS, infer_unit_from_header
from src.comparison import dataset_from_capsule
from src.derived_channels import derive_dataset_channels, ensure_capsule_derived_channels
from src.event_detector import DetectedEvent, detect_events
from src.file_ingestion import ImportedDataset
from src.signal_processing import compute_rms, compute_thd

APP_VERSION = "1.0.0"
FREQUENCY_NOMINAL_HZ = 60.0

_PHASE_VOLTAGE_CHANNELS = ("v_an", "v_bn", "v_cn")
_LINE_VOLTAGE_CHANNELS = ("v_ab", "v_bc", "v_ca")
_CURRENT_CHANNELS = ("i_a", "i_b", "i_c")
_OPTIONAL_CANONICAL_CHANNELS = ("freq", "p_mech", "q", "v_dc", "i_dc", "angle", "status")
_GENERIC_NUMERIC_EXCLUDES = frozenset(
    _PHASE_VOLTAGE_CHANNELS
    + _LINE_VOLTAGE_CHANNELS
    + _CURRENT_CHANNELS
    + ("freq", "status", "display_time_s")
)
_EXPECTED_VSM_CHANNELS = (
    *_PHASE_VOLTAGE_CHANNELS,
    *_LINE_VOLTAGE_CHANNELS,
    *_CURRENT_CHANNELS,
    "freq",
    "p_mech",
    "status",
)
_VSM_MODE_CHANNELS = frozenset(
    _PHASE_VOLTAGE_CHANNELS
    + _LINE_VOLTAGE_CHANNELS
    + _CURRENT_CHANNELS
    + ("freq", "v_dc", "i_dc")
)


def dataset_for_analysis(capsule: dict) -> ImportedDataset:
    """
    Return the best-available full-resolution dataset for *capsule*.
    """
    dataset = capsule.get("_dataset")
    if dataset is None:
        dataset = dataset_from_capsule(
            capsule, label=capsule.get("meta", {}).get("source_path", "")
        )

    dataset = derive_dataset_channels(dataset)
    ensure_capsule_derived_channels(capsule)
    capsule["_dataset"] = dataset
    return dataset


def events_for_capsule(capsule: dict) -> list[DetectedEvent]:
    """
    Detect events from the best-available analysis dataset.
    """
    return detect_events(dataset_for_analysis(capsule))


def _channel_metrics(
    dataset: ImportedDataset,
    channel: str,
    unit: str,
    *,
    include_thd: bool = False,
) -> dict:
    arr = dataset.channels.get(channel)
    if arr is None:
        return {"available": False, "unit": unit, "reason": f"{channel} not present"}

    value = {
        "available": True,
        "unit": unit,
        "rms": round(float(compute_rms(arr)), 6),
        "sample_count": int(arr.size),
    }
    if include_thd:
        value["thd_pct"] = round(
            float(compute_thd(arr, fs=dataset.sample_rate, time_data=dataset.time)),
            6,
        )
    return value


def _basic_channel_stats(dataset: ImportedDataset, channel: str) -> dict:
    arr = dataset.channels.get(channel)
    unit = CANONICAL_SIGNALS.get(channel, {}).get("unit") or infer_unit_from_header(channel) or ""
    if arr is None:
        return {"available": False, "unit": unit, "reason": f"{channel} not present"}

    valid = np.asarray(arr, dtype=np.float64)
    valid = valid[np.isfinite(valid)]
    if valid.size == 0:
        return {"available": False, "unit": unit, "reason": f"{channel} has no finite numeric samples"}

    return {
        "available": True,
        "unit": unit,
        "min": round(float(np.min(valid)), 6),
        "max": round(float(np.max(valid)), 6),
        "mean": round(float(np.mean(valid)), 6),
        "rms": round(float(compute_rms(valid)), 6),
        "peak_to_peak": round(float(np.max(valid) - np.min(valid)), 6),
        "sample_count": int(valid.size),
    }


def _estimate_frequency_series(
    time_s: np.ndarray,
    signal: np.ndarray,
) -> dict[str, np.ndarray] | None:
    def _spectral_estimate(x_time: np.ndarray, x_signal: np.ndarray) -> dict[str, np.ndarray] | None:
        if x_time.size < 64 or x_signal.size != x_time.size:
            return None
        dt = float(np.median(np.diff(x_time)))
        if dt <= 0:
            return None
        sample_rate = 1.0 / dt
        centered = np.asarray(x_signal, dtype=np.float64) - float(np.mean(x_signal))
        if centered.size > 50_000:
            step = int(np.ceil(centered.size / 50_000))
            centered = centered[::step]
            sample_rate = sample_rate / step
        if centered.size < 64:
            return None

        spectrum = np.fft.rfft(centered)
        freqs = np.fft.rfftfreq(centered.size, d=1.0 / sample_rate)
        band = (freqs >= 45.0) & (freqs <= 75.0)
        if not np.any(band):
            return None

        band_freqs = freqs[band]
        band_mags = np.abs(spectrum[band])
        if not np.any(band_mags > 0):
            return None

        dominant = float(band_freqs[int(np.argmax(band_mags))])
        time_mid = float((x_time[0] + x_time[-1]) / 2.0)
        return {
            "time": np.asarray([time_mid], dtype=np.float64),
            "values": np.asarray([dominant], dtype=np.float64),
        }

    crossings: list[float] = []
    if time_s.size < 16 or signal.size != time_s.size:
        return None

    if time_s.size > 200_000:
        step = int(np.ceil(time_s.size / 20_000))
        reduced = _estimate_frequency_series(time_s[::step], signal[::step])
        if reduced is not None:
            return reduced

    dt = float(np.median(np.diff(time_s))) if time_s.size >= 2 else 0.0
    if dt <= 0:
        return None
    sample_rate = 1.0 / dt

    # Smooth high-rate switching ripple before zero-crossing estimation.
    smooth_window = max(3, int(sample_rate / 2400.0))
    smooth_window = min(smooth_window, max(3, signal.size // 20))
    if smooth_window > 3:
        kernel = np.ones(smooth_window, dtype=np.float64) / smooth_window
        working = np.convolve(np.asarray(signal, dtype=np.float64), kernel, mode="same")
    else:
        working = np.asarray(signal, dtype=np.float64)

    for idx in range(signal.size - 1):
        a = float(working[idx])
        b = float(working[idx + 1])
        if not np.isfinite(a) or not np.isfinite(b):
            continue
        if a <= 0.0 < b:
            denom = b - a
            frac = (-a / denom) if abs(denom) > 1e-12 else 0.0
            crossings.append(
                float(time_s[idx] + frac * (time_s[idx + 1] - time_s[idx]))
            )

    if len(crossings) < 3:
        return None

    crossing_arr = np.asarray(crossings, dtype=np.float64)
    periods = np.diff(crossing_arr)
    valid = periods > 0
    if valid.sum() < 2:
        return None

    periods = periods[valid]
    freq_values = 1.0 / periods
    freq_times = (crossing_arr[:-1][valid] + crossing_arr[1:][valid]) / 2.0

    median_freq = float(np.median(freq_values)) if freq_values.size else 0.0
    if not 45.0 <= median_freq <= 75.0:
        return _spectral_estimate(time_s, signal)
    if freq_values.size >= 3 and float(np.std(freq_values)) > 5.0:
        spectral = _spectral_estimate(time_s, signal)
        if spectral is not None:
            return spectral

    return {"time": freq_times, "values": freq_values}


def _frequency_metrics(dataset: ImportedDataset, event_counts: Counter) -> dict:
    freq_arr = dataset.channels.get("freq")
    source = "channel"
    if freq_arr is None:
        source_signal = dataset.channels.get("v_an")
        if source_signal is None:
            return {
                "available": False,
                "unit": "Hz",
                "reason": "No freq channel and no V_an channel for estimation",
                "excursion_count": int(event_counts.get("freq_excursion", 0)),
            }
        estimate = _estimate_frequency_series(dataset.time, source_signal)
        if estimate is None:
            return {
                "available": False,
                "unit": "Hz",
                "reason": "Frequency could not be estimated from V_an zero crossings",
                "excursion_count": int(event_counts.get("freq_excursion", 0)),
            }
        freq_arr = estimate["values"]
        source = "estimated_from_v_an"

    freq_arr = np.asarray(freq_arr, dtype=np.float64)
    return {
        "available": True,
        "unit": "Hz",
        "source": source,
        "mean_hz": round(float(np.mean(freq_arr)), 6),
        "min_hz": round(float(np.min(freq_arr)), 6),
        "max_hz": round(float(np.max(freq_arr)), 6),
        "max_deviation_hz": round(
            float(np.max(np.abs(freq_arr - FREQUENCY_NOMINAL_HZ))), 6
        ),
        "excursion_count": int(event_counts.get("freq_excursion", 0)),
    }


def _balance_metrics(phase_metrics: dict[str, dict]) -> dict:
    if not all(phase_metrics[ch].get("available") for ch in _PHASE_VOLTAGE_CHANNELS):
        return {
            "available": False,
            "unit": "%",
            "reason": "All three phase voltages are required for imbalance metrics",
        }

    rms_values = np.asarray(
        [phase_metrics[ch]["rms"] for ch in _PHASE_VOLTAGE_CHANNELS],
        dtype=np.float64,
    )
    mean_rms = float(np.mean(rms_values))
    max_dev = float(np.max(np.abs(rms_values - mean_rms)))
    imbalance = (max_dev / mean_rms * 100.0) if mean_rms > 1e-12 else float("nan")

    return {
        "available": True,
        "unit": "%",
        "mean_phase_rms_v": round(mean_rms, 6),
        "max_rms_deviation_v": round(max_dev, 6),
        "percent_voltage_imbalance": round(float(imbalance), 6),
    }


def _current_metrics(dataset: ImportedDataset) -> dict:
    result: dict[str, dict] = {}
    for channel in _CURRENT_CHANNELS:
        result[channel] = _channel_metrics(dataset, channel, "A")
    return result


def _current_threshold_metrics(dataset: ImportedDataset, event_counts: Counter) -> dict:
    present = [dataset.channels[ch] for ch in _CURRENT_CHANNELS if ch in dataset.channels]
    if not present:
        return {
            "available": False,
            "unit": "A",
            "reason": "No phase current channels available",
            "overcurrent_count": int(event_counts.get("overcurrent", 0)),
        }

    baseline_rms: list[float] = []
    max_rms: list[float] = []
    for arr in present:
        arr = np.asarray(arr, dtype=np.float64)
        baseline_n = max(8, int(arr.size * 0.2))
        baseline_rms.append(float(compute_rms(arr[:baseline_n])))
        max_rms.append(float(compute_rms(arr)))

    baseline = float(np.mean(baseline_rms))
    measured = float(np.max(max_rms))
    threshold = baseline * 1.2 if baseline > 1e-9 else None
    return {
        "available": threshold is not None,
        "unit": "A",
        "baseline_rms_a": round(baseline, 6),
        "max_rms_a": round(measured, 6),
        "threshold_a": round(float(threshold), 6) if threshold is not None else None,
        "overcurrent_count": int(event_counts.get("overcurrent", 0)),
        "reason": None if threshold is not None else "Baseline current is near zero",
    }


def _event_counts(events: list[DetectedEvent]) -> Counter:
    return Counter(evt.kind for evt in events)


def _analysis_mode(dataset: ImportedDataset) -> tuple[str, str]:
    available = set(dataset.channels)
    if available & _VSM_MODE_CHANNELS:
        return "vsm", "VSM/GFM analysis mode"
    return "generic", "Generic data analysis mode"


def _sample_interval_s(dataset: ImportedDataset) -> float | None:
    if dataset.time.size < 2:
        return None
    diffs = np.diff(dataset.time)
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return None
    return round(float(np.median(diffs)), 9)


def compute_session_metrics(
    capsule: dict,
    events: list[DetectedEvent] | None = None,
) -> dict:
    """
    Build a deterministic engineering summary for *capsule*.
    """
    dataset = dataset_for_analysis(capsule)
    event_list = list(events) if events is not None else events_for_capsule(capsule)
    event_counts = _event_counts(event_list)

    meta = capsule.get("meta", {})
    import_meta = capsule.get("import_meta", {})
    source_path = import_meta.get("source_path") or meta.get("source_path") or ""
    source_name = os.path.basename(source_path) if source_path else meta.get(
        "session_id", "session"
    )
    analysis_mode, analysis_mode_label = _analysis_mode(dataset)
    available_canonical_channels = sorted(
        channel for channel in dataset.channels if channel in CANONICAL_SIGNALS
    )
    generic_numeric_channels = sorted(
        channel
        for channel in dataset.channels
        if channel not in _GENERIC_NUMERIC_EXCLUDES
    )
    generic_stats = {
        channel: _basic_channel_stats(dataset, channel)
        for channel in generic_numeric_channels
    }
    sample_interval_s = _sample_interval_s(dataset)

    phase_voltage = {
        channel: _channel_metrics(dataset, channel, "V", include_thd=True)
        for channel in _PHASE_VOLTAGE_CHANNELS
    }
    line_voltage = {
        channel: _channel_metrics(dataset, channel, "V")
        for channel in _LINE_VOLTAGE_CHANNELS
    }
    current = _current_metrics(dataset)
    frequency = _frequency_metrics(dataset, event_counts)
    balance = _balance_metrics(phase_voltage)
    current_thresholds = _current_threshold_metrics(dataset, event_counts)
    scale_factors = dict(import_meta.get("scale_factors") or dataset.meta.get("scale_factors", {}))

    return {
        "session": {
            "session_id": meta.get("session_id", source_name),
            "source_name": source_name,
            "source_path": source_path,
            "source_hash_sha256": dataset.meta.get("source_hash_sha256"),
            "sample_count": int(dataset.row_count),
            "sample_rate_hz": round(float(dataset.sample_rate), 6),
            "sample_interval_s": sample_interval_s,
            "time_start_s": round(float(dataset.time[0]), 6) if dataset.row_count else 0.0,
            "time_end_s": round(float(dataset.time[-1]), 6) if dataset.row_count else 0.0,
            "time_window_s": round(float(dataset.duration), 6),
            "file_type": dataset.source_type,
            "detected_time_column": dataset.meta.get("time_column"),
            "mapped_channels": sorted(
                v
                for v in import_meta.get("applied_mapping", {}).values()
                if v and v != "__unmapped__"
            ),
            "available_canonical_channels": available_canonical_channels,
            "derived_channels": sorted(
                set(dataset.meta.get("derived_channels", []))
                | set(import_meta.get("derived_channels", []))
            ),
            "generic_numeric_channels": generic_numeric_channels,
            "missing_expected_channels": sorted(
                channel for channel in _EXPECTED_VSM_CHANNELS if channel not in dataset.channels
            ),
            "raw_source_columns": list(import_meta.get("raw_headers", dataset.raw_headers)),
            "analysis_mode": analysis_mode,
            "analysis_mode_label": analysis_mode_label,
            "scale_factors": scale_factors,
            "app_version": APP_VERSION,
        },
        "phase_voltage": phase_voltage,
        "line_voltage": line_voltage,
        "current": current,
        "frequency": frequency,
        "balance": balance,
        "current_thresholds": current_thresholds,
        "generic_numeric": generic_stats,
        "events": {
            "total": len(event_list),
            "counts": {
                "voltage_sag": int(event_counts.get("voltage_sag", 0)),
                "frequency_excursion": int(event_counts.get("freq_excursion", 0)),
                "overcurrent": int(event_counts.get("overcurrent", 0)),
            },
        },
    }


def build_metric_rows(summary: dict) -> list[dict]:
    """
    Flatten a session summary into UI-friendly metric rows.
    """
    rows: list[dict] = []
    session = summary["session"]
    rows.extend(
        [
            {"section": "Session", "metric": "Source file", "value": session["source_name"], "unit": "", "note": ""},
            {"section": "Session", "metric": "Analysis mode", "value": session["analysis_mode_label"], "unit": "", "note": ""},
            {"section": "Session", "metric": "File type", "value": session["file_type"], "unit": "", "note": ""},
            {"section": "Session", "metric": "Sample count", "value": session["sample_count"], "unit": "samples", "note": ""},
            {"section": "Session", "metric": "Sample rate", "value": session["sample_rate_hz"], "unit": "Hz", "note": ""},
            {"section": "Session", "metric": "Sample interval", "value": session["sample_interval_s"] if session["sample_interval_s"] is not None else "N/A", "unit": "s", "note": ""},
            {"section": "Session", "metric": "Time window", "value": session["time_window_s"], "unit": "s", "note": ""},
            {"section": "Session", "metric": "Canonical channels", "value": ", ".join(session["available_canonical_channels"]) or "N/A", "unit": "", "note": ""},
            {"section": "Session", "metric": "Derived channels", "value": ", ".join(session["derived_channels"]) or "N/A", "unit": "", "note": ""},
        ]
    )

    for channel, info in summary["phase_voltage"].items():
        if info.get("available"):
            rows.append({"section": "Phase Voltage", "metric": f"{channel} RMS", "value": info["rms"], "unit": "V", "note": ""})
            rows.append({"section": "Phase Voltage", "metric": f"{channel} THD", "value": info["thd_pct"], "unit": "%", "note": "IEEE 519 reference 5%"})
        else:
            rows.append({"section": "Phase Voltage", "metric": f"{channel} RMS", "value": "N/A", "unit": "V", "note": info.get("reason", "")})

    for channel, info in summary["line_voltage"].items():
        if info.get("available"):
            rows.append({"section": "Line Voltage", "metric": f"{channel} RMS", "value": info["rms"], "unit": "V", "note": ""})
        else:
            rows.append({"section": "Line Voltage", "metric": f"{channel} RMS", "value": "N/A", "unit": "V", "note": info.get("reason", "")})

    freq = summary["frequency"]
    if freq.get("available"):
        rows.extend(
            [
                {"section": "Frequency", "metric": "Mean frequency", "value": freq["mean_hz"], "unit": "Hz", "note": freq.get("source", "")},
                {"section": "Frequency", "metric": "Min frequency", "value": freq["min_hz"], "unit": "Hz", "note": ""},
                {"section": "Frequency", "metric": "Max frequency", "value": freq["max_hz"], "unit": "Hz", "note": ""},
                {"section": "Frequency", "metric": "Max deviation", "value": freq["max_deviation_hz"], "unit": "Hz", "note": "vs 60 Hz nominal"},
                {"section": "Frequency", "metric": "Excursion count", "value": freq["excursion_count"], "unit": "events", "note": ""},
            ]
        )
    else:
        rows.append({"section": "Frequency", "metric": "Frequency metrics", "value": "N/A", "unit": "Hz", "note": freq.get("reason", "")})

    balance = summary["balance"]
    if balance.get("available"):
        rows.extend(
            [
                {"section": "Balance", "metric": "Max RMS deviation", "value": balance["max_rms_deviation_v"], "unit": "V", "note": ""},
                {"section": "Balance", "metric": "Voltage imbalance", "value": balance["percent_voltage_imbalance"], "unit": "%", "note": ""},
            ]
        )
    else:
        rows.append({"section": "Balance", "metric": "Voltage imbalance", "value": "N/A", "unit": "%", "note": balance.get("reason", "")})

    event_counts = summary["events"]["counts"]
    rows.extend(
        [
            {"section": "Events", "metric": "Voltage sag count", "value": event_counts["voltage_sag"], "unit": "events", "note": ""},
            {"section": "Events", "metric": "Frequency excursion count", "value": event_counts["frequency_excursion"], "unit": "events", "note": ""},
        ]
    )

    overcurrent_count = event_counts["overcurrent"]
    current_thresholds = summary["current_thresholds"]
    if current_thresholds.get("available"):
        rows.append({"section": "Events", "metric": "Overcurrent count", "value": overcurrent_count, "unit": "events", "note": f"Threshold {current_thresholds['threshold_a']} A"})
    else:
        rows.append({"section": "Events", "metric": "Overcurrent count", "value": "N/A", "unit": "events", "note": current_thresholds.get("reason", "")})

    for channel, stats in summary.get("generic_numeric", {}).items():
        if not stats.get("available"):
            rows.append({"section": "Generic Data", "metric": f"{channel}", "value": "N/A", "unit": stats.get("unit", ""), "note": stats.get("reason", "")})
            continue
        rows.extend(
            [
                {"section": "Generic Data", "metric": f"{channel} mean", "value": stats["mean"], "unit": stats.get("unit", ""), "note": ""},
                {"section": "Generic Data", "metric": f"{channel} RMS", "value": stats["rms"], "unit": stats.get("unit", ""), "note": ""},
                {"section": "Generic Data", "metric": f"{channel} min / max", "value": f"{stats['min']} / {stats['max']}", "unit": stats.get("unit", ""), "note": ""},
                {"section": "Generic Data", "metric": f"{channel} peak-to-peak", "value": stats["peak_to_peak"], "unit": stats.get("unit", ""), "note": ""},
            ]
        )

    return rows


def build_dataset_overview(capsule: dict) -> dict:
    """
    Build a screenshot-friendly overview payload for the imported dataset.
    """
    dataset = dataset_for_analysis(capsule)
    meta = capsule.get("meta", {})
    import_meta = capsule.get("import_meta", {})
    analysis_mode, analysis_mode_label = _analysis_mode(dataset)
    source_path = import_meta.get("source_path") or meta.get("source_path") or ""
    source_name = os.path.basename(source_path) if source_path else meta.get(
        "session_id", "session"
    )
    sample_interval_s = _sample_interval_s(dataset)
    available_canonical_channels = sorted(
        channel for channel in dataset.channels if channel in CANONICAL_SIGNALS
    )
    generic_numeric_channels = sorted(
        channel
        for channel in dataset.channels
        if channel not in _GENERIC_NUMERIC_EXCLUDES
    )
    derived_channels = sorted(
        set(dataset.meta.get("derived_channels", []))
        | set(import_meta.get("derived_channels", []))
    )
    mapped_channels = sorted(
        value
        for value in import_meta.get("applied_mapping", {}).values()
        if value and value != "__unmapped__"
    )
    warnings = list(capsule.get("import_meta", {}).get("warnings", []))
    scale_factors = dict(import_meta.get("scale_factors") or dataset.meta.get("scale_factors", {}))
    return {
        "source_name": source_name,
        "source_path": source_path,
        "file_type": dataset.source_type,
        "sample_count": int(dataset.row_count),
        "sample_rate_hz": round(float(dataset.sample_rate), 6),
        "sample_interval_s": sample_interval_s,
        "time_start_s": round(float(dataset.time[0]), 6) if dataset.row_count else 0.0,
        "time_end_s": round(float(dataset.time[-1]), 6) if dataset.row_count else 0.0,
        "time_window_s": round(float(dataset.duration), 6),
        "analysis_mode": analysis_mode,
        "analysis_mode_label": analysis_mode_label,
        "scale_factors": scale_factors,
        "mapped_channels": mapped_channels,
        "canonical_channels": available_canonical_channels,
        "derived_channels": derived_channels,
        "generic_numeric_channels": generic_numeric_channels,
        "missing_expected_channels": sorted(
            channel for channel in _EXPECTED_VSM_CHANNELS if channel not in dataset.channels
        ),
        "raw_source_columns": list(import_meta.get("raw_headers", dataset.raw_headers)),
        "warnings": warnings,
    }
