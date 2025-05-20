from core.setting import get_setting

# 전역 스타일시트 설정
light_style_sheet = """
    QMainWindow {
        background-color: #ffffff;
        font-size: 14px;
    }
    QPushButton {
        background-color: #2c3e50;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 13px;
        font-size: 15px;
    }
    QStatusBar {
        background-color: #ffffff; /* 기본 흰색 배경 */
        font-family: 'Tahoma';
        font-size: 10px;
        color: black;
    }
    QPushButton:hover {
        background-color: #34495e;
    }
    QLineEdit {
        border: 1px solid #bdc3c7;
        border-radius: 5px;
        padding: 8px;
        background-color: white;
        font-size: 14px;
        color: black;
    }
    QLabel {
        color: black;  /* 라벨 기본 텍스트 색상 */
        font-size: 14px;
        background-color: #ffffff; /* 라벨 배경 흰색 */
    }
    QTableWidget {
        background-color: white;
        border: 1px solid #bdc3c7;
        font-size: 14px;
        color: black;
    }
    QTableCornerButton::section {  /* 좌측 상단 정사각형 부분 스타일 */
        background-color: #2c3e50;
        border: 1px solid #2c3e50;
    }
    QHeaderView::section {
        background-color: #2c3e50;
        color: white;
        padding: 8px;
        border: none;
        font-size: 14px;
    }
    QListWidget {
        background-color: #2c3e50;
        color: white;
        font-family: 'Tahoma';
        font-size: 14px;
        border: none;
        min-width: 150px;
        max-width: 150px;
    }
    QListWidget::item {
        height: 40px;
        padding: 10px;
        font-family: 'Tahoma';
        font-size: 14px;
    }
    QListWidget::item:selected {
        background-color: #34495e;
    }
    QListWidget::item:hover {
        background-color: #34495e;
    }
    QTabWidget::pane {
        border-top: 2px solid #bdc3c7;
        background-color: #ffffff;
    }
    QTabWidget::tab-bar {
        left: 5px;
    }
    QTabBar::tab {
        background: #2c3e50;
        color: white;
        border: 1px solid #bdc3c7;
        border-bottom-color: #ffffff;
        border-radius: 4px;
        border-top-right-radius: 4px;
        padding: 10px;
        font-size: 14px;
        min-width: 100px;
        max-width: 200px;
    }
    QTabBar::tab:selected, QTabBar::tab:hover {
        background: #34495e;
    }
    QTabBar::tab:selected {
        border-color: #9B9B9B;
        border-bottom-color: #ffffff;
    }
    QFileDialog {
        background-color: #ffffff;
        color: #000000;
    }
    QFileDialog QListView, QTreeView {
        background-color: #ffffff;
        color: #000000;
    }
    QComboBox {
        background-color: #ffffff;
        color: #000000;
        border: 2px solid #bdc3c7; /* 두께를 증가시켜 입체감 추가 */
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 14px;
    }
    
    /* 드롭다운 버튼 스타일 */
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        background-color: #ecf0f1;
        border-left: 1px solid #bdc3c7;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }

    QGroupBox::title {
        color: black; /* 제목 텍스트 색상 */
    }
    QTextEdit {
        border: 1px solid #dcdcdc;
        border-radius: 4px;
        padding: 8px;
        font-size: 14px;
        background-color: #ffffff; /* 기본 흰색 배경 */
        color: #000000; /* 기본 검정 텍스트 */
    }

    QDialog {
        background-color: #ffffff; /* 기본 다이얼로그 흰색 배경 */
        color: #000000; /* 기본 텍스트 검정 */
        border: 1px solid #dcdcdc; /* 연한 회색 테두리 */
    }

    QScrollArea {
        background-color: #ffffff; /* 스크롤 영역 기본 흰색 배경 */
        color: #000000; /* 기본 텍스트 검정 */
    }

    QMessageBox {
        background-color: #ffffff; /* 메시지 박스 기본 흰색 배경 */
        color: #000000; /* 기본 텍스트 검정 */
    }

    QScrollBar:vertical {
        background: #f1f1f1; /* 수직 스크롤바 배경 */
        width: 16px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #c6c6c6; /* 수직 스크롤바 핸들 */
        min-height: 20px;
        border-radius: 4px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        background: #e6e6e6; /* 수직 스크롤바 상/하단 버튼 */
        height: 16px;
        subcontrol-position: bottom;
    }
    QScrollBar:horizontal {
        background: #f1f1f1; /* 수평 스크롤바 배경 */
        height: 16px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: #c6c6c6; /* 수평 스크롤바 핸들 */
        min-width: 20px;
        border-radius: 4px;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        background: #e6e6e6; /* 수평 스크롤바 좌/우 버튼 */
        width: 16px;
    }

    QCheckBox {
        spacing: 5px; /* 텍스트와 체크박스 간 간격 */
        font-size: 14px; /* 기본 폰트 크기 */
        color: #000000; /* 기본 검정 텍스트 */
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #dcdcdc; /* 체크박스 외곽선 */
        border-radius: 3px;
        background-color: #ffffff; /* 체크박스 배경 */
    }
    QCheckBox::indicator:checked {
        background-color: #0078d7; /* 체크된 상태의 배경 (파란색) */
        border: 1px solid #005bb5; /* 체크된 상태의 테두리 */
    }
    QCheckBox::indicator:unchecked {
        background-color: #ffffff; /* 체크 해제 상태의 배경 */
        border: 1px solid #dcdcdc; /* 체크 해제 상태의 테두리 */
    }
    QDateEdit {
        background-color: white; /* 밝은 배경색 */
        color: black; /* 텍스트 색상 */
        border: 1px solid #bdc3c7; /* 테두리 색상 */
        border-radius: 4px; /* 둥근 모서리 */
        padding: 5px; /* 내부 여백 */
        font-size: 14px;
    }

    QDateEdit::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        background-color: #ecf0f1; /* 드롭다운 배경 */
        border-left: 1px solid #bdc3c7; /* 드롭다운 구분선 */
    }

    QDateEdit::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 15px;
        background-color: #ecf0f1;
        border: none;
    }

    QDateEdit::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 15px;
        background-color: #ecf0f1;
        border: none;
    }

    QDateEdit QAbstractItemView {
        background-color: white; /* 드롭다운 리스트 배경 */
        color: black; /* 드롭다운 텍스트 색상 */
        selection-background-color: #bdc3c7; /* 선택 항목 배경 */
        selection-color: black; /* 선택 항목 텍스트 색상 */
        border: 1px solid #bdc3c7; /* 리스트 테두리 */
    }
    QRadioButton {
        background-color: transparent; /* 배경 투명 */
        color: black; /* 텍스트 색상 */
        font-size: 14px;
        padding: 5px;
    }
    """

