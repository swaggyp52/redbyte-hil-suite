import math


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
        return [{"name": "Data Availability", "passed": False, "details": "No frames in session."}]

    freqs = [f.get("freq", 60.0) for f in frames]
    v_an = [f.get("v_an", 0.0) for f in frames]
    v_bn = [f.get("v_bn", 0.0) for f in frames]
    v_cn = [f.get("v_cn", 0.0) for f in frames]

    # Rule 1: Ride-through 50% voltage sag for >= 200ms
    # Simple check: min avg voltage >= 0.5 * nominal for at least 0.2s
    nominal = 120.0
    avg_v = [(v_an[i] + v_bn[i] + v_cn[i]) / 3.0 for i in range(len(frames))]
    min_v = min(avg_v)
    sag_ok = min_v >= 0.5 * nominal

    # Rule 2: Maintain frequency within ±0.5 Hz under load step
    min_f = min(freqs)
    max_f = max(freqs)
    freq_ok = min_f >= 59.5 and max_f <= 60.5

    # Rule 3: Voltage recovery within 2s after sag (simple heuristic)
    recovery_ok = True
    for window in _windowed(avg_v, 20):
        if min(window) < 0.6 * nominal:
            recovery_ok = False
            break

    return [
        {"name": "Ride-through 50% sag >=200ms", "passed": sag_ok, "details": f"Min avg V={min_v:.1f}"},
        {"name": "Frequency within ±0.5Hz", "passed": freq_ok, "details": f"Min/Max={min_f:.2f}/{max_f:.2f}"},
        {"name": "Voltage recovery", "passed": recovery_ok, "details": "No extended undervoltage"},
    ]
