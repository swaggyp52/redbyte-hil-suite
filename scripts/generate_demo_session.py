"""
Generate a canonical demo session JSON for use without hardware.

Produces: data/demo_sessions/demo_session_baseline.json
  - ~300 frames at ~20 Hz covering:
      frames   0– 49: healthy baseline (60 Hz, balanced 3-phase)
      frames  50–109: voltage sag 50% (fault_type="sag")
      frames 110–179: post-sag recovery ramp
      frames 180–239: frequency drift +2 Hz (fault_type="drift")
      frames 240–299: recovery back to 60 Hz
  - insights list with relevant InsightEvent dicts
"""

from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "data" / "demo_sessions"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

def _phase_voltages(t: float, freq: float, v_peak: float) -> tuple[float, float, float]:
    w = 2 * math.pi * freq
    return (
        v_peak * math.sin(w * t),
        v_peak * math.sin(w * t - 2 * math.pi / 3),
        v_peak * math.sin(w * t + 2 * math.pi / 3),
    )


def _phase_currents(t: float, freq: float, i_peak: float) -> tuple[float, float, float]:
    w = 2 * math.pi * freq
    phi = math.radians(5)  # small current lag
    return (
        i_peak * math.sin(w * t - phi),
        i_peak * math.sin(w * t - phi - 2 * math.pi / 3),
        i_peak * math.sin(w * t - phi + 2 * math.pi / 3),
    )


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------

SAMPLE_RATE = 20.0  # frames / second
V_NOMINAL_PEAK = 120.0 * math.sqrt(2)  # 120 V RMS → ~169.7 V peak
I_NOMINAL_PEAK = 10.0 * math.sqrt(2)   # 10 A RMS peak
P_MECH_NOMINAL = 5000.0                 # W

def make_frame(
    idx: int,
    t_offset: float,
    freq: float,
    v_scale: float = 1.0,
    fault_type: str | None = None,
) -> dict:
    t = t_offset + idx / SAMPLE_RATE
    v_an, v_bn, v_cn = _phase_voltages(t, freq, V_NOMINAL_PEAK * v_scale)
    i_a, i_b, i_c = _phase_currents(t, freq, I_NOMINAL_PEAK)
    frame: dict = {
        "ts": round(t, 6),
        "v_an": round(v_an, 4),
        "v_bn": round(v_bn, 4),
        "v_cn": round(v_cn, 4),
        "i_a": round(i_a, 4),
        "i_b": round(i_b, 4),
        "i_c": round(i_c, 4),
        "freq": round(freq, 4),
        "p_mech": round(P_MECH_NOMINAL * v_scale, 2),
    }
    if fault_type:
        frame["fault_type"] = fault_type
    return frame


def lerp(a: float, b: float, frac: float) -> float:
    return a + (b - a) * frac


# ---------------------------------------------------------------------------
# Build frames
# ---------------------------------------------------------------------------

frames: list[dict] = []
t0 = time.time() - 300 / SAMPLE_RATE  # session started 15 s ago

# Phase 0: healthy baseline (0–49)
for i in range(50):
    frames.append(make_frame(len(frames), t0, freq=60.0))

# Phase 1: 50% voltage sag (50–109)
for i in range(60):
    frames.append(make_frame(len(frames), t0, freq=60.0, v_scale=0.5, fault_type="sag"))

# Phase 2: post-sag recovery ramp V 0.5→1.0 (110–179)
for i in range(70):
    v_scale = lerp(0.5, 1.0, i / 69)
    frames.append(make_frame(len(frames), t0, freq=60.0, v_scale=round(v_scale, 3)))

# Phase 3: frequency drift 60→62 Hz (180–239)
for i in range(60):
    freq = lerp(60.0, 62.0, i / 59)
    frames.append(make_frame(len(frames), t0, freq=round(freq, 4), fault_type="drift"))

# Phase 4: frequency recovery 62→60 Hz (240–299)
for i in range(60):
    freq = lerp(62.0, 60.0, i / 59)
    frames.append(make_frame(len(frames), t0, freq=round(freq, 4)))

# ---------------------------------------------------------------------------
# Build insights
# ---------------------------------------------------------------------------

insights: list[dict] = [
    {
        "ts": frames[50]["ts"],
        "type": "voltage_sag",
        "severity": "critical",
        "description": "Phase A voltage dropped to 50% nominal (sag fault injected)",
        "metrics": {"v_rms": round(V_NOMINAL_PEAK * 0.5 / math.sqrt(2), 2)},
        "phase": "A",
    },
    {
        "ts": frames[110]["ts"],
        "type": "voltage_recovery",
        "severity": "info",
        "description": "Voltage sag cleared — ramp recovery started",
        "metrics": {},
        "phase": "A",
    },
    {
        "ts": frames[180]["ts"],
        "type": "frequency_drift",
        "severity": "warning",
        "description": "Frequency drift detected — rising toward 62 Hz",
        "metrics": {"freq_hz": 60.0},
        "phase": None,
    },
    {
        "ts": frames[210]["ts"],
        "type": "frequency_exceeded",
        "severity": "critical",
        "description": "Frequency exceeded 61 Hz — outside IEEE 2800 ride-through band",
        "metrics": {"freq_hz": round(lerp(60.0, 62.0, 30 / 59), 4)},
        "phase": None,
    },
    {
        "ts": frames[240]["ts"],
        "type": "frequency_recovery",
        "severity": "info",
        "description": "Frequency returning to 60 Hz nominal",
        "metrics": {},
        "phase": None,
    },
]

# ---------------------------------------------------------------------------
# Assemble session document
# ---------------------------------------------------------------------------

start_ts = frames[0]["ts"]
end_ts = frames[-1]["ts"]
duration = end_ts - start_ts
sample_rate_estimate = round(len(frames) / duration, 2) if duration > 0 else SAMPLE_RATE

session = {
    "meta": {
        "version": "1.2",
        "session_id": str(uuid.uuid4()),
        "start_time": start_ts,
        "frame_count": len(frames),
        "sample_rate_estimate": sample_rate_estimate,
        "channels": ["v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "freq", "p_mech"],
        "description": "Demo session — baseline + sag + frequency drift (no hardware required)",
        "generated_by": "generate_demo_session.py",
    },
    "frames": frames,
    "insights": insights,
    "events": [],
}

out_path = OUT_DIR / "demo_session_baseline.json"
with open(out_path, "w") as f:
    json.dump(session, f, indent=2)

print(f"✅  Demo session written → {out_path}")
print(f"    {len(frames)} frames  |  {len(insights)} insights  |  {duration:.2f}s duration")
