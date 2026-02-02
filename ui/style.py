def get_global_stylesheet():
    """RedByte cyber-industrial premium stylesheet with glassmorphic effects and neon accents"""
    return """
    /* === GLOBAL BASE === */
    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #0a0e1a, stop:0.5 #0f1419, stop:1 #141921);
        color: #e8eef5;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Courier New', monospace;
        font-size: 9pt;
    }
    QWidget {
        color: #e8eef5;
        selection-background-color: #10b981;
        selection-color: #ffffff;
    }
    
    /* === TOOLBAR === */
    QToolBar {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #181f2e, stop:1 #0d1219);
        spacing: 8px;
        padding: 8px 12px;
        border: none;
        border-bottom: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 #10b981, stop:0.5 #3b82f6, stop:1 #8b5cf6);
    }
    QToolBar QLabel {
        color: #94a3b8;
        font-weight: 600;
        font-size: 9pt;
        padding: 0 8px;
    }
    
    /* === STATUS BAR === */
    QStatusBar {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #0d1219, stop:1 #181f2e);
        color: #cbd5e1;
        border-top: 2px solid #1a2332;
        font-size: 9pt;
    }
    
    /* === PILL-SHAPED GLASSMORPHIC BUTTONS === */
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(30, 41, 59, 180), 
                                    stop:1 rgba(15, 23, 42, 200));
        border: 1px solid rgba(71, 85, 105, 80);
        border-radius: 16px;
        padding: 7px 16px;
        color: #cbd5e1;
        font-weight: 600;
        font-size: 9pt;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(51, 65, 85, 200), 
                                    stop:1 rgba(30, 41, 59, 220));
        border: 1px solid rgba(100, 116, 139, 120);
        color: #10b981;
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(15, 23, 42, 220), 
                                    stop:1 rgba(30, 41, 59, 240));
        border: 1px solid rgba(16, 185, 129, 180);
    }
    QPushButton:checked {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(16, 185, 129, 180), 
                                    stop:1 rgba(5, 150, 105, 200));
        border: 2px solid #10b981;
        color: #ffffff;
    }
    QPushButton:disabled {
        background: rgba(30, 41, 59, 100);
        border: 1px solid rgba(71, 85, 105, 40);
        color: #475569;
    }
    
    /* === ROUNDED CARDS (GROUP BOXES) === */
    QGroupBox {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(17, 24, 39, 200), 
                                    stop:1 rgba(15, 23, 42, 180));
        border: 1px solid rgba(31, 41, 55, 150);
        border-radius: 12px;
        margin-top: 16px;
        padding: 12px;
        font-weight: 600;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 16px;
        padding: 2px 10px;
        color: #10b981;
        font-weight: 700;
        font-size: 10pt;
        background: rgba(16, 185, 129, 30);
        border-radius: 8px;
    }
    
    /* === TABS WITH NEON ACCENT === */
    QTabWidget::pane {
        background: rgba(15, 23, 42, 150);
        border: 1px solid rgba(31, 41, 55, 120);
        border-radius: 10px;
        padding: 8px;
    }
    QTabBar::tab {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(17, 24, 39, 180), 
                                    stop:1 rgba(15, 23, 42, 200));
        border: 1px solid rgba(31, 41, 55, 100);
        padding: 8px 14px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        margin-right: 4px;
        color: #94a3b8;
        font-weight: 600;
        font-size: 9pt;
    }
    QTabBar::tab:selected {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(16, 185, 129, 180), 
                                    stop:1 rgba(5, 150, 105, 200));
        border: 1px solid #10b981;
        border-bottom: 2px solid #10b981;
        color: #ffffff;
    }
    QTabBar::tab:hover:!selected {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(30, 41, 59, 200), 
                                    stop:1 rgba(17, 24, 39, 220));
        border: 1px solid rgba(71, 85, 105, 120);
        color: #cbd5e1;
    }
    
    /* === TABLE WITH DEPTH === */
    QTableWidget {
        background: rgba(15, 17, 21, 220);
        gridline-color: rgba(31, 38, 51, 100);
        border: 1px solid rgba(31, 41, 55, 120);
        border-radius: 10px;
        font-size: 9pt;
    }
    QTableWidget::item:selected {
        background: rgba(16, 185, 129, 120);
        color: #ffffff;
    }
    QTableWidget::item:hover {
        background: rgba(59, 130, 246, 80);
    }
    QHeaderView::section {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(20, 24, 36, 220), 
                                    stop:1 rgba(15, 17, 21, 240));
        color: #10b981;
        padding: 8px;
        border: 1px solid rgba(31, 38, 51, 80);
        font-weight: 700;
        font-size: 9pt;
    }
    
    /* === LIST WITH GLOW === */
    QListWidget {
        background: rgba(15, 17, 21, 200);
        border: 1px solid rgba(31, 41, 55, 120);
        border-radius: 10px;
        padding: 4px;
        font-size: 9pt;
    }
    QListWidget::item:selected {
        background: rgba(16, 185, 129, 150);
        color: #ffffff;
        border-radius: 6px;
    }
    QListWidget::item:hover {
        background: rgba(59, 130, 246, 100);
        border-radius: 6px;
    }
    
    /* === COMBOBOX GLASSMORPHIC === */
    QComboBox {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(15, 17, 21, 200), 
                                    stop:1 rgba(17, 24, 39, 180));
        border: 1px solid rgba(31, 41, 55, 120);
        border-radius: 8px;
        padding: 6px 10px;
        color: #cbd5e1;
        font-size: 9pt;
        font-weight: 600;
    }
    QComboBox:hover {
        border: 1px solid rgba(16, 185, 129, 150);
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(20, 24, 36, 220), 
                                    stop:1 rgba(17, 24, 39, 200));
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid #10b981;
        margin-right: 6px;
    }
    QComboBox QAbstractItemView {
        background: rgba(17, 24, 39, 240);
        border: 2px solid rgba(16, 185, 129, 180);
        border-radius: 8px;
        selection-background-color: rgba(16, 185, 129, 150);
        color: #cbd5e1;
        padding: 4px;
    }
    
    /* === SPINBOX === */
    QDoubleSpinBox, QSpinBox {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 rgba(15, 17, 21, 200), 
                                    stop:1 rgba(17, 24, 39, 180));
        border: 1px solid rgba(31, 41, 55, 120);
        border-radius: 8px;
        padding: 6px 8px;
        color: #cbd5e1;
        font-size: 9pt;
    }
    QDoubleSpinBox:focus, QSpinBox:focus {
        border: 1px solid rgba(16, 185, 129, 180);
    }
    
    /* === NEON GLOW SLIDER === */
    QSlider::groove:horizontal {
        height: 8px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 rgba(31, 38, 51, 150), 
                                    stop:1 rgba(20, 24, 36, 180));
        border-radius: 4px;
        border: 1px solid rgba(31, 41, 55, 100);
    }
    QSlider::handle:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #10b981, stop:1 #059669);
        width: 18px;
        height: 18px;
        margin: -5px 0;
        border-radius: 9px;
        border: 2px solid rgba(255, 255, 255, 50);
    }
    QSlider::handle:horizontal:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #34d399, stop:1 #10b981);
        border: 2px solid rgba(255, 255, 255, 100);
    }
    
    /* === SCROLLBAR CYBER STYLE === */
    QScrollBar:vertical {
        background: rgba(15, 17, 21, 150);
        width: 12px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 rgba(59, 130, 246, 180), 
                                    stop:1 rgba(16, 185, 129, 180));
        border-radius: 6px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 #3b82f6, stop:1 #10b981);
    }
    QScrollBar::add-line, QScrollBar::sub-line {
        height: 0px;
    }
    
    /* === LINE EDIT === */
    QLineEdit {
        background: rgba(15, 17, 21, 200);
        border: 1px solid rgba(31, 41, 55, 120);
        border-radius: 8px;
        padding: 6px 10px;
        color: #cbd5e1;
        font-size: 9pt;
    }
    QLineEdit:focus {
        border: 1px solid rgba(16, 185, 129, 180);
        background: rgba(17, 24, 39, 220);
    }
    
    /* === MDI SUBWINDOW WITH DEPTH SHADOW === */
    QMdiSubWindow {
        background: rgba(17, 24, 39, 200);
        border: 2px solid rgba(31, 41, 55, 150);
        border-radius: 12px;
    }
    QMdiSubWindow::title {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                    stop:0 rgba(16, 185, 129, 180), 
                                    stop:0.5 rgba(59, 130, 246, 180), 
                                    stop:1 rgba(139, 92, 246, 180));
        padding: 6px;
        font-weight: 700;
        color: #ffffff;
    }
    
    /* === TOOLTIP === */
    QToolTip {
        background: rgba(17, 24, 39, 240);
        border: 2px solid rgba(16, 185, 129, 200);
        border-radius: 8px;
        padding: 8px 12px;
        color: #e8eef5;
        font-size: 9pt;
        font-weight: 600;
    }
    """
