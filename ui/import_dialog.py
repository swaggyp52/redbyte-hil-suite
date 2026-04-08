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
from typing import Optional

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

from src.channel_mapping import CANONICAL_SIGNALS, UNMAPPED, ChannelMapper
from src.dataset_converter import dataset_to_session
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
            "Supported: CSV files (oscilloscope captures, simulation logs, telemetry data), "
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

        for label, widget in [
            ("Source type:", self._lbl_type),
            ("Rows / frames:", self._lbl_rows),
            ("Sample rate:", self._lbl_sr),
            ("Duration:", self._lbl_dur),
            ("Channels:", self._lbl_channels),
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
            "Assign each source column to a canonical signal name, or leave "
            "it as-is.  Generic channels like CH1/CH2 will be displayed under "
            "their original names wherever no mapping is applied."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b; font-size: 8pt;")
        layout.addWidget(note)

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
        self._mapping = dict(suggested)
        self._combo_map.clear()
        self._map_table.setRowCount(0)

        # Canonical choices for the dropdown
        canonical_options = [UNMAPPED] + sorted(CANONICAL_SIGNALS.keys())

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

    # ──────────────────────────────────────────────────────────────────────────
    # Mapping events
    # ──────────────────────────────────────────────────────────────────────────

    def _on_mapping_changed(self, col: str, value: str) -> None:
        self._mapping[col] = value

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

        # Apply channel mapping to produce renamed dataset
        mapped_ds = self._mapper.apply(self._dataset, self._mapping)

        try:
            capsule = dataset_to_session(mapped_ds)
        except Exception as exc:
            QMessageBox.critical(
                self, "Conversion Error",
                f"Failed to convert dataset to session:\n{exc}"
            )
            return

        # Attach the full-resolution dataset for analysis tabs that need it
        capsule["_dataset"] = mapped_ds

        logger.info(
            "Import confirmed: '%s', %d frames, channels=%s",
            os.path.basename(self._dataset.source_path),
            capsule["meta"]["frame_count"],
            capsule["meta"]["channels"],
        )

        self.session_imported.emit(capsule)
        self.accept()
