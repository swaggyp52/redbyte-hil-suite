"""
Comparison Panel for RedByte GFM HIL Suite.

Shows a side-by-side (overlay + delta) comparison of two loaded sessions.
Embedded as the 4th tab in ReplayStudio.

Layout:
  Top bar — Dataset A/B labels, Auto-Align, Offset spinner, Compare button
  Overlay plot — both channels overlaid (A = solid, B = dashed)
  Delta plot — (A − B) trace
  Metrics row — per-channel RMS / peak / correlation chips
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.comparison import (
    ComparisonResult,
    align_datasets,
    compare_datasets,
    dataset_from_capsule,
    find_overlapping_channels,
)

logger = logging.getLogger(__name__)

# Colour pairs (A_colour, B_colour) per channel slot
_CHANNEL_COLORS = [
    ("#38bdf8", "#f97316"),   # sky blue / orange
    ("#4ade80", "#f43f5e"),   # green / rose
    ("#a78bfa", "#fbbf24"),   # violet / amber
    ("#22d3ee", "#fb923c"),   # cyan / orange-light
]
_DELTA_COLOR = "#94a3b8"     # slate


class ComparisonPanel(QWidget):
    """
    Dual-session comparison view.

    Call :meth:`set_sessions` whenever the caller has a primary session (A)
    and an overlay session (B) ready.  The panel does not trigger comparison
    automatically — the user must click **Compare** (or **Auto-Align** first).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._session_a: Optional[dict] = None
        self._session_b: Optional[dict] = None
        self._last_result: Optional[ComparisonResult] = None
        self._build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_sessions(self, session_a: dict, session_b: dict) -> None:
        """
        Provide two session dicts (from ReplayStudio.sessions).

        Each dict is expected to have at least ``"data"`` (capsule dict)
        and ``"label"`` (str) keys.

        Args:
            session_a: Primary / reference session.
            session_b: Comparison session.
        """
        self._session_a = session_a
        self._session_b = session_b

        self._btn_align.setEnabled(True)
        self._btn_align.setToolTip(
            "Use cross-correlation to estimate timing offset between A and B"
        )
        self._btn_compare.setEnabled(True)
        self._btn_compare.setToolTip("")

        label_a = session_a.get("label", "Dataset A")
        label_b = session_b.get("label", "Dataset B")
        self._lbl_a.setText(f"Baseline: {label_a}")
        self._lbl_b.setText(f"Comparison/Fault: {label_b}")

        # Hide empty-state guidance once both sessions are available
        self._empty_hint.setVisible(False)

        # Populate channel selector
        self._populate_channels()

        # One-action compare workflow for demos: as soon as A and B are present,
        # attempt alignment and render an initial overlay/delta result.
        self._on_auto_align()
        self._on_compare()

    def clear(self) -> None:
        """Reset panel to empty state."""
        self._session_a = None
        self._session_b = None
        self._last_result = None
        self._lbl_a.setText("A: —")
        self._lbl_b.setText("B: —")
        self._channel_combo.clear()
        self._btn_align.setEnabled(False)
        self._btn_compare.setEnabled(False)
        self._empty_hint.setVisible(True)
        self._clear_plots()
        self._clear_metrics()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Top control bar ──────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        self._lbl_a = QLabel("A: —")
        self._lbl_a.setObjectName("CompareLabel")
        self._vs_lbl = QLabel("vs")
        self._vs_lbl.setStyleSheet("color: #64748b;")
        self._lbl_b = QLabel("B: —")
        self._lbl_b.setObjectName("CompareLabel")

        self._channel_combo = QComboBox()
        self._channel_combo.setMinimumWidth(120)
        self._channel_combo.setToolTip("Channel to display in detail view")

        self._btn_align = QPushButton("Auto-Align")
        self._btn_align.setToolTip(
            "Use cross-correlation to estimate timing offset between A and B"
        )
        self._btn_align.clicked.connect(self._on_auto_align)

        offset_lbl = QLabel("Offset (ms):")
        offset_lbl.setStyleSheet("color: #94a3b8;")
        self._offset_spin = QDoubleSpinBox()
        self._offset_spin.setRange(-5000.0, 5000.0)
        self._offset_spin.setSingleStep(1.0)
        self._offset_spin.setDecimals(1)
        self._offset_spin.setValue(0.0)
        self._offset_spin.setFixedWidth(80)

        self._btn_compare = QPushButton("Compare")
        self._btn_compare.setObjectName("AccentButton")
        self._btn_compare.clicked.connect(self._on_compare)

        for w in [self._lbl_a, self._vs_lbl, self._lbl_b,
                  self._channel_combo,
                  self._btn_align, offset_lbl, self._offset_spin,
                  self._btn_compare]:
            ctrl.addWidget(w)
        ctrl.addStretch()
        root.addLayout(ctrl)

        # Disable action buttons until both sessions are loaded
        self._btn_align.setEnabled(False)
        self._btn_align.setToolTip("Load two sessions first")
        self._btn_compare.setEnabled(False)
        self._btn_compare.setToolTip("Load two sessions first")

        # ── Empty state guidance (shown until both sessions loaded) ──
        self._empty_hint = QLabel(
            "Load a session in the Replay tab, then click <b>Add Overlay</b> "
            "to load a second session.<br><br>"
            "Once both datasets (A and B) are loaded, use <b>Auto-Align</b> to "
            "time-synchronise them and <b>Compare</b> to see overlay and delta plots."
        )
        self._empty_hint.setWordWrap(True)
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setStyleSheet(
            "color: #64748b; font-size: 9pt; padding: 32px 24px; "
            "background: rgba(15,17,21,180); border: 1px dashed rgba(31,41,55,180); "
            "border-radius: 10px;"
        )
        root.addWidget(self._empty_hint)

        # ── Confidence label (shown after auto-align) ─────────────
        self._align_info = QLabel("")
        self._align_info.setStyleSheet(
            "color: #94a3b8; font-size: 9pt; font-weight: 600; padding: 2px 4px;"
        )
        root.addWidget(self._align_info)

        # ── Splitter: overlay + delta plots ──────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._plot_overlay = pg.PlotWidget(title="Overlay (Baseline solid · Comparison dashed)")
        self._plot_overlay.setBackground("#0b0f14")
        self._plot_overlay.showGrid(x=True, y=True, alpha=0.3)
        self._plot_overlay.setLabel("bottom", "Time", units="s")
        self._plot_overlay.addLegend()
        splitter.addWidget(self._plot_overlay)

        self._plot_delta = pg.PlotWidget(title="Delta  (Comparison − Baseline)")
        self._plot_delta.setBackground("#0b0f14")
        self._plot_delta.showGrid(x=True, y=True, alpha=0.3)
        self._plot_delta.setLabel("bottom", "Time", units="s")
        self._plot_delta.setLabel("left", "Δ")
        splitter.addWidget(self._plot_delta)

        splitter.setSizes([300, 150])
        root.addWidget(splitter, stretch=1)

        # ── Metrics strip ─────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1e293b;")
        root.addWidget(sep)

        metrics_scroll = QScrollArea()
        metrics_scroll.setFixedHeight(80)
        metrics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        metrics_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        metrics_scroll.setWidgetResizable(True)
        self._metrics_inner = QWidget()
        self._metrics_layout = QHBoxLayout(self._metrics_inner)
        self._metrics_layout.setContentsMargins(4, 4, 4, 4)
        self._metrics_layout.setSpacing(12)
        self._metrics_layout.addStretch()
        metrics_scroll.setWidget(self._metrics_inner)
        root.addWidget(metrics_scroll)

        # placeholder curves
        self._overlay_curves_a: list = []
        self._overlay_curves_b: list = []
        self._delta_curve = self._plot_delta.plot(pen=pg.mkPen(_DELTA_COLOR, width=1))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_auto_align(self) -> None:
        if not self._sessions_ready():
            return
        try:
            ds_a = self._analysis_dataset(self._session_a)
            ds_b = self._analysis_dataset(self._session_b)
        except Exception as exc:
            logger.warning("Auto-align: cannot build datasets: %s", exc)
            return

        channel = self._selected_channel()
        if not channel:
            channels = find_overlapping_channels(ds_a, ds_b)
            if not channels:
                self._align_info.setText("No overlapping channels — cannot auto-align.")
                return
            channel = channels[0]

        offset_s, confidence = align_datasets(ds_a, ds_b, channel=channel,
                                               max_offset_s=1.0)
        self._offset_spin.setValue(round(offset_s * 1000.0, 1))

        conf_pct = int(confidence * 100)
        colour = "#10b981" if confidence > 0.7 else "#f59e0b" if confidence > 0.4 else "#ef4444"
        self._align_info.setStyleSheet(
            f"color: {colour}; font-size: 9pt; font-weight: 600; padding: 2px 4px;"
        )
        self._align_info.setText(
            f"Auto-align on '{channel}': offset {offset_s*1000:.1f} ms  "
            f"(confidence {conf_pct}%)"
        )

    def _on_compare(self) -> None:
        if not self._sessions_ready():
            return
        try:
            ds_a = self._analysis_dataset(self._session_a)
            ds_b = self._analysis_dataset(self._session_b)
        except Exception as exc:
            logger.warning("Compare: cannot build datasets: %s", exc)
            return

        timing_offset_s = self._offset_spin.value() / 1000.0

        # Check for duplicate datasets before comparing
        from src.comparison import detect_duplicate_datasets
        candidates = find_overlapping_channels(ds_a, ds_b)
        if candidates:
            dup_warn = detect_duplicate_datasets(ds_a, ds_b, channel=candidates[0])
            if dup_warn:
                self._align_info.setStyleSheet("color: #f59e0b; font-size: 9pt; font-weight: 600; padding: 2px 4px;")
                self._align_info.setText(f"\u26a0 {dup_warn}")

        result = compare_datasets(
            ds_a, ds_b,
            label_a=self._session_a.get("label", "A"),
            label_b=self._session_b.get("label", "B"),
            timing_offset_s=timing_offset_s,
        )
        self._last_result = result
        self._render(ds_a, ds_b, result)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self, ds_a, ds_b, result: ComparisonResult) -> None:
        self._clear_plots()
        self._clear_metrics()

        channel = self._selected_channel()
        channels_to_show = (
            [channel] if channel and channel in result.channels
            else list(result.channels.keys())
        )

        label_a = result.label_a
        label_b = result.label_b

        for i, ch in enumerate(channels_to_show[:4]):  # cap at 4 for readability
            col_a, col_b = _CHANNEL_COLORS[i % len(_CHANNEL_COLORS)]

            # Overlay: A solid, B dashed
            t_a = ds_a.time
            sig_a = ds_a.channels.get(ch)
            if sig_a is not None:
                c_a = self._plot_overlay.plot(
                    t_a, sig_a,
                    pen=pg.mkPen(col_a, width=2),
                    name=f"{label_a} · {ch}",
                )
                self._overlay_curves_a.append(c_a)

            t_b = ds_b.time + (result.timing_offset_s or 0.0)
            sig_b = ds_b.channels.get(ch)
            if sig_b is not None:
                c_b = self._plot_overlay.plot(
                    t_b, sig_b,
                    pen=pg.mkPen(col_b, width=2, style=Qt.PenStyle.DashLine),
                    name=f"{label_b} · {ch}",
                )
                self._overlay_curves_b.append(c_b)

        # Delta: first channel in results
        if channels_to_show:
            first_ch = channels_to_show[0]
            from src.comparison import generate_delta_trace
            t_delta, delta = generate_delta_trace(
                ds_a, ds_b, first_ch,
                timing_offset_s=result.timing_offset_s or 0.0,
                max_points=2000,
            )
            if len(t_delta) > 0:
                self._delta_curve.setData(t_delta, delta)
                unit = result.channels[first_ch].units or ""
                self._plot_delta.setTitle(f"Delta  ·  {first_ch}  (Comparison − Baseline)")
                self._plot_delta.setLabel("left", "Δ", units=unit or None)

        # Metrics chips
        for ch, r in result.channels.items():
            self._add_metric_chip(ch, r)

        # Skipped / warnings
        for skip in result.skipped_channels:
            self._add_skip_chip(skip)

    def _add_metric_chip(self, channel: str, r) -> None:
        chip = QFrame()
        chip.setObjectName("MetricChip")
        v = QVBoxLayout(chip)
        v.setContentsMargins(8, 4, 8, 4)
        v.setSpacing(2)

        title = QLabel(channel)
        title.setStyleSheet("font-weight: 700; color: #e2e8f0; font-size: 9pt;")

        corr_val = r.correlation
        corr_txt = f"{corr_val:.3f}" if corr_val == corr_val else "N/A"  # NaN check
        rms_txt  = f"{r.rms_error:.4f}" if r.rms_error == r.rms_error else "N/A"

        delta_rms_txt = f"{r.delta_rms:+.4f}" if r.delta_rms == r.delta_rms else "N/A"
        thd_txt = f"{r.delta_thd_pct:+.3f}%" if r.delta_thd_pct == r.delta_thd_pct else "N/A"
        body = QLabel(
            f"ΔRMS: {delta_rms_txt} {r.units}  |  max|Δ|: {r.peak_abs_error:.4f} {r.units}  |  r={corr_txt}"
        )
        body.setStyleSheet("color: #94a3b8; font-size: 8pt; font-family: 'JetBrains Mono', 'Consolas', monospace;")
        detail = QLabel(
            f"Baseline RMS {r.ref_rms:.4f} {r.units}  |  Comparison RMS {r.test_rms:.4f} {r.units}  |  ΔTHD {thd_txt}"
        )
        detail.setStyleSheet("color: #64748b; font-size: 8pt;")

        v.addWidget(title)
        v.addWidget(body)
        v.addWidget(detail)

        # Remove the trailing stretch before insert
        count = self._metrics_layout.count()
        self._metrics_layout.insertWidget(count - 1, chip)

    def _add_skip_chip(self, channel: str) -> None:
        chip = QLabel(f"⊘ {channel}")
        chip.setStyleSheet(
            "background: #292524; color: #78716c; border-radius: 4px; padding: 4px 8px; font-size: 8pt;"
        )
        count = self._metrics_layout.count()
        self._metrics_layout.insertWidget(count - 1, chip)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_channels(self) -> None:
        if not self._session_a or not self._session_b:
            return
        try:
            ds_a = self._analysis_dataset(self._session_a)
            ds_b = self._analysis_dataset(self._session_b)
        except Exception:
            return
        channels = find_overlapping_channels(ds_a, ds_b)
        self._channel_combo.clear()
        self._channel_combo.addItem("All matched channels", None)
        for ch in channels:
            self._channel_combo.addItem(ch, ch)

    def _selected_channel(self) -> Optional[str]:
        return self._channel_combo.currentData()

    def _analysis_dataset(self, session: dict):
        dataset = session.get("_dataset")
        if dataset is not None:
            return dataset
        return dataset_from_capsule(session["data"], session.get("label", ""))

    def _sessions_ready(self) -> bool:
        return self._session_a is not None and self._session_b is not None

    def _clear_plots(self) -> None:
        for c in self._overlay_curves_a + self._overlay_curves_b:
            self._plot_overlay.removeItem(c)
        self._overlay_curves_a.clear()
        self._overlay_curves_b.clear()
        self._delta_curve.setData([], [])

    def _clear_metrics(self) -> None:
        # Remove everything except the trailing stretch
        while self._metrics_layout.count() > 1:
            item = self._metrics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
