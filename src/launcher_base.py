"""
RedByte LauncherBase - Shared base class for all modular launcher windows.

Provides:
- Geometry persistence (panel position tracking across layout changes)
- Overlay notifications (fade-out messages)
- Help overlay (conditional first-run tips)
- Status bar with live metrics
- Context export/import toolbar actions
- --mock CLI argument support
- Per-panel tooltip application
"""

import sys
import os
import time
import argparse
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QMdiArea, QMdiSubWindow, QToolBar, QFileDialog,
    QStatusBar
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QAction

from hil_core import SessionContext
from ui.overlay import OverlayMessage
from ui.help_overlay import HelpOverlay


class LauncherBase(QMainWindow):
    """
    Base class for all RedByte launcher windows.

    Subclasses must implement:
        - create_panels(): Create and add MDI sub-windows
        - create_toolbar(): Build app-specific toolbar actions

    Subclasses may override:
        - app_name: str property identifying this launcher
        - get_exportable_apps(): list of target app names for export
    """

    app_name: str = "base"

    def __init__(self):
        super().__init__()

        # --- Geometry persistence state ---
        self.saved_geometries = {}
        self.user_moved_panels = set()
        self.last_auto_pin_time = {}
        self._layout_locked = False
        self._initializing = True

        # --- MDI area ---
        self.mdi = QMdiArea()
        self.mdi.setViewMode(QMdiArea.ViewMode.SubWindowView)
        self.setCentralWidget(self.mdi)

        # --- Overlay messages ---
        self.overlay = OverlayMessage(self)

        # --- Help overlay (hidden by default) ---
        self.help_overlay = HelpOverlay(self)
        self.help_overlay.hide()

        # --- Session context ---
        self.session = SessionContext()

    # ------------------------------------------------------------------
    # Geometry persistence
    # ------------------------------------------------------------------

    def _register_subwindow(self, sub: QMdiSubWindow):
        """Install event filter on a sub-window for geometry tracking."""
        sub.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Track user-initiated panel movements."""
        if (
            isinstance(obj, QMdiSubWindow)
            and event.type() == QEvent.Type.Move
            and not self._layout_locked
            and not self._initializing
        ):
            title = obj.windowTitle()
            self.user_moved_panels.add(title)
            self.saved_geometries[title] = obj.geometry()
        return super().eventFilter(obj, event)

    def _apply_geometry_if_not_moved(self, widget, x, y, w, h):
        """Apply geometry only if the panel hasn't been manually positioned."""
        parent = widget.parent()
        if parent is None:
            return
        title = parent.windowTitle()
        if title in self.user_moved_panels and title in self.saved_geometries:
            parent.setGeometry(self.saved_geometries[title])
        else:
            parent.setGeometry(int(x), int(y), int(w), int(h))

    def _finish_init(self):
        """Call at the end of subclass __init__ to finalize setup."""
        self._initializing = False

    # ------------------------------------------------------------------
    # Overlay notifications
    # ------------------------------------------------------------------

    def notify(self, text: str, color: str = "#38bdf8"):
        """Show a brief overlay notification."""
        self.overlay.show_message(text, color, (10, 10))

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------

    def _setup_status_bar(self, serial_mgr=None):
        """Set up a status bar with optional live metrics widget."""
        self.statusBar().showMessage(f"Ready - {self.windowTitle()}")
        if serial_mgr is not None:
            try:
                from ui.status_bar import StatusBarWidget
                self.status_widget = StatusBarWidget(serial_mgr)
                self.statusBar().addPermanentWidget(self.status_widget)
            except Exception:
                self.status_widget = None
        else:
            self.status_widget = None

    # ------------------------------------------------------------------
    # Tooltips
    # ------------------------------------------------------------------

    def _apply_panel_tooltips(self):
        """Apply per-panel tooltips for whichever panels exist."""
        try:
            from ui.tooltip_manager import (
                apply_tooltips_to_scope,
                apply_tooltips_to_phasor,
                apply_tooltips_to_injector,
                apply_tooltips_to_insights,
                apply_tooltips_to_dashboard,
            )
            if hasattr(self, "scope"):
                apply_tooltips_to_scope(self.scope)
            if hasattr(self, "phasor"):
                apply_tooltips_to_phasor(self.phasor)
            if hasattr(self, "phasor_view"):
                apply_tooltips_to_phasor(self.phasor_view)
            if hasattr(self, "injector"):
                apply_tooltips_to_injector(self.injector)
            if hasattr(self, "insights"):
                apply_tooltips_to_insights(self.insights)
            if hasattr(self, "dashboard"):
                apply_tooltips_to_dashboard(self.dashboard)
        except Exception:
            pass  # Tooltips are non-critical

    # ------------------------------------------------------------------
    # Context export / import
    # ------------------------------------------------------------------

    def _add_context_actions(self, toolbar: QToolBar):
        """Add Export Context / Load Context buttons to a toolbar."""
        toolbar.addSeparator()

        act_export = QAction("📤 Export Context", self)
        act_export.setToolTip("Export current session context to a file")
        act_export.triggered.connect(self._export_context)
        toolbar.addAction(act_export)

        act_import = QAction("📥 Load Context", self)
        act_import.setToolTip("Load session context from a file")
        act_import.triggered.connect(self._import_context)
        toolbar.addAction(act_import)

    def _export_context(self):
        """Export current session context to a user-chosen file."""
        import shutil

        # First export to temp
        temp_path = self.session.export_context(self.app_name)

        # Let user choose destination
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Context",
            str(Path.home() / "Downloads" / f"redbyte_session_{self.app_name}.json"),
            "JSON Files (*.json)",
        )
        if save_path:
            shutil.copy(str(temp_path), save_path)
            self.notify(f"Exported to {Path(save_path).name}")
            self.statusBar().showMessage(f"Exported context to {save_path}")

    def _import_context(self):
        """Import session context from a user-chosen file."""
        import shutil

        open_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Context",
            str(Path.home() / "Downloads"),
            "JSON Files (*.json)",
        )
        if open_path:
            # Copy to temp with a known name so import_context can find it
            dest = self.session.temp_dir / "redbyte_session_imported.json"
            shutil.copy(open_path, str(dest))
            if self.session.import_context("imported"):
                self.notify("Context loaded successfully", "#10b981")
                self.statusBar().showMessage(f"Loaded context from {open_path}")
                self._on_context_loaded()
            else:
                self.notify("Failed to load context", "#ef4444")

    def _on_context_loaded(self):
        """Hook for subclasses to refresh UI after context import."""
        pass

    # ------------------------------------------------------------------
    # CLI argument parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_args():
        """Parse common CLI arguments for all launchers."""
        parser = argparse.ArgumentParser(description="RedByte Launcher")
        parser.add_argument(
            "--mock", action="store_true",
            help="Start in mock/demo mode (no real hardware)"
        )
        parser.add_argument(
            "--load", type=str, default=None,
            help="Path to a context JSON file to auto-load on startup"
        )
        return parser.parse_args()
