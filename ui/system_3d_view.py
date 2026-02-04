from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import pyqtSlot, QTimer, Qt
import numpy as np
import math
import collections
from src.signal_processing import compute_rms
from src.opengl_check import get_opengl_fallback_message

try:
    import pyqtgraph.opengl as gl
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False


class System3DView(QWidget):
    """
    3D Visualization of the HIL Testbed showing:
    - Inverter and Grid/Load blocks with wireframe representation
    - Rotating rotor element representing VSM virtual rotor angle
    - Phase-coded power flow lines with current-proportional width
    - Power flow direction arrows
    - Fault state visualization (color changes)
    """
    def __init__(self, serial_mgr, scenario_ctrl=None):
        super().__init__()
        self.serial_mgr = serial_mgr
        self.scenario_ctrl = scenario_ctrl
        self.layout = QVBoxLayout(self)

        header = QLabel("System 3D — Rotor & Power Flow")
        header.setStyleSheet("font-size: 12pt; font-weight: 700; color: #34d399;")
        self.layout.addWidget(header)

        if not OPENGL_AVAILABLE:
            fallback_label = QLabel(get_opengl_fallback_message())
            fallback_label.setWordWrap(True)
            fallback_label.setTextFormat(Qt.TextFormat.RichText)
            fallback_label.setStyleSheet("background: transparent;")
            self.layout.addWidget(fallback_label)
            self.layout.addStretch()
            return

        self.view = gl.GLViewWidget()
        self.view.opts['distance'] = 25
        self.view.opts['elevation'] = 25
        self.view.opts['azimuth'] = -60
        self.view.setWindowTitle('3D System View')
        self.layout.addWidget(self.view)

        # Info bar
        info_layout = QHBoxLayout()
        self.lbl_power = QLabel("P: -- W")
        self.lbl_freq = QLabel("f: -- Hz")
        self.lbl_rotor = QLabel("Rotor: --")
        info_layout.addWidget(self.lbl_power)
        info_layout.addWidget(self.lbl_freq)
        info_layout.addWidget(self.lbl_rotor)
        self.layout.addLayout(info_layout)

        # -- Scene Objects --

        # Grid (Ground)
        grid = gl.GLGridItem()
        grid.scale(2, 2, 1)
        grid.setColor((80, 80, 80, 100))
        self.view.addItem(grid)

        # Inverter Block (left)
        self.inverter_box = self._create_box_outline(center=(-5, 0, 1.5), size=3, color=(0.2, 0.8, 0.2, 1))
        self.view.addItem(self.inverter_box)

        # Grid/Load Block (right)
        self.load_box = self._create_box_outline(center=(5, 0, 1.5), size=2.5, color=(0.2, 0.2, 0.8, 1))
        self.view.addItem(self.load_box)

        # Rotor visualization: a rotating line inside the inverter "box"
        self._rotor_angle = 0.0
        rotor_pts = np.array([[-5, 0, 1.5], [-5 + 1.2, 0, 1.5]])
        self.rotor_line = gl.GLLinePlotItem(pos=rotor_pts, color=(1, 1, 0, 1), width=4, antialias=True)
        self.view.addItem(self.rotor_line)

        # Rotor tip marker
        self.rotor_tip = gl.GLScatterPlotItem(
            pos=np.array([[rotor_pts[1][0], rotor_pts[1][1], rotor_pts[1][2]]]),
            color=(1, 1, 0, 1), size=8
        )
        self.view.addItem(self.rotor_tip)

        # Power flow wires (3-phase)
        self.lines = {}
        self.arrows = {}
        colors = {
            'a': (1, 1, 0, 1),
            'b': (0, 1, 0, 1),
            'c': (1, 0, 1, 1)
        }

        self.wire_start = {
            'a': np.array([-3.5, -1.2, 1.5]),
            'b': np.array([-3.5, 0.0, 1.5]),
            'c': np.array([-3.5, 1.2, 1.5])
        }
        self.wire_end = {
            'a': np.array([3.5, -1.2, 1.5]),
            'b': np.array([3.5, 0.0, 1.5]),
            'c': np.array([3.5, 1.2, 1.5])
        }

        for p in ['a', 'b', 'c']:
            start = self.wire_start[p]
            end = self.wire_end[p]
            line = gl.GLLinePlotItem(
                pos=np.vstack([start, end]),
                color=colors[p], width=2, antialias=True
            )
            self.view.addItem(line)
            self.lines[p] = line

            # Power flow arrow (triangle marker at midpoint)
            mid = (start + end) / 2
            arrow_pts = np.array([
                mid + np.array([-0.3, 0, 0.2]),
                mid + np.array([0.3, 0, 0]),
                mid + np.array([-0.3, 0, -0.2]),
                mid + np.array([-0.3, 0, 0.2]),
            ])
            arrow = gl.GLLinePlotItem(pos=arrow_pts, color=colors[p], width=2)
            self.view.addItem(arrow)
            self.arrows[p] = arrow

        # Labels
        self._add_text_label("INVERTER\n(VSM)", (-5, 0, 4))
        self._add_text_label("GRID/LOAD", (5, 0, 4))

        self.serial_mgr.frame_received.connect(self._on_frame)
        if self.scenario_ctrl:
            self.scenario_ctrl.event_triggered.connect(self._on_event)

        # Internal state
        self._last_mags = {'a': 0.0, 'b': 0.0, 'c': 0.0}
        self._current_bufs = {k: collections.deque(maxlen=40) for k in ['a', 'b', 'c']}
        self._freq_buf = collections.deque(maxlen=20)
        self._power_buf = collections.deque(maxlen=20)
        self._fault_active = False
        self._angle_override = None
        self._rotor_trail = collections.deque(maxlen=40)

        self.rotor_trail_line = gl.GLLinePlotItem(color=(1, 1, 0, 0.25), width=2, antialias=True)
        self.view.addItem(self.rotor_trail_line)

        # Animation timer for rotor
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate_rotor)
        self._anim_timer.start(33)  # ~30 FPS

    def _add_text_label(self, text, pos):
        """Add a text label in the 3D scene (via GLTextItem if available)."""
        try:
            label = gl.GLTextItem(pos=np.array(pos), text=text, color=(200, 200, 200, 255))
            label.setData(font=None)
            self.view.addItem(label)
        except (AttributeError, TypeError):
            pass  # GLTextItem not available in all pyqtgraph versions

    def _create_box_outline(self, center, size, color):
        x, y, z = center
        s = size / 2
        pts = np.array([
            [x-s, y-s, z-s], [x+s, y-s, z-s],
            [x+s, y-s, z-s], [x+s, y+s, z-s],
            [x+s, y+s, z-s], [x-s, y+s, z-s],
            [x-s, y+s, z-s], [x-s, y-s, z-s],
            [x-s, y-s, z+s], [x+s, y-s, z+s],
            [x+s, y-s, z+s], [x+s, y+s, z+s],
            [x+s, y+s, z+s], [x-s, y+s, z+s],
            [x-s, y+s, z+s], [x-s, y-s, z+s],
            [x-s, y-s, z-s], [x-s, y-s, z+s],
            [x+s, y-s, z-s], [x+s, y-s, z+s],
            [x+s, y+s, z-s], [x+s, y+s, z+s],
            [x-s, y+s, z-s], [x-s, y+s, z+s]
        ])
        return gl.GLLinePlotItem(pos=pts, color=color, width=2, mode='lines')

    @pyqtSlot(str, dict)
    def _on_event(self, type_name, data):
        if "fault" in type_name.lower():
            self._fault_active = True
            self.inverter_box.setData(color=(1, 0, 0, 1), width=4)
        else:
            self._fault_active = False
            self.inverter_box.setData(color=(0.2, 0.8, 0.2, 1), width=2)

    @pyqtSlot(dict)
    def _on_frame(self, frame):
        # Buffer current values for RMS
        self._current_bufs['a'].append(frame.get('i_a', 0))
        self._current_bufs['b'].append(frame.get('i_b', 0))
        self._current_bufs['c'].append(frame.get('i_c', 0))
        self._freq_buf.append(frame.get('freq', 60.0))
        self._power_buf.append(frame.get('p_mech', 0))
        if 'angle' in frame:
            try:
                self._angle_override = math.radians(float(frame.get('angle')))
            except Exception:
                self._angle_override = None

        # Compute RMS currents for wire width
        alpha = 0.15
        for p in ['a', 'b', 'c']:
            rms = compute_rms(list(self._current_bufs[p]))
            self._last_mags[p] = alpha * rms + (1 - alpha) * self._last_mags[p]

        self._update_wires()

        # Update info labels
        avg_freq = np.mean(self._freq_buf) if self._freq_buf else 60.0
        avg_power = np.mean(self._power_buf) if self._power_buf else 0
        self.lbl_freq.setText(f"f: {avg_freq:.2f} Hz")
        self.lbl_power.setText(f"P: {avg_power:.0f} W")

    def _animate_rotor(self):
        """Animate the virtual rotor based on measured frequency."""
        if not OPENGL_AVAILABLE:
            return

        avg_freq = np.mean(self._freq_buf) if self._freq_buf else 60.0

        if self._angle_override is not None:
            self._rotor_angle = self._angle_override
        else:
            # Rotor rotates at grid frequency (scaled for visibility)
            # At 60Hz, one full rotation per second in the visualization
            dt = 0.033  # ~30ms per frame
            self._rotor_angle += 2 * math.pi * (avg_freq / 60.0) * dt

        # Compute rotor line endpoints
        cx, cy, cz = -5, 0, 1.5
        r = 1.2
        end_x = cx + r * math.cos(self._rotor_angle)
        end_y = cy + r * math.sin(self._rotor_angle)

        pts = np.array([[cx, cy, cz], [end_x, end_y, cz]])
        self.rotor_line.setData(pos=pts)
        self.rotor_tip.setData(pos=np.array([[end_x, end_y, cz]]))

        self._rotor_trail.append([end_x, end_y, cz])
        if len(self._rotor_trail) > 2:
            self.rotor_trail_line.setData(pos=np.array(self._rotor_trail))

        # Rotor color reflects fault state
        if self._fault_active:
            self.rotor_line.setData(pos=pts, color=(1, 0.3, 0.3, 1))
        else:
            self.rotor_line.setData(pos=pts, color=(1, 1, 0, 1))

        angle_deg = math.degrees(self._rotor_angle) % 360
        self.lbl_rotor.setText(f"Rotor: {angle_deg:.0f}")

    def _update_wires(self):
        for p in ['a', 'b', 'c']:
            rms = self._last_mags[p]
            width = max(1, int(rms * 0.8))
            start = self.wire_start[p]
            end = self.wire_end[p]

            # Wire brightness reflects current magnitude
            brightness = min(1.0, rms / 10.0)
            base_colors = {'a': (1, 1, 0), 'b': (0, 1, 0), 'c': (1, 0, 1)}
            r, g, b = base_colors[p]
            color = (r * brightness + 0.2, g * brightness + 0.2, b * brightness + 0.2, 1.0)

            self.lines[p].setData(pos=np.vstack([start, end]), width=width, color=color)

            # Update arrow position and direction
            mid = (start + end) / 2
            arrow_scale = min(0.5, rms * 0.1)
            arrow_pts = np.array([
                mid + np.array([-arrow_scale, 0, arrow_scale * 0.6]),
                mid + np.array([arrow_scale, 0, 0]),
                mid + np.array([-arrow_scale, 0, -arrow_scale * 0.6]),
                mid + np.array([-arrow_scale, 0, arrow_scale * 0.6]),
            ])
            self.arrows[p].setData(pos=arrow_pts, color=color)
