from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
                             QLabel, QFileDialog, QComboBox, QTabWidget, QInputDialog,
                             QCheckBox, QFrame, QGridLayout, QTableWidget,
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
import threading
import pyqtgraph as pg
import pyqtgraph.exporters
import json
import time
import os
import logging
import numpy as np
from dataclasses import replace as _dc_replace
from src.signal_processing import compute_rms, compute_thd, compute_fft
from src.event_detector import detect_events
from src.comparison import dataset_from_capsule
from src.derived_channels import ensure_capsule_derived_channels
from src.session_analysis import build_metric_rows, compute_session_metrics
from ui.comparison_panel import ComparisonPanel
from ui.event_lane import EventLane

logger = logging.getLogger(__name__)


def _cap_dataset_for_events(dataset, max_samples: int = 50_000):
    """
    Return a downsampled copy of *dataset* so event detection never blocks
    the main thread on huge full-resolution recordings.

    At 10 MSa/s a 1 M-row import is only 0.1 s of data; 50 K samples is more
    than enough to detect sags, flatlines, THD spikes, and clipping reliably.
    """
    n = int(dataset.time.size)
    if n <= max_samples:
        return dataset
    step = max(1, n // max_samples)
    idx = np.arange(0, n, step)
    new_time = dataset.time[idx]
    new_channels = {ch: arr[idx] for ch, arr in dataset.channels.items()}
    new_sr = (
        1.0 / float(np.median(np.diff(new_time)))
        if len(new_time) > 1
        else dataset.sample_rate
    )
    return _dc_replace(dataset, time=new_time, channels=new_channels, sample_rate=new_sr)


class ReplayStudio(QWidget):
    """
    Advanced Replay Interface with:
    - Timeline scrubber and visual event markers
    - Multi-run overlay comparison
    - Derived metrics timeline (RMS, THD, frequency)
    - PNG export
    """
    # Emitted after event detection completes so parent can update summaries.
    events_detected = pyqtSignal(int)
    # Carries the full list of DetectedEvent objects for the insights panel.
    events_ready = pyqtSignal(list)
    # Internal signals: background worker → Qt main-thread UI update.
    _bg_analysis_ready = pyqtSignal(dict, str)   # (result_dict, session_label)
    _bg_events_ready   = pyqtSignal(list, str)   # (events_list, session_label)

    def __init__(self, recorder, serial_mgr):
        super().__init__()
        self.recorder = recorder
        self.serial_mgr = serial_mgr

        self.sessions = []  # List of loaded sessions [{data, label, color}]
        self.active_session = None  # Index of session being played
        self.is_playing = False
        self.play_idx = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self._is_scrubbing = False

        self.layout = QVBoxLayout(self)

        # --- Toolbar ---
        ctrl = QHBoxLayout()
        self.btn_load = QPushButton("Load Session")
        self.btn_load.clicked.connect(self._load)

        self.btn_overlay = QPushButton("Add Overlay")
        self.btn_overlay.clicked.connect(self._add_overlay)
        self.btn_overlay.setToolTip("Load a primary session first")
        self.btn_overlay.setEnabled(False)

        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.clicked.connect(self._clear_all)
        self.btn_clear.setEnabled(False)

        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_play.setEnabled(False)

        self.btn_export = QPushButton("Export Plot")
        self.btn_export.clicked.connect(self._export_plot)
        self.btn_export.setEnabled(False)
        self.btn_export.setToolTip("Load a session first")

        self.btn_quick_export = QPushButton("⚡ Quick Export")
        self.btn_quick_export.clicked.connect(self._on_quick_export)
        self.btn_quick_export.setEnabled(False)
        self.btn_quick_export.setToolTip("Export evidence package to artifacts/evidence_exports/ (no dialog)")

        self.btn_reset_zoom = QPushButton("Reset Zoom")
        self.btn_reset_zoom.setToolTip("Reset all plots to auto-range")
        self.btn_reset_zoom.clicked.connect(self._reset_zoom)
        self.btn_reset_zoom.setEnabled(False)

        self.chk_link_axes = QCheckBox("Link Axes")
        self.chk_link_axes.setChecked(True)
        self.chk_link_axes.setToolTip("Keep the replay plots on the same time window")
        self.chk_link_axes.toggled.connect(self._set_axes_linked)

        self.lbl_time = QLabel("0.00s")

        ctrl.addWidget(self.btn_load)
        ctrl.addWidget(self.btn_overlay)
        ctrl.addWidget(self.btn_clear)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_reset_zoom)
        ctrl.addWidget(self.chk_link_axes)
        ctrl.addWidget(self.btn_export)
        ctrl.addWidget(self.btn_quick_export)
        ctrl.addWidget(self.lbl_time)
        ctrl.addStretch()

        # Crosshair readout label
        self._readout = QLabel("")
        self._readout.setStyleSheet(
            "color: #94a3b8; font-family: 'JetBrains Mono', 'Consolas', monospace;"
            " font-size: 8pt; padding: 0 8px;"
        )
        ctrl.addWidget(self._readout)
        self.layout.addLayout(ctrl)

        # --- Channel Toggle Panel (hidden until session loaded) ---
        self._channel_bar = QWidget()
        self._channel_bar.setVisible(False)
        ch_bar_layout = QHBoxLayout(self._channel_bar)
        ch_bar_layout.setContentsMargins(4, 2, 4, 2)
        ch_bar_layout.setSpacing(8)
        ch_lbl = QLabel("Channels:")
        ch_lbl.setStyleSheet("color: #64748b; font-size: 8pt; font-weight: 600;")
        ch_bar_layout.addWidget(ch_lbl)
        self._channel_checks: dict[str, QCheckBox] = {}
        ch_bar_layout.addStretch()
        self.layout.addWidget(self._channel_bar)

        # --- Tab Widget for waveform vs metrics ---
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Tab 1: Analysis replay dashboard
        wave_container = QWidget()
        wave_layout = QVBoxLayout(wave_container)
        wave_layout.setContentsMargins(0, 0, 0, 0)
        wave_layout.setSpacing(6)

        self._wave_summary = QLabel("")
        self._wave_summary.setStyleSheet(
            "color: #cbd5e1; font-size: 10pt; font-weight: 600; "
            "padding: 6px 10px; background: rgba(15,23,42,140); "
            "border: 1px solid rgba(51,65,85,140); border-radius: 6px;"
        )
        self._wave_summary.setWordWrap(True)
        wave_layout.addWidget(self._wave_summary)

        self.plot_wave = pg.PlotWidget(title="Phase Voltages")
        self.plot_wave.setBackground('#0b0f14')
        self.plot_wave.showGrid(x=True, y=True, alpha=0.3)
        self.plot_wave.setLabel('left', 'Voltage', units='V')
        self.plot_wave.setLabel('bottom', 'Time', units='s')
        self.plot_wave.addLegend()
        wave_layout.addWidget(self.plot_wave, stretch=3)

        self.plot_line = pg.PlotWidget(title="Line-to-Line Voltages")
        self.plot_line.setBackground('#0b0f14')
        self.plot_line.showGrid(x=True, y=True, alpha=0.3)
        self.plot_line.setLabel('left', 'Voltage', units='V')
        self.plot_line.setLabel('bottom', 'Time', units='s')
        self.plot_line.addLegend()
        wave_layout.addWidget(self.plot_line, stretch=2)

        self.plot_current = pg.PlotWidget(title="Phase Currents")
        self.plot_current.setBackground('#0b0f14')
        self.plot_current.showGrid(x=True, y=True, alpha=0.3)
        self.plot_current.setLabel('left', 'Current', units='A')
        self.plot_current.setLabel('bottom', 'Time', units='s')
        self.plot_current.addLegend()
        wave_layout.addWidget(self.plot_current, stretch=2)

        self.plot_aux = pg.PlotWidget(title="Auxiliary Signals")
        self.plot_aux.setBackground('#0b0f14')
        self.plot_aux.showGrid(x=True, y=True, alpha=0.3)
        self.plot_aux.setLabel('left', 'Value')
        self.plot_aux.setLabel('bottom', 'Time', units='s')
        self.plot_aux.addLegend()
        wave_layout.addWidget(self.plot_aux, stretch=1)

        self.tabs.addTab(wave_container, "Replay")

        # Crosshair cursor lines (hover readout)
        self._crosshair_v = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen('#475569', width=1, style=Qt.PenStyle.DotLine),
        )
        self._crosshair_h = pg.InfiniteLine(
            angle=0, movable=False,
            pen=pg.mkPen('#475569', width=1, style=Qt.PenStyle.DotLine),
        )
        self.plot_wave.addItem(self._crosshair_v, ignoreBounds=True)
        self.plot_wave.addItem(self._crosshair_h, ignoreBounds=True)
        self._crosshair_v.setVisible(False)
        self._crosshair_h.setVisible(False)

        # Connect mouse-move for crosshair
        self._proxy = pg.SignalProxy(
            self.plot_wave.scene().sigMouseMoved,
            rateLimit=30, slot=self._on_mouse_moved,
        )

        # Tab 2: Derived Metrics (RMS, THD, Freq over time)
        metrics_container = QWidget()
        metrics_layout = QVBoxLayout(metrics_container)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(4)
        self.plot_metrics = pg.PlotWidget(title="Derived Metrics")
        self.plot_metrics.setBackground('#0b0f14')
        self.plot_metrics.showGrid(x=True, y=True, alpha=0.3)
        self.plot_metrics.setLabel('bottom', 'Time', units='s')
        self.plot_metrics.addLegend()
        metrics_layout.addWidget(self.plot_metrics, stretch=1)

        self._metric_cards: dict[str, QLabel] = {}
        self._metric_cards_container = QWidget()
        cards_layout = QGridLayout(self._metric_cards_container)
        cards_layout.setContentsMargins(4, 4, 4, 4)
        cards_layout.setHorizontalSpacing(8)
        cards_layout.setVerticalSpacing(8)
        card_keys = [
            ("phase_rms", "Phase RMS"),
            ("line_rms", "Line-to-Line RMS"),
            ("thd", "THD"),
            ("freq", "Frequency"),
            ("window", "Display Window"),
            ("derived", "Derived Channels"),
        ]
        for i, (key, title) in enumerate(card_keys):
            card = QFrame()
            card.setObjectName("MetricChip")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(2)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color: #94a3b8; font-size: 8pt; font-weight: 600;")
            value_lbl = QLabel("—")
            value_lbl.setStyleSheet("color: #e2e8f0; font-size: 9pt; font-weight: 700;")
            value_lbl.setWordWrap(True)
            card_layout.addWidget(title_lbl)
            card_layout.addWidget(value_lbl)
            self._metric_cards[key] = value_lbl
            cards_layout.addWidget(card, i // 3, i % 3)
        metrics_layout.addWidget(self._metric_cards_container)

        self._metrics_summary = QLabel("")
        self._metrics_summary.setStyleSheet(
            "color: #94a3b8; font-size: 11px; padding: 6px 8px; "
            "background: rgba(15,23,42,96); border: 1px solid rgba(51,65,85,96); "
            "border-radius: 6px;"
        )
        self._metrics_summary.setWordWrap(True)
        metrics_layout.addWidget(self._metrics_summary)
        self._metrics_table = QTableWidget(0, 5)
        self._metrics_table.setHorizontalHeaderLabels(
            ["Section", "Metric", "Value", "Units", "Notes"]
        )
        self._metrics_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._metrics_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._metrics_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._metrics_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._metrics_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self._metrics_table.setAlternatingRowColors(True)
        self._metrics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        metrics_layout.addWidget(self._metrics_table, stretch=1)
        self.tabs.addTab(metrics_container, "Metrics")

        # Tab 3: Spectrum
        self.plot_spectrum = pg.PlotWidget(title="Spectrum")
        self.plot_spectrum.setBackground('#0b0f14')
        self.plot_spectrum.showGrid(x=True, y=True, alpha=0.3)
        self.plot_spectrum.setLabel('bottom', 'Frequency', units='Hz')
        self.plot_spectrum.setLabel('left', 'Magnitude')
        self.tabs.addTab(self.plot_spectrum, "Spectrum")
        self._spectrum_curve = self.plot_spectrum.plot(pen=pg.mkPen('#38bdf8', width=2))
        self._spectrum_peaks = pg.ScatterPlotItem(size=8, brush=pg.mkBrush('#f97316'))
        self.plot_spectrum.addItem(self._spectrum_peaks)
        self._spectrum_label = pg.TextItem("", color='#f97316')
        self.plot_spectrum.addItem(self._spectrum_label)
        self._spectrum_peaks.sigClicked.connect(self._on_spectrum_click)

        # Tab 4: Comparison
        self._comparison_tab = ComparisonPanel()
        self.tabs.addTab(self._comparison_tab, "Compare")

        # Tab 5: Events
        self._event_lane = EventLane()
        self.tabs.addTab(self._event_lane, "Events")

        self._linked_plots = (self.plot_line, self.plot_current, self.plot_aux)
        self._set_axes_linked(self.chk_link_axes.isChecked())

        tab_bar = self.tabs.tabBar()
        tab_bar.setTabVisible(self.tabs.indexOf(self.plot_spectrum), False)
        tab_bar.setTabVisible(self.tabs.indexOf(self._event_lane), False)

        # Interactive Scrubber
        self.scrubber = pg.InfiniteLine(pos=0, angle=90, movable=True, pen=pg.mkPen('w', width=2))
        self.scrubber.sigDragged.connect(self._on_scrubber_dragged)
        self.scrubber.sigPositionChangeFinished.connect(self._on_scrubber_release)
        self.plot_wave.addItem(self.scrubber)
        self.plot_wave.scene().sigMouseClicked.connect(self._on_wave_click)
        self._event_lane.event_selected.connect(self._seek_to_time)
        self._bg_analysis_ready.connect(self._on_bg_analysis_ready)
        self._bg_events_ready.connect(self._on_bg_events_ready)

        self.markers = []
        self._ts_arr = np.array([])
        self._wave_curves = []
        self._metric_curves = []
        self._tags = []
        self._tag_data = []
        self._last_spectrum_ts = 0.0
        self._session_time_range = (0.0, 1.0)

        # Session colors for overlay
        self._session_colors = [
            ('y', 'g', 'm'),      # Primary session
            ('c', 'b', 'r'),      # Overlay 1
            ((255,165,0), (100,200,100), (200,100,200)),  # Overlay 2
        ]

    def _load(self):
        """Load a primary session (replaces current)."""
        fname, _ = QFileDialog.getOpenFileName(self, "Open Session", os.getcwd(), "JSON Files (*.json)")
        if not fname:
            return
        self._clear_all()
        self._load_session(fname, is_primary=True)

    def _add_overlay(self):
        """Load an additional session for overlay comparison."""
        if not self.sessions:
            self._load()
            return
        fname, _ = QFileDialog.getOpenFileName(self, "Add Overlay Session", os.getcwd(), "JSON Files (*.json)")
        if fname:
            self._load_session(fname, is_primary=False)

    def _load_session(self, fname, is_primary=True):
        if is_primary:
            self._clear_all()
        try:
            with open(fname, 'r') as f:
                data = json.load(f)
            label = os.path.basename(fname).replace('.json', '')
            self._load_session_from_data(data, label, is_primary, path=fname)
        except Exception as e:
            logger.error(f"Failed to load session: {e}")

    def load_session_from_dict(self, data: dict, label: str = "", is_primary: bool = True):
        """
        Load a session from an in-memory Data Capsule dict.

        Called by AppShell after an ImportDialog import.  The dict may contain
        an extra '_dataset' key with the full-resolution ImportedDataset;
        this is preserved in the session record for analysis tabs.

        Args:
            data:       Data Capsule dict (meta + frames + …).
            label:      Display label for the loaded session.
            is_primary: True = replaces the primary session.
        """
        if is_primary:
            self._clear_all()
        if not label:
            label = data.get("meta", {}).get("session_id", "imported")
        self._load_session_from_data(data, label, is_primary, path=None)

    def get_primary_capsule(self) -> dict | None:
        """Return the primary session's Data Capsule dict, or None if no session loaded."""
        primary = next((s for s in self.sessions if s.get("is_primary")), None)
        return primary["data"] if primary is not None else None

    def get_events(self) -> list:
        """Return detected events for the primary session (read-only copy)."""
        return self._event_lane.get_events()

    def get_annotations(self) -> dict:
        """Return user annotations keyed by ts_start string."""
        return self._event_lane.get_annotations()

    def _load_session_from_data(self, data: dict, label: str, is_primary: bool, path=None):
        """Internal: accept an already-parsed Data Capsule dict."""
        if is_primary and self.sessions:
            self._clear_all()
        ensure_capsule_derived_channels(data)
        frames = data.get('frames', [])
        if not frames:
            logger.warning("Session '%s' has no frames — nothing to display.", label)
            return

        # Collect warnings from imported files and show them
        import_meta = data.get('import_meta', {})
        for w in import_meta.get('warnings', []):
            logger.info("[Import warning] %s: %s", label, w)

        idx = len(self.sessions)
        colors = self._session_colors[min(idx, len(self._session_colors) - 1)]

        session = {
            'data': data,
            'frames': frames,
            'label': label,
            'colors': colors,
            'is_primary': is_primary,
            'path': path,
            '_dataset': data.get('_dataset'),  # full-res ImportedDataset or None
        }
        self.sessions.append(session)

        if is_primary:
            self.active_session = idx

        try:
            self._render_all_sessions()
        except Exception:
            logger.exception("Error rendering session '%s' — session loaded but display may be incomplete.", label)
        self._update_comparison_tab()
        # Event detection and metrics are now handled by background workers
        # started inside _render_all_sessions via _start_background_* methods.
        self._sync_button_state()
        logger.info("Loaded session '%s' with %d frames (overlay=%s)", label, len(frames), not is_primary)

    def _render_all_sessions(self):
        """Re-render all loaded sessions across the analysis plots."""
        self.plot_wave.clear()
        self.plot_wave.addItem(self.scrubber)
        self.plot_wave.addItem(self._crosshair_v, ignoreBounds=True)
        self.plot_wave.addItem(self._crosshair_h, ignoreBounds=True)
        self.plot_line.clear()
        self.plot_current.clear()
        self.plot_aux.clear()
        self.plot_metrics.clear()
        self._clear_markers()
        self._wave_curves = []
        self._metric_curves = []

        primary_session = next((s for s in self.sessions if s.get('is_primary')), None)
        primary_phase_channels: list[str] = []
        primary_line_channels: list[str] = []
        primary_current_channels: list[str] = []
        primary_aux_channels: list[str] = []
        primary_generic_channels: list[str] = []

        for session in self.sessions:
            frames = session['frames']
            if not frames:
                continue

            colors = session['colors']
            label = session['label']
            suffix = f" ({label})" if len(self.sessions) > 1 else ""
            style = Qt.PenStyle.SolidLine if session['is_primary'] else Qt.PenStyle.DashLine
            ts = self._build_display_time(frames)
            sample_frame = frames[0]

            def _is_boolean_channel(key: str) -> bool:
                vals = {f.get(key) for f in frames[:40] if isinstance(f.get(key), (int, float))}
                return bool(vals) and vals.issubset({0, 1, 0.0, 1.0})

            numeric_channels = [
                key for key in sample_frame
                if key not in {'ts', 'display_time_s'} and isinstance(sample_frame.get(key), (int, float))
                and not _is_boolean_channel(key)
            ]
            phase_channels = [ch for ch in ('v_an', 'v_bn', 'v_cn') if ch in numeric_channels]
            line_channels = [ch for ch in ('v_ab', 'v_bc', 'v_ca') if ch in numeric_channels]
            current_channels = [ch for ch in ('i_a', 'i_b', 'i_c') if ch in numeric_channels]
            aux_channels = [ch for ch in ('freq', 'p_mech', 'v_dc') if ch in numeric_channels]
            generic_channels = [
                ch for ch in numeric_channels
                if ch not in set(phase_channels + line_channels + current_channels + aux_channels)
            ]

            if session['is_primary']:
                primary_phase_channels = phase_channels
                primary_line_channels = line_channels
                primary_current_channels = current_channels
                primary_aux_channels = aux_channels or generic_channels[:2]
                primary_generic_channels = generic_channels
                if ts.size:
                    self._session_time_range = (float(ts[0]), float(ts[-1]))

            if phase_channels:
                self._plot_channel_group(self.plot_wave, frames, ts, phase_channels, colors, style, suffix)
            elif not session['is_primary'] and generic_channels:
                self._plot_channel_group(self.plot_wave, frames, ts, generic_channels[:3], colors, style, suffix)
            elif session['is_primary'] and generic_channels:
                self._plot_channel_group(self.plot_wave, frames, ts, generic_channels[:3], colors, style, suffix)
            elif session['is_primary'] and aux_channels and not phase_channels and not generic_channels:
                # Simulation datasets (e.g. p_mech-only) have channels that land
                # exclusively in aux_channels.  Plot them in plot_wave too so the
                # primary waveform view is never blank when data is present.
                self._plot_channel_group(self.plot_wave, frames, ts, aux_channels[:3], colors, style, suffix)

            if line_channels:
                self._plot_channel_group(self.plot_line, frames, ts, line_channels, colors, style, suffix)

            if current_channels:
                self._plot_channel_group(self.plot_current, frames, ts, current_channels, colors, style, suffix)

            if aux_channels:
                self._plot_channel_group(self.plot_aux, frames, ts, aux_channels, colors, style, suffix)
            elif generic_channels and session['is_primary']:
                self._plot_channel_group(self.plot_aux, frames, ts, generic_channels[:2], colors, style, suffix)

            if session['is_primary']:
                spectrum_channel = (
                    'v_an'
                    if 'v_an' in numeric_channels
                    else (phase_channels[0] if phase_channels else (generic_channels[0] if generic_channels else None))
                )
                self._ts_arr = ts
                self._load_tags(session)
                if spectrum_channel is not None:
                    primary_arr = np.array([f.get(spectrum_channel, np.nan) for f in frames], dtype=float)
                    primary_arr_clean = np.where(np.isnan(primary_arr), 0.0, primary_arr)
                    self.plot_spectrum.setTitle(f"Spectrum  ·  {spectrum_channel}")
                    self._render_spectrum(ts, primary_arr_clean)
                    self._render_primary_markers(session, ts, primary_arr)

        if primary_phase_channels:
            self.plot_wave.setTitle("Phase-to-Neutral Voltages")
        elif primary_generic_channels:
            self.plot_wave.setTitle("Generic Numeric Signals")
        elif primary_aux_channels:
            self.plot_wave.setTitle("Auxiliary Signals")
        else:
            self._set_empty_plot_state(
                self.plot_wave,
                "Waveform View",
                "No numeric channels are available for waveform plotting.",
                y_label="Value",
            )

        if not primary_line_channels:
            self._set_empty_plot_state(
                self.plot_line,
                "Line-to-Line Voltage Overlay",
                "V_ab, V_bc, and V_ca require mapped phase voltages.",
                y_label="Voltage",
                units="V",
            )
        if not primary_current_channels:
            self._set_empty_plot_state(
                self.plot_current,
                "Phase Currents",
                "No current data available; current-based checks remain N/A for this dataset.",
                y_label="Current",
                units="A",
            )
        if not primary_aux_channels:
            self._set_empty_plot_state(
                self.plot_aux,
                "Frequency / Auxiliary Channels",
                "No frequency or auxiliary data available; frequency checks remain N/A unless a freq channel or phase voltage is present.",
                y_label="Value",
            )

        if primary_session:
            # Lightweight UI updates first (channel bar, basic markers)
            sample = primary_session['frames'][0] if primary_session['frames'] else {}
            ch_names = [
                key for key in sample
                if key not in {'ts', 'display_time_s'} and isinstance(sample.get(key), (int, float))
            ]
            self._update_channel_bar(ch_names)

            # Defer heavy analysis (metrics, THD, FFT) and event detection to
            # background threads so the Qt main thread remains responsive.
            try:
                self._start_background_analysis(primary_session)
            except Exception:
                logger.exception("Failed to start async analysis worker")
            try:
                self._start_background_event_detection(primary_session)
            except Exception:
                logger.exception("Failed to start async event detection worker")

        self.play_idx = 0
        self.scrubber.setValue(0.0)
        self.lbl_time.setText("0.00s")
        self.tabs.setCurrentIndex(0)
        self._update_ui(0)
        self._apply_session_view_range()
        for plot in (self.plot_wave, self.plot_line, self.plot_current, self.plot_aux, self.plot_metrics, self.plot_spectrum):
            plot.autoRange()
        self._apply_session_view_range()

    def _plot_channel_group(self, plot, frames, ts, channels, colors, style, suffix):
        pen_colors = [colors[i % len(colors)] for i in range(len(channels))]
        for idx, channel in enumerate(channels):
            arr = np.array([f.get(channel, np.nan) for f in frames], dtype=float)
            pen = pg.mkPen(pen_colors[idx], width=1.4, style=style)
            curve = plot.plot(ts, arr, pen=pen, name=f"{channel}{suffix}")
            self._wave_curves.append(curve)

    def _frame_time(self, frame: dict, fallback: float = 0.0) -> float:
        """Read the replay display timestamp for one frame.

        Prefer explicit display_time_s if present, then fall back to ts.
        """
        display_time = frame.get('display_time_s')
        if display_time is not None:
            try:
                return float(display_time)
            except (TypeError, ValueError):
                pass
        ts = frame.get('ts')
        if ts is not None:
            try:
                return float(ts)
            except (TypeError, ValueError):
                pass
        try:
            return float(fallback)
        except (TypeError, ValueError):
            return 0.0

    def _build_display_time(self, frames: list[dict]) -> np.ndarray:
        if not frames:
            return np.array([], dtype=float)
        raw = np.array([self._frame_time(f, float(i)) for i, f in enumerate(frames)], dtype=float)
        if raw.size == 0:
            return np.array([], dtype=float)
        raw = raw - float(raw[0])
        # Guarantee monotonic non-decreasing display time to keep searchsorted stable.
        return np.maximum.accumulate(raw)

    def _apply_session_view_range(self) -> None:
        start_s, end_s = self._session_time_range
        if end_s <= start_s:
            end_s = start_s + 1.0
        for plot in (self.plot_wave, self.plot_line, self.plot_current, self.plot_aux):
            plot.setXRange(start_s, end_s, padding=0.02)
        self.plot_metrics.setXRange(start_s, end_s, padding=0.02)

    def _render_primary_markers(self, session, ts, primary_arr):
        frames = session['frames']
        if not frames:
            return

        # Safe y-anchor for labels: use nanmax, but fall back to 0 if all-NaN.
        valid_vals = primary_arr[~np.isnan(primary_arr)] if len(primary_arr) else np.array([])
        y_anchor = float(valid_vals.max()) if len(valid_vals) > 0 else 0.0

        t0 = self._frame_time(frames[0], 0.0)
        events = session['data'].get('events', [])
        for evt in events:
            t_evt = float(evt.get('ts', t0)) - t0
            evt_label = evt.get('type', 'Event')
            color = 'r' if 'fault' in evt_label.lower() else 'b'
            line = pg.InfiniteLine(pos=t_evt, angle=90, pen=pg.mkPen(color, style=Qt.PenStyle.DashLine))
            txt = pg.TextItem(evt_label, color=color, anchor=(0, 1))
            txt.setPos(t_evt, y_anchor)
            self.plot_wave.addItem(line)
            self.plot_wave.addItem(txt)
            self.markers.append(line)
            self.markers.append(txt)

        import_meta = session['data'].get('import_meta', {})
        if import_meta:
            src = import_meta.get('source_type', '')
            unmapped = [
                key for key, value in import_meta.get('applied_mapping', {}).items()
                if value in (None, '__unmapped__', '')
            ]
            if unmapped:
                notice_text = (
                    f"Source: {src}  ·  Unmapped channels: {', '.join(unmapped[:4])}"
                    + (" …" if len(unmapped) > 4 else "")
                )
                notice = pg.TextItem(notice_text, color='#f59e0b', anchor=(0, 0))
                notice.setPos(0, y_anchor)
                self.plot_wave.addItem(notice)
                self.markers.append(notice)

    def _set_optional_plot_visibility(self, plot, visible: bool) -> None:
        plot.setVisible(True)

    def _set_metric_cards_from_summary(self, summary: dict) -> None:
        """Populate high-level metric cards for demo-friendly readability."""
        session_info = summary.get("session", {})
        phase = summary.get("phase_voltage", {})
        line = summary.get("line_voltage", {})
        freq = summary.get("frequency", {})

        phase_labels = {"v_an": "AN", "v_bn": "BN", "v_cn": "CN"}
        line_labels = {"v_ab": "AB", "v_bc": "BC", "v_ca": "CA"}

        phase_values = [
            f"{phase_labels[ch]}  {phase.get(ch, {}).get('rms', 0.0):.2f} V"
            for ch in ("v_an", "v_bn", "v_cn")
            if phase.get(ch, {}).get("available") and phase.get(ch, {}).get("rms") is not None
        ]
        line_values = [
            f"{line_labels[ch]}  {line.get(ch, {}).get('rms', 0.0):.2f} V"
            for ch in ("v_ab", "v_bc", "v_ca")
            if line.get(ch, {}).get("available") and line.get(ch, {}).get("rms") is not None
        ]
        thd_values = [
            f"{phase_labels[ch]}  {phase.get(ch, {}).get('thd_pct', 0.0):.2f}%"
            for ch in ("v_an", "v_bn", "v_cn")
            if phase.get(ch, {}).get("available") and phase.get(ch, {}).get("thd_pct") is not None
        ]
        if freq.get("available"):
            freq_text = (
                f"mean  {freq.get('mean_hz', 0.0):.3f} Hz\n"
                f"max dev  {freq.get('max_deviation_hz', 0.0):.3f} Hz"
            )
        else:
            freq_text = "N/A"

        self._metric_cards["phase_rms"].setText("\n".join(phase_values) if phase_values else "N/A")
        self._metric_cards["line_rms"].setText("\n".join(line_values) if line_values else "N/A")
        self._metric_cards["thd"].setText("\n".join(thd_values) if thd_values else "N/A")
        self._metric_cards["freq"].setText(freq_text)
        self._metric_cards["window"].setText(
            f"{session_info.get('sample_count', 0):,} samples\n"
            f"{session_info.get('sample_rate_hz', 0.0):.2f} Hz\n"
            f"{session_info.get('time_window_s', 0.0):.4f} s"
        )
        derived = session_info.get("derived_channels", [])
        self._metric_cards["derived"].setText(
            "\n".join(derived[:4]) + ("\n…" if len(derived) > 4 else "") if derived else "none"
        )

    def _build_metrics_status_lines(self, summary: dict) -> list[str]:
        event_counts = summary.get("events", {}).get("counts", {})
        current_info = summary.get("current_thresholds", {})
        freq_info = summary.get("frequency", {})
        session_info = summary.get("session", {})

        lines = [
            f"Voltage sag events: {event_counts.get('voltage_sag', 0)}",
            f"Frequency excursions: {event_counts.get('frequency_excursion', 0)}",
        ]
        if current_info.get("available"):
            lines.append(f"Overcurrent events: {event_counts.get('overcurrent', 0)}")
        else:
            lines.append(
                "No current data available; current-based checks N/A "
                f"({current_info.get('reason', 'missing current')})"
            )

        if freq_info.get("available"):
            source = (
                "estimated from V_an"
                if freq_info.get("source") == "estimated_from_v_an"
                else "from dataset"
            )
            lines.append(
                f"Frequency available {source}: mean {freq_info.get('mean_hz', 0.0):.3f} Hz"
            )
        else:
            lines.append(
                "No frequency data available; frequency checks N/A "
                f"({freq_info.get('reason', 'missing frequency')})"
            )

        generic_channels = session_info.get("generic_numeric_channels", [])
        if generic_channels:
            lines.append(f"Generic channels: {', '.join(generic_channels[:3])}")
        else:
            lines.append("Generic channels: none")
        return lines

    def _set_axes_linked(self, linked: bool) -> None:
        target = self.plot_wave.getViewBox() if linked else None
        for plot in getattr(self, "_linked_plots", ()):
            plot.getViewBox().setXLink(target)

    def _set_empty_plot_state(self, plot, title: str, message: str, y_label: str, units=None) -> None:
        plot.clear()
        plot.setTitle(title)
        plot.setLabel('left', y_label, units=units)
        plot.setLabel('bottom', 'Time', units='s')
        plot.showGrid(x=True, y=True, alpha=0.3)
        plot.setYRange(0.0, 1.0, padding=0.0)
        start_s, end_s = self._session_time_range
        x_mid = start_s + ((end_s - start_s) / 2.0) if end_s > start_s else 0.5
        note = pg.TextItem(message, color='#94a3b8', anchor=(0.5, 0.5))
        note.setPos(x_mid, 0.5)
        plot.addItem(note)

    def _update_analysis_view(self, session) -> None:
        summary = compute_session_metrics(session['data'])
        rows = build_metric_rows(summary)
        self._populate_metrics_table(rows)
        self._set_metric_cards_from_summary(summary)

        session_info = summary["session"]
        derived = ", ".join(session_info["derived_channels"]) or "none"
        self._wave_summary.setText(
            f"{session_info['analysis_mode_label']}  ·  {session_info['source_name']}  ·  "
            f"{session_info['sample_count']:,} samples  ·  "
            f"{session_info['sample_rate_hz']:.2f} Hz  ·  "
            f"{session_info['time_window_s']:.4f} s  ·  "
            f"Canonical: {', '.join(session_info['available_canonical_channels']) or 'none'}  ·  "
            f"Derived: {derived}"
        )

        self._metrics_summary.setText("\n".join(self._build_metrics_status_lines(summary)))

        self.plot_metrics.clear()
        dataset = session.get('_dataset')
        if dataset is None:
            try:
                dataset = dataset_from_capsule(session.get('data', {}))
            except Exception:
                dataset = None
        if dataset is None or dataset.time.size < 4:
            return

        t_rel = np.asarray(dataset.time - dataset.time[0], dtype=float)
        phase_colors = {'v_an': '#f97316', 'v_bn': '#3b82f6', 'v_cn': '#22c55e'}
        window_n = max(8, min(int(max(dataset.sample_rate, 120.0) / 30.0), max(8, dataset.time.size // 24)))
        kernel = np.ones(window_n) / window_n
        for channel in ('v_an', 'v_bn', 'v_cn'):
            if channel not in dataset.channels:
                continue
            arr = np.asarray(dataset.channels[channel], dtype=float)
            rolling = np.sqrt(np.maximum(np.convolve(arr * arr, kernel, mode='same'), 0.0))
            self._metric_curves.append(
                self.plot_metrics.plot(
                    t_rel,
                    rolling,
                    pen=pg.mkPen(phase_colors[channel], width=1.5),
                    name=f"{channel} RMS",
                )
            )

        if 'freq' in dataset.channels:
            self._metric_curves.append(
                self.plot_metrics.plot(
                    t_rel,
                    np.asarray(dataset.channels['freq'], dtype=float),
                    pen=pg.mkPen('#a78bfa', width=1.3),
                    name="Frequency",
                )
            )

        # For simulation / generic datasets with no phase voltage channels,
        # plot available generic/aux channels (p_mech, v_dc, etc.) in the metrics view.
        _ALREADY_PLOTTED = frozenset({'v_an', 'v_bn', 'v_cn', 'freq'})
        generic_colors = ['#38bdf8', '#fbbf24', '#34d399', '#a78bfa', '#f97316']
        generic_idx = 0
        for ch in sorted(dataset.channels.keys()):
            if ch in _ALREADY_PLOTTED:
                continue
            arr = np.asarray(dataset.channels[ch], dtype=float)
            if not np.any(np.isfinite(arr)):
                continue
            color = generic_colors[generic_idx % len(generic_colors)]
            self._metric_curves.append(
                self.plot_metrics.plot(
                    t_rel,
                    arr,
                    pen=pg.mkPen(color, width=1.3),
                    name=ch,
                )
            )
            generic_idx += 1
            if generic_idx >= 5:
                break

    def _populate_metrics_table(self, rows: list[dict]) -> None:
        self._metrics_table.setRowCount(0)
        for row_data in rows:
            row = self._metrics_table.rowCount()
            self._metrics_table.insertRow(row)
            for col_idx, key in enumerate(("section", "metric", "value", "unit", "note")):
                item = QTableWidgetItem(str(row_data.get(key, "")))
                if key == "value" and str(row_data.get(key, "")).upper() == "N/A":
                    item.setForeground(Qt.GlobalColor.darkYellow)
                self._metrics_table.setItem(row, col_idx, item)

    def _clear_all(self):
        self.sessions = []
        self.active_session = None
        self.is_playing = False
        self.timer.stop()
        self.btn_play.setText("Play")
        self.play_idx = 0
        self._session_time_range = (0.0, 1.0)
        self.plot_wave.clear()
        self.plot_wave.addItem(self.scrubber)
        self.plot_wave.addItem(self._crosshair_v, ignoreBounds=True)
        self.plot_wave.addItem(self._crosshair_h, ignoreBounds=True)
        self.plot_line.clear()
        self.plot_current.clear()
        self.plot_aux.clear()
        self.plot_metrics.clear()
        self._metrics_summary.setText("")
        self._metrics_table.setRowCount(0)
        for lbl in self._metric_cards.values():
            lbl.setText("—")
        self._wave_summary.setText("")
        self._clear_markers()
        self._wave_curves = []
        self._metric_curves = []
        self._ts_arr = np.array([])
        self.lbl_time.setText("0.00s")
        self.scrubber.setValue(0.0)
        self.tabs.setCurrentIndex(0)
        self._comparison_tab.clear()
        self._event_lane.clear()
        self._sync_button_state()

    def _sync_button_state(self) -> None:
        """Enable / disable toolbar buttons based on whether sessions are loaded."""
        has = len(self.sessions) > 0
        self.btn_overlay.setEnabled(has)
        self.btn_overlay.setToolTip(
            "Load a second session to overlay for comparison" if has
            else "Load a primary session first"
        )
        self.btn_clear.setEnabled(has)
        self.btn_play.setEnabled(has)
        self.btn_export.setEnabled(has)
        self.btn_export.setToolTip("" if has else "Load a session first")
        self.btn_quick_export.setEnabled(has)
        self.btn_reset_zoom.setEnabled(has)

    def _update_comparison_tab(self) -> None:
        """Auto-populate the Compare tab when two sessions are available."""
        if len(self.sessions) >= 2:
            self._comparison_tab.set_sessions(self.sessions[0], self.sessions[1])
        else:
            self._comparison_tab.clear()

    def _update_event_lane(self) -> None:
        """Detect events in the primary session and populate the Events tab."""
        primary = next((s for s in self.sessions if s.get('is_primary')), None)
        if primary is None:
            return

        dataset = primary.get('_dataset')
        if dataset is None:
            try:
                dataset = dataset_from_capsule(primary.get('data', {}))
            except Exception as exc:
                logger.debug("Event lane: cannot reconstruct dataset: %s", exc)
                return

        try:
            events = detect_events(dataset)
            self._event_lane.load_events(events)
            self.events_detected.emit(len(events))
            self.events_ready.emit(events)
            logger.info("Event detection: %d events found in '%s'",
                        len(events), primary.get('label', '?'))
        except Exception as exc:
            logger.warning("Event detection failed: %s", exc)

    # ── Background workers ─────────────────────────────────────────────────

    def _start_background_analysis(self, session: dict) -> None:
        """Run metrics computation in a daemon thread; deliver result via Qt signal."""
        label = session.get('label', '')
        data = session.get('data', {})

        def _worker():
            try:
                t0 = time.perf_counter()
                logger.info("metrics.compute.start: %s", label)
                # Pass events=[] to skip redundant detect_events inside metrics.
                summary = compute_session_metrics(data, events=[])
                rows = build_metric_rows(summary)
                logger.info("metrics.compute.end: %s (%.3fs)", label, time.perf_counter() - t0)
                try:
                    self._bg_analysis_ready.emit({'summary': summary, 'rows': rows}, label)
                except RuntimeError:
                    pass  # Studio was GC'd before worker finished (e.g. test teardown).
            except Exception:
                logger.exception("Background analysis failed for '%s'", label)

        threading.Thread(target=_worker, daemon=True, name=f"analysis-{label[:20]}").start()

    def _start_background_event_detection(self, session: dict) -> None:
        """Run event detection in a daemon thread; deliver result via Qt signal."""
        label = session.get('label', '')
        dataset = session.get('_dataset')

        def _worker():
            try:
                t0 = time.perf_counter()
                logger.info("event_detection.start: %s", label)
                ds = dataset
                if ds is None:
                    try:
                        ds = dataset_from_capsule(session.get('data', {}))
                    except Exception:
                        logger.warning(
                            "Cannot reconstruct dataset for event detection: '%s'", label
                        )
                        try:
                            self._bg_events_ready.emit([], label)
                        except RuntimeError:
                            pass
                        return
                # Cap to avoid multi-second FFT / corrcoef on full-resolution arrays.
                ds = _cap_dataset_for_events(ds, max_samples=50_000)
                events = detect_events(ds)
                logger.info(
                    "event_detection.end: %s (%.3fs) \u2014 %d events",
                    label, time.perf_counter() - t0, len(events),
                )
                try:
                    self._bg_events_ready.emit(events, label)
                except RuntimeError:
                    pass  # Studio was GC'd before worker finished.
            except Exception:
                logger.exception("Background event detection failed for '%s'", label)
                try:
                    self._bg_events_ready.emit([], label)
                except RuntimeError:
                    pass

        threading.Thread(target=_worker, daemon=True, name=f"events-{label[:20]}").start()

    def _on_bg_analysis_ready(self, result: dict, label: str) -> None:
        """Update metrics UI on the Qt main thread when analysis finishes."""
        primary = next((s for s in self.sessions if s.get('is_primary')), None)
        if primary is None or primary.get('label') != label:
            return  # Stale — session was replaced before the worker finished.
        rows = result.get('rows', [])
        self._populate_metrics_table(rows)
        summary = result.get('summary', {})
        if not summary:
            return
        session_info = summary.get('session', {})
        derived = ', '.join(session_info.get('derived_channels', [])) or 'none'
        self._wave_summary.setText(
            f"{session_info.get('analysis_mode_label', '')}  ·  "
            f"{session_info.get('source_name', '')}  ·  "
            f"{session_info.get('sample_count', 0):,} samples  ·  "
            f"{session_info.get('sample_rate_hz', 0):.2f} Hz  ·  "
            f"{session_info.get('time_window_s', 0):.4f} s  ·  "
            f"Canonical: {', '.join(session_info.get('available_canonical_channels', [])) or 'none'}  ·  "
            f"Derived: {derived}"
        )
        self._metrics_summary.setText("\n".join(self._build_metrics_status_lines(summary)))
        self._set_metric_cards_from_summary(summary)
        # Rebuild rolling-RMS plot using the decimated frame data (fast; avoids
        # the expensive np.convolve on 1 M-row full-resolution arrays).
        self.plot_metrics.clear()
        self._metric_curves = []
        frames = primary.get('frames', [])
        if not frames:
            return
        t_rel = self._build_display_time(frames)
        phase_colors = {'v_an': '#f97316', 'v_bn': '#3b82f6', 'v_cn': '#22c55e'}
        window_n = max(8, min(len(frames) // 20, 200))
        kernel = np.ones(window_n) / window_n
        for ch in ('v_an', 'v_bn', 'v_cn'):
            vals = [f.get(ch) for f in frames]
            if not any(v is not None for v in vals):
                continue
            arr = np.array([v if v is not None else np.nan for v in vals], dtype=float)
            rolling = np.sqrt(np.maximum(np.convolve(arr * arr, kernel, mode='same'), 0.0))
            self._metric_curves.append(
                self.plot_metrics.plot(
                    t_rel, rolling,
                    pen=pg.mkPen(phase_colors[ch], width=1.5),
                    name=f"{ch} RMS",
                )
            )

    def _on_bg_events_ready(self, events: list, label: str) -> None:
        """Populate the Events tab on the Qt main thread when detection finishes."""
        primary = next((s for s in self.sessions if s.get('is_primary')), None)
        if primary is None or primary.get('label') != label:
            return  # Stale result.
        # Cache events on the session dict so quick_export can access them.
        primary['_events'] = events
        self._event_lane.load_events(events)
        self.events_detected.emit(len(events))
        self.events_ready.emit(events)
        logger.info("Event lane updated: %d events for '%s'", len(events), label)

    def _seek_to_time(self, ts: float) -> None:
        """Seek the waveform scrubber to *ts* seconds and switch to Waveforms tab."""
        self.scrubber.setValue(ts)
        self.tabs.setCurrentIndex(0)  # Switch to Waveforms
        # Trigger the scrubber drag handler to update the UI
        self._on_scrubber_dragged()

    def _clear_markers(self):
        for m in self.markers:
            self.plot_wave.removeItem(m)
        self.markers = []

        for tag in self._tags:
            self.plot_wave.removeItem(tag)
        self._tags = []

    def _toggle_play(self):
        if not self.sessions or self.active_session is None:
            return
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.btn_play.setText("Pause")
            self.timer.start(40)
        else:
            self.btn_play.setText("Play")
            self.timer.stop()

    def _tick(self):
        if not self.sessions or self._is_scrubbing or self.active_session is None:
            return
        frames = self.sessions[self.active_session]['frames']
        if self.play_idx < len(frames) - 1:
            self.play_idx += 1
            self._update_ui(self.play_idx)
            self.serial_mgr.frame_received.emit(frames[self.play_idx])
        else:
            self._toggle_play()

    def _on_scrubber_dragged(self):
        self._is_scrubbing = True
        if self.is_playing:
            self._toggle_play()

        t = self.scrubber.value()
        if self._ts_arr.size == 0 or self.active_session is None:
            return

        idx = int(np.searchsorted(self._ts_arr, t))
        idx = min(idx, len(self._ts_arr) - 1)

        self.play_idx = idx
        self._update_ui(idx, update_scrubber=False)
        self.serial_mgr.frame_received.emit(self.sessions[self.active_session]['frames'][idx])

    def _on_scrubber_release(self):
        self._is_scrubbing = False

    def _update_ui(self, idx, update_scrubber=True):
        if not self.sessions or self.active_session is None:
            return
        frames = self.sessions[self.active_session]['frames']
        if idx >= len(frames):
            return
        if self._ts_arr.size and idx < len(self._ts_arr):
            rel_t = float(self._ts_arr[idx])
        else:
            frame = frames[idx]
            rel_t = self._frame_time(frame, 0.0) - self._frame_time(frames[0], 0.0)

        self.lbl_time.setText(f"{rel_t:.2f}s")
        if update_scrubber:
            self.scrubber.setValue(rel_t)

    def _on_wave_click(self, event):
        if not self.sessions or self.active_session is None:
            return
        if not event.double():
            return  # Require double-click to add a tag (avoids accidental dialogs)
        mouse_point = self.plot_wave.plotItem.vb.mapSceneToView(event.scenePos())
        t = mouse_point.x()
        tag, ok = QInputDialog.getText(self, "Add Tag", "Tag label:")
        if not ok or not tag:
            return

        line = pg.InfiniteLine(pos=t, angle=90, pen=pg.mkPen('#facc15', style=Qt.PenStyle.DashLine))
        txt = pg.TextItem(tag, color='#facc15', anchor=(0, 1))
        txt.setPos(t, 0)
        self.plot_wave.addItem(line)
        self.plot_wave.addItem(txt)
        self._tags.extend([line, txt])

        self._tag_data.append({"time": float(t), "label": tag})
        self._persist_tags()

    def _load_tags(self, session):
        self._tag_data = session.get('data', {}).get('tags', [])
        for tag in self._tag_data:
            t = tag.get('time', 0)
            label = tag.get('label', '')
            line = pg.InfiniteLine(pos=t, angle=90, pen=pg.mkPen('#facc15', style=Qt.PenStyle.DashLine))
            txt = pg.TextItem(label, color='#facc15', anchor=(0, 1))
            txt.setPos(t, 0)
            self.plot_wave.addItem(line)
            self.plot_wave.addItem(txt)
            self._tags.extend([line, txt])

    def _persist_tags(self):
        if self.active_session is None:
            return
        session = self.sessions[self.active_session]
        path = session.get('path')
        if not path:
            return
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            data['tags'] = self._tag_data
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _on_quick_export(self):
        """Export evidence package without a file dialog."""
        if not self.sessions:
            return
        primary = next((s for s in self.sessions if s.get('is_primary')), None)
        if not primary:
            return
        capsule = primary.get('data', {})
        events = primary.get('_events', [])
        try:
            from src.session_exporter import quick_export
            result = quick_export(
                capsule,
                events=events,
                compliance_results=None,
                base_dir="artifacts/evidence_exports",
            )
            export_dir = result["export_dir"]
            artifact_lines = "\n".join(
                f"  {a['name']}: {a['size_bytes']:,} bytes"
                for a in result["artifacts"]
            )
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle("Quick Export Complete")
            msg.setText(
                f"Evidence package exported to:\n{export_dir}\n\n"
                f"Artifacts ({len(result['artifacts'])}):\n{artifact_lines}\n\n"
                f"Total: {result['total_bytes']:,} bytes"
            )
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        except Exception as exc:
            logger.error(f"Quick export failed: {exc}")

    def _export_plot(self):
        if not self.sessions:
            return
        try:
            current_tab = self.tabs.currentWidget()
            fname, _ = QFileDialog.getSaveFileName(
                self, "Export Plot", os.getcwd(), "PNG Image (*.png)"
            )
            if not fname:
                return
            if hasattr(current_tab, 'plotItem'):
                exporter = pyqtgraph.exporters.ImageExporter(current_tab.plotItem)
                exporter.parameters()['width'] = 1920
                exporter.export(fname)
            else:
                current_tab.grab().save(fname)
            logger.info(f"Exported plot: {fname}")
        except Exception as e:
            logger.error(f"Export failed: {e}")

    def _render_spectrum(self, ts, v_a):
        now = time.time()
        if now - self._last_spectrum_ts < 0.2:
            return
        self._last_spectrum_ts = now
        if len(ts) < 4:
            return
        freqs, mags = compute_fft(ts, v_a)
        self._spectrum_curve.setData(freqs, mags)

        # Find top harmonic peaks (skip DC)
        peaks = []
        max_idx = min(len(freqs) - 1, 200)
        for idx in range(1, max_idx):
            if idx + 1 >= len(mags):
                break
            if mags[idx] > mags[idx - 1] and mags[idx] > mags[idx + 1]:
                peaks.append((freqs[idx], mags[idx]))

        peaks = sorted(peaks, key=lambda x: x[1], reverse=True)[:5]
        spots = []
        for f, m in peaks:
            spots.append({"pos": (f, m), "data": (f, m)})
        self._spectrum_peaks.setData(spots)

    def _on_spectrum_click(self, plot, points):
        if not points:
            return
        f, m = points[0].data()
        self._spectrum_label.setText(f"Peak: {f:.1f} Hz — {m:.2f}")
        self._spectrum_label.setPos(f, m)

    # ── Interactive analysis tools ─────────────────────────────────────────

    def _on_mouse_moved(self, evt):
        """Track crosshair and readout on the Waveforms plot."""
        pos = evt[0]
        if not self.sessions or not self.plot_wave.sceneBoundingRect().contains(pos):
            self._crosshair_v.setVisible(False)
            self._crosshair_h.setVisible(False)
            self._readout.setText("")
            return

        mouse_pt = self.plot_wave.plotItem.vb.mapSceneToView(pos)
        t_val = mouse_pt.x()
        y_val = mouse_pt.y()

        self._crosshair_v.setPos(t_val)
        self._crosshair_h.setPos(y_val)
        self._crosshair_v.setVisible(True)
        self._crosshair_h.setVisible(True)

        self._readout.setText(f"t = {t_val:.4f}s   y = {y_val:.3f}")

    def _reset_zoom(self):
        """Restore plot ranges to the active session's display time window."""
        self.plot_wave.autoRange()
        self.plot_line.autoRange()
        self.plot_current.autoRange()
        self.plot_aux.autoRange()
        self.plot_metrics.autoRange()
        self.plot_spectrum.autoRange()
        self._apply_session_view_range()

    def _update_channel_bar(self, channels: list[str]) -> None:
        """Build or rebuild the channel toggle checkboxes."""
        # Clear old checkboxes
        layout = self._channel_bar.layout()
        for cb in list(self._channel_checks.values()):
            layout.removeWidget(cb)
            cb.deleteLater()
        self._channel_checks.clear()

        for ch in channels:
            cb = QCheckBox(ch)
            cb.setChecked(True)
            cb.setStyleSheet("color: #cbd5e1; font-size: 10px;")
            cb.toggled.connect(self._on_channel_toggled)
            # Insert before the stretch
            layout.insertWidget(layout.count() - 1, cb)
            self._channel_checks[ch] = cb

        self._channel_bar.setVisible(bool(channels))

    def _on_channel_toggled(self):
        """Show/hide waveform curves based on channel checkboxes."""
        if not self.sessions:
            return
        visible_channels = {
            ch for ch, cb in self._channel_checks.items() if cb.isChecked()
        }
        for curve in self._wave_curves:
            name = curve.name() or ""
            # Strip suffix like " (label)" to get raw channel name
            raw = name.split(" (")[0] if " (" in name else name
            curve.setVisible(raw in visible_channels)
