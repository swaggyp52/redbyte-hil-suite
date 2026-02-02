from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSlider, QLabel, QHBoxLayout, QCheckBox
from PyQt6.QtCore import pyqtSlot, Qt, QTimer
import pyqtgraph as pg
import numpy as np
import math
import collections
from src.signal_processing import extract_three_phase_phasors, compute_rms
from ui.overlay import OverlayMessage

PHASOR_BUF_SIZE = 200  # Samples buffered for phasor extraction (~4 cycles at 50Hz/60Hz)
TRAIL_LENGTH = 20  # Number of historical phasor positions to show


class PhasorView(QWidget):
    """
    Displays 3-Phase Voltage phasors with real-time angle extraction
    using Hilbert transform. Shows magnitude, phase angle, and balance status.
    """
    def __init__(self, serial_mgr):
        super().__init__()
        self.serial_mgr = serial_mgr
        self.layout = QVBoxLayout(self)

        header = QLabel("Phasor View — Live Angles")
        header.setStyleSheet("font-size: 12pt; font-weight: 700; color: #f472b6;")
        self.layout.addWidget(header)

        self.overlay = OverlayMessage(self)

        # Header Controls
        ctrl_layout = QHBoxLayout()
        self.lbl_scale = QLabel("Range: 200V")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(50, 600)
        self.slider.setValue(200)
        self.slider.valueChanged.connect(self._on_scale_changed)
        ctrl_layout.addWidget(QLabel("Scale:"))
        ctrl_layout.addWidget(self.slider)
        ctrl_layout.addWidget(self.lbl_scale)

        self.chk_trail = QCheckBox("Trail")
        self.chk_trail.setChecked(True)
        ctrl_layout.addWidget(self.chk_trail)

        self.layout.addLayout(ctrl_layout)

        # Polar Plot Widget
        self.plot_widget = pg.PlotWidget(title="Phasor Diagram (Real-Time)")
        self.plot_widget.setBackground('#0b0f14')
        self.plot_widget.setAspectLocked(True)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._set_range(200)
        self.plot_widget.hideAxis('bottom')
        self.plot_widget.hideAxis('left')

        # Reference circle at nominal voltage
        self.ref_circle = pg.Qt.QtWidgets.QGraphicsEllipseItem(-120, -120, 240, 240)
        self.ref_circle.setPen(pg.mkPen('w', style=Qt.PenStyle.DashLine, width=1))
        self.plot_widget.addItem(self.ref_circle)

        # Crosshairs
        self.plot_widget.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen('w', width=0.5, style=Qt.PenStyle.DotLine)))
        self.plot_widget.addItem(pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('w', width=0.5, style=Qt.PenStyle.DotLine)))

        self.layout.addWidget(self.plot_widget)

        # Phasor arrow plots
        self.arrows = {
            'v_a': self.plot_widget.plot(pen=pg.mkPen('y', width=3), name="V_a"),
            'v_b': self.plot_widget.plot(pen=pg.mkPen('g', width=3), name="V_b"),
            'v_c': self.plot_widget.plot(pen=pg.mkPen('m', width=3), name="V_c"),
        }

        # Trail scatter plots (historical phasor tips)
        self.trails = {
            'v_a': self.plot_widget.plot(pen=None, symbol='o', symbolSize=3, symbolBrush='y'),
            'v_b': self.plot_widget.plot(pen=None, symbol='o', symbolSize=3, symbolBrush='g'),
            'v_c': self.plot_widget.plot(pen=None, symbol='o', symbolSize=3, symbolBrush='m'),
        }
        self._trail_history = {k: collections.deque(maxlen=TRAIL_LENGTH) for k in ['v_a', 'v_b', 'v_c']}
        self._ab_hist = collections.deque(maxlen=25)
        self._ac_hist = collections.deque(maxlen=25)
        self._trail_lines = {
            'v_a': self.plot_widget.plot(pen=pg.mkPen((250, 204, 21, 80), width=1)),
            'v_b': self.plot_widget.plot(pen=pg.mkPen((34, 197, 94, 80), width=1)),
            'v_c': self.plot_widget.plot(pen=pg.mkPen((236, 72, 153, 80), width=1)),
        }
        
        # Event markers (for tag clicks, peak THD moments)
        self.event_dots = self.plot_widget.plot(
            pen=None, symbol='star', symbolSize=10, 
            symbolBrush=pg.mkBrush(16, 185, 129, 220),
            symbolPen=pg.mkPen('w', width=2)
        )
        self._event_positions = []
        
        # Angular deviation bands (tolerance zones)
        self.deviation_bands = []
        for angle_deg in [0, 120, 240]:  # Ideal 3-phase positions
            band = pg.Qt.QtWidgets.QGraphicsEllipseItem(-150, -150, 300, 300)
            band.setPen(pg.mkPen((59, 130, 246, 40), width=20, style=Qt.PenStyle.SolidLine))
            band.setStartAngle(int((angle_deg - 15) * 16))  # Qt uses 1/16th degree units
            band.setSpanAngle(int(30 * 16))  # ±15° tolerance band
            self.plot_widget.addItem(band)
            self.deviation_bands.append(band)

        # Info labels
        info_layout = QHBoxLayout()
        self.lbl_rms = QLabel("RMS: --")
        self.lbl_angles = QLabel("Angles: --")
        self.lbl_balance = QLabel("Balance: --")
        self.lbl_trend = QLabel("Δθ Trend: --")
        info_layout.addWidget(self.lbl_rms)
        info_layout.addWidget(self.lbl_angles)
        info_layout.addWidget(self.lbl_balance)
        info_layout.addWidget(self.lbl_trend)
        self.layout.addLayout(info_layout)

        # Internal Buffers for phasor extraction
        self._buf = {
            'v_a': collections.deque(maxlen=PHASOR_BUF_SIZE),
            'v_b': collections.deque(maxlen=PHASOR_BUF_SIZE),
            'v_c': collections.deque(maxlen=PHASOR_BUF_SIZE),
            'ts': collections.deque(maxlen=PHASOR_BUF_SIZE),
        }

        self.render_timer = QTimer()
        self.render_timer.timeout.connect(self._render_phasors)
        self.render_timer.start(80)  # ~12Hz for phasor update (computation-heavy)

        self.serial_mgr.frame_received.connect(self._on_frame)

    def _on_scale_changed(self, val):
        self._set_range(val)
        self.lbl_scale.setText(f"Range: {val}V")

    def _set_range(self, val):
        self.plot_widget.setXRange(-val, val)
        self.plot_widget.setYRange(-val, val)

    @pyqtSlot(dict)
    def _on_frame(self, frame):
        self._buf['v_a'].append(frame.get('v_an', 0))
        self._buf['v_b'].append(frame.get('v_bn', 0))
        self._buf['v_c'].append(frame.get('v_cn', 0))
        self._buf['ts'].append(frame.get('ts', 0))

    def _render_phasors(self):
        if len(self._buf['v_a']) < 32:
            return

        # Extract real phasors using Hilbert transform
        va = list(self._buf['v_a'])
        vb = list(self._buf['v_b'])
        vc = list(self._buf['v_c'])
        ts = list(self._buf['ts'])

        result = extract_three_phase_phasors(va, vb, vc, time_data=ts)

        if result is None:
            # Fallback: just show RMS with default angles
            rms_a = compute_rms(va)
            rms_b = compute_rms(vb)
            rms_c = compute_rms(vc)
            self._draw_vector('v_a', rms_a, 90)
            self._draw_vector('v_b', rms_b, -30)
            self._draw_vector('v_c', rms_c, 210)
            self.lbl_rms.setText(f"RMS: A={rms_a:.1f} B={rms_b:.1f} C={rms_c:.1f}")
            self.lbl_angles.setText("Angles: (fallback)")
            self.lbl_balance.setText("")
            return

        # Draw vectors with extracted angles
        mag_a = result['a']['magnitude']
        mag_b = result['b']['magnitude']
        mag_c = result['c']['magnitude']
        ang_a = result['a']['angle_deg']
        ang_b = result['b']['angle_deg']
        ang_c = result['c']['angle_deg']

        self._draw_vector('v_a', mag_a, ang_a)
        self._draw_vector('v_b', mag_b, ang_b)
        self._draw_vector('v_c', mag_c, ang_c)

        # Update info
        self.lbl_rms.setText(f"RMS: A={mag_a:.1f}V  B={mag_b:.1f}V  C={mag_c:.1f}V")
        self.lbl_angles.setText(
            f"AB={result['ab_angle']:.1f}  AC={result['ac_angle']:.1f}"
        )

        self._ab_hist.append(result['ab_angle'])
        self._ac_hist.append(result['ac_angle'])
        avg_ab = sum(self._ab_hist) / len(self._ab_hist)
        avg_ac = sum(self._ac_hist) / len(self._ac_hist)
        self.lbl_trend.setText(f"Δθ Avg: AB={avg_ab:.1f} AC={avg_ac:.1f}")

        bal_str = "BALANCED" if result['balanced'] else "UNBALANCED"
        bal_color = "green" if result['balanced'] else "red"
        self.lbl_balance.setText(f"<span style='color:{bal_color}'>{bal_str}</span>")

        if not result['balanced']:
            self.overlay.show_message("Unbalanced Phasor", color="#ef4444", pos=(10, 40))

        # Update trails
        if self.chk_trail.isChecked():
            for key, ang, mag in [('v_a', ang_a, mag_a), ('v_b', ang_b, mag_b), ('v_c', ang_c, mag_c)]:
                rad = math.radians(ang)
                x = mag * math.cos(rad)
                y = mag * math.sin(rad)
                self._trail_history[key].append((x, y))
                pts = list(self._trail_history[key])
                if pts:
                    xs, ys = zip(*pts)
                    self.trails[key].setData(list(xs), list(ys))
                    self._trail_lines[key].setData(list(xs), list(ys))
        else:
            for key in self.trails:
                self.trails[key].setData([], [])
                self._trail_lines[key].setData([], [])

    def _draw_vector(self, name, mag, angle_deg):
        rad = math.radians(angle_deg)
        x = mag * math.cos(rad)
        y = mag * math.sin(rad)
        self.arrows[name].setData([0, x], [0, y])
    
    def add_event_marker(self, event_type="tag"):
        """Add an event marker at the current phasor tip positions"""
        if len(self._trail_history['v_a']) > 0:
            # Add marker at most recent position
            pos = self._trail_history['v_a'][-1]
            self._event_positions.append(pos)
            
            # Keep only last 10 events
            if len(self._event_positions) > 10:
                self._event_positions.pop(0)
            
            # Update event dots
            if self._event_positions:
                xs, ys = zip(*self._event_positions)
                self.event_dots.setData(list(xs), list(ys))
            
            self.overlay.show_message(f"⭐ Event marked: {event_type}", duration=1500)
    
    def update_deviation_bands(self, show=True, tolerance_deg=15):
        """Update visibility and size of angular deviation bands"""
        for i, angle_deg in enumerate([0, 120, 240]):
            if show:
                self.deviation_bands[i].setStartAngle(int((angle_deg - tolerance_deg) * 16))
                self.deviation_bands[i].setSpanAngle(int(tolerance_deg * 2 * 16))
                self.deviation_bands[i].setVisible(True)
            else:
                self.deviation_bands[i].setVisible(False)
