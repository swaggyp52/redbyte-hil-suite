import pyqtgraph as pg
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QHBoxLayout, QComboBox, QGroupBox)
from src.analysis import AnalysisEngine
import csv

class AnalysisApp(QWidget):
    """
    UI for comparing two sessions.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analysis & Comparison")
        self.layout = QVBoxLayout(self)

        header = QLabel("Analysis — Session Comparison")
        header.setStyleSheet("font-size: 12pt; font-weight: 700; color: #60a5fa;")
        self.layout.addWidget(header)
        
        # File Selection
        file_layout = QHBoxLayout()
        self.btn_ref = QPushButton("Load Reference (A)")
        self.btn_ref.clicked.connect(lambda: self._load_file('ref'))
        self.lbl_ref = QLabel("None")
        
        self.btn_test = QPushButton("Load Test (B)")
        self.btn_test.clicked.connect(lambda: self._load_file('test'))
        self.lbl_test = QLabel("None")
        
        file_layout.addWidget(self.btn_ref)
        file_layout.addWidget(self.lbl_ref)
        file_layout.addSpacing(20)
        file_layout.addWidget(self.btn_test)
        file_layout.addWidget(self.lbl_test)
        self.layout.addLayout(file_layout)
        
        # Signal Selector
        self.combo_signal = QComboBox()
        self.combo_signal.addItems(["v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c", "freq", "p_mech"])
        self.btn_compare = QPushButton("Compare")
        self.btn_compare.clicked.connect(self._run_comparison)
        
        sig_layout = QHBoxLayout()
        sig_layout.addWidget(QLabel("Signal:"))
        sig_layout.addWidget(self.combo_signal)
        sig_layout.addWidget(self.btn_compare)
        self.layout.addLayout(sig_layout)
        
        # Stats
        self.lbl_stats = QLabel("RMSE: - | Max Delta: -")
        self.layout.addWidget(self.lbl_stats)
        
        # Plot
        self.plot_widget = pg.PlotWidget(title="Reference (Green) vs Test (Red)")
        self.plot_widget.setBackground('#0b0f14')
        self.plot_widget.addLegend()
        self.layout.addWidget(self.plot_widget)
        
        self.data_ref = None
        self.data_test = None
        
        # Export
        self.btn_export = QPushButton("Export Stats CSV")
        self.btn_export.clicked.connect(self._export_csv)
        self.layout.addWidget(self.btn_export)
        self.last_results = None

    def _load_file(self, role):
        fname, _ = QFileDialog.getOpenFileName(self, f"Open {role} Session", os.getcwd(), "JSON Files (*.json)")
        if fname:
            data = AnalysisEngine.load_session(fname)
            if role == 'ref':
                self.data_ref = data
                self.lbl_ref.setText(os.path.basename(fname))
            else:
                self.data_test = data
                self.lbl_test.setText(os.path.basename(fname))

    def _run_comparison(self):
        if not self.data_ref or not self.data_test:
            self.lbl_stats.setText("Load both files first.")
            return

        sig = self.combo_signal.currentText()
        results = AnalysisEngine.compare_sessions(self.data_ref, self.data_test, sig)
        self.last_results = results
        
        # Update Stats
        self.lbl_stats.setText(f"RMSE: {results['rmse']:.4f} | Max Delta: {results['max_delta']:.4f}")
        
        # Plot
        self.plot_widget.clear()
        ref_curve = self.plot_widget.plot(results['ref_values'], pen='g', name="Reference")
        test_curve = self.plot_widget.plot(results['test_values'], pen='r', name="Test")
        
        # Highlight high error? (Optional MVP enhancement)

    def _export_csv(self):
        if not self.last_results:
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Export Results", os.getcwd(), "CSV Files (*.csv)")
        if fname:
            with open(fname, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Index", "Ref", "Test", "Delta"])
                refs = self.last_results['ref_values']
                tests = self.last_results['test_values']
                deltas = self.last_results['deltas']
                for i in range(len(refs)):
                    writer.writerow([i, refs[i], tests[i], deltas[i]])
            # Add metadata footer?
