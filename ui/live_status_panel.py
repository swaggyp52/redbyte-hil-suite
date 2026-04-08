"""
LiveStatusPanel — compact one-line status bar for live telemetry.

Shows:  [SOURCE badge]  fps  •  active channels  •  last-frame age  •  warnings

Updates whenever SerialManager emits ``live_stats_updated``.
Displayed in DiagnosticsPage above the SystemHealthCard during live/demo sessions.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer

from src.serial_reader import LiveStats


_BADGE_STYLES = {
    "DEMO":        "background:#7c3aed; color:#fff;",
    "SERIAL":      "background:#0891b2; color:#fff;",
    "OPAL-RT":     "background:#047857; color:#fff;",
    "disconnected":"background:#374151; color:#9ca3af;",
}
_WARNING_COLOR = "#f59e0b"
_CONNECTED_COLOR = "#10b981"
_NEUTRAL_COLOR = "#94a3b8"
_MAX_CHANNELS_SHOWN = 8


class LiveStatusPanel(QWidget):
    """Compact one-line live telemetry status bar.

    Wire it up::

        panel.update_stats(serial_mgr.get_live_stats())
        serial_mgr.live_stats_updated.connect(panel.update_stats)
        serial_mgr.connection_status.connect(panel.set_connected)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LiveStatusPanel")
        self.setFixedHeight(30)
        self._build()
        self._stale_timer = QTimer(self)
        self._stale_timer.setInterval(2000)
        self._stale_timer.timeout.connect(self._check_stale)
        self._last_stats: LiveStats | None = None

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(12)

        self._badge = QLabel("—")
        self._badge.setObjectName("LiveBadge")
        self._badge.setFixedHeight(20)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            "border-radius:3px; padding:0 6px; font-size:10px; font-weight:700; "
            + _BADGE_STYLES["disconnected"]
        )
        layout.addWidget(self._badge)

        self._fps_lbl = QLabel("—")
        self._fps_lbl.setObjectName("LiveFps")
        self._fps_lbl.setStyleSheet(f"color:{_NEUTRAL_COLOR}; font-size:11px;")
        layout.addWidget(self._fps_lbl)

        sep1 = QLabel("•")
        sep1.setStyleSheet(f"color:#475569; font-size:11px;")
        layout.addWidget(sep1)

        self._ch_lbl = QLabel("no channels")
        self._ch_lbl.setObjectName("LiveChannels")
        self._ch_lbl.setStyleSheet(f"color:{_NEUTRAL_COLOR}; font-size:11px;")
        layout.addWidget(self._ch_lbl)

        self._age_lbl = QLabel("")
        self._age_lbl.setObjectName("LiveAge")
        self._age_lbl.setStyleSheet(f"color:{_NEUTRAL_COLOR}; font-size:11px;")
        layout.addWidget(self._age_lbl)

        self._warn_lbl = QLabel("")
        self._warn_lbl.setObjectName("LiveWarnings")
        self._warn_lbl.setStyleSheet(f"color:{_WARNING_COLOR}; font-size:11px;")
        layout.addWidget(self._warn_lbl)

        layout.addStretch()

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def set_connected(self, connected: bool, source: str) -> None:
        """Called by serial_mgr.connection_status signal."""
        if connected:
            source_key = source if source in ("MOCK", "OPAL") else "SERIAL"
            label_map = {"MOCK": "DEMO", "OPAL": "OPAL-RT"}
            label = label_map.get(source_key, f"SERIAL:{source}")
            style_key = label_map.get(source_key, "SERIAL")
            style = _BADGE_STYLES.get(style_key, _BADGE_STYLES["SERIAL"])
            self._badge.setText(label)
            self._badge.setStyleSheet(
                f"border-radius:3px; padding:0 6px; font-size:10px; font-weight:700; {style}"
            )
            self._stale_timer.start()
        else:
            self._badge.setText("DISCONNECTED")
            self._badge.setStyleSheet(
                "border-radius:3px; padding:0 6px; font-size:10px; font-weight:700; "
                + _BADGE_STYLES["disconnected"]
            )
            self._fps_lbl.setText("—")
            self._ch_lbl.setText("no channels")
            self._age_lbl.setText("")
            self._warn_lbl.setText("")
            self._stale_timer.stop()

    def update_stats(self, stats: LiveStats) -> None:
        """Slot for serial_mgr.live_stats_updated signal."""
        self._last_stats = stats

        # Badge (only update label if source changed)
        src = stats.source
        if src.startswith("SERIAL:"):
            badge_label = src
            style = _BADGE_STYLES["SERIAL"]
        elif src == "DEMO" or src == "—":
            badge_label = "DEMO" if stats.connected else "—"
            style = _BADGE_STYLES["DEMO"] if stats.connected else _BADGE_STYLES["disconnected"]
        else:
            badge_label = src
            style = _BADGE_STYLES.get(src, _BADGE_STYLES["SERIAL"])
        self._badge.setText(badge_label)
        self._badge.setStyleSheet(
            f"border-radius:3px; padding:0 6px; font-size:10px; font-weight:700; {style}"
        )

        # FPS
        if stats.fps > 0:
            self._fps_lbl.setText(f"{stats.fps:.1f} fps")
            self._fps_lbl.setStyleSheet(f"color:{_CONNECTED_COLOR}; font-size:11px;")
        else:
            self._fps_lbl.setText("— fps")
            self._fps_lbl.setStyleSheet(f"color:{_NEUTRAL_COLOR}; font-size:11px;")

        # Channels
        ch = sorted(stats.present_channels)
        if ch:
            shown = ch[:_MAX_CHANNELS_SHOWN]
            suffix = f"  +{len(ch) - _MAX_CHANNELS_SHOWN} more" if len(ch) > _MAX_CHANNELS_SHOWN else ""
            self._ch_lbl.setText("ch: " + "  ".join(shown) + suffix)
        else:
            self._ch_lbl.setText("no channels yet")

        # Warnings
        if stats.warnings:
            self._warn_lbl.setText("⚠  " + stats.warnings[0])
        else:
            self._warn_lbl.setText("")

        # Age is updated by stale timer — no need to update here

    # ──────────────────────────────────────────────────────────────
    # Stale detection
    # ──────────────────────────────────────────────────────────────

    def _check_stale(self) -> None:
        """Called every 2s to update the "last frame age" label."""
        if self._last_stats is None or not self._last_stats.connected:
            self._age_lbl.setText("")
            return
        age = self._last_stats.last_frame_age
        # Re-read from manager if needed — but we only have the snapshot here
        if age < 1.0:
            self._age_lbl.setText("")
            self._age_lbl.setStyleSheet(f"color:{_NEUTRAL_COLOR}; font-size:11px;")
        elif age < 5.0:
            self._age_lbl.setText(f"•  {age:.1f}s stale")
            self._age_lbl.setStyleSheet(f"color:{_WARNING_COLOR}; font-size:11px;")
        else:
            self._age_lbl.setText(f"•  {age:.0f}s stale — link lost?")
            self._age_lbl.setStyleSheet("color:#ef4444; font-size:11px;")
