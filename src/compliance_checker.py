import math


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


def _windowed(values, window):
    if window <= 0:
        return []
    return [values[i:i + window] for i in range(0, len(values) - window + 1, window)]


def evaluate_ieee_2800(session_data):
    """
    Basic IEEE 2800-inspired compliance checks (stubbed, domain-tunable).
    Returns list of dicts with name, passed, details.
    """
    frames = session_data.get("frames", [])
    if not frames:
        frames = _frames_from_waveform_context(session_data)
    if not frames:
        return [{"name": "Data Availability", "passed": False, "details": "No frames in session."}]

    freqs = [f.get("freq", 60.0) for f in frames]
    v_an = [f.get("v_an", 0.0) for f in frames]
    v_bn = [f.get("v_bn", 0.0) for f in frames]
    v_cn = [f.get("v_cn", 0.0) for f in frames]

    # Rule 1: Ride-through 50% voltage sag for >= 200ms
    # Use average absolute phase magnitude for instantaneous 3-phase samples.
    avg_abs_v = [
        (abs(v_an[i]) + abs(v_bn[i]) + abs(v_cn[i])) / 3.0
        for i in range(len(frames))
    ]
    nominal = max(avg_abs_v) if avg_abs_v else 120.0
    min_v = min(avg_abs_v) if avg_abs_v else 0.0
    sag_ok = min_v >= 0.5 * nominal

    # Rule 2: Maintain frequency within ±0.5 Hz under load step
    min_f = min(freqs)
    max_f = max(freqs)
    freq_ok = min_f >= 59.5 and max_f <= 60.5

    # Rule 3: Voltage recovery within 2s after sag (simple heuristic)
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
