"""
Simulation Controller - Manages run/pause/resume/stop states for HIL testing
Provides clean state management for demo scenarios
"""
import logging
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

logger = logging.getLogger(__name__)


class SimulationController(QObject):
    """
    Controls simulation state and transitions.
    
    States:
        IDLE: Not running (initial state)
        RUNNING: Data flowing normally
        PAUSED: Data flow suspended (watchdog goes stale)
        STOPPED: Cleanly shut down
    
    Signals:
        state_changed: Emitted when state changes (new_state)
        simulation_started: Emitted when Run clicked
        simulation_paused: Emitted when Pause clicked
        simulation_resumed: Emitted when Resume clicked
        simulation_stopped: Emitted when Stop clicked
    """
    
    # States
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    
    # Signals
    state_changed = pyqtSignal(str)  # new state
    simulation_started = pyqtSignal()
    simulation_paused = pyqtSignal()
    simulation_resumed = pyqtSignal()
    simulation_stopped = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.state = self.IDLE
        self.frame_count = 0
        logger.info("Simulation controller initialized")
    
    def start(self):
        """Start the simulation"""
        if self.state in (self.IDLE, self.STOPPED, self.PAUSED):
            self.state = self.RUNNING
            self.frame_count = 0
            logger.info("Simulation STARTED")
            self.state_changed.emit(self.state)
            self.simulation_started.emit()
            return True
        return False
    
    def pause(self):
        """Pause the simulation"""
        if self.state == self.RUNNING:
            self.state = self.PAUSED
            logger.info("Simulation PAUSED")
            self.state_changed.emit(self.state)
            self.simulation_paused.emit()
            return True
        return False
    
    def resume(self):
        """Resume a paused simulation"""
        if self.state == self.PAUSED:
            self.state = self.RUNNING
            logger.info("Simulation RESUMED")
            self.state_changed.emit(self.state)
            self.simulation_resumed.emit()
            return True
        return False
    
    def stop(self):
        """Stop the simulation cleanly"""
        if self.state != self.IDLE:
            self.state = self.STOPPED
            logger.info("Simulation STOPPED")
            self.state_changed.emit(self.state)
            self.simulation_stopped.emit()
            return True
        return False
    
    def reset(self):
        """Reset to idle state"""
        self.state = self.IDLE
        self.frame_count = 0
        logger.debug("Simulation reset to IDLE")
    
    def is_running(self):
        """Check if simulation is currently running"""
        return self.state == self.RUNNING
    
    def is_paused(self):
        """Check if simulation is paused"""
        return self.state == self.PAUSED
    
    def get_state(self):
        """Get current state"""
        return self.state
    
    def get_state_display(self):
        """Get human-readable state for UI"""
        displays = {
            self.IDLE: "Idle",
            self.RUNNING: "▶️ Running",
            self.PAUSED: "⏸ Paused",
            self.STOPPED: "⏹ Stopped"
        }
        return displays.get(self.state, "Unknown")
