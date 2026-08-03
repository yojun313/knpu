"""MANAGER 데스크톱 앱의 테마 시스템.

웹 서비스들(kemkim/network/statistics, system/ui/theme.css)과 같은 4종 스킨
(default/glass/neu/mesh) × 라이트/다크를 이 앱에도 제공한다. Qt QSS는 backdrop-filter
(실시간 블러)나 이중 오프셋 box-shadow(뉴모피즘 특유의 돌출 그림자)를 지원하지 않으므로,
글래스/뉴모피즘은 웹과 픽셀 단위로 똑같지는 않다 — 팔레트·둥근 모서리·테두리로 그 느낌만
근사한다. 지금까지의 기본 디자인이 곧 "default" 스킨이라 팔레트는 그대로 유지했다.

사용법:
    from ui.style import get_stylesheet
    app.setStyleSheet(get_stylesheet(style, mode))  # style: default|glass|neu|mesh, mode: light|dark
"""

# ────────────────────── 팔레트 (테마 4종 × 라이트/다크) ──────────────────────
# 웹 쪽 system/ui/theme.css의 CSS 커스텀 프로퍼티(--sidebar-bg, --accent 등)와
# 같은 값을 최대한 그대로 가져왔다. Qt 위젯은 반투명/블러를 안정적으로 지원하지 않으므로
# glass/mesh의 반투명 배경은 비슷한 톤의 불투명 색으로 근사했다.
PALETTES = {
    ("default", "light"): {
        "bg": "#ffffff",
        "bg_input": "#ffffff",
        "bg_dropdown": "#ecf0f1",
        "text": "#000000",
        "border": "#bdc3c7",
        "accent": "#2c3e50",
        "accent_hover": "#34495e",
        "accent_text": "#ffffff",
        "scrollbar_track": "#f1f1f1",
        "scrollbar_thumb": "#c6c6c6",
    },
    ("default", "dark"): {
        "bg": "#2b2b2b",
        "bg_input": "#3c3c3c",
        "bg_dropdown": "#3b4d61",
        "text": "#eaeaea",
        "border": "#5a5a5a",
        "accent": "#34495e",
        "accent_hover": "#3a539b",
        "accent_text": "#eaeaea",
        "scrollbar_track": "#2e2e2e",
        "scrollbar_thumb": "#5e5e5e",
    },
    ("glass", "light"): {
        "bg": "#eef1f7",
        "bg_input": "#ffffff",
        "bg_dropdown": "#e3e7f2",
        "text": "#2a3240",
        "border": "#d8d2e8",
        "accent": "#7c6fd6",
        "accent_hover": "#9c92e0",
        "accent_text": "#ffffff",
        "scrollbar_track": "#e5e8f0",
        "scrollbar_thumb": "#c7c2dd",
    },
    ("glass", "dark"): {
        "bg": "#1e2130",
        "bg_input": "#262a3a",
        "bg_dropdown": "#2c3040",
        "text": "#dde1ea",
        "border": "#383c4c",
        "accent": "#7c9ce8",
        "accent_hover": "#9db3ee",
        "accent_text": "#12141d",
        "scrollbar_track": "#181a26",
        "scrollbar_thumb": "#3a3f52",
    },
    ("neu", "light"): {
        "bg": "#e7e9ee",
        "bg_input": "#dfe2e8",
        "bg_dropdown": "#dadde3",
        "text": "#4a5568",
        "border": "#d1d4da",
        "accent": "#5b7fdb",
        "accent_hover": "#7897e4",
        "accent_text": "#ffffff",
        "scrollbar_track": "#dfe2e8",
        "scrollbar_thumb": "#c9ccd3",
    },
    ("neu", "dark"): {
        "bg": "#2b2e37",
        "bg_input": "#313540",
        "bg_dropdown": "#363b47",
        "text": "#d7dae2",
        "border": "#212329",
        "accent": "#7c96d9",
        "accent_hover": "#97ade4",
        "accent_text": "#12141a",
        "scrollbar_track": "#25272f",
        "scrollbar_thumb": "#3d414d",
    },
    ("mesh", "light"): {
        "bg": "#eef0f4",
        "bg_input": "#ffffff",
        "bg_dropdown": "#e3e7ec",
        "text": "#2a3240",
        "border": "#d7e3ea",
        "accent": "#4f9dc9",
        "accent_hover": "#79b9dc",
        "accent_text": "#ffffff",
        "scrollbar_track": "#e4e8ed",
        "scrollbar_thumb": "#c3d3dc",
    },
    ("mesh", "dark"): {
        "bg": "#14151f",
        "bg_input": "#1c1e2b",
        "bg_dropdown": "#212333",
        "text": "#e0e3ea",
        "border": "#2a2d3d",
        "accent": "#22d3ee",
        "accent_hover": "#67e8f9",
        "accent_text": "#0a1418",
        "scrollbar_track": "#191a26",
        "scrollbar_thumb": "#2e3244",
    },
}

