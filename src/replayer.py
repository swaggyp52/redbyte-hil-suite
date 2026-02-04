import logging
import json
import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

logger = logging.getLogger(__name__)

class ReplayValidationError(Exception):
    """Raised when replay data validation fails"""
    pass

class Replayer(QObject):
    """
    Replays a 'Data Capsule' JSON file with accurate timing.
    
    Features:
    - Validates data integrity before playback
    - Supports variable playback speed
    - Handles missing timestamps gracefully
    - Emits progress updates
    - Detects and reports timing anomalies
    """
    frame_playback = pyqtSignal(dict)
    finished = pyqtSignal()
    progress_update = pyqtSignal(int, int)  # current_frame, total_frames
    validation_warning = pyqtSignal(str)  # warning message
    
    def __init__(self):
        super().__init__()
        self.frames = []
        self.events = []
        self.metadata = {}
        self.current_idx = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.last_tick_time = 0
        self.playback_speed = 1.0
        self.mode = "realtime"  # or "fast"
        self.sim_start_time = 0.0
        self.play_start_time = 0.0
        self.validation_errors = []
        self.total_frames = 0

    def load_file(self, filepath: str):
        """Load and validate a session file for replay"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Validate structure
            if not self._validate_session(data):
                logger.error(f"Session validation failed: {filepath}")
                return False
            
            self.frames = data.get("frames", [])
            self.events = data.get("events", [])
            self.metadata = data.get("meta", {})
            self.total_frames = len(self.frames)
            
            # Check for timestamp consistency
            self._check_timestamps()
            
            logger.info(f"Loaded {len(self.frames)} frames, {len(self.events)} events from {filepath}")
            
            if self.validation_errors:
                for err in self.validation_errors:
                    logger.warning(f"Validation warning: {err}")
                    self.validation_warning.emit(err)
            
            return True
            
        except FileNotFoundError:
            logger.error(f"Replay file not found: {filepath}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in replay file: {e}")
            return False
        except Exception as e:
            logger.error(f"Replay load error: {e}")
            return False
    
    def _validate_session(self, data: dict) -> bool:
        """Validate session data structure"""
        self.validation_errors = []
        
        if "frames" not in data:
            logger.error("Missing 'frames' field")
            return False
        
        frames = data["frames"]
        if not isinstance(frames, list):
            logger.error("'frames' is not a list")
            return False
        
        if len(frames) == 0:
            logger.error("No frames to replay")
            return False
        
        # Check for timestamp field
        if "ts" not in frames[0]:
            self.validation_errors.append("Frames missing 'ts' field - using fixed interval mode")
            self.mode = "fast"
        
        return True
    
    def _check_timestamps(self):
        """Check for timestamp anomalies"""
        if not self.frames or self.mode == "fast":
            return
        
        timestamps = [f.get("ts", 0) for f in self.frames]
        
        # Check if timestamps are monotonically increasing
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i-1]:
                self.validation_errors.append(f"Non-monotonic timestamp at frame {i}")
        
        # Check for large gaps
        deltas = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
        if deltas:
            avg_delta = sum(deltas) / len(deltas)
            for i, delta in enumerate(deltas):
                if delta > avg_delta * 5:  # 5x average gap
                    self.validation_errors.append(f"Large time gap ({delta:.2f}s) at frame {i+1}")

    def start(self):
        if not self.frames:
            return
        
        self.current_idx = 0
        # Normalize time base if possible, or just play relative to start
        # Ideally, we look at 'ts' diffs.
        self.timer.start(10) # 100Hz base tick, or faster?
        # A better approach for accurate replay is to schedule next frame based on delta.
        # Simple MVP: fixed interval or simple delta check.
        
        self.last_wall_time = time.time()
        # Find first frame timestamp reference
        if 'ts' in self.frames[0]:
            self.sim_start_time = self.frames[0]['ts']
            self.play_start_time = time.time()
            self.mode = "realtime"
        else:
            self.mode = "fast" # or fixed rate
            
        logger.info("Replay started")

    def _tick(self):
        """Replay tick - emit next frame(s) based on timing"""
        if self.current_idx >= len(self.frames):
            self.stop()
            self.finished.emit()
            return

        # Emit progress periodically
        if self.current_idx % 10 == 0:
            self.progress_update.emit(self.current_idx, self.total_frames)

        # Real-time mode: respect original timestamps
        if self.mode == "realtime":
            target_frame = self.frames[self.current_idx]
            frame_time_rel = target_frame.get('ts', 0) - self.sim_start_time
            wall_time_rel = (time.time() - self.play_start_time) * self.playback_speed
            
            if wall_time_rel >= frame_time_rel:
                self.frame_playback.emit(target_frame)
                self.current_idx += 1
                
                # Catch-up loop for frames that should have already been emitted
                while self.current_idx < len(self.frames):
                    next_target = self.frames[self.current_idx]
                    next_frame_time = next_target.get('ts', 0) - self.sim_start_time
                    if wall_time_rel >= next_frame_time:
                        self.frame_playback.emit(next_target)
                        self.current_idx += 1
                    else:
                        break
        else:
            # Fast mode: emit at fixed interval (10ms = 100 Hz)
            self.frame_playback.emit(self.frames[self.current_idx])
            self.current_idx += 1

    def stop(self):
        self.timer.stop()
        logger.info("Replay stopped")
