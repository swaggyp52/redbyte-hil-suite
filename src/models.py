"""
Canonical data models and normalisation helpers for RedByte HIL Suite.

    normalize_frame()     – normalise raw frames into TelemetryFrame schema
    make_insight_event()  – build canonical InsightEvent dicts

Canonical TelemetryFrame keys
  Required : ts, v_an, v_bn, v_cn, i_a, i_b, i_c, freq, p_mech
  Optional : angle (degrees), v_rms, i_rms, thd, q, s, pf, fault_type, status

Canonical InsightEvent keys
  Required : ts, type, severity, description
  Optional : metrics (dict), phase (str)
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TelemetryFrame
# ---------------------------------------------------------------------------

_REQUIRED_FLOAT_KEYS: tuple[str, ...] = (
    "v_an", "v_bn", "v_cn",
    "i_a",  "i_b",  "i_c",
    "freq", "p_mech",
)

# Maps legacy or non-canonical keys → canonical key.
# Includes aliases from the real Arduino firmware (t_ms, vdc, p_kw, q_kvar)
# so that SerialAdapter frames are correctly normalized without extra logic.
_KEY_ALIASES: dict[str, str] = {
    "timestamp": "ts",
    "time":      "ts",
    # Arduino firmware (GFM_Telemetry_v1/v3): t_ms is milliseconds; the
    # normalize_frame caller must convert to seconds — handled below via the
    # _POST_CONVERT map rather than a simple rename.
    # We still alias it so the key arrives as "ts"; conversion happens after.
    "t_ms":      "ts",
    # voltage
    "v_a":  "v_an",
    "v_b":  "v_bn",
    "v_c":  "v_cn",
    "Va":   "v_an",
    "Vb":   "v_bn",
    "Vc":   "v_cn",
    # Arduino DC bus voltage.  Maps to v_dc rather than v_an because the
    # real breadboard hardware only measures DC link, not phase voltages.
    "vdc":  "v_dc",
    # current
    "Ia":   "i_a",
    "Ib":   "i_b",
    "Ic":   "i_c",
    "i_an": "i_a",
    "i_bn": "i_b",
    "i_cn": "i_c",
    # power — Arduino sends kW; conversion factor applied in normalize_frame
    "p_kw":   "p_mech",
    "p":      "p_mech",
    "p_w":    "p_mech",
    # reactive power — Arduino sends kVAR
    "q_kvar": "q",
    # frequency
    "frequency": "freq",
    "f":    "freq",
    "Freq": "freq",
    # fault
    "fault": "status",
}

_WARNED_MISSING: set[str] = set()

# Unit-conversion scale factors applied BEFORE key aliasing, keyed by the
# original (pre-alias) field name.
# - Arduino millis() timestamps arrive as t_ms; convert to seconds.
# - Arduino reports power in kW and reactive power in kVAR; convert to W/VAR.
_PRE_ALIAS_SCALE: dict[str, float] = {
    "t_ms":   1e-3,    # ms → s
    "p_kw":   1e3,     # kW → W
    "q_kvar": 1e3,     # kVAR → VAR
}


def normalize_frame(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw telemetry dict into the canonical TelemetryFrame schema.

    * Applies pre-alias unit scaling (t_ms → ts in seconds, p_kw → p_mech in
      watts, q_kvar → q in VAR).
    * Renames keys via ``_KEY_ALIASES`` (does not mutate the input dict).
    * Ensures ``ts`` is present and positive; falls back to ``time.time()``.
    * Fills missing *required* numeric keys with ``0.0`` and emits a one-time
      log warning per missing key.

    Returns a **new** dict.  Extra non-canonical keys are preserved so callers
    can still access pass-through fields (e.g. ``angle``, ``fault_type``).
    """
    frame: dict[str, Any] = {}

    # 1. Apply pre-alias scaling then rename
    for raw_key, value in raw.items():
        scale = _PRE_ALIAS_SCALE.get(raw_key)
        if scale is not None:
            try:
                value = float(value) * scale
            except (TypeError, ValueError):
                pass
        canonical = _KEY_ALIASES.get(raw_key, raw_key)
        if canonical not in frame or raw_key == canonical:
            frame[canonical] = value

    # 2. Validate / fill ts
    ts_val = frame.get("ts")
    if not isinstance(ts_val, (int, float)) or ts_val <= 0:
        frame["ts"] = time.time()

    # 3. Fill missing required floats
    for key in _REQUIRED_FLOAT_KEYS:
        if key not in frame:
            if key not in _WARNED_MISSING:
                logger.warning(
                    "normalize_frame: missing key '%s', defaulting to 0.0", key
                )
                _WARNED_MISSING.add(key)
            frame[key] = 0.0
        else:
            try:
                frame[key] = float(frame[key])
            except (TypeError, ValueError):
                frame[key] = 0.0

    return frame


# ---------------------------------------------------------------------------
# InsightEvent
# ---------------------------------------------------------------------------

_VALID_SEVERITIES: frozenset[str] = frozenset(("info", "warning", "critical"))


def make_insight_event(
    ts: float,
    event_type: str,
    description: str,
    severity: str = "info",
    metrics: Optional[dict[str, Any]] = None,
    phase: Optional[str] = None,
) -> dict[str, Any]:
    """Build a canonical InsightEvent dict.

    Args:
        ts:          Timestamp (seconds, matching TelemetryFrame.ts scale).
        event_type:  Category string, e.g. ``'thd'``, ``'frequency'``,
                     ``'unbalance'``, ``'fault'``.
        description: Short human-readable string for the InsightsPanel UI.
        severity:    One of ``'info' | 'warning' | 'critical'``.
        metrics:     Optional supporting numeric values.
        phase:       Optional phase identifier (``'A'``, ``'B'``, ``'C'``).

    Returns:
        dict with keys: ts, type, severity, description, metrics, phase
    """
    if severity not in _VALID_SEVERITIES:
        logger.warning(
            "make_insight_event: invalid severity '%s', using 'info'", severity
        )
        severity = "info"

    return {
        "ts":          float(ts),
        "type":        str(event_type),
        "severity":    severity,
        "description": str(description),
        "metrics":     dict(metrics) if metrics else {},
        "phase":       phase,
    }
