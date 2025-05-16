from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QShortcut, QVBoxLayout, QTextEdit, QHeaderView, QDialog, QPushButton

def makeTable(parent, widgetname, data, column, right_click_function=None, popupsize=None):
    def show_details(item):
        # 이미 창이 열려있는지 확인
        if hasattr(parent, "details_dialog") and parent.details_dialog.isVisible():
            return  # 창이 열려있다면 새로 열지 않음
        # 팝업 창 생성
        parent.details_dialog = QDialog()
        parent.details_dialog.setWindowTitle("상세 정보")
        if popupsize == None:
            parent.details_dialog.resize(200, 150)
        elif popupsize == 'max':
            parent.details_dialog.showMaximized()
        else:
            parent.details_dialog.resize(popupsize[0], popupsize[1])

        # 레이아웃 설정
        layout = QVBoxLayout(parent.details_dialog)

        # 스크롤 가능한 QTextEdit 위젯 생성
        text_edit = QTextEdit()
        text_edit.setText(item.text())
        text_edit.setReadOnly(True)  # 텍스트 편집 불가로 설정
        layout.addWidget(text_edit)

        # 확인 버튼 생성
        ok_button = QPushButton("확인")
        ok_button.clicked.connect(
            parent.details_dialog.accept)  # 버튼 클릭 시 다이얼로그 닫기
        layout.addWidget(ok_button)

        shortcut = QShortcut(QKeySequence("Ctrl+W"), parent.details_dialog)
        shortcut.activated.connect(parent.details_dialog.close)

        shortcut2 = QShortcut(QKeySequence("Ctrl+ㅈ"), parent.details_dialog)
        shortcut2.activated.connect(parent.details_dialog.close)

        # 다이얼로그 실행
        parent.details_dialog.exec_()

    widgetname.setRowCount(len(data))
    widgetname.setColumnCount(len(column))
    widgetname.setHorizontalHeaderLabels(column)
    widgetname.setSelectionBehavior(QTableWidget.SelectRows)
    widgetname.setSelectionMode(QTableWidget.SingleSelection)
    widgetname.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    for i, row_data in enumerate(data):
        for j, cell_data in enumerate(row_data):
            item = QTableWidgetItem(cell_data)
            item.setTextAlignment(Qt.AlignCenter)  # 가운데 정렬 설정
            item.setToolTip(str(cell_data)+"\n\n더블클릭 시 상세보기")  # Tooltip 설정
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # 수정 불가능 설정
            widgetname.setItem(i, j, item)

    # 셀을 더블 클릭하면 show_details 함수를 호출
    try:
        widgetname.itemDoubleClicked.disconnect()
    except TypeError:
        # 연결이 안 되어 있을 경우 발생하는 오류를 무시
        pass
    widgetname.itemDoubleClicked.connect(show_details)

    if right_click_function:
        widgetname.setContextMenuPolicy(Qt.CustomContextMenu)
        widgetname.customContextMenuRequested.connect(
            lambda pos: right_click_function(widgetname.rowAt(pos.y()))
        )