dark_style_sheet = """
    QMainWindow {
        background-color: #2b2b2b;
        font-size: 14px;
        color: #eaeaea;  /* 기본 텍스트 색상 */
    }
    QPushButton {
        background-color: #34495e;
        color: #eaeaea;  /* 버튼 텍스트 색상 */
        border: none;
        border-radius: 5px;
        padding: 13px;
        font-size: 15px;
    }
    QStatusBar {
        font-family: 'Tahoma';
        background-color: #2b2b2b;
        font-size: 10px;
        color: white;
    }
    QPushButton:hover {
        background-color: #3a539b;
    }
    QLineEdit {
        border: 1px solid #5a5a5a;
        border-radius: 5px;
        padding: 8px;
        background-color: #3c3c3c;
        color: #eaeaea;  /* 입력 텍스트 색상 */
        font-size: 14px;
    }
    QTextEdit {
        background-color: #3c3c3c;  /* 배경색 */
        color: #eaeaea;  /* 텍스트 색상 */
        font-family: 'Tahoma';  /* 폰트 */
        font-size: 14px;  /* 폰트 크기 */
        border: 1px solid #5a5a5a;  /* 테두리 색상 */
        border-radius: 4px;  /* 모서리 둥글기 */
        padding: 8px;  /* 내부 여백 */
    }
    QLabel {
        background-color: #2b2b2b;  /* 내부 위젯 배경색 */
        color: white;            /* 글자 색 */
        font-size: 14px;
    }
    QTableWidget {
        background-color: #2b2b2b;  /* 테이블 전체 배경 */
        gridline-color: #5a5a5a;  /* 셀 간격선 색상 */
        color: #eaeaea;  /* 셀 텍스트 색상 */
        font-size: 14px;
        border: 1px solid #5a5a5a;  /* 테두리 설정 */
    }
    QTableWidget::item {
        background-color: #3c3c3c;  /* 셀 배경색 */
        color: #eaeaea;  /* 셀 텍스트 색상 */
    }
    QTableWidget::item:selected {
        background-color: #34495e;  /* 선택된 셀 배경색 */
        color: #ffffff;  /* 선택된 셀 텍스트 색상 */
    }
    QTableCornerButton::section {  /* 좌측 상단 정사각형 부분 스타일 */
        background-color: #3c3c3c;
        border: 1px solid #5a5a5a;
    }
    QHeaderView::section {
        background-color: #3c3c3c;
        color: #eaeaea;  /* 헤더 텍스트 색상 */
        padding: 8px;
        border: 1px solid #5a5a5a;
        font-size: 14px;
    }
    QHeaderView::corner {  /* 좌측 상단 정사각형 부분 */
        background-color: #3c3c3c; /* 테이블 배경과 동일한 색상 */
        border: 1px solid #5a5a5a;
    }
    QHeaderView {
        background-color: #2b2b2b;  /* 헤더 전체 배경 */
        border: none;
    }
    QListWidget {
        background-color: #3c3c3c;
        color: #eaeaea;  /* 리스트 아이템 텍스트 색상 */
        font-family: 'Tahoma';
        font-size: 14px;
        border: none;
        min-width: 150px;  /* 가로 크기 고정: 최소 크기 설정 */
        max-width: 150px;
    }
    QListWidget::item {
        height: 40px;
        padding: 10px;
        font-family: 'Tahoma';
        font-size: 14px;
    }
    QListWidget::item:selected {
        background-color: #34495e;
        color: #ffffff;
    }
    QListWidget::item:hover {
        background-color: #34495e;
    }
    QTabWidget::pane {
        border-top: 2px solid #5a5a5a;
        background-color: #2b2b2b;
    }
    QTabWidget::tab-bar {
        left: 5px;
    }
    QTabBar::tab {
        background: #3c3c3c;
        color: #eaeaea;  /* 탭 텍스트 색상 */
        border: 1px solid #5a5a5a;
        border-bottom-color: #2b2b2b;
        border-radius: 4px;
        padding: 10px;
        font-size: 14px;
        min-width: 100px;  /* 최소 가로 길이 설정 */
        max-width: 200px;  /* 최대 가로 길이 설정 */
    }
    QTabBar::tab:selected, QTabBar::tab:hover {
        background: #34495e;
        color: #ffffff;
    }
    QDialog {
        background-color: #2b2b2b;  /* 다이얼로그 배경색 */
        color: #eaeaea;
        border: 1px solid #5a5a5a;
        font-size: 14px;
    }
    QScrollArea {
        background-color: #2b2b2b;  /* 다이얼로그 배경색 */
        color: #eaeaea;
        border: 1px solid #5a5a5a;
        font-size: 14px;
    }
    QMessageBox {
        background-color: #2b2b2b;  /* 메시지 박스 배경색 */
        color: #eaeaea;  /* 메시지 텍스트 색상 */
        font-size: 14px;
        border: 1px solid #5a5a5a;
    }
    QMessageBox QLabel {
        color: #eaeaea;  /* 메시지 박스 라벨 색상 */
    }
    QMessageBox QPushButton {
        background-color: #34495e;  /* 버튼 배경색 */
        color: #eaeaea;  /* 버튼 텍스트 색상 */
        border: none;
        border-radius: 5px;
        padding: 10px;
    }
    QMessageBox QPushButton:hover {
        background-color: #3a539b;  /* 버튼 hover 효과 */
    }
    QScrollBar:vertical {
        background: #2e2e2e;
        width: 16px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #5e5e5e;
        min-height: 20px;
        border-radius: 4px;
    }
    QScrollBar::add-line:vertical {
        background: #3a3a3a;
        height: 16px;
        subcontrol-position: bottom;
        subcontrol-origin: margin;
    }
    QScrollBar::sub-line:vertical {
        background: #3a3a3a;
        height: 16px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: #2e2e2e;
    }
    QScrollBar:horizontal {
        background: #2e2e2e;
        height: 16px;
        margin: 0px;
    }
    QScrollBar::handle:horizontal {
        background: #5e5e5e;
        min-width: 20px;
        border-radius: 4px;
    }
    QScrollBar::add-line:horizontal {
        background: #3a3a3a;
        width: 16px;
        subcontrol-position: right;
        subcontrol-origin: margin;
    }
    QScrollBar::sub-line:horizontal {
        background: #3a3a3a;
        width: 16px;
        subcontrol-position: left;
        subcontrol-origin: margin;
    }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: #2e2e2e;
    }
    QFileDialog {
        background-color: #2e2e2e;
        color: #ffffff;
    }
    QFileDialog QListView, QTreeView {
        background-color: #2e2e2e;
        color: #ffffff;
    }
    QComboBox {
        background-color: #2e2e2e; /* 다크 모드 배경 */
        color: #ecf0f1;
        border: 2px solid #34495e;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 14px;
    }
    
    /* 드롭다운 버튼 스타일 */
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        background-color: #3b4d61;
        border-left: 1px solid #34495e;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
    }

    QCheckBox {
        spacing: 5px; /* 텍스트와 체크박스 간 간격 */
        color: white; /* 기본 텍스트 색상 */
        font-size: 14px;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #5a5a5a; /* 체크박스 외곽선 색상 */
        border-radius: 3px;
        background-color: #2b2b2b; /* 체크박스 배경 */
    }

    QCheckBox::indicator:hover {
        border: 1px solid #3a539b; /* 마우스 오버 시 외곽선 색상 */
    }

    QCheckBox::indicator:checked {
        background-color: #34495e; /* 체크된 상태 배경 */
        border: 1px solid #3a539b; /* 체크된 상태 외곽선 */
        image: url('checkmark.png'); /* 체크된 상태 이미지 (선택 사항) */
    }

    QCheckBox::indicator:unchecked {
        background-color: #2b2b2b; /* 체크 안 된 상태 배경 */
        border: 1px solid #5a5a5a; /* 체크 안 된 상태 외곽선 */
    }

    QCheckBox::indicator:disabled {
        background-color: #3c3c3c; /* 비활성화 상태 배경 */
        border: 1px solid #5a5a5a; /* 비활성화 상태 외곽선 */
        color: #777777; /* 비활성화 상태 텍스트 색상 */
    }
    QGroupBox::title {
        color: white; /* 제목 텍스트 색상 */
    }
    QDateEdit {
        background-color: #3c3c3c; /* 다크 배경색 */
        color: white; /* 텍스트 색상 */
        border: 1px solid #3c3c3c; /* 테두리 색상 */
        border-radius: 4px; /* 둥근 모서리 */
        padding: 5px; /* 내부 여백 */
        font-size: 14px;
    }

    QDateEdit::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        background-color: #3c3c3c; /* 드롭다운 배경 */
        border-left: 1px solid #5c5c5c; /* 드롭다운 구분선 */
    }

    QDateEdit::up-button {
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 15px;
        background-color: #3c3c3c;
        border: none;
    }

    QDateEdit::down-button {
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 15px;
        background-color: #3c3c3c;
        border: none;
    }

    QDateEdit QAbstractItemView {
        background-color: #3c3c3c; /* 드롭다운 리스트 배경 */
        color: white; /* 드롭다운 텍스트 색상 */
        selection-background-color: #5c5c5c; /* 선택 항목 배경 */
        selection-color: white; /* 선택 항목 텍스트 색상 */
        border: 1px solid #5c5c5c; /* 리스트 테두리 */
    }
    QRadioButton {
        background-color: transparent; /* 배경 투명 */
        color: white; /* 텍스트 색상 */
        font-size: 14px;
        padding: 5px;
    }

    """

theme_option = {
    'default': light_style_sheet,
    'dark': dark_style_sheet
}


def updateTableStyleHtml(parent):
    if get_setting('Theme') != 'default':
        parent.style_html = f"""
            <style>
                h2 {{
                    color: #2c3e50;
                    text-align: center;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                    color: white;
                }}
                th, td {{
                    border: 1px solid #bdc3c7;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #34495e;
                    color: white;
                }}
                td {{
                    color: white;
                }}
                .detail-content {{
                    white-space: pre-wrap;
                    margin-top: 5px;
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                }}
            </style>
        """
    else:
        parent.style_html = f"""
            <style>
                h2 {{
                    color: #2c3e50;
                    text-align: center;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                    color: black;
                }}
                th, td {{
                    border: 1px solid #bdc3c7;
                    padding: 8px;
                    text-align: left;
                    color: white;
                }}
                th {{
                    background-color: #34495e;
                }}
                td {{
                    color: black;
                }}
                .detail-content {{
                    white-space: pre-wrap;
                    margin-top: 5px;
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                    color: black;
                }}
            </style>
        """
