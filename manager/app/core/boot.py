import os
import socket
import traceback
from libs.console import openConsole, closeConsole

import requests
from packaging import version

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QCursor, QShortcut
from PySide6.QtWidgets import QStatusBar, QLabel, QInputDialog, QMessageBox

from config import ASSETS_PATH, VERSION, MANAGER_SERVER_API
from ui.status import printStatus
from services.api import Request, get_api_headers
from core.setting import get_setting, set_setting
from services.auth import checkPassword
from ui.status import showActiveThreadsDialog
from windows.splash_window import AboutDialog

class ClickableLabel(QLabel):
    clicked = Signal()  # 클릭 시그널 정의

    def mousePressEvent(self, event):
        self.clicked.emit()  # 클릭되면 시그널 발생
        super().mousePressEvent(event)

def loginProgram(parent):
    try:
        parent.userDevice = socket.gethostname()

        # 이전에 발급된 토큰이 있는지 확인
        saved_token = get_setting('auth_token')

        if saved_token:
            res = requests.get(
                f"{MANAGER_SERVER_API}/auth/login", headers=get_api_headers())
            if res.status_code == 200:
                userData = res.json()['user']
                parent.user = userData['name']
                parent.userUid = userData['uid']
                parent.usermail = userData['email']
                return True

        # 사용자 이름 입력 대화
        parent.closeBootscreen()
        printStatus(parent, "로그인 중...")

        inputDialogId = QInputDialog(parent)
        inputDialogId.setWindowTitle('Login')
        inputDialogId.setLabelText('User Name:')
        inputDialogId.resize(300, 200)
        ok = inputDialogId.exec()
        userName = inputDialogId.textValue()

        if not ok:
            QMessageBox.warning(parent, 'Program Shutdown', '프로그램을 종료합니다')
            return False

        parent.user = userName

        res = requests.get(f"{MANAGER_SERVER_API}/auth/request",
                            params={"name": parent.user}).json()
        printStatus(parent)
        QMessageBox.information(parent, "Information",
                                f"{parent.user}님의 메일로 인증번호가 전송되었습니다\n\n"
                                "인증번호를 확인 후 입력하십시오")

        ok, password = checkPassword(parent, string="메일 인증번호")
        if not ok:
            QMessageBox.warning(parent, 'Error', '프로그램을 종료합니다')
            return False

        res = requests.post(f"{MANAGER_SERVER_API}/auth/verify",
                            params={"name": parent.user, "code": password, "device": parent.userDevice}).json()
        userData = res['user']
        access_token = res['access_token']

        parent.user = userData['name']
        parent.usermail = userData['email']
        parent.userUid = userData['uid']
        set_setting('auth_token', access_token)

    except Exception:
        parent.closeBootscreen()
        QMessageBox.critical(parent, "Error",
                                f"오류가 발생했습니다.\n\nError Log: {traceback.format_exc()}")
        return False

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
