from PyQt6.QtGui import QKeySequence
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidget, QAbstractItemView, QTableWidgetItem, QVBoxLayout, QTextEdit, QHeaderView, QDialog, QPushButton, QApplication
from PyQt6.QtGui import QShortcut

def makeTable(parent, widgetname, data, column, right_click_function=None, popupsize=None):
    def show_details(item):
        # 이미 창이 열려있는지 확인
        if hasattr(parent, "details_dialog") and parent.details_dialog.isVisible():
            return  # 창이 열려있다면 새로 열지 않음

        # 팝업 창 생성
        parent.details_dialog = QDialog()
        parent.details_dialog.setWindowTitle("상세 정보")

        if popupsize is None:
            parent.details_dialog.resize(200, 150)
        elif popupsize == 'max':
            parent.details_dialog.showMaximized()
        else:
            parent.details_dialog.resize(popupsize[0], popupsize[1])

        # 레이아웃 설정
        layout = QVBoxLayout(parent.details_dialog)

        # 텍스트 표시 영역
        text_edit = QTextEdit()
        text_edit.setText(item.text())
        text_edit.setReadOnly(True)  # 편집 불가
        layout.addWidget(text_edit)

        # 복사 버튼 생성
        copy_button = QPushButton("복사")
        def copy_text():
            clipboard = QApplication.clipboard()
            clipboard.setText(text_edit.toPlainText())

        copy_button.clicked.connect(copy_text)
        layout.addWidget(copy_button)

        # 확인 버튼 생성
        ok_button = QPushButton("확인")
        ok_button.clicked.connect(parent.details_dialog.accept)
        layout.addWidget(ok_button)

        # 단축키 등록 (닫기)
        shortcut = QShortcut(QKeySequence("Ctrl+W"), parent.details_dialog)
        shortcut.activated.connect(parent.details_dialog.close)

        shortcut2 = QShortcut(QKeySequence("Ctrl+ㅈ"), parent.details_dialog)
        shortcut2.activated.connect(parent.details_dialog.close)

        # 다이얼로그 실행
        parent.details_dialog.exec()

    widgetname.setRowCount(len(data))
    widgetname.setColumnCount(len(column))
    widgetname.setHorizontalHeaderLabels(column)
    widgetname.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widgetname.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widgetname.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    
    for i, row_data in enumerate(data):
        for j, cell_data in enumerate(row_data):
            item = QTableWidgetItem(str(cell_data))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # 가운데 정렬 설정
            item.setToolTip(str(cell_data)+"\n\n더블클릭 시 상세보기")  # Tooltip 설정
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            widgetname.setItem(i, j, item)

    # 셀을 더블 클릭하면 show_details 함수를 호출
    try:
        widgetname.itemDoubleClicked.disconnect()
    except TypeError:
        # 연결이 안 되어 있을 경우 발생하는 오류를 무시
        pass
    widgetname.itemDoubleClicked.connect(show_details)

    if right_click_function:
        widgetname.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widgetname.customContextMenuRequested.connect(
            lambda pos: right_click_function(widgetname.rowAt(pos.y()))
        )
