import os
import socket
import traceback

import requests
from packaging import version

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QStatusBar, QLabel, QInputDialog, QShortcut, QMessageBox
)

from config import ASSETS_PATH, VERSION, MANAGER_SERVER_API
from ui.status import printStatus
from services.api import Request, api_headers
from core.setting import get_setting, set_setting
from services.auth import checkPassword


def loginProgram(parent):
    try:
        parent.userDevice = socket.gethostname()

        # 이전에 발급된 토큰이 있는지 확인
        saved_token = get_setting('auth_token')

        if saved_token:
            res = requests.get(
                f"{MANAGER_SERVER_API}/auth/login", headers=api_headers)
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
        ok = inputDialogId.exec_()
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
        """리스트 위젯의 특정 항목에만 아이콘 추가 및 텍스트 제거"""

        iconPath = os.path.join(ASSETS_PATH, 'setting.png')

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

    parent.leftLabel = QLabel('  ' + f'Version {VERSION}')
    parent.rightLabel = QLabel('')

    parent.leftLabel.setToolTip("새 버전 확인을 위해 Ctrl+U")
    parent.rightLabel.setToolTip("상태표시줄")
    parent.leftLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    parent.rightLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    parent.statusbar.addPermanentWidget(parent.leftLabel, 1)
    parent.statusbar.addPermanentWidget(parent.rightLabel, 1)

def initShortcut(parent):
    parent.ctrld = QShortcut(QKeySequence("Ctrl+D"), parent)
    parent.ctrls = QShortcut(QKeySequence("Ctrl+S"), parent)
    parent.ctrlv = QShortcut(QKeySequence("Ctrl+V"), parent)
    parent.ctrlu = QShortcut(QKeySequence("Ctrl+U"), parent)
    parent.ctrll = QShortcut(QKeySequence("Ctrl+L"), parent)
    parent.ctrla = QShortcut(QKeySequence("Ctrl+A"), parent)
    parent.ctrli = QShortcut(QKeySequence("Ctrl+I"), parent)
    parent.ctrle = QShortcut(QKeySequence("Ctrl+E"), parent)
    parent.ctrlr = QShortcut(QKeySequence("Ctrl+R"), parent)
    parent.ctrlk = QShortcut(QKeySequence("Ctrl+K"), parent)
    parent.ctrlm = QShortcut(QKeySequence("Ctrl+M"), parent)
    parent.ctrlp = QShortcut(QKeySequence("Ctrl+P"), parent)
    parent.ctrlc = QShortcut(QKeySequence("Ctrl+C"), parent)
    parent.ctrlq = QShortcut(QKeySequence("Ctrl+Q"), parent)
    parent.ctrlpp = QShortcut(QKeySequence("Ctrl+Shift+P"), parent)

    parent.cmdd = QShortcut(QKeySequence("Ctrl+ㅇ"), parent)
    parent.cmds = QShortcut(QKeySequence("Ctrl+ㄴ"), parent)
    parent.cmdv = QShortcut(QKeySequence("Ctrl+ㅍ"), parent)
    parent.cmdu = QShortcut(QKeySequence("Ctrl+ㅕ"), parent)
    parent.cmdl = QShortcut(QKeySequence("Ctrl+ㅣ"), parent)
    parent.cmda = QShortcut(QKeySequence("Ctrl+ㅁ"), parent)
    parent.cmdi = QShortcut(QKeySequence("Ctrl+ㅑ"), parent)
    parent.cmde = QShortcut(QKeySequence("Ctrl+ㄷ"), parent)
    parent.cmdr = QShortcut(QKeySequence("Ctrl+ㄱ"), parent)
    parent.cmdk = QShortcut(QKeySequence("Ctrl+ㅏ"), parent)
    parent.cmdm = QShortcut(QKeySequence("Ctrl+ㅡ"), parent)
    parent.cmdp = QShortcut(QKeySequence("Ctrl+ㅔ"), parent)
    parent.cmdc = QShortcut(QKeySequence("Ctrl+ㅊ"), parent)
    parent.cmdq = QShortcut(QKeySequence("Ctrl+ㅂ"), parent)
    parent.cmdpp = QShortcut(QKeySequence("Ctrl+Shift+ㅔ"), parent)

    parent.ctrlu.activated.connect(lambda: parent.updateProgram(sc=True))
    parent.ctrlq.activated.connect(lambda: parent.close())
    parent.ctrlp.activated.connect(lambda: parent.developerMode(True))
    parent.ctrlpp.activated.connect(lambda: parent.developerMode(False))

    parent.cmdu.activated.connect(lambda: parent.updateProgram(sc=True))
    parent.cmdq.activated.connect(lambda: parent.close())
    parent.cmdp.activated.connect(lambda: parent.developerMode(True))
    parent.cmdpp.activated.connect(lambda: parent.developerMode(False))
    
def checkNewVersion(parent):
    newestVersion = Request('get', '/board/version/newest').json()['data']
    currentVersion = version.parse(VERSION)
    parent.newVersion = version.parse(newestVersion)
    return True if currentVersion < parent.newVersion else False

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
            # Google을 기본으로 확인 (URL은 다른 사이트로 변경 가능)
            response = requests.get("http://www.google.com", timeout=5)
            break
        except requests.ConnectionError:
            printStatus(parent)
            parent.closeBootscreen()
            reply = QMessageBox.question(parent, "Internet Connection Error",
                                            "인터넷에 연결되어 있지 않습니다\n\n인터넷 연결 후 재시도해주십시오\n\n재시도하시겠습니까?",
                                            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                continue
            else:
                os._exit(0)

    while True:
        try:
            # FastAPI 서버의 상태를 확인하는 핑 API 또는 기본 경로 사용
            response = requests.get(f"{MANAGER_SERVER_API}/ping", timeout=5)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            printStatus(parent)
            parent.closeBootscreen()
            reply = QMessageBox.question(parent, "서버 연결 실패",
                                            f"서버에 연결할 수 없습니다.\n\n관리자에게 문의하십시오\n\n재시도하시겠습니까?",
                                            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                continue
            else:
                os._exit(0)