STYLES = ["default", "glass", "neu", "mesh"]
STYLE_LABELS = {
    "default": "기본",
    "glass": "글래스모피즘",
    "neu": "뉴모피즘",
    "mesh": "그라디언트 메시",
}
MODES = ["light", "dark"]

# 상태색(성공/에러)은 스킨과 무관하게 고정 — 웹 쪽도 경고/성공 색은 테마와 별개로 고정색을 쓴다.
_SUCCESS = "#4CAF50"
_DANGER = "#E74C3C"

_TEMPLATE = """
    QMainWindow {{
        background-color: {bg};
        font-size: 14px;
        color: {text};
    }}
    QWidget {{
        background-color: {bg};
        color: {text};
    }}
    QPushButton {{
        background-color: {accent};
        color: {accent_text};
        border: none;
        border-radius: 5px;
        padding: 13px;
        font-size: 15px;
    }}
    QPushButton:hover {{
        background-color: {accent_hover};
    }}
    QStatusBar {{
        background-color: {bg};
        font-family: 'Tahoma';
        font-size: 10px;
        color: {text};
    }}
    QLineEdit {{
        border: 1px solid {border};
        border-radius: 5px;
        padding: 8px;
        background-color: {bg_input};
        font-size: 14px;
        color: {text};
    }}
    QLabel {{
        color: {text};
        font-size: 14px;
        background-color: transparent;
    }}
    QTableWidget {{
        background-color: {bg};
        gridline-color: {border};
        border: 1px solid {border};
        font-size: 14px;
        color: {text};
    }}
    QTableWidget::item {{
        background-color: {bg_input};
        color: {text};
    }}
    QTableWidget::item:selected {{
        background-color: {accent_hover};
        color: {accent_text};
    }}
    QTableCornerButton::section {{
        background-color: {accent};
        border: 1px solid {accent};
    }}
    QHeaderView {{
        background-color: {bg};
        border: none;
    }}
    QHeaderView::section {{
        background-color: {accent};
        color: {accent_text};
        padding: 8px;
        border: none;
        font-size: 14px;
    }}
    QHeaderView::corner {{
        background-color: {bg_input};
        border: 1px solid {border};
    }}
    QListWidget {{
        background-color: {accent};
        color: {accent_text};
        font-family: 'Tahoma';
        font-size: 14px;
        border: none;
        min-width: 150px;
        max-width: 150px;
    }}
    QListWidget::item {{
        height: 40px;
        padding: 10px;
        font-family: 'Tahoma';
        font-size: 14px;
    }}
    QListWidget::item:selected, QListWidget::item:hover {{
        background-color: {accent_hover};
    }}
    QTabWidget::pane {{
        border-top: 2px solid {border};
        background-color: {bg};
    }}
    QTabWidget::tab-bar {{
        left: 5px;
    }}
    QTabBar::tab {{
        background: {accent};
        color: {accent_text};
        border: 1px solid {border};
        border-bottom-color: {bg};
        border-radius: 4px;
        border-top-right-radius: 4px;
        padding: 10px;
        font-size: 14px;
        min-width: 100px;
        max-width: 200px;
    }}
    QTabBar::tab:selected, QTabBar::tab:hover {{
        background: {accent_hover};
    }}
    QTabBar::tab:selected {{
        border-color: {border};
        border-bottom-color: {bg};
    }}
    QFileDialog {{
        background-color: {bg};
        color: {text};
    }}
    QFileDialog QListView, QTreeView {{
        background-color: {bg};
        color: {text};
    }}
    QComboBox {{
        background-color: {bg_input};
        color: {text};
        border: 2px solid {border};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 14px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {bg_input};
        color: {text};
        selection-background-color: {accent_hover};
        selection-color: {accent_text};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        background-color: {bg_dropdown};
        border-left: 1px solid {border};
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }}
    QGroupBox::title {{
        color: {text};
    }}
    QTextEdit {{
        border: 1px solid {border};
        border-radius: 4px;
        padding: 8px;
        font-size: 14px;
        background-color: {bg_input};
        color: {text};
    }}
    QDialog {{
        background-color: {bg};
        color: {text};
        border: 1px solid {border};
    }}
    QMessageBox {{
        background-color: {bg};
        color: {text};
    }}
    QMessageBox QLabel {{
        color: {text};
    }}
    QMessageBox QPushButton {{
        background-color: {accent};
        color: {accent_text};
        border: none;
        border-radius: 5px;
        padding: 10px;
    }}
    QMessageBox QPushButton:hover {{
        background-color: {accent_hover};
    }}
    QScrollArea {{
        background-color: {bg};
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: {bg};
    }}
    QScrollBar:vertical {{
        background: {scrollbar_track};
        width: 16px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {scrollbar_thumb};
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        background: {scrollbar_track};
        height: 16px;
        subcontrol-position: bottom;
        subcontrol-origin: margin;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: {scrollbar_track};
    }}
    QScrollBar:horizontal {{
        background: {scrollbar_track};
        height: 16px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {scrollbar_thumb};
        min-width: 20px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        background: {scrollbar_track};
        width: 16px;
        subcontrol-position: right;
        subcontrol-origin: margin;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: {scrollbar_track};
    }}
    QCheckBox {{
        spacing: 5px;
        font-size: 14px;
        color: {text};
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {border};
        border-radius: 3px;
        background-color: {bg_input};
    }}
    QCheckBox::indicator:hover {{
        border: 1px solid {accent_hover};
    }}
    QCheckBox::indicator:checked {{
        background-color: {accent};
        border: 1px solid {accent_hover};
    }}
    QCheckBox::indicator:unchecked {{
        background-color: {bg_input};
        border: 1px solid {border};
    }}
    QCheckBox::indicator:disabled {{
        background-color: {bg};
        border: 1px solid {border};
    }}
    QDateEdit {{
        background-color: {bg_input};
        color: {text};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 5px;
        font-size: 14px;
    }}
    QDateEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        background-color: {bg_dropdown};
        border-left: 1px solid {border};
    }}
    QDateEdit::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 15px;
        background-color: {bg_dropdown};
        border: none;
    }}
    QDateEdit::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 15px;
        background-color: {bg_dropdown};
        border: none;
    }}
    QDateEdit QAbstractItemView {{
        background-color: {bg_input};
        color: {text};
        selection-background-color: {accent_hover};
        selection-color: {accent_text};
        border: 1px solid {border};
    }}
    QRadioButton {{
        background-color: transparent;
        color: {text};
        font-size: 14px;
        padding: 5px;
    }}
    QPlainTextEdit {{
        background-color: {bg_input};
        color: {text};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 8px;
        font-size: 14px;
    }}
    QLabel#downloadMsgLabel {{
        font-weight: bold;
        color: {text};
        font-size: 13px;
        background-color: transparent;
    }}
    QProgressBar#downloadProgressBar {{
        border: 1px solid {border};
        border-radius: 8px;
        background-color: {bg_input};
        height: 22px;
        text-align: center;
        font-size: 12px;
        color: {text};
    }}
    QProgressBar#downloadProgressBar::chunk {{
        background-color: """ + _SUCCESS + """;
        border-radius: 8px;
    }}
    QProgressBar#downloadProgressBar[state="error"]::chunk {{
        background-color: """ + _DANGER + """;
    }}
    QDoubleSpinBox {{
        background-color: {bg_input};
        color: {text};
        border: 2px solid {border};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 14px;
    }}
    QDoubleSpinBox:hover {{
        border: 2px solid {accent_hover};
    }}
    QDoubleSpinBox:focus {{
        border: 2px solid {accent};
    }}
    QDoubleSpinBox::up-button {{
        subcontrol-position: top right;
        border-top-right-radius: 6px;
    }}
    QDoubleSpinBox::down-button {{
        subcontrol-position: bottom right;
        border-bottom-right-radius: 6px;
    }}
    QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {{
        width: 10px;
        height: 10px;
    }}
    QSpinBox {{
        background-color: {bg_input};
        color: {text};
        border: 2px solid {border};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 14px;
    }}
    QSpinBox:hover {{
        border: 2px solid {accent_hover};
    }}
    QSpinBox:focus {{
        border: 2px solid {accent};
    }}
    QSpinBox::up-button {{
        subcontrol-position: top right;
        border-top-right-radius: 6px;
    }}
    QSpinBox::down-button {{
        subcontrol-position: bottom right;
        border-bottom-right-radius: 6px;
    }}
    QSpinBox::up-arrow, QSpinBox::down-arrow {{
        width: 10px;
        height: 10px;
    }}
"""


def get_stylesheet(style: str = "default", mode: str = "light") -> str:
    """스킨(default/glass/neu/mesh) + 라이트/다크 조합의 QSS를 반환한다."""
    palette = PALETTES.get((style, mode)) or PALETTES[("default", "light")]
    return _TEMPLATE.format(**palette)
