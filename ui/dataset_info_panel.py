"""
DatasetInfoPanel: overview summary for the active imported or recorded dataset.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.session_analysis import build_dataset_overview
from src.session_state import ActiveSession


_SOURCE_COLORS: dict[str, str] = {
    "rigol_csv": "#0ea5e9",
    "simulation_excel": "#10b981",
    "data_capsule_json": "#8b5cf6",
    "live": "#f59e0b",
}
_DEFAULT_SOURCE_COLOR = "#64748b"


class DatasetInfoPanel(QFrame):
    replace_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    open_replay_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DatasetInfoPanel")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._warnings: list[str] = []
        self._warnings_expanded = False
        self._build()

    def load_session(self, session: ActiveSession) -> None:
        overview = build_dataset_overview(session.capsule)

        color = _SOURCE_COLORS.get(session.source_type, _DEFAULT_SOURCE_COLOR)
        self._badge.setText(session.source_type_display)
        self._badge.setStyleSheet(
            f"background:{color}; color:#fff; border-radius:3px; "
            "padding:1px 6px; font-size:11px; font-weight:600;"
        )

        self._filename.setText(session.source_filename)
        self._filename.setToolTip(session.source_path)

        self._set_chip(self._type_val, "File type", overview["file_type"])
        self._set_chip(self._samples_val, "Samples", session.row_count_display)
        self._set_chip(self._dur_val, "Time window", f"{overview['time_window_s']:.6f} s")
        self._set_chip(self._rate_val, "Sample rate", session.sample_rate_display)
        interval = overview.get("sample_interval_s")
        interval_text = f"{interval:.9f} s" if isinstance(interval, (int, float)) else "N/A"
        self._set_chip(self._interval_val, "Sample interval", interval_text)

        n_mapped = len(session.mapped_channels)
        n_unmapped = len(session.unmapped_channels)
        ch_parts = [f"<b>{n_mapped}</b> mapped"]
        if n_unmapped:
            ch_parts.append(f"<b>{n_unmapped}</b> unmapped")
        dead_warnings = [w for w in session.warnings if "dead or constant" in w]
        if dead_warnings:
            dead_names = []
            for warning in dead_warnings:
                parts = warning.split("'")
                if len(parts) >= 2:
                    dead_names.append(parts[1])
            ch_parts.append(
                "<span style='color:#f59e0b;'>&#x26A0; "
                f"{len(dead_names)} dead: {', '.join(dead_names)}</span>"
            )
        self._ch_label.setText("  /  ".join(ch_parts))
        if n_unmapped:
            self._ch_label.setToolTip(
                "Unmapped channels use original source names:\n"
                + "\n".join(f"  {channel}" for channel in session.unmapped_channels)
            )
        else:
            self._ch_label.setToolTip("")

        self._mode_label.setText(overview["analysis_mode_label"])
        self._mode_label.setStyleSheet(
            "color:#10b981; font-size:12px; font-weight:700;"
            if overview["analysis_mode"] == "vsm"
            else "color:#38bdf8; font-size:12px; font-weight:700;"
        )
        self._scale_label.setText(
            "Applied scale factors: "
            + self._format_scale_factors(overview.get("scale_factors", {}))
        )
        self._raw_label.setText(
            "Raw source columns: " + self._truncate_channels(overview["raw_source_columns"])
        )
        self._mapped_label.setText(
            "Canonical mapped channels: "
            + self._truncate_channels(overview["mapped_channels"], empty="none")
        )
        self._derived_label.setText(
            "Derived computed channels: "
            + self._truncate_channels(overview["derived_channels"], empty="none")
        )
        self._generic_label.setText(
            "Generic or auxiliary numeric channels: "
            + self._truncate_channels(overview["generic_numeric_channels"], empty="none")
        )
        self._missing_label.setText(
            "Missing expected VSM channels: "
            + self._truncate_channels(overview["missing_expected_channels"], empty="none")
        )

        self._warnings = session.warnings
        self._refresh_warnings()
        self.show()

    def clear(self) -> None:
        self._warnings = []
        self.hide()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self._badge = QLabel()
        self._badge.setFixedHeight(20)
        self._badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._filename = QLabel()
        self._filename.setStyleSheet("font-weight:600; font-size:13px;")
        self._filename.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        btn_open = QPushButton("Open Analysis Workspace")
        btn_open.setObjectName("PrimaryBtn")
        btn_open.setFixedHeight(24)
        btn_open.setFixedWidth(180)
        btn_open.clicked.connect(self.open_replay_requested)

        btn_replace = QPushButton("Replace")
        btn_replace.setObjectName("SecondaryBtn")
        btn_replace.setFixedHeight(24)
        btn_replace.setFixedWidth(72)
        btn_replace.clicked.connect(self.replace_requested)

        btn_clear = QPushButton("Clear")
        btn_clear.setObjectName("SecondaryBtn")
        btn_clear.setFixedHeight(24)
        btn_clear.setFixedWidth(52)
        btn_clear.clicked.connect(self.clear_requested)

        row1.addWidget(self._badge)
        row1.addWidget(self._filename, stretch=1)
        row1.addWidget(btn_open)
        row1.addWidget(btn_replace)
        row1.addWidget(btn_clear)

        row2 = QHBoxLayout()
        row2.setSpacing(18)
        self._type_val = self._chip("File type", "-")
        self._samples_val = self._chip("Samples", "-")
        self._dur_val = self._chip("Time window", "-")
        self._rate_val = self._chip("Sample rate", "-")
        self._interval_val = self._chip("Sample interval", "-")
        for chip in (
            self._type_val,
            self._samples_val,
            self._dur_val,
            self._rate_val,
            self._interval_val,
        ):
            row2.addWidget(chip)
        row2.addStretch()

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        ch_icon = QLabel("[]")
        ch_icon.setStyleSheet("color:#94a3b8; font-size:12px;")
        self._ch_label = QLabel()
        self._ch_label.setStyleSheet("font-size:12px; color:#94a3b8;")
        row3.addWidget(ch_icon)
        row3.addWidget(self._ch_label)
        row3.addStretch()

        self._mode_label = QLabel("-")
        self._mode_label.setStyleSheet("color:#cbd5e1; font-size:12px; font-weight:700;")
        self._scale_label = QLabel("Applied scale factors: none")
        self._scale_label.setWordWrap(True)
        self._scale_label.setStyleSheet("font-size:11px; color:#94a3b8;")
        self._raw_label = QLabel("Raw source columns: -")
        self._mapped_label = QLabel("Canonical mapped channels: -")
        self._derived_label = QLabel("Derived computed channels: -")
        self._generic_label = QLabel("Generic or auxiliary numeric channels: -")
        self._missing_label = QLabel("Missing expected VSM channels: -")
        for label in (
            self._raw_label,
            self._mapped_label,
            self._derived_label,
            self._generic_label,
            self._missing_label,
        ):
            label.setWordWrap(True)
            label.setStyleSheet("font-size:11px; color:#94a3b8;")

        self._warn_row = QHBoxLayout()
        self._warn_row.setSpacing(6)
        self._warn_icon = QLabel()
        self._warn_icon.setStyleSheet("font-size:12px;")
        self._warn_label = QLabel()
        self._warn_label.setStyleSheet("font-size:12px; color:#f59e0b;")
        self._warn_label.mousePressEvent = self._toggle_warnings
        self._warn_row.addWidget(self._warn_icon)
        self._warn_row.addWidget(self._warn_label)
        self._warn_row.addStretch()

        self._warn_detail = QLabel()
        self._warn_detail.setWordWrap(True)
        self._warn_detail.setStyleSheet(
            "font-size:11px; color:#94a3b8; padding-left:18px;"
        )
        self._warn_detail.hide()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#334155;")

        root.addLayout(row1)
        root.addWidget(sep)
        root.addLayout(row2)
        root.addLayout(row3)
        root.addWidget(self._mode_label)
        root.addWidget(self._scale_label)
        root.addWidget(self._raw_label)
        root.addWidget(self._mapped_label)
        root.addWidget(self._derived_label)
        root.addWidget(self._generic_label)
        root.addWidget(self._missing_label)
        root.addLayout(self._warn_row)
        root.addWidget(self._warn_detail)

        self.setStyleSheet(
            """
            DatasetInfoPanel {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QPushButton#PrimaryBtn {
                background: #0ea5e9;
                color: #fff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#PrimaryBtn:hover {
                background: #38bdf8;
            }
            QPushButton#SecondaryBtn {
                background: #334155;
                color: #cbd5e1;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton#SecondaryBtn:hover {
                background: #475569;
            }
            """
        )

    def _chip(self, label: str, value: str) -> QLabel:
        chip = QLabel(f"<span style='color:#64748b;'>{label}:</span> {value}")
        chip.setStyleSheet("font-size:12px;")
        return chip

    def _refresh_warnings(self) -> None:
        count = len(self._warnings)
        if count == 0:
            self._warn_icon.hide()
            self._warn_label.hide()
            self._warn_detail.hide()
            return

        self._warn_icon.setText("!")
        self._warn_icon.setStyleSheet("color:#f59e0b; font-size:13px; font-weight:700;")
        self._warn_icon.show()
        self._warn_label.setText(
            f"{count} warning{'s' if count != 1 else ''} - click to expand"
            if not self._warnings_expanded
            else f"{count} warning{'s' if count != 1 else ''} - click to collapse"
        )
        self._warn_label.show()

        if self._warnings_expanded:
            self._warn_detail.setText("\n".join(f"- {warning}" for warning in self._warnings))
            self._warn_detail.show()
        else:
            self._warn_detail.hide()

    def _toggle_warnings(self, _event=None) -> None:
        self._warnings_expanded = not self._warnings_expanded
        self._refresh_warnings()

    def _set_chip(self, chip_widget: QLabel, label: str, value: str) -> None:
        chip_widget.setText(f"<span style='color:#64748b;'>{label}:</span> {value}")

    @staticmethod
    def _truncate_channels(channels: list[str], *, empty: str = "N/A", limit: int = 8) -> str:
        if not channels:
            return empty
        text = ", ".join(channels[:limit])
        if len(channels) > limit:
            text += f" +{len(channels) - limit}"
        return text

    @staticmethod
    def _format_scale_factors(scale_factors: dict[str, float]) -> str:
        if not scale_factors:
            return "none"

        formatted = []
        for channel in sorted(scale_factors):
            value = float(scale_factors[channel])
            if value.is_integer():
                text = str(int(value))
            else:
                text = f"{value:.6g}"
            formatted.append(f"{channel}×{text}")
        return ", ".join(formatted)
