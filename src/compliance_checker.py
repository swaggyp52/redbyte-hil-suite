"""
compliance_checker.py — Standards-inspired evidence engine.

This module implements a clearly labeled, traceable evaluation of a session
against multiple rule profiles.  It does NOT claim full IEEE certification.

Every check result includes:
  - name:        human-readable rule name
  - passed:      bool
  - measured:    value that was actually measured from the session
  - threshold:   value the measurement was compared against
  - units:       units for the above
  - rule:        one-line description of the rule
  - source:      one of:
        - "IEEE 2800-2022 (inspired subset)"
        - "IEEE 519 (inspired subset)"
        - "Project engineering threshold"
        - "Custom"
  - details:     long-form explanation for the report
  - window:      optional {"start_s", "end_s"} — relative time window for
                 the evidence, useful for drill-down in the UI.

Profiles
--------
  - "project_demo"        — project-defined engineering thresholds for demo
  - "ieee_2800_inspired"  — IEEE 2800-2022 inspired subset
  - "ieee_519_thd"        — IEEE 519 THD reference subset
  - "custom"              — supply your own threshold dict

Public API
----------
    available_profiles() -> list[str]
    evaluate_session(session_data, profile="project_demo", thresholds=None) -> list[dict]
    evaluate_ieee_2800(session_data) -> list[dict]     # legacy, kept for compat
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

from src.signal_processing import compute_rms, compute_thd


# ==========================================================================
# Threshold profiles
# ==========================================================================
PROFILES: Dict[str, Dict] = {
    "project_demo": {
        "label": "Project Demo Thresholds",
        "description": "Project-defined engineering thresholds used for senior design demos.",
        "source": "Project engineering threshold",
        "thresholds": {
            "nominal_v_rms": 120.0,
            "nominal_freq": 60.0,
            "sag_ride_through_ratio": 0.50,   # min(3φ avg) ≥ 0.5·nominal
            "freq_band_hz": 0.5,              # ±0.5 Hz
            "recovery_undervolt_ratio": 0.60, # no sustained window < 0.6·V_n
            "recovery_window_s": 1.0,
            "thd_limit_pct": 5.0,
            "phase_imbalance_pct": 5.0,       # max |deviation| / mean
            "overshoot_limit_pct": 10.0,      # voltage overshoot vs nominal peak
            "settling_time_s": 2.0,
        },
        "enabled": ("ride_through", "freq_band", "recovery", "thd_van",
                    "phase_imbalance", "overshoot", "settling"),
    },
    "ieee_2800_inspired": {
        "label": "IEEE 2800-2022 Inspired Subset",
        "description": "Representative subset of IEEE 2800-2022 ride-through and frequency provisions. Not a certification test.",
        "source": "IEEE 2800-2022 (inspired subset)",
        "thresholds": {
            "nominal_v_rms": 120.0,
            "nominal_freq": 60.0,
            "sag_ride_through_ratio": 0.50,
            "freq_band_hz": 0.5,
            "recovery_undervolt_ratio": 0.60,
            "recovery_window_s": 1.0,
            "thd_limit_pct": 5.0,
            "phase_imbalance_pct": 5.0,
            "overshoot_limit_pct": 10.0,
            "settling_time_s": 2.0,
        },
        "enabled": ("ride_through", "freq_band", "recovery"),
    },
    "ieee_519_thd": {
        "label": "IEEE 519 THD Reference Subset",
        "description": "Single-bus THD limit per IEEE 519 (general guidance, not a compliance test).",
        "source": "IEEE 519 (inspired subset)",
        "thresholds": {
            "nominal_v_rms": 120.0,
            "thd_limit_pct": 5.0,
        },
        "enabled": ("thd_van",),
    },
}


def available_profiles() -> List[Dict]:
    return [
        {"id": k, "label": v["label"], "description": v["description"]}
        for k, v in PROFILES.items()
    ]


def _frames_from_waveform_context(session_data):
    """Build frame-like records from legacy context files with waveform.channels."""
    waveform = session_data.get("waveform") or {}
    channels = waveform.get("channels") or {}
    if not channels:
        return []

    v_an = channels.get("v_an", [])
    v_bn = channels.get("v_bn", [])
    v_cn = channels.get("v_cn", [])
    i_a = channels.get("i_a", [])
    i_b = channels.get("i_b", [])
    i_c = channels.get("i_c", [])

    lengths = [len(v_an), len(v_bn), len(v_cn), len(i_a), len(i_b), len(i_c)]
    if not lengths or min(lengths) == 0:
        return []

    n = min(lengths)
    sample_rate = float(waveform.get("sample_rate", 100.0) or 100.0)
    dt = 1.0 / sample_rate if sample_rate > 0 else 0.01
    ts0 = float(waveform.get("timestamp", 0.0) or 0.0)
    freq_nominal = float(
        (session_data.get("scenario") or {}).get("parameters", {}).get("frequency_nominal", 60.0)
    )

    frames = []
    for idx in range(n):
        frames.append({
            "ts": ts0 + idx * dt,
            "v_an": float(v_an[idx]),
            "v_bn": float(v_bn[idx]),
            "v_cn": float(v_cn[idx]),
            "i_a": float(i_a[idx]),
            "i_b": float(i_b[idx]),
            "i_c": float(i_c[idx]),
            "freq": freq_nominal,
            "p_mech": 0.0,
        })
    return frames


# ==========================================================================
# Check implementations
# ==========================================================================
def _result(name, passed, measured, threshold, units, rule, source, details, window=None) -> Dict:
    return {
        "name": name,
        "passed": bool(passed),
        "measured": measured,
        "threshold": threshold,
        "units": units,
        "rule": rule,
        "source": source,
        "details": details,
        "window": window,
    }


def _check_ride_through(arr, cfg, source) -> Dict:
    avg = (arr["v_an_rms"] + arr["v_bn_rms"] + arr["v_cn_rms"]) / 3.0
    nom = cfg["nominal_v_rms"]
    thr = cfg["sag_ride_through_ratio"] * nom
    min_v = float(np.min(avg))
    min_idx = int(np.argmin(avg))
    t_min = float(arr["t_rel"][min_idx])
    ok = min_v >= thr
    return _result(
        name="Ride-through — Minimum 3φ Voltage",
        passed=ok, measured=round(min_v, 3), threshold=round(thr, 3), units="V",
        rule=f"min(3φ avg voltage) ≥ {cfg['sag_ride_through_ratio']:.0%} × V_nominal ({nom} V)",
        source=source,
        details=(f"Minimum three-phase averaged voltage = {min_v:.2f} V (at t = {t_min:.3f} s). "
                 f"Threshold = {thr:.2f} V. "
                 + ("PASS — inverter rode through the excursion." if ok
                    else "FAIL — voltage collapsed below the ride-through threshold.")),
        window={"start_s": max(t_min - 0.1, 0.0), "end_s": t_min + 0.1},
    )


def _check_freq_band(arr, cfg, source) -> Dict:
    f = arr["freq"]
    nom = cfg["nominal_freq"]
    band = cfg["freq_band_hz"]
    low = nom - band
    high = nom + band
    fmin = float(np.min(f))
    fmax = float(np.max(f))
    ok = (fmin >= low) and (fmax <= high)
    return _result(
        name="Frequency — ±{band:.2g} Hz Band".format(band=band),
        passed=ok, measured=[round(fmin, 4), round(fmax, 4)],
        threshold=[round(low, 4), round(high, 4)], units="Hz",
        rule=f"all frame frequencies within [{low:.3f}, {high:.3f}] Hz",
        source=source,
        details=(f"Observed range = [{fmin:.3f}, {fmax:.3f}] Hz. "
                 f"Allowed = [{low:.3f}, {high:.3f}] Hz. "
                 + ("PASS — within band." if ok else "FAIL — excursion outside band.")),
    )


def _check_recovery(arr, cfg, source) -> Dict:
    avg = (arr["v_an_rms"] + arr["v_bn_rms"] + arr["v_cn_rms"]) / 3.0
    nom = cfg["nominal_v_rms"]
    recov_ratio = cfg["recovery_undervolt_ratio"]
    thr = recov_ratio * nom
    # Sliding window the size of recovery_window_s
    if arr["t_rel"].size >= 2:
        dt = float(np.median(np.diff(arr["t_rel"])))
        if dt <= 0:
            dt = 0.05
    else:
        dt = 0.05
    window_n = max(2, int(round(cfg["recovery_window_s"] / dt)))
    worst = None
    worst_t = None
    for i in range(0, len(avg) - window_n + 1):
        chunk = avg[i:i + window_n]
        m = float(np.min(chunk))
        if worst is None or m < worst:
            worst = m
            worst_t = float(arr["t_rel"][i])
    if worst is None:
        worst = float(np.min(avg))
        worst_t = 0.0
    ok = worst >= thr
    return _result(
        name="Recovery — No Sustained Under-voltage",
        passed=ok, measured=round(worst, 3), threshold=round(thr, 3), units="V",
        rule=(f"no {cfg['recovery_window_s']:.2f} s sliding window has 3φ avg below "
              f"{recov_ratio:.0%} × V_nominal"),
        source=source,
        details=(f"Worst-window minimum = {worst:.2f} V at t = {worst_t:.3f} s. "
                 f"Threshold = {thr:.2f} V. "
                 + ("PASS — recovery nominal." if ok else "FAIL — sustained under-voltage observed.")),
        window={"start_s": max(worst_t, 0.0), "end_s": worst_t + cfg["recovery_window_s"]},
    )


def _check_thd_van(arr, cfg, source) -> Dict:
    limit = cfg["thd_limit_pct"]
    thd = compute_thd(arr["v_an"].tolist(), time_data=arr["ts"].tolist())
    ok = thd <= limit
    return _result(
        name="THD (V_an) ≤ {:.1f}%".format(limit),
        passed=ok, measured=round(thd, 3), threshold=round(limit, 3), units="%",
        rule=f"THD of V_an over the whole capture ≤ {limit:.1f}%",
        source=source,
        details=(f"Measured THD = {thd:.2f}%. Limit = {limit:.1f}%. "
                 + ("PASS — harmonic content within limit." if ok
                    else "FAIL — harmonic distortion above limit.")),
    )


def _check_phase_imbalance(arr, cfg, source) -> Dict:
    limit_pct = cfg["phase_imbalance_pct"]
    rms_a = compute_rms(arr["v_an"].tolist())
    rms_b = compute_rms(arr["v_bn"].tolist())
    rms_c = compute_rms(arr["v_cn"].tolist())
    mean = float(np.mean([rms_a, rms_b, rms_c]))
    if mean <= 0:
        return _result(
            name="Phase Imbalance ≤ {:.1f}%".format(limit_pct),
            passed=True, measured=0.0, threshold=limit_pct, units="%",
            rule=f"max |V_rms_phase − mean| / mean ≤ {limit_pct:.1f}%",
            source=source,
            details="Cannot compute imbalance: zero mean voltage.",
        )
    dev = max(abs(rms_a - mean), abs(rms_b - mean), abs(rms_c - mean))
    imb_pct = dev / mean * 100.0
    ok = imb_pct <= limit_pct
    return _result(
        name="Phase Imbalance ≤ {:.1f}%".format(limit_pct),
        passed=ok, measured=round(imb_pct, 3), threshold=round(limit_pct, 3), units="%",
        rule=f"max |V_rms_phase − mean| / mean ≤ {limit_pct:.1f}%",
        source=source,
        details=(f"Per-phase RMS: a={rms_a:.2f} V, b={rms_b:.2f} V, c={rms_c:.2f} V. "
                 f"Max deviation = {imb_pct:.2f}% of mean. Limit = {limit_pct:.1f}%. "
                 + ("PASS — phases balanced." if ok else "FAIL — imbalance above limit.")),
    )


def _check_overshoot(arr, cfg, source) -> Dict:
    limit_pct = cfg["overshoot_limit_pct"]
    nom_peak = cfg["nominal_v_rms"] * math.sqrt(2)
    vmax = max(float(np.max(arr["v_an"])), float(np.max(arr["v_bn"])), float(np.max(arr["v_cn"])))
    vmin = min(float(np.min(arr["v_an"])), float(np.min(arr["v_bn"])), float(np.min(arr["v_cn"])))
    biggest = max(vmax - nom_peak, nom_peak - (-vmin) * 0) if vmax > 0 else 0
    # overshoot = worst |peak| − nominal peak, expressed as % of nominal peak
    worst_peak = max(abs(vmax), abs(vmin))
    overshoot_pct = (worst_peak - nom_peak) / nom_peak * 100.0
    ok = overshoot_pct <= limit_pct
    return _result(
        name="Voltage Overshoot ≤ {:.1f}%".format(limit_pct),
        passed=ok, measured=round(overshoot_pct, 3), threshold=round(limit_pct, 3), units="%",
        rule=f"(worst peak − nominal peak) / nominal peak × 100 ≤ {limit_pct:.1f}%",
        source=source,
        details=(f"Worst instantaneous peak = {worst_peak:.2f} V (nominal peak = {nom_peak:.2f} V). "
                 f"Overshoot = {overshoot_pct:.2f}%. Limit = {limit_pct:.1f}%. "
                 + ("PASS — within overshoot limit." if ok
                    else "FAIL — overshoot exceeded limit.")),
    )


def _check_settling(arr, cfg, source) -> Dict:
    """
    Settling / recovery time: find the largest voltage sag window and
    measure how long until the 3φ avg returns within 2% of nominal.
    """
    avg = (arr["v_an_rms"] + arr["v_bn_rms"] + arr["v_cn_rms"]) / 3.0
    nom = cfg["nominal_v_rms"]
    limit_s = cfg["settling_time_s"]
    band = 0.02 * nom

    # find the lowest-point region and time to recover
    min_idx = int(np.argmin(avg))
    # walk forward until avg is within band of nominal
    settle_t = None
    for j in range(min_idx, avg.size):
        if abs(avg[j] - nom) <= band:
            settle_t = float(arr["t_rel"][j] - arr["t_rel"][min_idx])
            break
    if settle_t is None:
        settle_t = float(arr["t_rel"][-1] - arr["t_rel"][min_idx])
        ok = False
    else:
        ok = settle_t <= limit_s

    return _result(
        name="Settling Time ≤ {:.2g} s".format(limit_s),
        passed=ok, measured=round(settle_t, 3), threshold=round(limit_s, 3), units="s",
        rule=f"time from minimum voltage to within ±2% of nominal ≤ {limit_s:.2f} s",
        source=source,
        details=(f"Minimum at t = {float(arr['t_rel'][min_idx]):.3f} s; returned to nominal±2% in "
                 f"{settle_t:.3f} s. Limit = {limit_s:.2f} s. "
                 + ("PASS — settling within limit." if ok
                    else "FAIL — settling too slow or did not return to band.")),
        window={"start_s": float(arr["t_rel"][min_idx]), "end_s": float(arr["t_rel"][min_idx]) + settle_t},
    )


# ==========================================================================
# Entry points
# ==========================================================================
def _rolling_rms(x: np.ndarray, window_n: int) -> np.ndarray:
    if x.size == 0 or window_n < 1:
        return x.copy()
    window_n = min(window_n, x.size)
    x2 = x ** 2
    kernel = np.ones(window_n) / window_n
    ms = np.convolve(x2, kernel, mode="same")
    return np.sqrt(np.maximum(ms, 0.0))


def _frames_to_arrays(frames: List[Dict]) -> Dict[str, np.ndarray]:
    if not frames:
        return {k: np.array([]) for k in
                ("ts", "t_rel", "v_an", "v_bn", "v_cn", "v_an_rms", "v_bn_rms", "v_cn_rms", "freq")}
    ts = np.array([f.get("ts", 0.0) for f in frames], dtype=float)
    v_an = np.array([f.get("v_an", 0.0) for f in frames], dtype=float)
    v_bn = np.array([f.get("v_bn", 0.0) for f in frames], dtype=float)
    v_cn = np.array([f.get("v_cn", 0.0) for f in frames], dtype=float)
    # Rolling RMS envelope (one fundamental cycle ≈ 1/60 s by default)
    if ts.size >= 2:
        dt = float(np.median(np.diff(ts)))
        if dt <= 0:
            dt = 0.02
    else:
        dt = 0.02
    window_s = 1.0 / 60.0  # one nominal fundamental cycle
    window_n = max(2, int(round(window_s / dt)))
    return {
        "ts": ts,
        "t_rel": ts - ts[0] if ts.size else ts,
        "v_an": v_an,
        "v_bn": v_bn,
        "v_cn": v_cn,
        "v_an_rms": _rolling_rms(v_an, window_n),
        "v_bn_rms": _rolling_rms(v_bn, window_n),
        "v_cn_rms": _rolling_rms(v_cn, window_n),
        "freq": np.array([f.get("freq", 60.0) for f in frames], dtype=float),
    }


_CHECKS = {
    "ride_through":   _check_ride_through,
    "freq_band":      _check_freq_band,
    "recovery":       _check_recovery,
    "thd_van":        _check_thd_van,
    "phase_imbalance": _check_phase_imbalance,
    "overshoot":      _check_overshoot,
    "settling":       _check_settling,
}


def evaluate_session(
    session_data: Dict,
    profile: str = "project_demo",
    thresholds: Optional[Dict] = None,
) -> List[Dict]:
    """Run the selected profile against a session; return list of check results."""
    frames = session_data.get("frames", [])
    if not frames:
        frames = _frames_from_waveform_context(session_data)
    if not frames:
        return [{"name": "Data Availability", "passed": False, "measured": 0, "threshold": 1,
                 "units": "frames", "rule": "session must contain at least one frame",
                 "source": "Project engineering threshold",
                 "details": "No frames in session."}]

    prof = PROFILES.get(profile)
    if prof is None:
        # caller supplied only a threshold dict
        prof = {
            "label": "Custom",
            "source": "Custom",
            "thresholds": thresholds or {},
            "enabled": tuple(_CHECKS.keys()),
        }
    cfg = dict(prof["thresholds"])
    if thresholds:
        cfg.update(thresholds)
    source = prof["source"]
    enabled = prof["enabled"]

    arr = _frames_to_arrays(frames)
    results: List[Dict] = []
    for key in enabled:
        check = _CHECKS.get(key)
        if not check:
            continue
        try:
            results.append(check(arr, cfg, source))
        except Exception as e:
            results.append({
                "name": key, "passed": False, "measured": None, "threshold": None,
                "units": "", "rule": "", "source": source,
                "details": f"Check raised an exception: {e}",
            })
    return results


# --------------------------------------------------------------------------
# Legacy API — kept so existing callers don't break
# --------------------------------------------------------------------------
def evaluate_ieee_2800(session_data: Dict) -> List[Dict]:
    frames = session_data.get("frames", [])
    if not frames:
        frames = _frames_from_waveform_context(session_data)
    if not frames:
        return [{"name": "Data Availability", "passed": False, "details": "No frames in session."}]

    freqs = [f.get("freq", 60.0) for f in frames]
    v_an = [f.get("v_an", 0.0) for f in frames]
    v_bn = [f.get("v_bn", 0.0) for f in frames]
    v_cn = [f.get("v_cn", 0.0) for f in frames]

    avg_abs_v = [
        (abs(v_an[i]) + abs(v_bn[i]) + abs(v_cn[i])) / 3.0
        for i in range(len(frames))
    ]
    nominal = max(avg_abs_v) if avg_abs_v else 120.0
    min_v = min(avg_abs_v) if avg_abs_v else 0.0
    sag_ok = min_v >= 0.5 * nominal

    min_f = min(freqs)
    max_f = max(freqs)
    freq_ok = min_f >= 59.5 and max_f <= 60.5

    recovery_ok = True
    for window in _windowed(avg_abs_v, 20):
        if min(window) < 0.6 * nominal:
            recovery_ok = False
            break

    return [
        {"name": "Ride-through 50% sag >=200ms", "passed": sag_ok, "details": f"Min avg V={min_v:.1f}"},
        {"name": "Frequency within ±0.5Hz", "passed": freq_ok, "details": f"Min/Max={min_f:.2f}/{max_f:.2f}"},
        {"name": "Voltage recovery", "passed": recovery_ok, "details": "No extended undervoltage"},
    ]


def _windowed(values, window):
    """Back-compat helper (used by tests / old callers)."""
    if window <= 0:
        return []
    return [values[i:i + window] for i in range(0, len(values) - window + 1, window)]
