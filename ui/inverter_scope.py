from PyQt6.QtCore import pyqtSlot, QTimer, QPointF
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtGui import QPolygonF, QPen, QColor
import logging
import numpy as np
import collections
import pyqtgraph as pg
from src.signal_processing import compute_fft, compute_rms, compute_thd
from src.config_manager import ConfigManager
from ui.overlay import OverlayMessage

logger = logging.getLogger(__name__)

class InverterScope(QWidget):
    """
    Real-time 3-phase scope for VSM Inverter signals.
    Displays V_abc, I_abc, and control metrics.
    """
    def __init__(self, serial_mgr, parent=None):
        super().__init__(parent)
        self.serial_mgr = serial_mgr
        
        self.layout = QVBoxLayout(self)
        
        # Load Config
        ConfigManager.load()
        self.channels = ConfigManager.get_channel_config()
        
        # Data Buffers (Optimized with collections.deque)
        self.buffer_size = 500
        self.time_data = collections.deque(maxlen=self.buffer_size)
        self.data = {k: collections.deque(maxlen=self.buffer_size) for k in self.channels.keys()}

        # Store (t_arr, y_arr) snapshots to keep shapes aligned
        self._trail_buffers = {k: collections.deque(maxlen=3) for k in self.channels.keys()}
        self._trail_curves = {k: [] for k in self.channels.keys()}
        self._frame_count = 0
        
        self._init_ui()

        self.overlay = OverlayMessage(self)
        
        # Performance: Decouple update from input
        self.render_timer = QTimer()
        self.render_timer.timeout.connect(self._update_plot)
        self.render_timer.start(40) # 25Hz update rate is plenty for human eyes
        
        self.serial_mgr.frame_received.connect(self._on_frame)
        self.paused = False

    def _init_ui(self):
        header = QLabel("Inverter Scope — Live Telemetry")
        header.setStyleSheet("font-size: 12pt; font-weight: 700; color: #93c5fd;")
        self.layout.addWidget(header)

        # Controls
        control_layout = QHBoxLayout()
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Voltage", "Current", "Spectrum"])
        self.combo_mode.currentTextChanged.connect(self._on_mode_changed)
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setCheckable(True)
        self.btn_pause.toggled.connect(self._toggle_pause)
        
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_data)
        
        self.lbl_status = QLabel("Status: Live")
        
        control_layout.addWidget(self.btn_pause)
        control_layout.addWidget(self.btn_clear)
        control_layout.addWidget(self.combo_mode)
        control_layout.addWidget(self.lbl_status)
        control_layout.addStretch()
        self.layout.addLayout(control_layout)

        # Plots
        self.plot_v = pg.PlotWidget(title="3-Phase Voltage (V_abc)")
        self.plot_v.setBackground('#0b0f14')
        self.plot_v.showGrid(x=True, y=True, alpha=0.25)
        self.plot_v.setLabel('left', 'Voltage (V)')
        self.layout.addWidget(self.plot_v)
        
        # Energy ribbon overlays (RMS bands)
        self.energy_ribbons = {}
        for phase, color in [('a', (250, 204, 21)), ('b', (34, 197, 94)), ('c', (236, 72, 153))]:
            ribbon = pg.PlotCurveItem()
            ribbon.setPen(pg.mkPen((*color, 80), width=20, style=pg.Qt.QtCore.Qt.PenStyle.SolidLine))
            self.plot_v.addItem(ribbon)
            self.energy_ribbons[phase] = ribbon
        
        self.plot_i = pg.PlotWidget(title="3-Phase Current (I_abc)")
        self.plot_i.setBackground('#0b0f14')
        self.plot_i.showGrid(x=True, y=True, alpha=0.25)
        self.plot_i.setLabel('left', 'Current (A)')
        self.layout.addWidget(self.plot_i)

        self.plot_s = pg.PlotWidget(title="Spectrum (V_an)")
        self.plot_s.setBackground('#0b0f14')
        self.plot_s.showGrid(x=True, y=True, alpha=0.25)
        self.plot_s.setLabel('left', 'Magnitude')
        self.plot_s.setLabel('bottom', 'Frequency', units='Hz')
        self.layout.addWidget(self.plot_s)
        self.plot_s.hide()
        self.spectrum_curve = self.plot_s.plot(pen=pg.mkPen('#38bdf8', width=2))
        
        # Mini-FFT sparkline overlay (shows on hover)
        self.mini_fft_label = QLabel("")
        self.mini_fft_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 rgba(17, 24, 39, 240), 
                                            stop:1 rgba(15, 23, 42, 220));
                border: 2px solid rgba(16, 185, 129, 180);
                border-radius: 8px;
                padding: 8px 12px;
                color: #10b981;
                font-size: 9pt;
                font-weight: 700;
            }
        """)
        self.mini_fft_label.hide()
        self.layout.addWidget(self.mini_fft_label)
        
        # Connect mouse hover for time cursor
        self.plot_v.scene().sigMouseMoved.connect(self._on_mouse_hover)


        # Traces
        self.traces = {}
        colors = {'a': 'y', 'b': 'g', 'c': 'm'} 
        
        for ch, cfg in self.channels.items():
            if 'v_' in ch:
                phase = ch.split('_')[-1][0]
                self.traces[ch] = self.plot_v.plot(pen=colors.get(phase, 'w'), name=cfg['label'])
            elif 'i_' in ch:
                phase = ch.split('_')[-1][0]
                self.traces[ch] = self.plot_i.plot(pen=colors.get(phase, 'w'), name=cfg['label'])

            # Trail curves (faded history)
            trail_alpha = [60, 40, 25]
            for a in trail_alpha:
                pen = pg.mkPen(colors.get(ch.split('_')[-1][0], 'w'), width=1)
                color = pen.color().lighter(120)
                color.setAlpha(a)
                pen.setColor(color)
                target_plot = self.plot_v if 'v_' in ch else self.plot_i
                curve = target_plot.plot(pen=pen)
                self._trail_curves[ch].append(curve)

    @pyqtSlot(dict)
    def _on_frame(self, frame):
        if self.paused: return
        try:
            ts = frame.get('ts', 0)
            self.time_data.append(ts)
            for ch in self.data:
                self.data[ch].append(frame.get(ch, 0.0))
        except Exception:
            pass

    def _update_plot(self):
        if not self.time_data or self.paused: return
        
        # Batch conversions for performance
        t_arr = np.array(self.time_data)
        for ch, trace in self.traces.items():
            if ch in self.data:
                y_arr = np.array(self.data[ch])
                if len(t_arr) != len(y_arr):
                    continue
                trace.setData(t_arr, y_arr)
        
        # Update energy ribbon overlays (RMS bands with THD color saturation)
        for phase, ch_key in [('a', 'v_an'), ('b', 'v_bn'), ('c', 'v_cn')]:
            if ch_key in self.data and len(self.data[ch_key]) > 0:
                y_arr = np.array(self.data[ch_key])
                rms_val = compute_rms(y_arr)
                
                # Create ribbon at RMS level
                if len(t_arr) == len(y_arr):
                    ribbon_y = np.full_like(y_arr, rms_val)
                    self.energy_ribbons[phase].setData(t_arr, ribbon_y)
                    
                    # Color intensity based on THD
                    try:
                        thd = compute_thd(y_arr, 1.0/((t_arr[-1] - t_arr[0]) / len(t_arr)))
                        alpha = min(180, 80 + int(thd * 10))  # Higher THD = more opaque
                        color = (250, 204, 21) if phase == 'a' else (34, 197, 94) if phase == 'b' else (236, 72, 153)
                        self.energy_ribbons[phase].setPen(pg.mkPen((*color, alpha), width=20))
                    except:
                        pass

        if self.combo_mode.currentText() == "Spectrum":
            if 'v_an' in self.data:
                y_arr = np.array(self.data['v_an'])
                if len(t_arr) == len(y_arr) and len(t_arr) > 4:
                    freqs, mags = compute_fft(t_arr, y_arr)
                    self.spectrum_curve.setData(freqs, mags)

        # Update ghost trails every few frames
        self._frame_count += 1
        if self._frame_count % 4 == 0:
            for ch in self.data:
                y_arr = np.array(self.data[ch])
                if len(t_arr) != len(y_arr):
                    continue
                self._trail_buffers[ch].append((t_arr.copy(), y_arr.copy()))
                trails = list(self._trail_buffers[ch])
                for idx, curve in enumerate(self._trail_curves[ch]):
                    if idx < len(trails):
                        t_hist, y_hist = trails[-(idx+1)]
                        if len(t_hist) == len(y_hist):
                            curve.setData(t_hist, y_hist)
    
    def _on_mouse_hover(self, pos):
        """Show mini-FFT sparkline when hovering over waveform"""
        if not self.time_data or len(self.time_data) < 32:
            self.mini_fft_label.hide()
            return
        
        # Get mouse position in plot coordinates
        mouse_point = self.plot_v.plotItem.vb.mapSceneToView(pos)
        t_cursor = mouse_point.x()
        
        # Find nearest time index
        t_arr = np.array(self.time_data)
        idx = np.argmin(np.abs(t_arr - t_cursor))
        
        # Extract window around cursor
        window_size = 64
        start_idx = max(0, idx - window_size // 2)
        end_idx = min(len(t_arr), start_idx + window_size)
        
        if end_idx - start_idx < 16:
            self.mini_fft_label.hide()
            return
        
        # Compute FFT for window
        if 'v_an' in self.data:
            y_window = np.array(list(self.data['v_an']))[start_idx:end_idx]
            t_window = t_arr[start_idx:end_idx]
            
            if len(t_window) > 4 and len(y_window) == len(t_window):
                freqs, mags = compute_fft(t_window, y_window)
                
                # Find dominant frequency
                peak_idx = np.argmax(mags[1:10]) + 1  # Skip DC
                peak_freq = freqs[peak_idx] if peak_idx < len(freqs) else 0
                peak_mag = mags[peak_idx] if peak_idx < len(mags) else 0
                
                # Show sparkline info
                self.mini_fft_label.setText(
                    f"⚡ FFT @ t={t_cursor:.3f}s: Peak {peak_freq:.1f}Hz ({peak_mag:.1f}V)"
                )
                self.mini_fft_label.show()
            else:
                self.mini_fft_label.hide()
        else:
            self.mini_fft_label.hide()

    def _toggle_pause(self, checked):
        self.paused = checked
        self.lbl_status.setText("Status: Paused" if checked else "Status: Live")
        if checked:
            self.overlay.show_message("Paused", color="#f59e0b", pos=(10, 40))

    def _on_mode_changed(self, mode):
        if mode == "Voltage":
            self.plot_v.show()
            self.plot_i.hide()
            self.plot_s.hide()
        elif mode == "Current":
            self.plot_v.hide()
            self.plot_i.show()
            self.plot_s.hide()
        else:
            self.plot_v.hide()
            self.plot_i.hide()
            self.plot_s.show()

    def clear_data(self):
        self.time_data.clear()
        for k in self.data:
            self.data[k].clear()
        for trace in self.traces.values():
            trace.clear()
