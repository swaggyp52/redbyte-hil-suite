from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QGroupBox, QFrame)
from PyQt6.QtCore import pyqtSlot, Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QBrush, QFont
import time


class InsightsPanel(QWidget):
    """Enhanced insights panel with event clusters, rich icons, and collapsible groups.

    Two modes:
      1. Live mode: receives individual insight dicts via add_insight()
      2. Summary mode: receives a batch of DetectedEvent objects via
         load_event_summary() and shows a compact analysis overview.
    """
    
    INSIGHT_ICONS = {
        "harmonic": "⚡",
        "bloom": "⚡",
        "thd": "🎯",
        "unbalance": "⚖️",
        "phase": "⚖️",
        "frequency": "📊",
        "undershoot": "📉",
        "recovery": "🔄",
        "fault": "💥",
        "voltage_sag": "📉",
        "voltage_swell": "📈",
        "step_change": "⚡",
        "flatline": "▬",
        "clipping": "📏",
        "duplicate_channel": "🔗",
        "thd_spike": "🎯",
        "freq_excursion": "📊",
        "default": "ℹ️"
    }
    
    INSIGHT_COLORS = {
        "harmonic": "#f59e0b",
        "bloom": "#f59e0b",
        "thd": "#3b82f6",
        "unbalance": "#ef4444",
        "phase": "#ef4444",
        "frequency": "#8b5cf6",
        "undershoot": "#ec4899",
        "recovery": "#10b981",
        "fault": "#dc2626",
        "voltage_sag": "#ef4444",
        "voltage_swell": "#f59e0b",
        "step_change": "#f97316",
        "flatline": "#64748b",
        "clipping": "#a78bfa",
        "duplicate_channel": "#6366f1",
        "thd_spike": "#3b82f6",
        "freq_excursion": "#8b5cf6",
        "default": "#64748b"
    }
    
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)
        
        header = QLabel("Insights")
        header.setStyleSheet("font-size: 12pt; font-weight: 700; color: #10b981;")
        self.layout.addWidget(header)

        # Summary frame (populated by load_event_summary)
        self._summary_frame = QFrame()
        self._summary_frame.setStyleSheet(
            "QFrame { background: #0d1117; border: 1px solid #1e293b; "
            "border-radius: 6px; padding: 4px; }"
        )
        self._summary_layout = QVBoxLayout(self._summary_frame)
        self._summary_layout.setContentsMargins(8, 8, 8, 8)
        self._summary_layout.setSpacing(4)
        self._summary_frame.setVisible(False)
        self.layout.addWidget(self._summary_frame)
        
        # Control buttons
        ctrl_layout = QHBoxLayout()
        self.btn_expand_all = QPushButton("Expand All")
        self.btn_expand_all.clicked.connect(self._expand_all)
        self.btn_collapse_all = QPushButton("Collapse All")
        self.btn_collapse_all.clicked.connect(self._collapse_all)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear_insights)
        
        ctrl_layout.addWidget(self.btn_expand_all)
        ctrl_layout.addWidget(self.btn_collapse_all)
        ctrl_layout.addWidget(self.btn_clear)
        ctrl_layout.addStretch()
        self.layout.addLayout(ctrl_layout)
        
        # Tree widget for clustered insights
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Event Clusters"])
        self.tree.setStyleSheet("""
            QTreeWidget {
                background: rgba(15, 17, 21, 200);
                border: 1px solid rgba(31, 41, 55, 120);
                border-radius: 10px;
                font-size: 9pt;
            }
            QTreeWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QTreeWidget::item:selected {
                background: rgba(16, 185, 129, 150);
                color: #ffffff;
            }
            QTreeWidget::item:hover {
                background: rgba(59, 130, 246, 100);
            }
        """)
        self.tree.setAnimated(True)
        self.layout.addWidget(self.tree)
        
        # Summary label
        self.summary = QLabel("No events analyzed yet")
        self.summary.setStyleSheet("font-size: 9pt; color: #94a3b8; font-weight: 600;")
        self.layout.addWidget(self.summary)
        
        # Event clusters (by type)
        self.clusters = {}
        self.insight_count = 0
        self.critical_count = 0

    # ── Summary mode (batch events from detection) ────────────────────

    def load_event_summary(self, events) -> None:
        """Show a compact analysis summary from detected events.

        Args:
            events: list of DetectedEvent objects from the event detector.
        """
        self._clear_insights()

        if not events:
            self._show_clean_bill()
            return

        # Build summary
        n_crit = sum(1 for e in events if e.severity == "critical")
        n_warn = sum(1 for e in events if e.severity == "warning")
        n_info = sum(1 for e in events if e.severity == "info")

        # Populate summary frame
        self._clear_summary_frame()
        if n_crit > 0:
            self._add_summary_line(
                f"⚠ {n_crit} critical issue{'s' if n_crit != 1 else ''}",
                "#ef4444",
            )
        if n_warn > 0:
            self._add_summary_line(
                f"△ {n_warn} warning{'s' if n_warn != 1 else ''}",
                "#f59e0b",
            )
        if n_info > 0:
            self._add_summary_line(
                f"ℹ {n_info} informational",
                "#64748b",
            )

        # Group events by kind
        by_kind: dict[str, list] = {}
        for e in events:
            by_kind.setdefault(e.kind, []).append(e)

        # Top finding
        if n_crit > 0:
            worst = next(e for e in events if e.severity == "critical")
            self._add_summary_line(
                f"Worst: {worst.description[:80]}",
                "#fca5a5",
            )
        elif n_warn > 0:
            worst = next(e for e in events if e.severity == "warning")
            self._add_summary_line(
                f"Note: {worst.description[:80]}",
                "#fcd34d",
            )

        # Affected channels
        channels = sorted({e.channel for e in events})
        if channels:
            ch_str = ", ".join(channels[:6])
            if len(channels) > 6:
                ch_str += f" (+{len(channels)-6})"
            self._add_summary_line(f"Channels: {ch_str}", "#94a3b8")

        self._summary_frame.setVisible(True)

        # Populate tree with event clusters
        for kind, kind_events in sorted(by_kind.items()):
            for evt in kind_events:
                self.add_insight(evt.to_dict())

        self.summary.setText(
            f"{len(events)} events  |  {n_crit} critical  |  {n_warn} warnings"
        )
        if n_crit > 0:
            self.summary.setStyleSheet(
                "font-size: 9pt; color: #ef4444; font-weight: 700;"
                "background: rgba(239,68,68,30); border-radius: 6px; padding: 4px 8px;"
            )
        elif n_warn > 0:
            self.summary.setStyleSheet(
                "font-size: 9pt; color: #f59e0b; font-weight: 700;"
            )

    def _show_clean_bill(self) -> None:
        """Show a positive 'no issues' summary when event detection finds nothing."""
        self._clear_summary_frame()
        self._add_summary_line("✓ No anomalies detected", "#10b981")
        self._add_summary_line("Signal quality looks good", "#64748b")
        self._summary_frame.setVisible(True)
        self.summary.setText("Clean — no issues found")
        self.summary.setStyleSheet(
            "font-size: 9pt; color: #10b981; font-weight: 700;"
        )

    def _clear_summary_frame(self) -> None:
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_summary_line(self, text: str, color: str) -> None:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 600;")
        self._summary_layout.addWidget(lbl)
    
    def _get_icon(self, insight_type):
        """Get emoji icon for insight type"""
        insight_lower = insight_type.lower()
        for key, icon in self.INSIGHT_ICONS.items():
            if key in insight_lower:
                return icon
        return self.INSIGHT_ICONS["default"]
    
    def _get_color(self, insight_type):
        """Get color for insight type"""
        insight_lower = insight_type.lower()
        for key, color in self.INSIGHT_COLORS.items():
            if key in insight_lower:
                return color
        return self.INSIGHT_COLORS["default"]
    
    @pyqtSlot(dict)
    def add_insight(self, payload):
        ts = payload.get("ts", 0)
        kind = payload.get("type", "Insight")
        desc = payload.get("description", "")
        severity = payload.get("severity", "info")  # info, warning, critical
        
        self.insight_count += 1
        if severity == "critical" or "fault" in kind.lower() or "unbalance" in kind.lower():
            self.critical_count += 1
        
        # Get or create cluster for this insight type
        if kind not in self.clusters:
            cluster = QTreeWidgetItem(self.tree)
            icon = self._get_icon(kind)
            color = self._get_color(kind)
            cluster.setText(0, f"{icon} {kind} Events (0)")
            cluster.setForeground(0, QBrush(QColor(color)))
            font = QFont()
            font.setBold(True)
            font.setPointSize(10)
            cluster.setFont(0, font)
            self.clusters[kind] = {"item": cluster, "count": 0, "icon": icon, "color": color}
        
        # Add event to cluster
        cluster_data = self.clusters[kind]
        event_item = QTreeWidgetItem(cluster_data["item"])
        event_item.setText(0, f"  t={ts:.2f}s — {desc}")
        event_item.setForeground(0, QBrush(QColor("#cbd5e1")))
        
        # Update cluster count
        cluster_data["count"] += 1
        cluster_data["item"].setText(0, f"{cluster_data['icon']} {kind} Events ({cluster_data['count']})")
        
        # Auto-expand new clusters
        cluster_data["item"].setExpanded(True)
        
        # Keep only last 100 events per cluster
        if cluster_data["item"].childCount() > 100:
            cluster_data["item"].removeChild(cluster_data["item"].child(0))
        
        # Update summary
        self.summary.setText(f"Total Events: {self.insight_count} | Critical: {self.critical_count}")
        
        # Highlight critical events with glow
        if severity == "critical" or self.critical_count > 0:
            self.summary.setStyleSheet("""
                font-size: 9pt; 
                color: #ef4444; 
                font-weight: 700;
                background: rgba(239, 68, 68, 30);
                border-radius: 6px;
                padding: 4px 8px;
            """)
    
    def _expand_all(self):
        self.tree.expandAll()
    
    def _collapse_all(self):
        self.tree.collapseAll()
    
    def _clear_insights(self):
        self.tree.clear()
        self.clusters.clear()
        self.insight_count = 0
        self.critical_count = 0
        self._clear_summary_frame()
        self._summary_frame.setVisible(False)
        self.summary.setText("No events analyzed yet")
        self.summary.setStyleSheet("font-size: 9pt; color: #94a3b8; font-weight: 600;")
