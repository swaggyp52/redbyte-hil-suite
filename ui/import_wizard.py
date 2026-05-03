"""
import_wizard.py — PyQt6 dialog for importing external CSV/Excel datasets
into a normalized Data Capsule suitable for the Replay Studio and the rest
of the VSM Evidence Workbench.

Usage:
    from ui.import_wizard import ImportWizard
    dlg = ImportWizard(parent=self)
    if dlg.exec():
        capsule_path = dlg.saved_capsule_path  # str path to .json capsule
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QGroupBox, QCheckBox, QDoubleSpinBox,
    QDialogButtonBox, QPlainTextEdit, QWidget, QFrame,
)

from src.importer import DataImporter, CANONICAL_CHANNELS

logger = logging.getLogger(__name__)


REQUIRED_MAPPINGS = ("ts",)
STRONGLY_RECOMMENDED = ("v_an", "v_bn", "v_cn", "freq")


class ImportWizard(QDialog):
    """Three-step dialog: pick file -> map columns -> preview & save."""

    def __init__(self, parent=None, start_dir: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Import External Dataset — VSM Evidence Workbench")
        self.resize(960, 720)

        self.start_dir = start_dir or os.getcwd()
        self._filepath: Optional[str] = None
        self._columns: List[str] = []
        self._preview_rows: List[Dict] = []
        self._suggested_map: Dict[str, str] = {}
        self._suggested_time_unit: str = "s"
        self._sheet_names: List[str] = []
        self._capsule = None
        self.saved_capsule_path: Optional[str] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- header ---
        title = QLabel("Import External Dataset")
        title.setStyleSheet("font-size:14pt;font-weight:700;color:#38bdf8;")
        root.addWidget(title)

        subtitle = QLabel(
            "Import CSV or Excel exports from lab / simulation tools. "
            "Columns will be mapped to canonical VSM channels (v_an/…/freq) "
            "and the data will be saved as a normalized session capsule."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#94a3b8;")
        root.addWidget(subtitle)

        # ---- Step 1: file picker ----
        step1 = QGroupBox("1. Source file")
        s1 = QHBoxLayout(step1)
        self.ed_path = QLineEdit()
        self.ed_path.setReadOnly(True)
        self.ed_path.setPlaceholderText("Select a .csv / .xlsx / .xls file …")
        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.clicked.connect(self._on_browse)
        s1.addWidget(self.ed_path, 1)
        s1.addWidget(self.btn_browse)

        # Excel sheet picker
        self.cb_sheet = QComboBox()
        self.cb_sheet.setVisible(False)
        self.cb_sheet.currentTextChanged.connect(self._on_sheet_changed)
        s1.addWidget(QLabel("Sheet:"))
        s1.addWidget(self.cb_sheet)
        root.addWidget(step1)

        # ---- Step 2: mapping ----
        step2 = QGroupBox("2. Column mapping")
        s2 = QVBoxLayout(step2)
        hint = QLabel(
            "Map each canonical channel to a source column.  "
            "Auto-detect runs on file open; adjust as needed.  "
            "Only the time column is strictly required."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#94a3b8;font-size:9pt;")
        s2.addWidget(hint)

        self.map_table = QTableWidget(len(CANONICAL_CHANNELS), 3)
        self.map_table.setHorizontalHeaderLabels(["Canonical Channel", "Source Column", "Status"])
        self.map_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.map_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.map_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.map_table.verticalHeader().setVisible(False)
        self._mapping_combos: Dict[str, QComboBox] = {}

        # First row = ts; then canonical channels
        row_keys = ("ts",) + tuple(CANONICAL_CHANNELS)
        self.map_table.setRowCount(len(row_keys))
        for r, key in enumerate(row_keys):
            lbl = QTableWidgetItem(key + ("  *" if key in REQUIRED_MAPPINGS else ""))
            lbl.setFlags(lbl.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.map_table.setItem(r, 0, lbl)
            cb = QComboBox()
            cb.addItem("(none)")
            cb.currentTextChanged.connect(self._update_mapping_status)
            self._mapping_combos[key] = cb
            self.map_table.setCellWidget(r, 1, cb)
            self.map_table.setItem(r, 2, QTableWidgetItem(""))
        s2.addWidget(self.map_table, 1)
        root.addWidget(step2, 1)

        # ---- Step 3: options ----
        step3 = QGroupBox("3. Options")
        s3 = QGridLayout(step3)
        s3.addWidget(QLabel("Time unit:"), 0, 0)
        self.cb_time_unit = QComboBox()
        self.cb_time_unit.addItems(["auto", "s", "ms"])
        s3.addWidget(self.cb_time_unit, 0, 1)

        self.chk_resample = QCheckBox("Resample to uniform dt")
        s3.addWidget(self.chk_resample, 1, 0)
        self.spn_dt = QDoubleSpinBox()
        self.spn_dt.setDecimals(6)
        self.spn_dt.setRange(0.000001, 10.0)
        self.spn_dt.setValue(0.02)
        self.spn_dt.setSuffix(" s")
        self.spn_dt.setEnabled(False)
        self.chk_resample.toggled.connect(self.spn_dt.setEnabled)
        s3.addWidget(self.spn_dt, 1, 1)

        self.chk_keep_extras = QCheckBox("Keep unmapped numeric columns as extras")
        s3.addWidget(self.chk_keep_extras, 2, 0, 1, 2)

        root.addWidget(step3)

        # ---- Step 4: preview / summary ----
        step4 = QGroupBox("4. Preview & validation")
        s4 = QVBoxLayout(step4)
        self.preview_table = QTableWidget(0, 0)
        self.preview_table.setMaximumHeight(180)
        s4.addWidget(self.preview_table, 2)

        self.txt_summary = QPlainTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setMaximumHeight(140)
        self.txt_summary.setStyleSheet("font-family:Consolas,monospace;font-size:9pt;")
        s4.addWidget(self.txt_summary, 1)

        action_row = QHBoxLayout()
        self.btn_validate = QPushButton("Validate Mapping")
        self.btn_validate.clicked.connect(self._on_validate)
        action_row.addWidget(self.btn_validate)
        action_row.addStretch()
        s4.addLayout(action_row)
        root.addWidget(step4, 2)

        # ---- Footer: save / cancel ----
        foot = QDialogButtonBox()
        self.btn_import = foot.addButton("Import && Save Capsule", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_cancel = foot.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.btn_import.clicked.connect(self._on_import)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_import.setEnabled(False)
        root.addWidget(foot)

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------
    def _on_browse(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select data file", self.start_dir,
            "Data files (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls)",
        )
        if not fname:
            return
        self._filepath = fname
        self.ed_path.setText(fname)

        # If Excel, populate sheet list first
        ext = os.path.splitext(fname)[1].lower()
        if ext in (".xlsx", ".xls"):
            sheets = DataImporter.list_excel_sheets(fname)
            self._sheet_names = sheets
            self.cb_sheet.clear()
            self.cb_sheet.addItems(sheets)
            self.cb_sheet.setVisible(True)
            # loading preview happens via _on_sheet_changed
            if sheets:
                self.cb_sheet.setCurrentIndex(0)  # triggers preview load
            else:
                self._load_preview()
        else:
            self.cb_sheet.setVisible(False)
            self._sheet_names = []
            self._load_preview()

    def _on_sheet_changed(self, _text: str):
        if self._filepath:
            self._load_preview()

    def _load_preview(self):
        try:
            sheet = self.cb_sheet.currentText() if self.cb_sheet.isVisible() else None
            preview = DataImporter.preview(self._filepath, sheet_name=sheet, n_rows=8)
        except Exception as e:
            QMessageBox.critical(self, "Preview failed", f"Could not read file:\n{e}")
            return

        self._columns = preview["columns"]
        self._preview_rows = preview["head"]
        self._suggested_map = preview["suggested_mapping"]
        self._suggested_time_unit = preview.get("suggested_time_unit", "s")

        # populate mapping combos
        for key, cb in self._mapping_combos.items():
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("(none)")
            for c in self._columns:
                cb.addItem(c)
            # pre-select suggested
            suggested = self._suggested_map.get(key)
            if suggested and suggested in self._columns:
                cb.setCurrentText(suggested)
            else:
                cb.setCurrentText("(none)")
            cb.blockSignals(False)

        # Default time unit to detected
        self.cb_time_unit.setCurrentText("auto")

        # populate preview table
        cols = self._columns
        rows = self._preview_rows
        self.preview_table.setRowCount(len(rows))
        self.preview_table.setColumnCount(len(cols))
        self.preview_table.setHorizontalHeaderLabels(cols)
        for r, row in enumerate(rows):
            for c, col in enumerate(cols):
                val = row.get(col, "")
                self.preview_table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
        self.preview_table.resizeColumnsToContents()

        self._update_mapping_status()
        self._on_validate()  # auto-run validation summary

    def _update_mapping_status(self, *_):
        # Third column: tick / dash based on selection
        for r in range(self.map_table.rowCount()):
            label_item = self.map_table.item(r, 0)
            if not label_item:
                continue
            key = label_item.text().replace("  *", "").strip()
            cb: QComboBox = self._mapping_combos.get(key)
            if cb is None:
                continue
            selected = cb.currentText()
            status_item = self.map_table.item(r, 2)
            if selected == "(none)":
                if key in REQUIRED_MAPPINGS:
                    status_item.setText("REQUIRED")
                    status_item.setForeground(Qt.GlobalColor.red)
                elif key in STRONGLY_RECOMMENDED:
                    status_item.setText("recommended")
                    status_item.setForeground(Qt.GlobalColor.darkYellow)
                else:
                    status_item.setText("optional")
                    status_item.setForeground(Qt.GlobalColor.gray)
            else:
                status_item.setText("mapped")
                status_item.setForeground(Qt.GlobalColor.darkGreen)

        # enable import only if time column mapped
        ts_cb = self._mapping_combos.get("ts")
        if ts_cb and ts_cb.currentText() != "(none)":
            self.btn_import.setEnabled(True)
        else:
            self.btn_import.setEnabled(False)

    def _collect_mapping(self) -> Dict[str, str]:
        m: Dict[str, str] = {}
        for key, cb in self._mapping_combos.items():
            val = cb.currentText()
            if val and val != "(none)":
                m[key] = val
        return m

    def _collect_options(self) -> Dict:
        opts: Dict = {
            "time_unit": self.cb_time_unit.currentText(),
            "keep_extras": self.chk_keep_extras.isChecked(),
        }
        if self.chk_resample.isChecked():
            opts["resample"] = float(self.spn_dt.value())
        return opts

    # ------------------------------------------------------------------
    # Validate / Import
    # ------------------------------------------------------------------

    # Maximum number of rows used for the live validation preview.
    # Large Rigol CSV files (1 M+ rows) must NOT be fully loaded in the
    # UI thread — we only need a representative sample to check whether
    # the mapping is structurally valid.
    _VALIDATE_PREVIEW_ROWS = 2_000

    def _on_validate(self):
        if not self._filepath:
            self.txt_summary.setPlainText("Select a file first.")
            return

        mapping = self._collect_mapping()
        if "ts" not in mapping:
            self.txt_summary.setPlainText(
                "⚠ Time column not mapped.\n"
                "The importer needs a numeric time column (seconds or ms).\n"
                "Map the 'ts' row to the appropriate source column."
            )
            self._capsule = None
            return

        try:
            sheet = self.cb_sheet.currentText() if self.cb_sheet.isVisible() else None
            options = self._collect_options()
            # Use a row-limited sample so the UI does not freeze on large CSV
            # files.  The sample capsule is only used to populate the summary
            # text; the full import happens later in _on_import().
            sample_options = dict(options)
            if sheet is not None:
                capsule = DataImporter.import_excel(
                    self._filepath, sheet_name=sheet,
                    column_map=mapping, options=sample_options,
                )
            else:
                capsule = DataImporter.import_csv(
                    self._filepath, column_map=mapping,
                    options=sample_options,
                    max_rows=self._VALIDATE_PREVIEW_ROWS,
                )
        except Exception as e:
            self.txt_summary.setPlainText(f"✖ Import would fail:\n{e}")
            self._capsule = None
            return

        # Store the validated mapping/options so _on_import can rebuild with
        # the full dataset.  Do NOT store the row-limited capsule as the final
        # output — it is only used for the summary text below.
        self._validated_mapping = mapping
        self._validated_options = options
        self._capsule = capsule  # preview only; overwritten in _on_import

        meta_imp = capsule["meta"].get("import", {})
        n_preview = capsule["meta"]["frame_count"]
        dur = capsule["meta"]["duration_s"]
        missing = meta_imp.get("missing_channels", [])
        warns = meta_imp.get("warnings", [])
        resample = meta_imp.get("resample")

        # Estimate total frames from preview row count
        preview_note = (
            f" (preview of first {n_preview:,} rows — full file imported on save)"
            if n_preview >= self._VALIDATE_PREVIEW_ROWS else ""
        )

        lines = [
            f"✔  Mapping validated{preview_note}.",
            f"   Duration (preview): {dur:.3f} s",
            f"   Time unit used: {meta_imp.get('time_unit_detected', '?')}",
        ]
        if resample:
            lines.append(
                f"   Resampled to dt={resample['target_dt_s']:.6g} s "
                f"({resample['original_frames']} -> {resample['resampled_frames']} frames)"
            )
        lines.append("")
        lines.append("Column map:")
        for k, v in mapping.items():
            lines.append(f"   {k:<8} <-  {v}")
        if missing:
            lines.append("")
            lines.append("Missing channels (filled with 0.0):")
            lines.append("   " + ", ".join(missing))
        if warns:
            lines.append("")
            lines.append("Warnings:")
            for w in warns:
                lines.append(f"   • {w}")

        self.txt_summary.setPlainText("\n".join(lines))

    def _on_import(self):
        # Re-run validation to confirm mapping is still coherent and to
        # populate self._validated_mapping / self._validated_options.
        self._on_validate()
        if self._capsule is None:
            QMessageBox.warning(self, "Cannot import", "Fix the validation errors first.")
            return

        mapping = getattr(self, "_validated_mapping", self._collect_mapping())
        options = getattr(self, "_validated_options", self._collect_options())
        sheet = self.cb_sheet.currentText() if self.cb_sheet.isVisible() else None

        # Derive a sensible default output filename from the source file.
        import os as _os
        src_stem = _os.path.splitext(_os.path.basename(self._filepath))[0]
        default_name = src_stem + ".json"
        default_dir = _os.path.join(_os.getcwd(), "data", "sessions")
        _os.makedirs(default_dir, exist_ok=True)

        fname, _ = QFileDialog.getSaveFileName(
            self, "Save Session Capsule",
            _os.path.join(default_dir, default_name),
            "JSON Session (*.json)",
        )
        if not fname:
            return

        # Perform the FULL import now (not the row-limited preview).
        try:
            if sheet is not None:
                full_capsule = DataImporter.import_excel(
                    self._filepath, sheet_name=sheet,
                    column_map=mapping, options=options,
                )
            else:
                full_capsule = DataImporter.import_csv(
                    self._filepath, column_map=mapping, options=options,
                )
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return

        try:
            self.saved_capsule_path = DataImporter.save_capsule(full_capsule, fname)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return

        QMessageBox.information(
            self, "Import complete",
            f"Saved normalized capsule to:\n{self.saved_capsule_path}",
        )
        self.accept()
