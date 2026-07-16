PRIMARY = "#155A8A"
PRIMARY_DARK = "#1F3344"
BACKGROUND = "#F5F7FA"
CARD_BG = "#FFFFFF"
TEXT = "#1F2937"
MUTED = "#64748B"
BORDER = "#D7DEE8"
SUCCESS = "#16803C"
WARNING = "#B7791F"
DANGER = "#B91C1C"


def app_stylesheet():
    return f"""
    QWidget {{
        background: {BACKGROUND};
        color: {TEXT};
        font-family: Segoe UI, Arial, sans-serif;
        font-size: 10pt;
    }}
    QFrame#Header {{
        background: {PRIMARY_DARK};
        border: none;
    }}
    QLabel#HeaderTitle {{
        color: white;
        font-size: 22pt;
        font-weight: 700;
        background: transparent;
    }}
    QLabel#HeaderSubtitle {{
        color: #DBEAFE;
        background: transparent;
    }}
    QLabel#Badge {{
        color: #EAF2FF;
        background: {PRIMARY};
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 9pt;
    }}
    QFrame#Card {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    QLabel#CardTitle {{
        background: transparent;
        color: {PRIMARY_DARK};
        font-weight: 700;
        font-size: 12pt;
    }}
    QLabel#Muted {{
        background: transparent;
        color: {MUTED};
    }}
    QLabel#Ready {{
        background: transparent;
        color: {SUCCESS};
    }}
    QLabel#Missing {{
        background: transparent;
        color: {DANGER};
    }}
    QPushButton {{
        background: #E8EDF5;
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 8px 12px;
    }}
    QPushButton:hover {{
        background: #DDE6F2;
    }}
    QPushButton:disabled {{
        color: #94A3B8;
        background: #EEF2F7;
    }}
    QPushButton#PrimaryButton {{
        color: white;
        background: {PRIMARY};
        border: 1px solid {PRIMARY};
        font-weight: 700;
    }}
    QPushButton#PrimaryButton:hover {{
        background: {PRIMARY_DARK};
    }}
    QPushButton#DangerButton {{
        color: white;
        background: {DANGER};
        border: 1px solid {DANGER};
        font-weight: 700;
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: white;
        border: 1px solid {BORDER};
        border-radius: 5px;
        padding: 6px;
    }}
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        background: {CARD_BG};
        border-radius: 6px;
    }}
    QTabBar::tab {{
        background: #E8EDF5;
        border: 1px solid {BORDER};
        padding: 8px 12px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: white;
        color: {PRIMARY_DARK};
        font-weight: 700;
    }}
    QHeaderView::section {{
        background: #E8EDF5;
        border: none;
        border-right: 1px solid {BORDER};
        padding: 7px;
        font-weight: 700;
    }}
    QTableWidget {{
        background: white;
        border: none;
        gridline-color: #E5EAF0;
        selection-background-color: #D6E8FF;
    }}
    QProgressBar {{
        background: #E8EDF5;
        border: none;
        border-radius: 6px;
        height: 12px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: {PRIMARY};
        border-radius: 6px;
    }}
    """
