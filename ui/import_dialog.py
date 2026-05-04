"""
Import dialog for RedByte GFM HIL Suite.

Provides a two-step workflow:
  1. File selection and automatic ingestion (CSV / Excel / JSON).
  2. Channel mapping — the user assigns generic source columns to canonical
     engineering signal names, or leaves them as-is.

The dialog emits ``session_imported(dict)`` when the user confirms, passing a
Data Capsule-compatible session dict that can be fed directly into ReplayStudio.
The original ImportedDataset is also attached as ``session['_dataset']`` for
full-resolution analysis (FFT, THD) that needs the raw numpy arrays.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.channel_mapping import (
    CANONICAL_SIGNALS,
    UNMAPPED,
    ChannelMapper,
    apply_rigol_three_phase_defaults,
    ordered_mapping_targets,
    DIRECT_LINE_TO_LINE_MAPPING_TARGETS,
)
from src.dataset_converter import dataset_to_session
from src.derived_channels import LINE_TO_LINE_CHANNELS
from src.file_ingestion import ImportedDataset, IngestionError, ingest_file

logger = logging.getLogger(__name__)


class ImportDialog(QDialog):
    """
    Modal file import dialog.

    Signals:
        session_imported(dict)  — emitted when the user clicks Import.
            The dict is a Data Capsule capsule with an extra '_dataset' key
            pointing to the full-resolution ImportedDataset.
    """

    session_imported  = pyqtSignal(dict)
    # Internal: carries ImportedDataset on success, Exception on failure.
    # Must be a signal (not a direct call) so the handler always runs on the
    # main Qt thread even when ingestion runs on a worker thread.
    _ingestion_done   = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Run File")
        self.setMinimumSize(900, 600)
        self.setSizeGripEnabled(True)

        self._dataset: Optional[ImportedDataset] = None
        self._mapper = ChannelMapper()
        self._mapping: dict[str, str] = {}
        self._combo_map: dict[str, QComboBox] = {}  # col → combo widget
        self._ingestion_path: str = ""

        self._ingestion_done.connect(self._on_ingestion_done)
        self._build_ui()

    # ──────────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QLabel("Import Run File")
        hdr.setStyleSheet("font-size: 13pt; font-weight: 700; color: #38bdf8;")
        root.addWidget(hdr)

        sub = QLabel(
            "Supported: CSV files (oscilloscope captures, recorded analysis logs, exported measurements), "
            "simulation Excel files (.xlsx / .xls), "
            "existing Data Capsule sessions (.json)"
        )
        sub.setStyleSheet("color: #94a3b8; font-size: 9pt;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── File picker row ───────────────────────────────────────────────────
        pick_row = QHBoxLayout()
        self._lbl_path = QLabel("No file selected")
        self._lbl_path.setStyleSheet("color: #64748b;")
        self._lbl_path.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        btn_browse = QPushButton("Browse…")
        btn_browse.setFixedWidth(90)
        btn_browse.clicked.connect(self._browse)
        pick_row.addWidget(self._lbl_path)
        pick_row.addWidget(btn_browse)
        root.addLayout(pick_row)

        self._lbl_loading = QLabel("")
        self._lbl_loading.setStyleSheet("color: #f59e0b; font-size: 8pt;")
        root.addWidget(self._lbl_loading)

        # ── Main splitter ─────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # Left: metadata + warnings
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)

        # Right: channel mapping
        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)
        splitter.setSizes([310, 510])

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        # Profile buttons
        self._btn_load_profile = QPushButton("Load Profile…")
        self._btn_load_profile.setEnabled(False)
        self._btn_load_profile.clicked.connect(self._load_profile)

        self._btn_save_profile = QPushButton("Save Profile…")
        self._btn_save_profile.setEnabled(False)
        self._btn_save_profile.clicked.connect(self._save_profile)

        btn_row.addWidget(self._btn_load_profile)
        btn_row.addWidget(self._btn_save_profile)
        btn_row.addStretch()

        self._btn_import = QPushButton("Import")
        self._btn_import.setEnabled(False)
        self._btn_import.setStyleSheet(
            "background:#2563eb; color:white; font-weight:700; padding:6px 20px;"
        )
        self._btn_import.clicked.connect(self._do_import)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self._btn_import)
        root.addLayout(btn_row)

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        # File metadata
        grp_meta = QGroupBox("File Metadata")
        meta_layout = QFormLayout(grp_meta)
        meta_layout.setContentsMargins(8, 8, 8, 8)
        meta_layout.setVerticalSpacing(4)

        self._lbl_type = QLabel("—")
        self._lbl_rows = QLabel("—")
        self._lbl_sr = QLabel("—")
        self._lbl_dur = QLabel("—")
        self._lbl_channels = QLabel("—")
        self._lbl_numeric = QLabel("—")
        self._lbl_time = QLabel("—")

        for label, widget in [
            ("Source type:", self._lbl_type),
            ("Rows / frames:", self._lbl_rows),
            ("Sample rate:", self._lbl_sr),
            ("Duration:", self._lbl_dur),
            ("Channels:", self._lbl_channels),
            ("Numeric columns:", self._lbl_numeric),
            ("Detected time column:", self._lbl_time),
        ]:
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #94a3b8; font-size: 8pt;")
            meta_layout.addRow(lbl, widget)

        layout.addWidget(grp_meta)

        # Warnings
        grp_warn = QGroupBox("Warnings")
        warn_layout = QVBoxLayout(grp_warn)
        warn_layout.setContentsMargins(4, 4, 4, 4)
        self._warn_list = QListWidget()
        self._warn_list.setStyleSheet("font-size: 8pt;")
        self._warn_list.setMaximumHeight(180)
        warn_layout.addWidget(self._warn_list)
        layout.addWidget(grp_warn)

        grp_preview = QGroupBox("Import Preview")
        preview_layout = QVBoxLayout(grp_preview)
        preview_layout.setContentsMargins(6, 6, 6, 6)
        self._summary_box = QTextEdit()
        self._summary_box.setReadOnly(True)
        self._summary_box.setMinimumHeight(180)
        self._summary_box.setStyleSheet("font-size: 8pt; color: #cbd5e1;")
        preview_layout.addWidget(self._summary_box)
        layout.addWidget(grp_preview)

        layout.addStretch()
        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(6)

        hdr = QLabel("Channel Mapping")
        hdr.setStyleSheet("font-weight: 700; color: #e2e8f0;")
        layout.addWidget(hdr)

        note = QLabel(
            "Assign source columns to canonical engineering channels when possible. "
            "Unmapped numeric columns still import in Generic Data Analysis Mode "
            "and remain available for plotting and basic statistics.\n"
            "For Rigol 3-phase captures: map CH1(V)->v_an, CH2(V)->v_bn, CH3(V)->v_cn. "
            "Line-to-line channels (v_ab/v_bc/v_ca) are normally derived automatically after import."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b; font-size: 8pt;")
        layout.addWidget(note)

        # Rigol helper: appears when CH1/CH2/CH3 are detected in the source file
        self._rigol_hint = QLabel("")
        self._rigol_hint.setStyleSheet("color: #60a5fa; font-size: 9pt; font-weight:600;")
        self._rigol_hint.setWordWrap(True)
        self._rigol_hint.setVisible(False)
        layout.addWidget(self._rigol_hint)

        self._btn_rigol_map = QPushButton("Apply Rigol 3-Phase Mapping")
        self._btn_rigol_map.setVisible(False)
        self._btn_rigol_map.setFixedWidth(230)
        self._btn_rigol_map.clicked.connect(self._apply_rigol_mapping)
        layout.addWidget(self._btn_rigol_map)

        self._map_table = QTableWidget(0, 4)
        self._map_table.setHorizontalHeaderLabels(
            ["Source column", "Unit", "Range (min → max)", "Map to (canonical)"]
        )
        self._map_table.horizontalHeader().setStretchLastSection(True)
        self._map_table.setColumnWidth(0, 160)
        self._map_table.setColumnWidth(1, 60)
        self._map_table.setColumnWidth(2, 160)
        self._map_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._map_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )
        layout.addWidget(self._map_table, stretch=1)
        return w

    # ──────────────────────────────────────────────────────────────────────────
    # File browsing and ingestion
    # ──────────────────────────────────────────────────────────────────────────

    def load_file(self, path: str) -> None:
        """Pre-load a file before or after the dialog is shown.

        Called from AppShell when a file is opened via drag-and-drop so the
        dialog opens with ingestion already in progress rather than blank.
        """
        self._load_file(path)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Run File",
            os.getcwd(),
            "Supported files (*.csv *.xls *.xlsx *.json);;"
            "Rigol CSV (*.csv);;"
            "Excel Simulation (*.xls *.xlsx);;"
            "Data Capsule JSON (*.json)",
        )
        if not path:
            return
        self._load_file(path)

    def _load_file(self, path: str) -> None:
        """
        Begin ingesting a file.  Ingestion runs on a daemon thread so the UI
        stays responsive for large files (e.g. 1 M-row Rigol captures).
        Results are marshalled back onto the main thread via _ingestion_done.
        """
        fname = os.path.basename(path)
        self._lbl_path.setText(fname)
        self._lbl_path.setStyleSheet("color: #94a3b8;")
        self._lbl_loading.setText("Reading file…  (large files may take a few seconds)")
        self._btn_import.setEnabled(False)
        self._btn_save_profile.setEnabled(False)
        self._btn_load_profile.setEnabled(False)
        self._warn_list.clear()
        self._map_table.setRowCount(0)
        self._combo_map.clear()
        self._ingestion_path = path

        t = threading.Thread(target=self._run_ingestion, args=(path,), daemon=True)
        t.start()

    def _run_ingestion(self, path: str) -> None:
        """Worker: called on background thread.  Emits _ingestion_done."""
        try:
            dataset = ingest_file(path)
            self._ingestion_done.emit(dataset)
        except (IngestionError, FileNotFoundError) as exc:
            self._ingestion_done.emit(exc)
        except Exception as exc:
            logger.exception("Unexpected error ingesting '%s'", path)
            self._ingestion_done.emit(exc)

    def _on_ingestion_done(self, result: object) -> None:
        """Main-thread handler called after background ingestion completes."""
        self._lbl_loading.setText("")

        if isinstance(result, Exception):
            self._lbl_path.setStyleSheet("color: #ef4444;")
            QMessageBox.critical(self, "Import Error", str(result))
            return

        # result is an ImportedDataset
        dataset: ImportedDataset = result  # type: ignore[assignment]
        self._dataset = dataset
        self._lbl_path.setStyleSheet("color: #e2e8f0;")
        self._populate_metadata(dataset)
        self._populate_warnings(dataset)
        self._populate_mapping_table(dataset)

        self._btn_import.setEnabled(True)
        self._btn_save_profile.setEnabled(True)
        self._btn_load_profile.setEnabled(True)

    # ──────────────────────────────────────────────────────────────────────────
    # Panel population helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _populate_metadata(self, ds: ImportedDataset) -> None:
        type_labels = {
            "rigol_csv":         "CSV",
            "simulation_excel":  "Simulation Excel",
            "data_capsule_json": "Data Capsule JSON",
        }
        self._lbl_type.setText(type_labels.get(ds.source_type, ds.source_type))
        self._lbl_rows.setText(f"{ds.row_count:,}")
        if ds.sample_rate > 0:
            self._lbl_sr.setText(f"{ds.sample_rate:,.1f} Hz")
        else:
            self._lbl_sr.setText("unknown")
        self._lbl_dur.setText(f"{ds.duration:.3f} s" if ds.duration > 0 else "—")
        self._lbl_channels.setText(str(len(ds.channels)))
        self._lbl_numeric.setText(str(len(ds.channels)))
        self._lbl_time.setText(ds.meta.get("time_column") or "none")

    def _populate_warnings(self, ds: ImportedDataset) -> None:
        self._warn_list.clear()
        if not ds.warnings:
            item = QListWidgetItem("No warnings.")
            item.setForeground(QColor("#10b981"))
            self._warn_list.addItem(item)
            return
        for w in ds.warnings:
            item = QListWidgetItem(w)
            item.setForeground(QColor("#f59e0b"))
            self._warn_list.addItem(item)

    def _populate_mapping_table(self, ds: ImportedDataset) -> None:
        from src.channel_mapping import infer_unit_from_header
        import numpy as np

        suggested = self._mapper.auto_suggest(ds.raw_headers)
        suggested = apply_rigol_three_phase_defaults(ds.raw_headers, suggested)
        # Exclude the time column from channel mappings — it is the x-axis, not a
        # signal channel, and including it produces a spurious "Unmapped: Time(s)"
        # notice in the waveform view.
        _time_col = ds.meta.get("time_column")
        self._mapping = {k: v for k, v in suggested.items() if k != _time_col}
        self._combo_map.clear()
        self._map_table.setRowCount(0)

        # Canonical choices for the dropdown — present primary targets first
        canonical_options = [UNMAPPED] + ordered_mapping_targets(include_direct_line_to_line=True)

        for col in ds.raw_headers:
            if col == ds.meta.get("time_column"):
                continue  # skip the time axis row
            self._map_table.insertRow(self._map_table.rowCount())
            row = self._map_table.rowCount() - 1

            # Column 0: source name
            it_src = QTableWidgetItem(col)
            it_src.setToolTip(col)
            self._map_table.setItem(row, 0, it_src)

            # Column 1: inferred unit
            unit = infer_unit_from_header(col) or "—"
            it_unit = QTableWidgetItem(unit)
            it_unit.setForeground(QColor("#94a3b8"))
            it_unit.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._map_table.setItem(row, 1, it_unit)

            # Column 2: value range (min → max) — surfaces dead/constant channels
            arr = ds.channels.get(col)
            if arr is not None and len(arr) > 0:
                valid = arr[~np.isnan(arr)]
                if len(valid) > 0:
                    vmin, vmax = float(valid.min()), float(valid.max())
                    span = vmax - vmin
                    range_str = f"{vmin:.4g}  →  {vmax:.4g}"
                    # Flag near-zero or nearly-constant channels
                    ref = max(abs(vmin), abs(vmax), 1e-12)
                    if span < 0.001 * ref:
                        range_color = "#f59e0b"  # amber — constant/dead
                        it_src.setToolTip(
                            f"{col}\nWARNING: near-constant value (range={span:.2e})"
                        )
                    else:
                        range_color = "#94a3b8"
                else:
                    range_str = "all NaN"
                    range_color = "#ef4444"
            else:
                range_str = "—"
                range_color = "#64748b"

            it_range = QTableWidgetItem(range_str)
            it_range.setForeground(QColor(range_color))
            it_range.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._map_table.setItem(row, 2, it_range)

            # Column 3: canonical mapping dropdown
            combo = QComboBox()
            combo.addItems(canonical_options)
            # Insert a non-selectable separator before direct line-to-line choices
            try:
                first_direct = DIRECT_LINE_TO_LINE_MAPPING_TARGETS[0]
                if first_direct in canonical_options:
                    sep_idx = canonical_options.index(first_direct)
                    combo.insertSeparator(sep_idx)
            except Exception:
                # Non-fatal: if the QComboBox API differs, skip the separator.
                pass
            target = suggested.get(col, UNMAPPED)
            if target and target in canonical_options:
                combo.setCurrentText(target)
            else:
                combo.setCurrentText(UNMAPPED)
            combo.currentTextChanged.connect(
                lambda val, c=col: self._on_mapping_changed(c, val)
            )
            self._map_table.setCellWidget(row, 3, combo)
            self._combo_map[col] = combo

        # If Rigol 3-phase headers are present, surface the helper and button
        rigol_cols = ["CH1(V)", "CH2(V)", "CH3(V)"]
        if all(c in ds.raw_headers for c in rigol_cols):
            self._rigol_hint.setText(
                "Detected 3 voltage channels. Mapping was preselected as "
                "CH1(V)→v_an, CH2(V)→v_bn, CH3(V)→v_cn. "
                "CH4(V), if present, stays unmapped by default and should be treated as raw auxiliary unless calibrated. "
                "V_ab/V_bc/V_ca will be derived after import."
            )
            self._rigol_hint.setVisible(True)
            self._btn_rigol_map.setVisible(True)
        else:
            self._rigol_hint.setVisible(False)
            self._btn_rigol_map.setVisible(False)

        self._refresh_analysis_preview()

    # ──────────────────────────────────────────────────────────────────────────
    # Mapping events
    # ──────────────────────────────────────────────────────────────────────────

    def _on_mapping_changed(self, col: str, value: str) -> None:
        self._mapping[col] = value
        self._refresh_analysis_preview()

    # ──────────────────────────────────────────────────────────────────────────
    # Profile management
    # ──────────────────────────────────────────────────────────────────────────

    def _load_profile(self) -> None:
        profiles = self._mapper.list_profiles()
        if not profiles:
            QMessageBox.information(self, "Profiles", "No saved profiles found.")
            return

        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getItem(
            self, "Load Profile", "Select profile:", profiles, 0, False
        )
        if not ok or not name:
            return

        prof = self._mapper.load_profile(name)
        if prof is None:
            return

        # Apply to combo boxes
        for col, combo in self._combo_map.items():
            target = prof.get(col, UNMAPPED)
            idx = combo.findText(target)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            self._mapping[col] = target

    def _save_profile(self) -> None:
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "Save Profile", "Profile name:"
        )
        if ok and name.strip():
            self._mapper.save_profile(name.strip(), self._mapping)
            QMessageBox.information(
                self, "Saved", f"Profile '{name.strip()}' saved."
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Import action
    # ──────────────────────────────────────────────────────────────────────────

    def _do_import(self) -> None:
        if self._dataset is None:
            return

        # ── Probe-scale detection for Rigol CSV voltage channels ─────────────
        # Rigol oscilloscopes with a ×100 probe write reduced-amplitude values.
        # Detect this automatically: if source is a Rigol CSV and the mapped
        # phase voltages have a raw RMS below 5 V (vs expected ~120 V), apply
        # a ×100 scale factor so every downstream component (metrics, compliance,
        # waveform plots) sees physically-correct voltages.
        _VOLTAGE_CANONICAL = {"v_an", "v_bn", "v_cn", "v_ab", "v_bc", "v_ca"}
        scale_factors: dict[str, float] = {}
        probe_note: str = ""
        if self._dataset.source_type == "rigol_csv":
            mapped_voltage_channels = {
                target: src
                for src, target in self._mapping.items()
                if target in _VOLTAGE_CANONICAL and src in self._dataset.channels
            }
            if mapped_voltage_channels:
                import numpy as _np
                first_ch_src = next(iter(mapped_voltage_channels.values()))
                raw_arr = self._dataset.channels[first_ch_src]
                raw_rms = float(_np.sqrt(_np.mean(raw_arr.astype(_np.float64) ** 2)))
                # raw_rms < 5 V strongly suggests ×100 probe attenuation
                if 0.0 < raw_rms < 5.0:
                    for canonical in mapped_voltage_channels:
                        scale_factors[canonical] = 100.0
                    probe_note = (
                        f"Rigol ×100 probe scale auto-applied to "
                        f"{', '.join(sorted(mapped_voltage_channels))} "
                        f"(raw RMS was {raw_rms:.3f} V → scaled to "
                        f"{raw_rms * 100:.1f} V)"
                    )
                    logger.info("import_dialog.probe_scale: %s", probe_note)

        # Apply channel mapping (and scale factors) to produce renamed dataset
        mapped_ds = self._mapper.apply(
            self._dataset, self._mapping,
            scale_factors=scale_factors if scale_factors else None,
        )

        try:
            t0 = time.perf_counter()
            logger.info("import_dialog.convert.start: %s", os.path.basename(self._dataset.source_path))
            capsule = dataset_to_session(mapped_ds)
            elapsed = time.perf_counter() - t0
            logger.info("import_dialog.convert.end: %s (%.3fs)", os.path.basename(self._dataset.source_path), elapsed)
        except Exception as exc:
            QMessageBox.critical(
                self, "Conversion Error",
                f"Failed to convert dataset to session:\n{exc}"
            )
            return

        # Attach the full-resolution dataset for analysis tabs that need it
        capsule["_dataset"] = mapped_ds

        if probe_note:
            capsule.setdefault("import_meta", {}).setdefault("notes", [])
            capsule["import_meta"]["notes"].append(probe_note)

        logger.info(
            "Import confirmed: '%s', %d frames, channels=%s",
            os.path.basename(self._dataset.source_path),
            capsule["meta"]["frame_count"],
            capsule["meta"]["channels"],
        )

        t1 = time.perf_counter()
        logger.info("import_dialog.emit.start: %s", os.path.basename(self._dataset.source_path))
        self.session_imported.emit(capsule)
        self.accept()
        logger.info("import_dialog.emit.end: %s (%.3fs)", os.path.basename(self._dataset.source_path), time.perf_counter() - t1)

    def _refresh_analysis_preview(self) -> None:
        if self._dataset is None:
            self._summary_box.setPlainText("")
            return

        time_column = self._dataset.meta.get("time_column") or "none"
        raw_columns = [col for col in self._dataset.raw_headers if col != self._dataset.meta.get("time_column")]
        mapped_channels = sorted(
            target for target in self._mapping.values()
            if target and target != UNMAPPED
        )
        unmapped_numeric = [
            col for col in raw_columns
            if self._mapping.get(col, UNMAPPED) in (UNMAPPED, "", None)
        ]
        derived_channels = sorted(
            target
            for target, (pos_key, neg_key, _label) in LINE_TO_LINE_CHANNELS.items()
            if pos_key in mapped_channels and neg_key in mapped_channels
        )
        analysis_mode = (
            "VSM/GFM analysis mode"
            if any(channel in mapped_channels for channel in ("v_an", "v_bn", "v_cn", "freq", "i_a", "i_b", "i_c", "p_mech"))
            else "Generic data analysis mode"
        )

        lines = [
            f"Source file: {os.path.basename(self._dataset.source_path)}",
            f"Detected time column: {time_column}",
            f"Raw source columns: {', '.join(raw_columns) if raw_columns else 'none'}",
            f"Canonical mapped channels: {', '.join(mapped_channels) if mapped_channels else 'none'}",
            f"Derived computed channels: {', '.join(derived_channels) if derived_channels else 'none'}",
            f"Generic or auxiliary numeric channels kept as-is: {', '.join(unmapped_numeric) if unmapped_numeric else 'none'}",
            f"Analysis mode after import: {analysis_mode}",
        ]
        if analysis_mode == "Generic data analysis mode":
            lines.append(
                "Compliance behavior: VSM-specific checks will report N/A unless voltage/frequency channels are mapped."
            )

        ch4_key = next(
            (c for c in raw_columns if c.lower() in ("ch4(v)", "ch4", "ch4 (v)")),
            None,
        )
        if ch4_key is not None:
            ch4_target = self._mapping.get(ch4_key, UNMAPPED)
            ch4_arr = self._dataset.channels.get(ch4_key)
            ch4_note = (
                "CH4(V) guidance: this channel is usually a raw auxiliary signal. "
                "Leave it unmapped or map to aux_ch4 unless a calibration is known."
            )
            if ch4_arr is not None and len(ch4_arr) > 0:
                ch4_valid = ch4_arr[np.isfinite(ch4_arr)]
                if len(ch4_valid) > 0:
                    ch4_rms = float(np.sqrt(np.mean(ch4_valid.astype(np.float64) ** 2)))
                    ch4_span = float(ch4_valid.max() - ch4_valid.min())
                    if ch4_rms < 0.05 and ch4_span < 0.2:
                        ch4_note += (
                            f" Detected low-level amplitude (RMS {ch4_rms:.4f}, span {ch4_span:.4f}), "
                            "so treating it as v_dc would be misleading."
                        )
            if ch4_target == "v_dc":
                ch4_note += " Current mapping selects v_dc; consider changing to aux_ch4 or unmapped."
            elif ch4_target == "aux_ch4":
                ch4_note += " Current mapping aux_ch4 is appropriate for an uncalibrated auxiliary channel."
            lines.append(ch4_note)

        self._summary_box.setPlainText("\n".join(lines))

    def _apply_rigol_mapping(self) -> None:
        """Apply a conservative Rigol 3-phase mapping to the current mapping UI.

        Only applies when the exact headers CH1(V)/CH2(V)/CH3(V) are present.
        This sets the dropdowns but does not silently import; the user must
        still click Import to confirm.
        """
        if self._dataset is None:
            return
        rigol_cols = ["CH1(V)", "CH2(V)", "CH3(V)"]
        if not all(c in self._dataset.raw_headers for c in rigol_cols):
            return

        mapping = {
            "CH1(V)": "v_an",
            "CH2(V)": "v_bn",
            "CH3(V)": "v_cn",
        }
        # Update combo boxes and internal mapping
        for col, target in mapping.items():
            combo = self._combo_map.get(col)
            if combo is not None:
                idx = combo.findText(target)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setCurrentText(target)
            self._mapping[col] = target

        self._refresh_analysis_preview()
