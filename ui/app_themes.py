"""
App-Specific Themed Stylesheets
Each RedByte app has a unique neon accent while preserving core aesthetics
"""

def get_base_style() -> str:
    """Core RedByte styling shared by all apps"""
    return """
    QMainWindow {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #0f172a,
            stop:1 #1e293b
        );
        color: #e2e8f0;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 10pt;
    }
    
    QWidget {
        background: transparent;
        color: #e2e8f0;
    }
    
    /* Glassmorphic panels */
    QMdiSubWindow {
        background: rgba(30, 41, 59, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.3);
        border-radius: 12px;
    }
    
    /* Scrollbars */
    QScrollBar:vertical {
        background: rgba(15, 23, 42, 0.6);
        width: 12px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical {
        background: rgba(100, 116, 139, 0.8);
        border-radius: 6px;
        min-height: 30px;
    }
    
    QScrollBar::handle:vertical:hover {
        background: rgba(148, 163, 184, 1.0);
    }
    """


def get_diagnostics_style() -> str:
    """RedByte Diagnostics - Green accent theme (🟩 Live Ops + Anomaly Injection)"""
    return get_base_style() + """
    /* Diagnostics Green Accent */
    QPushButton {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(16, 185, 129, 0.3),
            stop:1 rgba(5, 150, 105, 0.3)
        );
        border: 2px solid rgba(16, 185, 129, 0.6);
        border-radius: 16px;
        color: #10b981;
        font-weight: bold;
        padding: 8px 16px;
        font-size: 10pt;
    }
    
    QPushButton:hover {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(16, 185, 129, 0.5),
            stop:1 rgba(5, 150, 105, 0.5)
        );
        border-color: #10b981;
    }
    
    QPushButton:pressed {
        background: rgba(16, 185, 129, 0.7);
    }
    
    QGroupBox {
        border: 2px solid rgba(16, 185, 129, 0.4);
        border-radius: 12px;
        margin-top: 12px;
        padding: 16px;
        background: rgba(15, 23, 42, 0.5);
        font-weight: bold;
        color: #10b981;
    }
    
    QGroupBox::title {
        color: #10b981;
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        background: rgba(16, 185, 129, 0.2);
        border-radius: 8px;
    }
    
    QLabel#accent {
        color: #10b981;
        font-weight: bold;
    }
    
    QProgressBar {
        border: 2px solid rgba(16, 185, 129, 0.4);
        border-radius: 8px;
        text-align: center;
        background: rgba(15, 23, 42, 0.6);
        color: #10b981;
    }
    
    QProgressBar::chunk {
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #10b981,
            stop:1 #059669
        );
        border-radius: 6px;
    }
    """


def get_replay_style() -> str:
    """RedByte Replay Studio - Cyan accent theme (🔵 Temporal Tracing & Review)"""
    return get_base_style() + """
    /* Replay Cyan Accent */
    QPushButton {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(6, 182, 212, 0.3),
            stop:1 rgba(8, 145, 178, 0.3)
        );
        border: 2px solid rgba(6, 182, 212, 0.6);
        border-radius: 16px;
        color: #06b6d4;
        font-weight: bold;
        padding: 8px 16px;
        font-size: 10pt;
    }
    
    QPushButton:hover {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(6, 182, 212, 0.5),
            stop:1 rgba(8, 145, 178, 0.5)
        );
        border-color: #06b6d4;
    }
    
    QGroupBox {
        border: 2px solid rgba(6, 182, 212, 0.4);
        border-radius: 12px;
        margin-top: 12px;
        padding: 16px;
        background: rgba(15, 23, 42, 0.5);
        font-weight: bold;
        color: #06b6d4;
    }
    
    QGroupBox::title {
        color: #06b6d4;
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        background: rgba(6, 182, 212, 0.2);
        border-radius: 8px;
    }
    
    QLabel#accent {
        color: #06b6d4;
        font-weight: bold;
    }
    
    QSlider::groove:horizontal {
        border: 1px solid rgba(6, 182, 212, 0.4);
        height: 8px;
        background: rgba(15, 23, 42, 0.6);
        border-radius: 4px;
    }
    
    QSlider::handle:horizontal {
        background: #06b6d4;
        border: 2px solid rgba(6, 182, 212, 0.8);
        width: 20px;
        margin: -6px 0;
        border-radius: 10px;
    }
    """


