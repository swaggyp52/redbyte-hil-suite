from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QDoubleSpinBox,
                             QHBoxLayout, QGroupBox, QCheckBox)
from PyQt6.QtCore import QTimer
import pyqtgraph as pg
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)


class SignalSculptor(QWidget):
    """
    Parametric Waveform Builder & Injector.
    Generates test signals and can inject them into the live data stream
    or send parameters to hardware for physical signal generation.
    """
    def __init__(self, serial_mgr):
        super().__init__()
        self.serial_mgr = serial_mgr
        self.layout = QVBoxLayout(self)

        header = QLabel("Signal Sculptor — Parametric Injection")
        header.setStyleSheet("font-size: 12pt; font-weight: 700; color: #a78bfa;")
        self.layout.addWidget(header)

        # Injection Timer
        self.inject_timer = QTimer()
        self.inject_timer.timeout.connect(self._on_inject_tick)
        self.inject_frames = []
        self._inject_idx = 0

        # --- Controls ---
        grp_ctrl = QGroupBox("Signal Parameters")
        form = QHBoxLayout()

        self.spin_freq = self._create_spin("Freq (Hz)", 60.0, 40.0, 70.0)
        self.spin_amp = self._create_spin("Amp (V pk)", 170.0, 0.0, 400.0)
        self.spin_noise = self._create_spin("Noise (V)", 0.0, 0.0, 20.0)
        self.spin_duration = self._create_spin("Duration (s)", 1.0, 0.1, 10.0)

        form.addLayout(self.spin_freq)
        form.addLayout(self.spin_amp)
        form.addLayout(self.spin_noise)
        form.addLayout(self.spin_duration)

        grp_ctrl.setLayout(form)
        self.layout.addWidget(grp_ctrl)

        # --- Preview ---
        self.plot = pg.PlotWidget(title="Waveform Preview (3-Phase)")
        self.plot.setBackground('#0b0f14')
        self.plot.setYRange(-400, 400)
        self.plot.showGrid(x=True, y=True)
        self.plot.addLegend()
        self.curve_a = self.plot.plot(pen='y', name="V_an")
        self.curve_b = self.plot.plot(pen='g', name="V_bn")
        self.curve_c = self.plot.plot(pen='m', name="V_cn")
        self.layout.addWidget(self.plot)

        # --- Options ---
        opt_layout = QHBoxLayout()
        self.chk_hardware = QCheckBox("Send to hardware")
        self.chk_hardware.setToolTip("If checked, sends waveform parameters to the hardware adapter")
        opt_layout.addWidget(self.chk_hardware)
        opt_layout.addStretch()
        self.layout.addLayout(opt_layout)

        # --- Action ---
        btn_layout = QHBoxLayout()
        self.btn_inject = QPushButton("Inject Waveform Burst")
        self.btn_inject.clicked.connect(self._start_injection)
        btn_layout.addWidget(self.btn_inject)

        self.lbl_status = QLabel("")
        btn_layout.addWidget(self.lbl_status)
        btn_layout.addStretch()
        self.layout.addLayout(btn_layout)

        self._update_preview()

    def _create_spin(self, label, val, min_val, max_val):
        layout = QVBoxLayout()
        lbl = QLabel(label)
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(val)
        spin.setSingleStep(0.1 if max_val <= 100 else 1.0)
        spin.valueChanged.connect(self._update_preview)
        layout.addWidget(lbl)
        layout.addWidget(spin)
        return layout

    @property
    def freq(self):
        return self.spin_freq.itemAt(1).widget().value()

    @property
    def amp(self):
        return self.spin_amp.itemAt(1).widget().value()

    @property
    def noise(self):
        return self.spin_noise.itemAt(1).widget().value()

    @property
    def duration(self):
        return self.spin_duration.itemAt(1).widget().value()

    def _update_preview(self):
        fs = 1000  # Hz preview resolution
        dur = min(2.0 / max(self.freq, 1), 0.1)  # Show ~2 cycles
        t = np.linspace(0, dur, int(dur * fs))

        v_a = self.amp * np.sin(2 * np.pi * self.freq * t)
        v_b = self.amp * np.sin(2 * np.pi * self.freq * t - 2.0944)
        v_c = self.amp * np.sin(2 * np.pi * self.freq * t + 2.0944)

        if self.noise > 0:
            v_a += np.random.normal(0, self.noise, len(t))
            v_b += np.random.normal(0, self.noise, len(t))
            v_c += np.random.normal(0, self.noise, len(t))

        self.curve_a.setData(t * 1000, v_a)  # ms on x-axis
        self.curve_b.setData(t * 1000, v_b)
        self.curve_c.setData(t * 1000, v_c)
        self.plot.setLabel('bottom', 'Time', units='ms')

    def _start_injection(self):
        if self.inject_timer.isActive():
            return

        f = self.freq
        a = self.amp
        n = self.noise
        dur = self.duration

        # Optionally send parameters to hardware
        if self.chk_hardware.isChecked() and self.serial_mgr:
            self.serial_mgr.write_command('inject_waveform', {
                'freq': f, 'amplitude': a, 'noise': n, 'duration': dur
            })
            self.lbl_status.setText("Sent to hardware")

        # Also generate local frames for UI visualization
        fs = 50  # Frame rate for UI injection
        t_steps = int(dur * fs)
        dt = 1.0 / fs

        self.inject_frames = []
        start_ts = time.time()

        for i in range(t_steps):
            t = i * dt
            v_an = a * np.sin(2 * np.pi * f * t) + np.random.normal(0, n)
            v_bn = a * np.sin(2 * np.pi * f * t - 2.0944) + np.random.normal(0, n)
            v_cn = a * np.sin(2 * np.pi * f * t + 2.0944) + np.random.normal(0, n)

            i_a = (a / 24.0) * np.sin(2 * np.pi * f * t - 0.1)
            i_b = (a / 24.0) * np.sin(2 * np.pi * f * t - 2.0944 - 0.1)
            i_c = (a / 24.0) * np.sin(2 * np.pi * f * t + 2.0944 - 0.1)

            frame = {
                "ts": start_ts + t,
                "v_an": float(v_an), "v_bn": float(v_bn), "v_cn": float(v_cn),
                "i_a": float(i_a), "i_b": float(i_b), "i_c": float(i_c),
                "freq": f,
                "p_mech": 0.0,
            }
            self.inject_frames.append(frame)

        self._inject_idx = 0
        self.btn_inject.setEnabled(False)
        self.btn_inject.setText("Injecting...")
        self.lbl_status.setText(f"Injecting {f:.1f}Hz, {a:.0f}V for {dur:.1f}s")
        self.inject_timer.start(int(1000 / fs))
        logger.info(f"Started injection: {f}Hz, {a}V, {dur}s")

    def _on_inject_tick(self):
        if self._inject_idx < len(self.inject_frames):
            frame = self.inject_frames[self._inject_idx]
            self.serial_mgr.frame_received.emit(frame)
            self._inject_idx += 1
        else:
            self.inject_timer.stop()
            self.btn_inject.setEnabled(True)
            self.btn_inject.setText("Inject Waveform Burst")
            self.lbl_status.setText("Injection complete")
            logger.info("Injection complete.")
