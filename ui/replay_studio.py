from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
                             QLabel, QFileDialog, QComboBox, QTabWidget, QInputDialog,
                             QCheckBox, QFrame, QGridLayout)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg
import pyqtgraph.exporters
import json
import time
import os
import logging
import numpy as np
from src.signal_processing import compute_rms, compute_thd, compute_fft
from src.event_detector import detect_events
from src.comparison import dataset_from_capsule
from ui.comparison_panel import ComparisonPanel
from ui.event_lane import EventLane

logger = logging.getLogger(__name__)


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

        self.btn_reset_zoom = QPushButton("Reset Zoom")
        self.btn_reset_zoom.setToolTip("Reset all plots to auto-range")
        self.btn_reset_zoom.clicked.connect(self._reset_zoom)
        self.btn_reset_zoom.setEnabled(False)

        self.lbl_time = QLabel("0.00s")

        ctrl.addWidget(self.btn_load)
        ctrl.addWidget(self.btn_overlay)
        ctrl.addWidget(self.btn_clear)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_reset_zoom)
        ctrl.addWidget(self.btn_export)
        ctrl.addWidget(self.lbl_time)
        ctrl.addStretch()

        # Crosshair readout label
        self._readout = QLabel("")
        self._readout.setStyleSheet(
            "color: #94a3b8; font-family: monospace; font-size: 10px; padding: 0 8px;"
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
        ch_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        ch_bar_layout.addWidget(ch_lbl)
        self._channel_checks: dict[str, QCheckBox] = {}
        ch_bar_layout.addStretch()
        self.layout.addWidget(self._channel_bar)

        # --- Tab Widget for waveform vs metrics ---
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Tab 1: Waveform Timeline (title updated dynamically on load)
        self.plot_wave = pg.PlotWidget(title="Waveforms")
        self.plot_wave.setBackground('#0b0f14')
        self.plot_wave.showGrid(x=True, y=True, alpha=0.3)
        self.plot_wave.setLabel('left', 'Voltage', units='V')
        self.plot_wave.setLabel('bottom', 'Time', units='s')
        self.plot_wave.addLegend()
        self.tabs.addTab(self.plot_wave, "Waveforms")

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
        self._metrics_summary = QLabel("")
        self._metrics_summary.setStyleSheet(
            "color: #64748b; font-family: monospace; font-size: 10px; "
            "padding: 4px 8px; background: transparent;"
        )
        self._metrics_summary.setWordWrap(False)
        metrics_layout.addWidget(self._metrics_summary)
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

        # Interactive Scrubber
        self.scrubber = pg.InfiniteLine(pos=0, angle=90, movable=True, pen=pg.mkPen('w', width=2))
        self.scrubber.sigDragged.connect(self._on_scrubber_dragged)
        self.scrubber.sigPositionChangeFinished.connect(self._on_scrubber_release)
        self.plot_wave.addItem(self.scrubber)
        self.plot_wave.scene().sigMouseClicked.connect(self._on_wave_click)
        self._event_lane.event_selected.connect(self._seek_to_time)

        self.markers = []
        self._ts_arr = np.array([])
        self._wave_curves = []
        self._metric_curves = []
        self._tags = []
        self._tag_data = []
        self._last_spectrum_ts = 0.0

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

        self._render_all_sessions()
        self._update_comparison_tab()
        # Defer event detection so the waveform plots appear immediately.
        QTimer.singleShot(0, self._update_event_lane)
        self._sync_button_state()
        logger.info("Loaded session '%s' with %d frames (overlay=%s)", label, len(frames), not is_primary)

    def _render_all_sessions(self):
        """Re-render all loaded sessions on both plots."""
        # Clear existing curves
        self.plot_wave.clear()
        self.plot_wave.addItem(self.scrubber)
        self._clear_markers()
        self.plot_metrics.clear()
        self._wave_curves = []
        self._metric_curves = []

        for idx, session in enumerate(self.sessions):
            frames = session['frames']
            colors = session['colors']
            label = session['label']

            if not frames:
                continue

            t0 = frames[0]['ts']
            ts = np.array([f['ts'] - t0 for f in frames])

            suffix = f" ({label})" if len(self.sessions) > 1 else ""
            style = Qt.PenStyle.SolidLine if session['is_primary'] else Qt.PenStyle.DashLine

            # ── Detect plottable waveform channels ───────────────────────────
            # Prefer canonical 3-phase voltage names, then DC bus, then current;
            # fall back to any numeric channel present (up to 6 channels).
            # Boolean/flag channels (only 0/1 values) are excluded from all paths.
            sample_frame = frames[0]
            canonical_v = [
                k for k in ('v_an', 'v_bn', 'v_cn', 'v_dc') if k in sample_frame
            ]
            canonical_i = [
                k for k in ('i_a', 'i_b', 'i_c') if k in sample_frame
            ]

            def _is_boolean_channel(key: str) -> bool:
                """Return True when the channel only contains 0/1 values (flag column)."""
                vals = {f.get(key) for f in frames[:40]
                        if isinstance(f.get(key), (int, float))}
                return bool(vals) and vals.issubset({0, 1, 0.0, 1.0})

            non_ts_keys = [
                k for k in sample_frame
                if k != 'ts' and isinstance(sample_frame[k], (int, float))
                and not _is_boolean_channel(k)
            ]

            if canonical_v:
                wave_channels = canonical_v
            elif canonical_i:
                wave_channels = canonical_i
            else:
                # Generic or simulation channels — use up to 6
                wave_channels = non_ts_keys[:6]

            if not wave_channels:
                continue

            # Update waveform tab title and Y-axis to reflect the primary channel type
            if session['is_primary']:
                if 'v_dc' in wave_channels and not any(k in wave_channels for k in ('v_an', 'v_bn', 'v_cn')):
                    self.plot_wave.setTitle("DC Bus Voltage")
                    self.plot_wave.setLabel('left', 'Voltage', units='V')
                elif canonical_v:
                    self.plot_wave.setTitle("Voltage Waveforms")
                    self.plot_wave.setLabel('left', 'Voltage', units='V')
                elif canonical_i:
                    self.plot_wave.setTitle("Current Waveforms")
                    self.plot_wave.setLabel('left', 'Current', units='A')
                else:
                    # Build title from the actual channel names loaded
                    ch_title = " · ".join(wave_channels[:4])
                    if len(wave_channels) > 4:
                        ch_title += f" (+{len(wave_channels)-4} more)"
                    self.plot_wave.setTitle(ch_title)
                    self.plot_wave.setLabel('left', 'Value')

            # ── Build arrays and plot waveforms ──────────────────────────────
            # Rotate through the session color tuple; wrap if more than 3 channels
            pen_colors = [colors[i % len(colors)] for i in range(len(wave_channels))]

            for ci, ch in enumerate(wave_channels):
                arr = np.array([f.get(ch, np.nan) for f in frames])
                pen = pg.mkPen(pen_colors[ci], width=1, style=style)
                curve = self.plot_wave.plot(ts, arr, pen=pen, name=f"{ch}{suffix}")
                self._wave_curves.append(curve)

            # ── Derived metrics ───────────────────────────────────────────────
            # Only compute RMS/THD/freq when a meaningful voltage channel is present
            primary_ch = wave_channels[0]
            primary_arr = np.array([f.get(primary_ch, np.nan) for f in frames])

            # Replace NaN with 0 only for metric windowing (not for raw plot)
            primary_arr_clean = np.where(np.isnan(primary_arr), 0.0, primary_arr)

            # Adaptive windowing: cap at 500 windows to avoid large FFT loops
            # on the main thread for big datasets.
            window = max(20, len(frames) // 500)
            n_windows = len(frames) // window
            if n_windows > 0:
                metric_ts = []
                rms_vals = []
                thd_vals = []
                freq_vals = []

                for w in range(n_windows):
                    start = w * window
                    end = start + window
                    chunk_v = primary_arr_clean[start:end]
                    chunk_ts = ts[start:end]

                    metric_ts.append(float(np.mean(chunk_ts)))
                    rms_vals.append(compute_rms(chunk_v))
                    thd_vals.append(compute_thd(chunk_v, time_data=chunk_ts))

                    # Use 'freq' field if available; otherwise mark 0
                    freq_slice = [
                        f.get('freq', None) for f in frames[start:end]
                    ]
                    valid_freqs = [x for x in freq_slice if x is not None]
                    freq_vals.append(float(np.mean(valid_freqs)) if valid_freqs else 0.0)

                metric_ts_arr = np.array(metric_ts)
                self._metric_curves.append(
                    self.plot_metrics.plot(
                        metric_ts_arr, rms_vals,
                        pen=pg.mkPen('y', width=2, style=style),
                        name=f"RMS({primary_ch}){suffix}",
                    )
                )
                if any(v > 0 for v in thd_vals):
                    self._metric_curves.append(
                        self.plot_metrics.plot(
                            metric_ts_arr, thd_vals,
                            pen=pg.mkPen('r', width=2, style=style),
                            name=f"THD(%){suffix}",
                        )
                    )
                if any(v > 0 for v in freq_vals):
                    self._metric_curves.append(
                        self.plot_metrics.plot(
                            metric_ts_arr, freq_vals,
                            pen=pg.mkPen('c', width=2, style=style),
                            name=f"Freq(Hz){suffix}",
                        )
                    )

            # ── Per-channel summary stats label (primary only) ────────────────
            if session['is_primary'] and wave_channels:
                lines = []
                for ch in wave_channels:
                    arr = np.array([f.get(ch, np.nan) for f in frames])
                    arr_c = np.where(np.isnan(arr), 0.0, arr)
                    rms = compute_rms(arr_c)
                    thd = compute_thd(arr_c, time_data=ts)
                    lines.append(f"{ch:<16s}  RMS={rms:>8.3f}  THD={thd:>5.1f}%")
                self._metrics_summary.setText("  |  ".join(lines))

            # ── Event markers (primary session only) ─────────────────────────
            if session['is_primary']:
                self._ts_arr = ts
                self.plot_spectrum.setTitle(f"Spectrum  ·  {primary_ch}")
                self._render_spectrum(ts, primary_arr_clean)
                self._load_tags(session)
                events = session['data'].get('events', [])
                for evt in events:
                    t_evt = evt['ts'] - t0
                    evt_label = evt.get('type', 'Event')
                    color = 'r' if 'fault' in evt_label.lower() else 'b'
                    line = pg.InfiniteLine(pos=t_evt, angle=90, pen=pg.mkPen(color, style=Qt.PenStyle.DashLine))
                    txt = pg.TextItem(evt_label, color=color, anchor=(0, 1))
                    txt.setPos(t_evt, float(np.nanmax(primary_arr)) if len(primary_arr) else 0)
                    self.plot_wave.addItem(line)
                    self.plot_wave.addItem(txt)
                    self.markers.append(line)
                    self.markers.append(txt)

                # ── Import-source notice ──────────────────────────────────────
                import_meta = session['data'].get('import_meta', {})
                if import_meta:
                    src = import_meta.get('source_type', '')
                    unmapped = [
                        k for k, v in import_meta.get('applied_mapping', {}).items()
                        if v in (None, '__unmapped__', '')
                    ]
                    if unmapped:
                        notice_text = (
                            f"Source: {src}  ·  "
                            f"Unmapped channels: {', '.join(unmapped[:4])}"
                            + (" …" if len(unmapped) > 4 else "")
                        )
                        notice = pg.TextItem(notice_text, color='#f59e0b', anchor=(0, 0))
                        notice.setPos(0, float(np.nanmax(primary_arr)) if len(primary_arr) else 0)
                        self.plot_wave.addItem(notice)
                        self.markers.append(notice)

        self.play_idx = 0
        self._update_ui(0)
        self.plot_wave.autoRange()
        self.plot_metrics.autoRange()
        self.plot_spectrum.autoRange()

        # Update channel toggle bar from primary session channels
        primary = next((s for s in self.sessions if s.get('is_primary')), None)
        if primary:
            sample = primary['frames'][0] if primary['frames'] else {}
            ch_names = [
                k for k in sample
                if k != 'ts' and isinstance(sample.get(k), (int, float))
            ]
            self._update_channel_bar(ch_names)

    def _clear_all(self):
        self.sessions = []
        self.active_session = None
        self.plot_wave.clear()
        self.plot_wave.addItem(self.scrubber)
        self.plot_metrics.clear()
        self._metrics_summary.setText("")
        self._clear_markers()
        self._wave_curves = []
        self._metric_curves = []
        self._ts_arr = np.array([])
        self.lbl_time.setText("0.00s")
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
        self.btn_reset_zoom.setEnabled(has)

    def _update_comparison_tab(self) -> None:
        """Auto-populate the Compare tab when two sessions are available."""
        if len(self.sessions) >= 2:
            self._comparison_tab.set_sessions(self.sessions[0], self.sessions[1])

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
        frame = frames[idx]
        t0 = frames[0]['ts']
        rel_t = frame['ts'] - t0

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

    def _export_plot(self):
        if not self.sessions:
            return
        try:
            current_tab = self.tabs.currentWidget()
            if hasattr(current_tab, 'plotItem'):
                exporter = pyqtgraph.exporters.ImageExporter(current_tab.plotItem)
                exporter.parameters()['width'] = 1920
                fname, _ = QFileDialog.getSaveFileName(self, "Export Plot", os.getcwd(), "PNG Image (*.png)")
                if fname:
                    exporter.export(fname)
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
        """Auto-range all plot widgets."""
        self.plot_wave.autoRange()
        self.plot_metrics.autoRange()
        self.plot_spectrum.autoRange()

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
