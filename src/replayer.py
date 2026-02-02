import logging
import json
import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

logger = logging.getLogger(__name__)

class Replayer(QObject):
    """
    Replays a 'Data Capsule' JSON file appropriately timed.
    """
    frame_playback = pyqtSignal(dict)
    finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.frames = []
        self.events = []
        self.current_idx = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.last_tick_time = 0
        self.playback_speed = 1.0

    def load_file(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.frames = data.get("frames", [])
                self.events = data.get("events", [])
                logger.info(f"Loaded {len(self.frames)} frames from {filepath}")
                return True
        except Exception as e:
            logger.error(f"Replay load error: {e}")
            return False

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
        if self.current_idx >= len(self.frames):
            self.stop()
            self.finished.emit()
            return

        # Simple Replay: Just blast them out at reasonable speed for MVP if timestamps tricky
        # "Real-Time" Replay:
        if self.mode == "realtime":
            target_frame = self.frames[self.current_idx]
            frame_time_rel = target_frame['ts'] - self.sim_start_time
            wall_time_rel = (time.time() - self.play_start_time) * self.playback_speed
            
            if wall_time_rel >= frame_time_rel:
                self.frame_playback.emit(target_frame)
                self.current_idx += 1
                # Catch up loop
                while self.current_idx < len(self.frames):
                     next_target = self.frames[self.current_idx]
                     if wall_time_rel >= (next_target['ts'] - self.sim_start_time):
                         self.frame_playback.emit(next_target)
                         self.current_idx += 1
                     else:
                         break
        else:
            # Fixed 10ms emission
            self.frame_playback.emit(self.frames[self.current_idx])
            self.current_idx += 1

    def stop(self):
        self.timer.stop()
        logger.info("Replay stopped")
