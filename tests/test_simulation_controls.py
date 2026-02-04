"""
Test suite for simulation controller and UI controls
Validates state transitions and button management
"""
import pytest
from PyQt6.QtWidgets import QApplication
from src.simulation_controller import SimulationController
from ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for all tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSimulationController:
    """Test the SimulationController class"""
    
    def test_initialization(self):
        """Test controller initializes in IDLE state"""
        ctrl = SimulationController()
        assert ctrl.get_state() == SimulationController.IDLE
        assert ctrl.frame_count == 0
        assert not ctrl.is_running()
        assert not ctrl.is_paused()
    
    def test_state_transitions(self):
        """Test valid state transitions"""
        ctrl = SimulationController()
        
        # IDLE -> RUNNING
        assert ctrl.start()
        assert ctrl.is_running()
        
        # RUNNING -> PAUSED
        assert ctrl.pause()
        assert ctrl.is_paused()
        
        # PAUSED -> RUNNING
        assert ctrl.resume()
        assert ctrl.is_running()
        
        # RUNNING -> STOPPED
        assert ctrl.stop()
        assert ctrl.get_state() == SimulationController.STOPPED
    
    def test_invalid_transitions(self):
        """Test invalid state transitions are rejected"""
        ctrl = SimulationController()
        
        # Can't pause when idle
        assert not ctrl.pause()
        
        # Start first
        ctrl.start()
        
        # Can't resume when running
        assert not ctrl.resume()
        
        # Can't start when already running
        assert not ctrl.start()
    
    def test_reset(self):
        """Test reset returns to IDLE"""
        ctrl = SimulationController()
        ctrl.start()
        assert ctrl.is_running()
        
        ctrl.reset()
        assert ctrl.get_state() == SimulationController.IDLE
        assert ctrl.frame_count == 0
    
    def test_signals_emitted(self, qapp):
        """Test signals are emitted on state changes"""
        ctrl = SimulationController()
        
        # Track emitted signals
        started = []
        paused = []
        resumed = []
        stopped = []
        
        ctrl.simulation_started.connect(lambda: started.append(True))
        ctrl.simulation_paused.connect(lambda: paused.append(True))
        ctrl.simulation_resumed.connect(lambda: resumed.append(True))
        ctrl.simulation_stopped.connect(lambda: stopped.append(True))
        
        # Trigger transitions
        ctrl.start()
        assert len(started) == 1
        
        ctrl.pause()
        assert len(paused) == 1
        
        ctrl.resume()
        assert len(resumed) == 1
        
        ctrl.stop()
        assert len(stopped) == 1
    
    def test_state_display(self):
        """Test human-readable state display"""
        ctrl = SimulationController()
        
        assert "Idle" in ctrl.get_state_display()
        
        ctrl.start()
        assert "Running" in ctrl.get_state_display()
        
        ctrl.pause()
        assert "Paused" in ctrl.get_state_display()
        
        ctrl.stop()
        assert "Stopped" in ctrl.get_state_display()


class TestSimulationUIControls:
    """Test simulation controls in main window"""
    
    def test_main_window_has_simulation_controls(self, qapp):
        """Verify MainWindow has simulation controller and buttons"""
        window = MainWindow()
        
        assert hasattr(window, 'sim_ctrl'), "Missing simulation controller"
        assert hasattr(window, 'act_run'), "Missing run button"
        assert hasattr(window, 'act_pause'), "Missing pause button"
        assert hasattr(window, 'act_resume'), "Missing resume button"
        assert hasattr(window, 'act_stop'), "Missing stop button"
        assert hasattr(window, 'sim_status_label'), "Missing status label"
        
        window.close()
    
    def test_button_states_idle(self, qapp):
        """Test button states when simulation is idle"""
        window = MainWindow()
        
        assert window.act_run.isEnabled()
        assert not window.act_pause.isEnabled()
        assert not window.act_resume.isEnabled()
        assert not window.act_stop.isEnabled()
        
        window.close()
    
    def test_button_states_running(self, qapp):
        """Test button states when simulation is running"""
        window = MainWindow()
        
        window._start_simulation()
        
        assert not window.act_run.isEnabled()
        assert window.act_pause.isEnabled()
        assert not window.act_resume.isEnabled()
        assert window.act_stop.isEnabled()
        
        window.close()
    
    def test_button_states_paused(self, qapp):
        """Test button states when simulation is paused"""
        window = MainWindow()
        
        window._start_simulation()
        window._pause_simulation()
        
        assert not window.act_run.isEnabled()
        assert not window.act_pause.isEnabled()
        assert window.act_resume.isEnabled()
        assert window.act_stop.isEnabled()
        
        window.close()
    
    def test_status_label_updates(self, qapp):
        """Test status label reflects simulation state"""
        window = MainWindow()
        window.show()
        
        # Initial state
        assert "Idle" in window.sim_status_label.text()
        
        # Start
        window._start_simulation()
        assert "Running" in window.sim_status_label.text()
        assert "#10b981" in window.sim_status_label.styleSheet()  # Green
        
        # Pause
        window._pause_simulation()
        assert "Paused" in window.sim_status_label.text()
        assert "#f59e0b" in window.sim_status_label.styleSheet()  # Amber
        
        # Resume
        window._resume_simulation()
        assert "Running" in window.sim_status_label.text()
        
        # Stop
        window._stop_simulation()
        assert "Stopped" in window.sim_status_label.text()
        
        window.close()
    
    def test_watchdog_reset_on_start(self, qapp):
        """Test that watchdog resets when simulation starts"""
        window = MainWindow()
        
        # Simulate some frame activity
        window.telemetry_watchdog.last_frame_time = 1.0
        window.telemetry_watchdog.frame_count = 100
        
        # Start simulation should reset watchdog
        window._start_simulation()
        
        assert window.telemetry_watchdog.last_frame_time is None
        assert window.telemetry_watchdog.frame_count == 0
        
        window.close()
    
    def test_simulation_pause_workflow(self, qapp):
        """Test complete pause/resume workflow"""
        window = MainWindow()
        
        # Start → Pause → Resume → Stop
        window._start_simulation()
        assert window.sim_ctrl.is_running()
        
        window._pause_simulation()
        assert window.sim_ctrl.is_paused()
        assert not window.act_pause.isEnabled()
        assert window.act_resume.isEnabled()
        
        window._resume_simulation()
        assert window.sim_ctrl.is_running()
        assert window.act_pause.isEnabled()
        assert not window.act_resume.isEnabled()
        
        window._stop_simulation()
        assert window.sim_ctrl.get_state() == "stopped"
        assert window.act_run.isEnabled()
        
        window.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
