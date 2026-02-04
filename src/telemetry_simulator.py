"""
Telemetry Simulator - Generates realistic mock GFM inverter data
Feeds frames to the system so UI elements update and watchdog monitors health
"""
import threading
import time
import math
import logging
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class TelemetrySimulator(QObject):
    """
    Generates mock telemetry frames simulating a Grid-Forming inverter.
    Injects frames into the system via signals so the entire UI updates.
    
    Signals:
        frame_generated: Emitted when a new frame is generated (frame_dict)
    """
    
    frame_generated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.paused = False
        self.thread = None
        self.frame_count = 0
        self.start_time = None
        
        # Simulation parameters
        self.frequency = 60.0  # Hz
        self.v_rms = 230.0  # Volts RMS
        self.i_rms = 5.0   # Amps RMS
        self.thd = 0.05    # 5% THD (low, healthy)
        
        logger.info("Telemetry simulator initialized")
    
    def start_streaming(self):
        """Start generating telemetry frames"""
        if self.thread and self.thread.is_alive():
            logger.warning("Simulator already running")
            return
        
        self.running = True
        self.paused = False
        self.frame_count = 0
        self.start_time = time.time()
        
        self.thread = threading.Thread(target=self._simulate_loop, daemon=True)
        self.thread.start()
        
        logger.info("Telemetry simulation started")
    
    def pause(self):
        """Pause frame generation (triggers stale data after 2s)"""
        if self.running and not self.paused:
            self.paused = True
            logger.info("Telemetry simulation paused")
    
    def resume(self):
        """Resume frame generation after pause"""
        if self.running and self.paused:
            self.paused = False
            self.start_time = time.time() - (self.frame_count * 0.05)  # Adjust start time
            logger.info("Telemetry simulation resumed")
    
    def stop(self):
        """Stop frame generation"""
        self.running = False
        self.paused = False
        logger.info("Telemetry simulation stopped")
    
    def _simulate_loop(self):
        """Main simulation loop - generates frames at 20 Hz"""
        frame_interval = 0.05  # 20 Hz = 50ms between frames
        last_frame_time = time.time()
        
        while self.running:
            # Respect pause without blocking
            if self.paused:
                time.sleep(0.01)  # Check pause status 100x per second
                continue
            
            # Generate frame at regular intervals
            now = time.time()
            if now - last_frame_time >= frame_interval:
                frame = self._generate_frame()
                self.frame_generated.emit(frame)
                self.frame_count += 1
                last_frame_time = now
            else:
                time.sleep(0.001)  # Small sleep to prevent busy waiting
    
    def _generate_frame(self):
        """Generate a realistic GFM inverter telemetry frame"""
        if self.start_time is None:
            self.start_time = time.time()  # Initialize if not set
        
        elapsed = time.time() - self.start_time
        
        # Simulate three-phase sinusoidal AC
        angle_a = 2 * math.pi * self.frequency * elapsed
        angle_b = angle_a - (2 * math.pi / 3)
        angle_c = angle_a - (4 * math.pi / 3)
        
        # Phase-to-neutral voltages
        v_an = self.v_rms * math.sqrt(2) * math.sin(angle_a)
        v_bn = self.v_rms * math.sqrt(2) * math.sin(angle_b)
        v_cn = self.v_rms * math.sqrt(2) * math.sin(angle_c)
        
        # Phase currents
        i_an = self.i_rms * math.sqrt(2) * math.sin(angle_a)
        i_bn = self.i_rms * math.sqrt(2) * math.sin(angle_b)
        i_cn = self.i_rms * math.sqrt(2) * math.sin(angle_c)
        
        # Add some harmonic distortion (3rd harmonic, 5th harmonic)
        v_an += 0.05 * self.v_rms * math.sqrt(2) * math.sin(3 * angle_a)
        v_an += 0.03 * self.v_rms * math.sqrt(2) * math.sin(5 * angle_a)
        
        # Real power (P) and reactive power (Q)
        p = (v_an * i_an + v_bn * i_bn + v_cn * i_cn) / 3
        q = p * 0.1  # Small reactive component
        
        # Create frame
        frame = {
            "ts": time.time(),  # Timestamp field expected by UI
            "frame_id": self.frame_count,
            
            # Voltages (V) - lowercase to match UI expectations
            "v_an": v_an,
            "v_bn": v_bn,
            "v_cn": v_cn,
            "v_ab": v_an - v_bn,
            "v_bc": v_bn - v_cn,
            "v_ca": v_cn - v_an,
            
            # Currents (A) - lowercase
            "i_an": i_an,
            "i_bn": i_bn,
            "i_cn": i_cn,
            
            # RMS values
            "v_rms": self.v_rms,
            "i_rms": self.i_rms,
            
            # Power metrics
            "p": p,  # Lowercase
            "q": q,
            "s": math.sqrt(p**2 + q**2),
            "pf": p / math.sqrt(p**2 + q**2) if (p**2 + q**2) > 0 else 1.0,
            
            # Power quality
            "thd": self.thd,  # Lowercase
            "freq": self.frequency,
            
            # Health indicators
            "temp": 45.0 + 5.0 * math.sin(elapsed / 10),  # Oscillating temperature
            "status": "HEALTHY",
        }
        
        return frame
    
    def get_stats(self):
        """Get simulation statistics"""
        return {
            "running": self.running,
            "paused": self.paused,
            "frame_count": self.frame_count,
            "elapsed": time.time() - self.start_time if self.start_time else 0,
            "frequency": self.frequency,
            "v_rms": self.v_rms,
            "i_rms": self.i_rms,
        }
