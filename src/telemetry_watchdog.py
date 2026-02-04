"""
Telemetry Watchdog - Detects stale/missing data during live operation
Critical for reliable demos and catching hardware failures early
"""
import time
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

logger = logging.getLogger(__name__)

class TelemetryWatchdog(QObject):
    """
    Monitors telemetry stream health and alerts on issues.
    
    Signals:
        stale_data: Emitted when no new frames received for timeout_ms
        data_resumed: Emitted when data flow resumes after stale period
        frame_rate_changed: Emitted when frame rate significantly changes
    """
    stale_data = pyqtSignal(float)  # seconds since last frame
    data_resumed = pyqtSignal()
    frame_rate_changed = pyqtSignal(float)  # new rate in Hz
    
    def __init__(self, timeout_ms=2000, check_interval_ms=500):
        super().__init__()
        self.timeout_ms = timeout_ms
        self.last_frame_time = None
        self.is_stale = False
        self.frame_count = 0
        self.rate_check_start = None
        self.rate_check_count = 0
        self.last_reported_rate = 0.0
        
        # Watchdog timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_health)
        self.timer.start(check_interval_ms)
        
        logger.info(f"Telemetry watchdog initialized (timeout: {timeout_ms}ms)")
    
    def on_frame_received(self, frame: dict):
        """Call this every time a telemetry frame arrives"""
        now = time.time()
        
        # Update health status
        if self.is_stale:
            logger.info("Telemetry data resumed")
            self.data_resumed.emit()
            self.is_stale = False
        
        self.last_frame_time = now
        self.frame_count += 1
        
        # Track frame rate
        if self.rate_check_start is None:
            self.rate_check_start = now
            self.rate_check_count = 1
        else:
            self.rate_check_count += 1
            elapsed = now - self.rate_check_start
            
            # Report rate every 2 seconds
            if elapsed >= 2.0:
                rate = self.rate_check_count / elapsed
                
                # Alert if rate changes significantly (>20%)
                if self.last_reported_rate > 0:
                    change_pct = abs(rate - self.last_reported_rate) / self.last_reported_rate
                    if change_pct > 0.2:
                        logger.warning(f"Frame rate changed: {self.last_reported_rate:.1f} -> {rate:.1f} Hz")
                        self.frame_rate_changed.emit(rate)
                
                self.last_reported_rate = rate
                self.rate_check_start = now
                self.rate_check_count = 0
    
    def _check_health(self):
        """Periodic health check"""
        if self.last_frame_time is None:
            return  # No data yet, not an error
        
        elapsed_ms = (time.time() - self.last_frame_time) * 1000
        
        if elapsed_ms > self.timeout_ms and not self.is_stale:
            logger.warning(f"Telemetry data stale ({elapsed_ms:.0f}ms since last frame)")
            self.is_stale = True
            self.stale_data.emit(elapsed_ms / 1000.0)
    
    def reset(self):
        """Reset watchdog state (call on disconnect/reconnect)"""
        self.last_frame_time = None
        self.is_stale = False
        self.frame_count = 0
        self.rate_check_start = None
        self.rate_check_count = 0
        logger.debug("Watchdog reset")
    
    def get_stats(self):
        """Get current telemetry statistics"""
        if self.last_frame_time is None:
            return {
                "status": "no_data",
                "frame_count": 0,
                "rate_hz": 0.0,
                "last_frame_age_ms": None
            }
        
        age_ms = (time.time() - self.last_frame_time) * 1000
        
        return {
            "status": "stale" if self.is_stale else "healthy",
            "frame_count": self.frame_count,
            "rate_hz": self.last_reported_rate,
            "last_frame_age_ms": age_ms
        }
