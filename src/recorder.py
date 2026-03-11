import logging
import json
import time
import os
from datetime import datetime
from pathlib import Path
from src.signal_processing import compute_rms, compute_thd

logger = logging.getLogger(__name__)

_SESSION_FORMAT_VERSION = "1.2"


class Recorder:
    """
    Logs telemetry to a JSON session file (Data Capsule).

    Session file format (v1.2):
    {
        "meta": {
            "version": "1.2",
            "session_id": "session_YYYYmmdd_HHMMSS",
            "start_time": "ISO8601",
            "frame_count": N,
            "sample_rate_estimate": Hz,
            "channels": ["v_an", "v_bn", ...]
        },
        "frames":   [TelemetryFrame, ...],
        "insights": [InsightEvent, ...],
        "events":   [legacy event dicts, ...]
    }
    """

    def __init__(self, data_dir: str = "data/sessions"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.is_recording = False
        self.buffer: list[dict] = []
        self.insights: list[dict] = []
        self.events: list[dict] = []
        self.start_time: datetime | None = None
        self.session_id: str | None = None
        self._first_ts: float | None = None
        self._last_ts: float | None = None

    def start(self):
        self.is_recording = True
        self.buffer = []
        self.insights = []
        self.events = []
        self.start_time = datetime.now()
        self.session_id = f"session_{self.start_time.strftime('%Y%m%d_%H%M%S')}"
        self._first_ts = None
        self._last_ts = None
        logger.info(f"Recording started: {self.session_id}")

    def stop(self) -> str | None:
        if not self.is_recording:
            return None
        self.is_recording = False
        filepath = self._save_to_disk()
        logger.info(f"Recording stopped. Saved to {filepath}")
        return filepath

    def log_frame(self, frame: dict):
        if self.is_recording:
            self.buffer.append(frame)
            ts = frame.get("ts")
            if isinstance(ts, (int, float)) and ts > 0:
                if self._first_ts is None:
                    self._first_ts = ts
                self._last_ts = ts

    def log_insight(self, insight: dict):
        """Log a canonical InsightEvent dict to the session."""
        if self.is_recording:
            self.insights.append(insight)

    def log_event(self, event_type: str, details: str):
        if self.is_recording:
            event = {
                "ts": time.time(),
                "type": event_type,
                "details": details,
            }
            self.events.append(event)
            logger.info(f"Event logged: {event_type}")

    def _estimate_sample_rate(self) -> float:
        """Estimate Hz from recorded timestamps."""
        if len(self.buffer) < 2 or self._first_ts is None or self._last_ts is None:
            return 0.0
        duration = self._last_ts - self._first_ts
        if duration <= 0:
            return 0.0
        return round((len(self.buffer) - 1) / duration, 2)

    def _detected_channels(self) -> list[str]:
        """Return sorted list of canonical channel keys present in frames."""
        if not self.buffer:
            return []
        canonical = {"ts", "v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "freq", "p_mech"}
        found: set[str] = set()
        for f in self.buffer[:20]:          # sample first 20 frames
            found.update(f.keys())
        return sorted(found & canonical)

    def _save_to_disk(self) -> str | None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        capsule = {
            "meta": {
                "version":              _SESSION_FORMAT_VERSION,
                "session_id":           self.session_id,
                "start_time":           self.start_time.isoformat() if self.start_time else "",
                "frame_count":          len(self.buffer),
                "sample_rate_estimate": self._estimate_sample_rate(),
                "channels":             self._detected_channels(),
            },
            "frames":   self.buffer,
            "insights": self.insights,
            "events":   self.events,
        }

        filename = f"{self.session_id}.json"
        filepath = os.path.join(self.data_dir, filename)

        try:
            with open(filepath, "w") as f:
                json.dump(capsule, f, indent=2)
            return filepath
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return None

    def export_smart_csv(self, session_path, insights=None, compliance=None, out_path="data/session_export.csv"):
        try:
            with open(session_path, "r") as f:
                data = json.load(f)
        except Exception:
            return None

        frames = data.get("frames", [])
        if not frames:
            return None

        ts    = [f.get("ts") for f in frames]
        v_an  = [f.get("v_an", 0.0) for f in frames]
        v_bn  = [f.get("v_bn", 0.0) for f in frames]
        v_cn  = [f.get("v_cn", 0.0) for f in frames]
        i_a   = [f.get("i_a",  0.0) for f in frames]
        i_b   = [f.get("i_b",  0.0) for f in frames]
        i_c   = [f.get("i_c",  0.0) for f in frames]
        freq  = [f.get("freq", 60.0) for f in frames]
        thd   = compute_thd(v_an, time_data=ts)
        rms   = compute_rms(v_an)

        insight_ts = set()
        if insights:
            for ins in insights:
                insight_ts.add(ins.get("ts"))

        compliance_str = ""
        if compliance:
            compliance_str = "; ".join(
                [f"{c['name']}={'PASS' if c['passed'] else 'FAIL'}" for c in compliance]
            )

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w") as f:
            f.write("ts,v_an,v_bn,v_cn,i_a,i_b,i_c,freq,thd,rms,fault,compliance,insight\n")
            for idx, frame in enumerate(frames):
                line = [
                    frame.get("ts"),
                    v_an[idx], v_bn[idx], v_cn[idx],
                    i_a[idx],  i_b[idx],  i_c[idx],
                    freq[idx], thd, rms,
                    frame.get("fault_type"),
                    compliance_str,
                    "1" if frame.get("ts") in insight_ts else "0",
                ]
                f.write(",".join([str(x) for x in line]) + "\n")
        return out_path
