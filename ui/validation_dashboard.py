from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, 
                             QHeaderView, QPushButton, QHBoxLayout, QListWidget, QTabWidget, QFrame)
from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtGui import QColor, QPixmap, QPainter, QPen, QBrush
import datetime
import numpy as np


class WaveformThumbnail(QLabel):
    """Mini waveform snapshot widget for inline display"""
    def __init__(self, data_points, width=120, height=40, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.data_points = data_points
        self._render_waveform()
    
    def _render_waveform(self):
        """Render waveform as pixmap"""
        pixmap = QPixmap(self.width(), self.height())
        pixmap.fill(QColor(15, 17, 21, 200))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if len(self.data_points) < 2:
            painter.end()
            self.setPixmap(pixmap)
            return
        
        # Normalize data to widget height
        data_arr = np.array(self.data_points)
        data_min = data_arr.min()
        data_max = data_arr.max()
        data_range = data_max - data_min if data_max != data_min else 1
        
        # Draw waveform
        pen = QPen(QColor(16, 185, 129), 2)
        painter.setPen(pen)
        
        x_scale = self.width() / len(self.data_points)
        for i in range(len(self.data_points) - 1):
            y1 = self.height() - int(((self.data_points[i] - data_min) / data_range) * (self.height() - 4)) - 2
            y2 = self.height() - int(((self.data_points[i+1] - data_min) / data_range) * (self.height() - 4)) - 2
            x1 = int(i * x_scale)
            x2 = int((i+1) * x_scale)
            painter.drawLine(x1, y1, x2, y2)
        
        # Draw border
        pen = QPen(QColor(59, 130, 246, 120), 1)
        painter.setPen(pen)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        
        painter.end()
        self.setPixmap(pixmap)


class EventTimeline(QFrame):
    """Color-coded timeline showing injected faults vs detected insights"""
    def __init__(self, events, width=300, height=30, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.events = events  # List of {"ts": float, "type": "fault"|"insight", "name": str}
        self.setStyleSheet("""
            QFrame {
                background: rgba(15, 17, 21, 200);
                border: 1px solid rgba(59, 130, 246, 120);
                border-radius: 6px;
            }
        """)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        if not self.events or len(self.events) == 0:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Find time range
        times = [e["ts"] for e in self.events]
        t_min = min(times)
        t_max = max(times)
        t_range = t_max - t_min if t_max != t_min else 1
        
        # Draw events as vertical bars
        margin = 5
        for evt in self.events:
            x_pos = margin + int(((evt["ts"] - t_min) / t_range) * (self.width() - 2 * margin))
            
            if evt["type"] == "fault":
                color = QColor(239, 68, 68, 200)  # Red for faults
            else:
                color = QColor(16, 185, 129, 200)  # Green for insights
            
            painter.setPen(QPen(color, 3))
            painter.drawLine(x_pos, margin, x_pos, self.height() - margin)
        
        painter.end()

class ValidationDashboard(QWidget):
    """
    Live dashboard showing Scenario Validation results.
    """
    def __init__(self, scenario_controller):
        super().__init__()
        self.ctrl = scenario_controller
        self.layout = QVBoxLayout(self)
        
        header = QHBoxLayout()
        title = QLabel("Validation Scorecard")
        title.setStyleSheet("font-size: 12pt; font-weight: 700; color: #22d3ee;")
        header.addWidget(title)
        header.addStretch()
        
        self.btn_clear = QPushButton("Clear Scorecard")
        self.btn_clear.clicked.connect(self.clear)
        header.addWidget(self.btn_clear)
        
        self.layout.addLayout(header)

        self.summary_list = QListWidget()
        self.summary_list.setMaximumHeight(110)
        self.layout.addWidget(self.summary_list)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Scenario", "Waveform", "Result", "Details"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(2, 140)  # Waveform thumbnail column
        self.table.setAlternatingRowColors(True)
        self.table.setRowHeight(0, 50)  # Taller rows for thumbnails
        self.tabs.addTab(self.table, "Scorecard")

        self.compliance_table = QTableWidget()
        self.compliance_table.setColumnCount(3)
        self.compliance_table.setHorizontalHeaderLabels(["Rule", "Result", "Details"])
        self.compliance_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.compliance_table.setAlternatingRowColors(True)
        self.tabs.addTab(self.compliance_table, "Compliance")
        
        if hasattr(self.ctrl, 'validation_complete'):
            self.ctrl.validation_complete.connect(self.add_entry)

    def clear(self):
        self.table.setRowCount(0)

    @pyqtSlot(dict)
    def add_entry(self, result_pkg):
        """
        result_pkg: {"scenario": str, "passed": bool, "details": str, "ts": float, 
                     "waveform_data": list (optional), "events": list (optional)}
        """
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 50)
        
        ts = result_pkg.get("ts", 0)
        ts_str = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        self.table.setItem(row, 0, QTableWidgetItem(ts_str))
        self.table.setItem(row, 1, QTableWidgetItem(result_pkg.get("scenario", "Unknown")))
        
        # Add waveform thumbnail if data available
        waveform_data = result_pkg.get("waveform_data", [])
        if waveform_data and len(waveform_data) > 0:
            thumbnail = WaveformThumbnail(waveform_data)
            self.table.setCellWidget(row, 2, thumbnail)
        else:
            self.table.setItem(row, 2, QTableWidgetItem("—"))
        
        passed = result_pkg.get("passed", False)
        status_item = QTableWidgetItem("PASS" if passed else "FAIL")
        status_item.setForeground(QColor("green" if passed else "red"))
        self.table.setItem(row, 3, status_item)
        
        self.table.setItem(row, 4, QTableWidgetItem(result_pkg.get("details", "")))
        self.table.scrollToBottom()

        # Summary card (keep last 5)
        summary = f"{'✔' if passed else '✖'} {result_pkg.get('scenario', 'Unknown')} — {result_pkg.get('details', '')}"
        self.summary_list.insertItem(0, summary)
        while self.summary_list.count() > 5:
            self.summary_list.takeItem(self.summary_list.count() - 1)

        compliance = result_pkg.get("compliance")
        if compliance:
            self.set_compliance(compliance)

    def set_compliance(self, compliance_results):
        self.compliance_table.setRowCount(0)
        for item in compliance_results:
            row = self.compliance_table.rowCount()
            self.compliance_table.insertRow(row)
            self.compliance_table.setItem(row, 0, QTableWidgetItem(item.get("name", "")))
            passed = item.get("passed", False)
            status = QTableWidgetItem("PASS" if passed else "FAIL")
            status.setForeground(QColor("green" if passed else "red"))
            self.compliance_table.setItem(row, 1, status)
            self.compliance_table.setItem(row, 2, QTableWidgetItem(item.get("details", "")))
