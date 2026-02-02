from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel,
                             QFileDialog, QHBoxLayout, QListWidget, QGroupBox)
from PyQt6.QtCore import pyqtSlot, QEvent
from src.scenario import ScenarioController, ScenarioValidator
from src.compliance_checker import evaluate_ieee_2800
from ui.overlay import OverlayMessage
import json
import os
import logging

logger = logging.getLogger(__name__)


class FaultInjector(QWidget):
    """
    UI for selecting and running test scenarios, with manual fault injection
    that sends real commands through the serial adapter.
    """
    def __init__(self, scenario_ctrl: ScenarioController, serial_mgr=None):
        super().__init__()
        self.setWindowTitle("Fault Injector")
        self.ctrl = scenario_ctrl
        self.serial_mgr = serial_mgr
        self.layout = QVBoxLayout(self)

        header = QLabel("Fault Injector — Scenario Control")
        header.setStyleSheet("font-size: 12pt; font-weight: 700; color: #f97316;")
        self.layout.addWidget(header)

        self.overlay = OverlayMessage(self)

        # Load / Info
        self.lbl_info = QLabel("No Scenario Loaded")
        self.btn_load = QPushButton("Load Scenario File...")
        self.btn_load.clicked.connect(self._load_scenario)

        self.layout.addWidget(self.btn_load)
        self.layout.addWidget(self.lbl_info)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_run = QPushButton("Run Scenario")
        self.btn_run.clicked.connect(self._run)
        self.btn_run.setEnabled(False)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self._stop)
        self.btn_stop.setEnabled(False)

        self.btn_quick_demo = QPushButton("Run Quick Demo")
        self.btn_quick_demo.clicked.connect(self._run_quick_demo)
        self.btn_quick_demo.setStyleSheet("background-color: #2c3e50; font-weight: bold;")

        ctrl_layout.addWidget(self.btn_run)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_quick_demo)
        self.layout.addLayout(ctrl_layout)

        # Manual Injection (sends real commands through adapter)
        grp_manual = QGroupBox("Fast Injection (Hardware Commands)")
        man_layout = QHBoxLayout()
        self.btn_inject_sag = QPushButton("Voltage Sag (50%)")
        self.btn_inject_sag.clicked.connect(self._inject_sag)
        self.btn_inject_sag.installEventFilter(self)

        self.btn_inject_drift = QPushButton("Freq Drift (+2Hz)")
        self.btn_inject_drift.clicked.connect(self._inject_drift)
        self.btn_inject_drift.installEventFilter(self)

        self.btn_clear_fault = QPushButton("Clear Faults")
        self.btn_clear_fault.clicked.connect(self._clear_faults)
        self.btn_clear_fault.installEventFilter(self)

        man_layout.addWidget(self.btn_inject_sag)
        man_layout.addWidget(self.btn_inject_drift)
        man_layout.addWidget(self.btn_clear_fault)
        grp_manual.setLayout(man_layout)
        self.layout.addWidget(grp_manual)

        # Validation
        val_layout = QHBoxLayout()
        self.btn_validate = QPushButton("Validate Last Run")
        self.btn_validate.clicked.connect(self._validate_last)
        val_layout.addWidget(self.btn_validate)

        self.lbl_result = QLabel("")
        val_layout.addWidget(self.lbl_result)

        self.layout.addLayout(val_layout)

        # Event Log
        self.log_list = QListWidget()
        self.layout.addWidget(QLabel("Real-time Event Log:"))
        self.layout.addWidget(self.log_list)

        # Scenario timeline preview
        self.timeline_list = QListWidget()
        self.layout.addWidget(QLabel("Scenario Timeline:"))
        self.layout.addWidget(self.timeline_list)

        # Signals
        self.ctrl.event_triggered.connect(self._on_event)
        self.ctrl.finished.connect(self._on_finished)

    def _inject_sag(self):
        """Sends a voltage sag command through the hardware adapter."""
        self.ctrl.manual_inject("fault", "sag_50")
        if self.serial_mgr:
            self.serial_mgr.write_command('fault_sag', {'duration': 0.5, 'depth': 0.5})
        self.log_list.addItem("[INJECT] Voltage Sag 50% sent to hardware")
        self.log_list.scrollToBottom()
        self.overlay.show_message("Voltage Sag Injected", color="#f97316", pos=(10, 40))

    def _inject_drift(self):
        """Sends a frequency drift command through the hardware adapter."""
        self.ctrl.manual_inject("fault", "drift_up")
        if self.serial_mgr:
            self.serial_mgr.write_command('fault_drift', {'duration': 2.0, 'offset': 2.0})
        self.log_list.addItem("[INJECT] Freq Drift +2Hz sent to hardware")
        self.log_list.scrollToBottom()
        self.overlay.show_message("Frequency Drift Injected", color="#f97316", pos=(10, 40))

    def _clear_faults(self):
        """Clears all active faults on the hardware."""
        if self.serial_mgr:
            self.serial_mgr.write_command('clear_fault')
        self.log_list.addItem("[CLEAR] All faults cleared")
        self.log_list.scrollToBottom()
        self.overlay.show_message("Faults Cleared", color="#22c55e", pos=(10, 40))

    def _run_quick_demo(self):
        demo_paths = [
            "data/scenarios/grid_fault.json",
            "data/scenario_validation_test.json",
            "scenarios/grid_fault.json",
        ]
        found = False
        for p in demo_paths:
            if os.path.exists(p):
                self.ctrl.load_scenario(p)
                found = True
                break
        if found:
            self._run()
            self.log_list.addItem(">>> QUICK DEMO STARTED")
        else:
            self.log_list.addItem("ERR: No scenario file found in standard paths.")

    def _validate_last(self):
        data_dir = "data/sessions"
        if not os.path.exists(data_dir):
            self.log_list.addItem("WARN: No sessions directory found.")
            return
        files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".json")]
        if not files:
            self.log_list.addItem("WARN: No session files to validate.")
            return
        latest = max(files, key=os.path.getmtime)
        self._validate_log_file(latest)

    def _load_scenario(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open Scenario", "data", "JSON Files (*.json)")
        if fname:
            if self.ctrl.load_scenario(fname):
                self.lbl_info.setText(f"Active: {os.path.basename(fname)}")
                self.btn_run.setEnabled(True)
                self.lbl_result.setText("")
                self._populate_timeline()

    def _populate_timeline(self):
        self.timeline_list.clear()
        if not self.ctrl.scenario_data:
            return
        for evt in self.ctrl.scenario_data.get("events", []):
            self.timeline_list.addItem(f"{evt.get('time', 0):.2f}s — {evt.get('type', '')} {evt.get('label','')}")

    def _validate_log_file(self, fname):
        try:
            with open(fname, 'r') as f:
                session_data = json.load(f)

            if not self.ctrl.scenario_data:
                self.log_list.addItem("WARN: No scenario loaded for validation rules.")
                return

            rules = self.ctrl.scenario_data.get("validation", {})
            if not rules:
                self.log_list.addItem("WARN: Scenario has no validation rules.")
                return

            result = ScenarioValidator.validate(session_data, rules)
            status = "PASS" if result["passed"] else "FAIL"
            color = "green" if result["passed"] else "red"

            self.lbl_result.setText(f"Result: {status}")
            self.lbl_result.setStyleSheet(f"font-weight: bold; color: {color}; font-size: 14pt;")

            # Broadcast to Dashboard
            import time
            compliance = evaluate_ieee_2800(session_data)
            pkg = {
                "ts": time.time(),
                "scenario": self.ctrl.scenario_data.get("name", "Unknown"),
                "passed": result["passed"],
                "details": "; ".join(result["logs"]),
                "compliance": compliance
            }
            self.ctrl.validation_complete.emit(pkg)

            for log_line in result["logs"]:
                self.log_list.addItem(f"  {log_line}")
            self.log_list.scrollToBottom()

        except Exception as e:
            logger.error(f"Validation error: {e}")
            self.log_list.addItem(f"ERR: Validation failed: {e}")

    def _run(self):
        self.ctrl.start()
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_list.addItem("--- Scenario Triggered ---")

    def _stop(self):
        self.ctrl.stop()
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.log_list.addItem("--- Forced Stop ---")

    @pyqtSlot(str, dict)
    def _on_event(self, type_str, data):
        self.log_list.addItem(f"[{type_str.upper()}] {data}")
        self.log_list.scrollToBottom()

    @pyqtSlot()
    def _on_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.log_list.addItem("--- Sequence Complete ---")
        self._validate_last()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            if obj == self.btn_inject_sag:
                self.overlay.show_message("Preview: Voltage sag", color="#f97316", pos=(10, 70))
            elif obj == self.btn_inject_drift:
                self.overlay.show_message("Preview: Frequency drift", color="#f97316", pos=(10, 70))
            elif obj == self.btn_clear_fault:
                self.overlay.show_message("Preview: Clear faults", color="#22c55e", pos=(10, 70))
        return super().eventFilter(obj, event)
