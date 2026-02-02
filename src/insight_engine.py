import json
import time
import collections
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from src.signal_processing import compute_thd, extract_three_phase_phasors


@dataclass
class InsightEvent:
    ts: float
    kind: str
    description: str


class InsightEngine(QObject):
    insight_emitted = pyqtSignal(dict)

    def __init__(self, log_path="data/insights_log.json"):
        super().__init__()
        self.log_path = log_path
        self._buf = collections.deque(maxlen=200)
        self._ts = collections.deque(maxlen=200)
        self._freq = collections.deque(maxlen=200)
        self._va = collections.deque(maxlen=200)
        self._vb = collections.deque(maxlen=200)
        self._vc = collections.deque(maxlen=200)
        self._active_fault_ts = None
        self._insights = []
        self._last_emit = {}
        self._debounce_s = 0.6

    def update(self, frame):
        ts = frame.get("ts", time.time())
        self._ts.append(ts)
        self._freq.append(frame.get("freq", 60.0))
        self._va.append(frame.get("v_an", 0.0))
        self._vb.append(frame.get("v_bn", 0.0))
        self._vc.append(frame.get("v_cn", 0.0))

        fault_type = frame.get("fault_type")
        if fault_type and self._active_fault_ts is None:
            self._active_fault_ts = ts
        if not fault_type and self._active_fault_ts is not None:
            self._active_fault_ts = None

        self._detect(ts)

    def _emit(self, ts, kind, description):
        last = self._last_emit.get(kind, 0)
        if ts - last < self._debounce_s:
            return
        self._last_emit[kind] = ts
        payload = {"ts": ts, "type": kind, "description": description}
        self._insights.append(payload)
        self.insight_emitted.emit(payload)
        self._persist()

    def _persist(self):
        try:
            with open(self.log_path, "w") as f:
                json.dump({"insights": self._insights}, f, indent=2)
        except Exception:
            pass

    def _detect(self, ts):
        if len(self._va) < 40:
            return

        # Harmonic Bloom: THD rises >10% within 0.5s
        thd = compute_thd(list(self._va), time_data=list(self._ts))
        if thd > 10.0:
            self._emit(ts, "Harmonic Bloom", f"THD {thd:.1f}% exceeded 10%")

        # Phase Imbalance: angle deviation > 20°
        ph = extract_three_phase_phasors(list(self._va), list(self._vb), list(self._vc), time_data=list(self._ts))
        if ph is not None:
            if abs(ph["ab_angle"]) > 140 or abs(ph["ac_angle"]) > 140:
                self._emit(ts, "Phase Imbalance", "Angle deviation > 20° detected")

        # Frequency undershoot: < 58.5 Hz for > 0.3s
        if len(self._freq) > 6:
            recent = list(self._freq)[-6:]
            if all(f < 58.5 for f in recent):
                self._emit(ts, "Frequency Undershoot", "f < 58.5 Hz for > 0.3s")

        # Recovery delay: > 0.5s after fault clear
        if self._active_fault_ts is not None:
            elapsed = ts - self._active_fault_ts
            if elapsed > 0.5:
                self._emit(ts, "Recovery Delay", f"Recovery > {elapsed:.2f}s")

    def export_insights(self, path=None):
        if path is None:
            path = self.log_path
        with open(path, "w") as f:
            json.dump({"insights": self._insights}, f, indent=2)
