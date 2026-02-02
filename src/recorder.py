import logging
import json
import time
import os
from datetime import datetime
from src.signal_processing import compute_rms, compute_thd

logger = logging.getLogger(__name__)

class Recorder:
    """
    Logs telemetry to a JSON 'Data Capsule'.
    Format:
    {
        "meta": {
            "start_time": "ISO8601",
            "firmware": "v1.0",
            "scenario": "..."
        },
        "frames": [
            {"ts": 123.4, "val": ...}, ...
        ],
        "events": []
    }
    """
    def __init__(self, data_dir: str = "data/sessions"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.is_recording = False
        self.buffer = []
        self.events = []
        self.start_time = None
        self.session_id = None

    def start(self):
        self.is_recording = True
        self.buffer = []
        self.events = []
        self.start_time = datetime.now()
        self.session_id = f"session_{self.start_time.strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Recording started: {self.session_id}")

    def stop(self):
        if not self.is_recording:
            return None
        
        self.is_recording = False
        filepath = self._save_to_disk()
        logger.info(f"Recording stopped. Saved to {filepath}")
        return filepath

    def log_frame(self, frame: dict):
        if self.is_recording:
            self.buffer.append(frame)

    def log_event(self, event_type: str, details: str):
        if self.is_recording:
            event = {
                "ts": time.time(),
                "type": event_type,
                "details": details
            }
            self.events.append(event)
            logger.info(f"Event logged: {event_type}")

    def _save_to_disk(self):
        capsule = {
            "meta": {
                "session_id": self.session_id,
                "start_time": self.start_time.isoformat(),
                "frame_count": len(self.buffer)
            },
            "events": self.events,
            "frames": self.buffer
        }
        
        filename = f"{self.session_id}.json"
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(capsule, f, indent=2)
            return filepath
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return None

    def export_smart_csv(self, session_path, insights=None, compliance=None, out_path="data/session_export.csv"):
        try:
            with open(session_path, 'r') as f:
                data = json.load(f)
        except Exception:
            return None

        frames = data.get("frames", [])
        if not frames:
            return None

        ts = [f.get("ts") for f in frames]
        v_an = [f.get("v_an", 0.0) for f in frames]
        v_bn = [f.get("v_bn", 0.0) for f in frames]
        v_cn = [f.get("v_cn", 0.0) for f in frames]
        i_a = [f.get("i_a", 0.0) for f in frames]
        i_b = [f.get("i_b", 0.0) for f in frames]
        i_c = [f.get("i_c", 0.0) for f in frames]
        freq = [f.get("freq", 60.0) for f in frames]
        thd = compute_thd(v_an, time_data=ts)
        rms = compute_rms(v_an)

        insight_ts = set()
        if insights:
            for ins in insights:
                insight_ts.add(ins.get("ts"))

        compliance_str = ""
        if compliance:
            compliance_str = "; ".join([f"{c['name']}={'PASS' if c['passed'] else 'FAIL'}" for c in compliance])

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w') as f:
            f.write("ts,v_an,v_bn,v_cn,i_a,i_b,i_c,freq,thd,rms,fault,compliance,insight\n")
            for idx, frame in enumerate(frames):
                line = [
                    frame.get("ts"),
                    v_an[idx], v_bn[idx], v_cn[idx],
                    i_a[idx], i_b[idx], i_c[idx],
                    freq[idx], thd, rms,
                    frame.get("fault_type"),
                    compliance_str,
                    "1" if frame.get("ts") in insight_ts else "0",
                ]
                f.write(",".join([str(x) for x in line]) + "\n")
        return out_path
