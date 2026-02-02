import logging
import json
import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from src.signal_processing import calculate_step_metrics

logger = logging.getLogger(__name__)

class ScenarioController(QObject):
    """
    Manages execution of predefined test scenarios.
    """
    event_triggered = pyqtSignal(str, dict) # type, details
    validation_complete = pyqtSignal(dict) # result package for dashboard
    finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.current_scenario = None
        self.scenario_data = None # Alias for validator compatibility
        self.running = False
        self.start_time = 0
        self.events = []
        self.next_event_idx = 0
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        
    def load_scenario(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.current_scenario = data
                self.scenario_data = data # Ensure sync
                # Sort events by time just in case
                self.events = sorted(data.get("events", []), key=lambda x: x['time'])
                logger.info(f"Loaded scenario: {data.get('name')}")
                return True
        except Exception as e:
            logger.error(f"Failed to load scenario: {e}")
            return False

    def start(self):
        if not self.current_scenario:
            logger.warning("No scenario loaded")
            return

        self.scenario_data = self.current_scenario 
        self.running = True
        self.start_time = time.time()
        self.next_event_idx = 0
        self.timer.start(50) # check every 50ms
        logger.info(f"Started scenario: {self.current_scenario.get('name')}")
        self.event_triggered.emit("scenario_start", {"name": self.current_scenario.get('name')})

    def stop(self):
        self.running = False
        self.timer.stop()
        self.event_triggered.emit("scenario_stop", {})
        logger.info("Scenario stopped")

    def _tick(self):
        if not self.running:
            return
            
        elapsed = time.time() - self.start_time
        
        while self.next_event_idx < len(self.events):
            evt = self.events[self.next_event_idx]
            if elapsed >= evt['time']:
                # Trigger Event
                self.event_triggered.emit(evt['type'], evt)
                logger.info(f"Executed event: {evt['type']} at {evt['time']}s")
                self.next_event_idx += 1
            else:
                break
        
        # Check if done (optional: wait a bit after last event?)
        if self.next_event_idx >= len(self.events) and elapsed > self.events[-1]['time'] + 1.0:
            self.stop()
            self.finished.emit()
            
    def manual_inject(self, event_type, value):
        """Allows manual injection parallel to scenario."""
        self.event_triggered.emit(event_type, {"value": value, "manual": True})
        logger.info(f"Manual injection: {event_type} = {value}")

class ScenarioValidator:
    """
    Validates a recorded session against scenario rules.
    """
    @staticmethod
    def validate(session_data, validation_rules):
        """
        Args:
            session_data (dict): The full loaded session JSON.
            validation_rules (dict): The 'validation' block from scenario JSON.
            
        Returns:
            dict: { "passed": bool, "logs": [str] }
        """
        logs = []
        passed = True
        
        frames = session_data.get("frames", [])
        if not frames:
            return {"passed": False, "logs": ["No frames in session data."]}
            
        # Extract time-series for vectorized checks
        # Assuming frames are chronologically sorted
        try:
            # Handle key variations if needed (v vs v_an)
            # This validator assumes 'v' and 'i' keys are present (legacy) or mapped.
            # Production system uses v_an, v_bn etc.
            # For back-compat or specific rule checks, we might need to be smart.
            # Assuming 'v' represents average or specific phase if not specified.
            # Let's try to get v_an if v missing
            
            ts = [f['ts'] for f in frames]
            
            # Helper to get scalar voltage
            def get_v(f):
                if 'v' in f: return f['v']
                if 'v_an' in f: return (f['v_an'] + f['v_bn'] + f['v_cn']) / 3.0 # Avg
                return 0.0
                
            vs = [get_v(f) for f in frames]
            freqs = [f.get('freq', 60.0) for f in frames]
        except KeyError:
             return {"passed": False, "logs": ["Malformed session data (missing keys)."]}

        import numpy as np
        
        # 1. Min/Max Checks
        if "frequency_nadir" in validation_rules:
            limit = validation_rules["frequency_nadir"].get("min")
            if limit is not None:
                min_freq = min(freqs)
                if min_freq < limit:
                    passed = False
                    logs.append(f"FAIL: Freq Nadir {min_freq:.2f}Hz < Limit {limit}Hz")
                else:
                    logs.append(f"PASS: Freq Nadir {min_freq:.2f}Hz >= {limit}Hz")

        if "voltage_sag" in validation_rules:
            limit = validation_rules["voltage_sag"].get("min")
            if limit is not None:
                min_v = min(vs)
                if min_v < limit:
                    passed = False
                    logs.append(f"FAIL: Avg Voltage {min_v:.2f}V < Limit {limit}V")
                else:
                    logs.append(f"PASS: Avg Voltage {min_v:.2f}V >= {limit}V")

        # 2. Step Response Metrics
        if "recovery_time" in validation_rules:
            metrics = calculate_step_metrics(ts, vs)
            max_rec = validation_rules["recovery_time"].get("max")
            
            if metrics and max_rec:
                if metrics['rise_time'] > max_rec:
                    passed = False
                    logs.append(f"FAIL: Rise Time {metrics['rise_time']:.2f}s > {max_rec}s")
                else:
                    logs.append(f"PASS: Rise Time {metrics['rise_time']:.2f}s <= {max_rec}s")
            elif not metrics:
                logs.append("WARN: Could not calculate step metrics for recovery check.")
                
        if not logs:
            logs.append("No validation checks ran.")

        return {"passed": passed, "logs": logs}
