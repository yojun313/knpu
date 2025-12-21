import os
import traceback
import requests
from packaging import version

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtWidgets import QStatusBar, QLabel, QMessageBox

from config import ASSETS_PATH, VERSION, MANAGER_SERVER_API
from services.api import Request
from core.setting import get_setting, set_setting
from ui.status import showActiveThreadsDialog
from windows.splash_window import AboutDialog

class ClickableLabel(QLabel):
    clicked = Signal()  # 클릭 시그널 정의

    def mousePressEvent(self, event):
        self.clicked.emit()  # 클릭되면 시그널 발생
        super().mousePressEvent(event)

def initListWidget(parent):
    try:
        parent.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
        parent.centralWidget().layout().setSpacing(0)
        
        iconPath = os.path.join(ASSETS_PATH, 'setting.png')
        parent.database_searchDB_button.setText("") 
        parent.database_searchDB_button.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '..', 'assets', 'search.png')))
        parent.database_searchDB_button.setIconSize(QSize(18, 18))  

        parent.database_chatgpt_button.setText("")  
        parent.database_chatgpt_button.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '..', 'assets', 'chatgpt_logo.png')))
        parent.database_chatgpt_button.setIconSize(QSize(19, 19))  
        

        # 리스트 위젯의 모든 항목 가져오기
        for index in range(parent.listWidget.count()):
            item = parent.listWidget.item(index)
            if item.text() == "SETTING":
                # SETTING 항목에 아이콘 추가 및 텍스트 제거
                item.setIcon(QIcon(iconPath))
                item.setText("")  # 텍스트 제거

        # 아이콘 크기 설정
        parent.listWidget.setIconSize(QSize(25, 25))  # 아이콘 크기를 64x64로 설정
    except Exception as e:
        print(traceback.format_exc())

def initStatusbar(parent):
    # 상태 표시줄 생성
    parent.statusbar = QStatusBar()
    parent.setStatusBar(parent.statusbar)

    parent.leftLabel = ClickableLabel('  ' + f'Version {VERSION}')
    parent.leftLabel.clicked.connect(lambda: AboutDialog(VERSION, "light" if get_setting("Theme") == "default" else "dark", parent).exec())
    parent.rightLabel = ClickableLabel('')
    parent.rightLabel.clicked.connect(lambda: showActiveThreadsDialog())
        
    parent.leftLabel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    parent.rightLabel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    parent.leftLabel.setToolTip("새 버전 확인을 위해 Ctrl+U")
    parent.leftLabel.setAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    parent.rightLabel.setToolTip("실행 중인 작업 보기")
    parent.rightLabel.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    parent.statusbar.addPermanentWidget(parent.leftLabel, 1)
    parent.statusbar.addPermanentWidget(parent.rightLabel, 1)

def getVersionInfo(version):
    newestVersion = Request('get', f'/board/version/{version}').json()['data']
    return newestVersion

def checkNewVersion():
    newestVersion = Request('get', '/board/version/newest').json()['data']
    currentVersion = version.parse(VERSION)
    newVersion = version.parse(newestVersion[0])
    return newestVersion if currentVersion < newVersion else None

def checkNewPost(parent):
    if len(parent.managerBoardObj.origin_post_data) == 0:
        return False
    new_post_uid = parent.managerBoardObj.origin_post_data[0]['uid']
    new_post_writer = parent.managerBoardObj.origin_post_data[0]['writerName']
    old_post_uid = get_setting('OldPostUid')
    
    if new_post_uid == old_post_uid:
        return False
    elif old_post_uid == 'default':
        set_setting('OldPostUid', new_post_uid)
        return False
    elif new_post_uid != old_post_uid and parent.user != new_post_writer:
        set_setting('OldPostUid', new_post_uid)
        return True

def checkNetwork(parent):
    while True:
        try:
            response = requests.get("https://www.google.com/generate_204", timeout=2)
            break
        except requests.RequestException:
            reply = QMessageBox.question(parent, "Internet Connection Error",
                                            "인터넷에 연결되어 있지 않습니다\n\n인터넷 연결 후 재시도해주십시오\n\n재시도하시겠습니까?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                continue
            else:
                parent.force_quit()
    while True:
        try:
            response = requests.get(f"{MANAGER_SERVER_API}/ping/", timeout=2)
            response.raise_for_status()
            return True
        except requests.RequestException:
            reply = QMessageBox.question(parent, "서버 연결 실패",
                                            f"서버에 연결할 수 없습니다\n\n관리자에게 문의하십시오\n\n재시도하시겠습니까?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                continue
            else:
                parent.force_quit()