def get_compliance_style() -> str:
    """RedByte Compliance Lab - Purple accent theme (🟪 Standards, Scoring & Snapshots)"""
    return get_base_style() + """
    /* Compliance Purple Accent */
    QPushButton {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(139, 92, 246, 0.3),
            stop:1 rgba(124, 58, 237, 0.3)
        );
        border: 2px solid rgba(139, 92, 246, 0.6);
        border-radius: 16px;
        color: #8b5cf6;
        font-weight: bold;
        padding: 8px 16px;
        font-size: 10pt;
    }
    
    QPushButton:hover {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(139, 92, 246, 0.5),
            stop:1 rgba(124, 58, 237, 0.5)
        );
        border-color: #8b5cf6;
    }
    
    QGroupBox {
        border: 2px solid rgba(139, 92, 246, 0.4);
        border-radius: 12px;
        margin-top: 12px;
        padding: 16px;
        background: rgba(15, 23, 42, 0.5);
        font-weight: bold;
        color: #8b5cf6;
    }
    
    QGroupBox::title {
        color: #8b5cf6;
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        background: rgba(139, 92, 246, 0.2);
        border-radius: 8px;
    }
    
    QLabel#accent {
        color: #8b5cf6;
        font-weight: bold;
    }
    
    QTableWidget {
        border: 2px solid rgba(139, 92, 246, 0.4);
        border-radius: 8px;
        background: rgba(15, 23, 42, 0.6);
        gridline-color: rgba(139, 92, 246, 0.2);
    }
    
    QHeaderView::section {
        background: rgba(139, 92, 246, 0.3);
        color: #8b5cf6;
        border: none;
        padding: 8px;
        font-weight: bold;
    }
    """


def get_insights_style() -> str:
    """RedByte Insight Studio - Amber accent theme (🟨 AI Cognitive Insight Layers)"""
    return get_base_style() + """
    /* Insights Amber Accent */
    QPushButton {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(245, 158, 11, 0.3),
            stop:1 rgba(217, 119, 6, 0.3)
        );
        border: 2px solid rgba(245, 158, 11, 0.6);
        border-radius: 16px;
        color: #f59e0b;
        font-weight: bold;
        padding: 8px 16px;
        font-size: 10pt;
    }
    
    QPushButton:hover {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(245, 158, 11, 0.5),
            stop:1 rgba(217, 119, 6, 0.5)
        );
        border-color: #f59e0b;
    }
    
    QGroupBox {
        border: 2px solid rgba(245, 158, 11, 0.4);
        border-radius: 12px;
        margin-top: 12px;
        padding: 16px;
        background: rgba(15, 23, 42, 0.5);
        font-weight: bold;
        color: #f59e0b;
    }
    
    QGroupBox::title {
        color: #f59e0b;
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        background: rgba(245, 158, 11, 0.2);
        border-radius: 8px;
    }
    
    QLabel#accent {
        color: #f59e0b;
        font-weight: bold;
    }
    
    QTreeWidget {
        border: 2px solid rgba(245, 158, 11, 0.4);
        border-radius: 8px;
        background: rgba(15, 23, 42, 0.6);
    }
    
    QTreeWidget::item:selected {
        background: rgba(245, 158, 11, 0.3);
        color: #f59e0b;
    }
    """


def get_sculptor_style() -> str:
    """RedByte Signal Sculptor - Orange accent theme (🟧 Live Waveform Editing)"""
    return get_base_style() + """
    /* Sculptor Orange Accent */
    QPushButton {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(249, 115, 22, 0.3),
            stop:1 rgba(234, 88, 12, 0.3)
        );
        border: 2px solid rgba(249, 115, 22, 0.6);
        border-radius: 16px;
        color: #f97316;
        font-weight: bold;
        padding: 8px 16px;
        font-size: 10pt;
    }
    
    QPushButton:hover {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(249, 115, 22, 0.5),
            stop:1 rgba(234, 88, 12, 0.5)
        );
        border-color: #f97316;
    }
    
    QGroupBox {
        border: 2px solid rgba(249, 115, 22, 0.4);
        border-radius: 12px;
        margin-top: 12px;
        padding: 16px;
        background: rgba(15, 23, 42, 0.5);
        font-weight: bold;
        color: #f97316;
    }
    
    QGroupBox::title {
        color: #f97316;
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 4px 12px;
        background: rgba(249, 115, 22, 0.2);
        border-radius: 8px;
    }
    
    QLabel#accent {
        color: #f97316;
        font-weight: bold;
    }
    
    QDial {
        background: rgba(15, 23, 42, 0.6);
    }
    
    QDial::handle {
        background: #f97316;
        border: 2px solid rgba(249, 115, 22, 0.8);
        border-radius: 8px;
    }
    """


# Accent color mapping for quick reference
APP_ACCENTS = {
    'diagnostics': '#10b981',  # Green
    'replay': '#06b6d4',       # Cyan
    'compliance': '#8b5cf6',   # Purple
    'insights': '#f59e0b',     # Amber
    'sculptor': '#f97316'      # Orange
}
