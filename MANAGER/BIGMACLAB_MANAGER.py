##############################################################################################################
# Project Name: BIGMACLAB MANAGER
# Version: 2.X.X
# Developer: Moon Yo Jun (POSTECH, Computer Science and Engineering)
# GitHub: https://github.com/yojun313
# Date Created: 2024-08-03
# Released: 2024-08-05
# Download: https://knpu.re.kr/tool
# Affiliation: BIGMACLAB(https://knpu.re.kr), Korea National Police University, Asan, Chungcheongnam-do
#
# Contact:
# - Email: yojun313@postech.ac.kr / moonyojun@gmail.com
# - Phone: +82-10-4072-9190
##############################################################################################################pip

VERSION = '2.7.1'

import os
import platform
from PyQt5.QtWidgets import QApplication
from Manager_SplashDialog import SplashDialog, theme_option
from PyQt5.QtCore import QCoreApplication, Qt, QSettings
from PyQt5.QtGui import QFont
from PyQt5.QtWebEngineWidgets import QWebEngineView

os.environ.update({
    "QT_DEVICE_PIXEL_RATIO": "0",
    "QT_AUTO_SCREEN_SCALE_FACTOR": "1",
    "QT_SCREEN_SCALE_FACTORS": "1",
    "QT_SCALE_FACTOR": "1"
})

# High DPI 스케일링 활성화
QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

app = QApplication([])
app.setApplicationDisplayName("MANAGER")
app.setApplicationName("BIGMACLAB_MANAGER")
app.setApplicationVersion(VERSION)
app.setOrganizationName("BIGMACLAB")
app.setOrganizationDomain("https://knpu.re.kr")

# 기본 폰트 설정 및 힌팅 설정
font = QFont(os.path.join(os.path.dirname(__file__), 'source', 'malgun.ttf'))
font.setHintingPreference(QFont.PreferNoHinting)
font.setStyleStrategy(QFont.PreferAntialias)  # 안티앨리어싱 활성화
app.setFont(font)

settings = QSettings("BIGMACLAB", "BIGMACLAB_MANAGER")
if platform.system() == 'Windows':
    theme = settings.value('Theme', 'default')
else:
    def is_mac_dark_mode():
        """
        macOS 시스템 설정에서 다크 모드 활성화 여부 확인
        """
        try:
            import subprocess
            # macOS 명령어를 사용하여 다크 모드 상태를 가져옴
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # "Dark"가 반환되면 다크 모드가 활성화됨
            return "Dark" in result.stdout
        except Exception as e:
            # 오류가 발생하면 기본적으로 라이트 모드로 간주
            return False
    theme = 'dark' if is_mac_dark_mode() else 'default'
    settings.setValue('Theme', theme)

app.setStyleSheet(theme_option[theme])

# 로딩 다이얼로그 표시
splashDialog = SplashDialog(version=VERSION, theme=theme)
splashDialog.show()

splashDialog.updateStatus("Loading System Libraries")
import os
import sys
import json
import subprocess
from getmac import get_mac_address
from openai import OpenAI
from mySQL import mySQL
from datetime import datetime
import requests
from packaging import version
import pandas as pd
from pathlib import Path
import socket
import gc
import traceback
import requests
import re
import logging
import shutil
import requests

splashDialog.updateStatus("Loading GUI Libraries")
from Manager_Settings import Manager_Setting
from Manager_ToolModule import ToolModule
from Manager_Database import Manager_Database
from Manager_Web import Manager_Web
from Manager_Board import Manager_Board
from Manager_User import Manager_User
from Manager_Analysis import Manager_Analysis
from Manager_Console import openConsole, closeConsole
from PyQt5 import uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QShortcut, QVBoxLayout, QTextEdit, QHeaderView, \
    QHBoxLayout, QLabel, QStatusBar, QDialog, QInputDialog, QLineEdit, QMessageBox, QFileDialog, QSizePolicy, \
    QPushButton, QMainWindow, QSpacerItem, QAbstractItemView
from PyQt5.QtCore import Qt, QCoreApplication, QObject, QEvent, QSize, QModelIndex, QEventLoop
from PyQt5.QtGui import QKeySequence, QIcon

DB_IP = '121.152.225.232'
LOCAL_IP = '192.168.0.3'

class MainWindow(QMainWindow):

    def __init__(self, splashDialog):
        try:
            self.server_api = "http://localhost:8000/api"
            self.server_api = "https://manager.knpu.re.kr/api"
            self.versionNum = VERSION
            self.version = f'Version {self.versionNum}'
            self.splashDialog = splashDialog

            self.toolmodule = ToolModule()

            super(MainWindow, self).__init__()
            uiPath = os.path.join(os.path.dirname(__file__), 'source', 'BIGMACLAB_MANAGER_GUI.ui')
            iconPath = os.path.join(os.path.dirname(__file__), 'source', 'exe_icon.png')

            uic.loadUi(uiPath, self)
            self.initSettings()
            self.initListWidget()
            self.updateStyleHtml()
            self.setWindowTitle("MANAGER")  # 창의 제목 설정
            self.setWindowIcon(QIcon(iconPath))

            self.resize(1400, 1000)

            self.initStatusbar()
            self.decryptProcess()

            setUpLogging()
            self.eventLogger = EventLogger()
            self.installEventFilter(self)

            def loadProgram():
                try:
                    self.listWidget.setCurrentRow(0)
                    if self.SETTING['BootTerminal'] == 'on':
                        openConsole("Boot Process")
                    self.startTime = datetime.now()
                    self.gpt_api_key = self.SETTING['GPT_Key']
                    self.CONFIG = {
                        'Logging': 'On'
                    }
                    self.checkNetwork()
                    self.listWidget.currentRowChanged.connect(self.display)

                    if platform.system() == "Windows":
                        localAppdataPath = os.getenv("LOCALAPPDATA")
                        desktopPath = os.path.join(os.getenv("USERPROFILE"), "Desktop")

                        self.programDirectory = os.path.join(localAppdataPath, "MANAGER")
                        self.localDirectory = "C:/BIGMACLAB_MANAGER"
                        if not os.path.exists(self.localDirectory):
                            os.makedirs(self.localDirectory)
                    else:
                        self.programDirectory = os.path.dirname(__file__)
                        self.localDirectory = '/Users/yojunsmacbookprp/Documents/BIGMACLAB_MANAGER'
                        if not os.path.exists(self.localDirectory):
                            os.makedirs(self.localDirectory)

                    self.readmePath = os.path.join(self.localDirectory, 'README.txt')
                    if not Path(self.readmePath).exists():
                        with open(self.readmePath, "w", encoding="utf-8", errors="ignore") as txt:
                            text = (
                                "[ BIGMACLAB MANAGER README ]\n\n\n"
                                "C:/BIGMACLAB_MANAGER is default directory folder of this program. This folder is automatically built by program.\n\n"
                                "All files made in this program will be saved in this folder without any change.\n\n\n\n"
                                "< Instructions >\n\n"
                                "- MANAGER: https://knpu.re.kr/tool\n"
                                "- KEMKIM: https://knpu.re.kr/kemkim"
                            )
                            txt.write(text)

                    if os.path.isdir(self.localDirectory) == False:
                        os.mkdir(self.localDirectory)

                    DB_ip = DB_IP
                    if socket.gethostname() in ['DESKTOP-502IMU5', 'DESKTOP-0I9OM9K', 'BigMacServer', 'BIGMACLAB-Z8']:
                        DB_ip = LOCAL_IP

                    self.networkText = (
                        "\n\n[ DB 접속 반복 실패 시... ]\n"
                        "\n1. Wi-Fi 또는 유선 네트워크가 정상적으로 동작하는지 확인하십시오"
                        "\n2. 네트워크 호환성에 따라 DB 접속이 불가능한 경우가 있습니다. 다른 네트워크 연결을 시도해보십시오\n"
                    )
                    
                    # User Checking & Login Process
                    print("\nI. Checking User... ", end='')
                    self.splashDialog.updateStatus("Checking User")
                    if self.loginProgram() == False:
                        os._exit(0)

                    # Loading User info from DB
                    while True:
                        try:
                            self.mySQLObj = mySQL(host=DB_ip, user='admin', password=self.public_password, port=3306)
                            print("\nII. Loading Boards from DB... ", end='')
                            self.splashDialog.updateStatus("Loading User Info from DB")
                            if self.mySQLObj.showAllDB() == []:
                                raise
                            # DB 불러오기
                            self.managerBoardObj = Manager_Board(self)
                            self.managerUserObj = Manager_User(self)
                            self.userList = self.managerUserObj.userList  # Device Table 유저 리스트
                            self.deviceList = self.managerUserObj.deviceList
                            self.macList = self.managerUserObj.macList
                            self.userPushOverKeyList = self.managerUserObj.userKeyList
                            print("Done")
                            break
                        except Exception as e:
                            print("Failed")
                            print(traceback.format_exc())
                            self.closeBootscreen()
                            self.printStatus()
                            reply = QMessageBox.warning(self, 'Connection Failed',
                                                        f"DB 서버 접속에 실패했습니다\n네트워크 점검이 필요합니다{self.networkText}\n다시 시도하시겠습니까?",
                                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                            if reply == QMessageBox.Yes:
                                self.printStatus("접속 재시도 중...")
                                continue
                            else:
                                os._exit(0)
                                
                    self.splashDialog.updateStatus("Checking New Version")
                    print("\nIII. Checking New Version... ", end='')
                    if self.checkNewVersion() == True:
                        self.closeBootscreen()
                        self.updateProgram(auto=self.SETTING['AutoUpdate'])

                    # Loading Data from DB & Making object
                    while True:
                        try:
                            print("\nIV. Loading Data from DB... ", end='')
                            self.splashDialog.updateStatus("Loading Data from DB")
                            self.managerUserObj.makeUserDBLayout()
                            self.DB = self.updateDB()
                            self.managerDatabaseObj = Manager_Database(self)
                            self.managerWebObj = Manager_Web(self)
                            self.managerAnalysisObj = Manager_Analysis(self)
                            print("Done")
                            break
                        except Exception as e:
                            print("Failed")
                            print(traceback.format_exc())
                            self.closeBootscreen()
                            self.printStatus()
                            reply = QMessageBox.warning(self, 'Connection Failed',
                                                        f"DB 서버 접속에 실패했습니다\n네트워크 점검이 필요합니다{self.networkText}\n\n다시 시도하시겠습니까?",
                                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                            if reply == QMessageBox.Yes:
                                self.printStatus("접속 재시도 중...")
                                continue
                            else:
                                os._exit(0)

                    self.splashDialog.updateStatus(f"안녕하세요, {self.user}님!")
                    newpost = self.checkNewPost()
                    print(f"\n{self.user}님 환영합니다!")

                    self.initShortcut()
                    self.managerDatabaseObj.setDatabaseShortcut()
                    self.userLogging(f'Booting ({self.getUserLocation()})', booting=True, force=True)
                    self.initConfiguration()

                    closeConsole()
                    self.closeBootscreen()

                    if self.SETTING['ScreenSize'] == 'max':
                        self.showMaximized()
                    self.printStatus(f"{self.fullStorage} GB / 2 TB")

                    # After Booting

                    if newpost == True:
                        reply = QMessageBox.question(self, "New Post", "새로운 게시물이 업로드되었습니다\n\n확인하시겠습니까?",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                        if reply == QMessageBox.Yes:
                            self.managerBoardObj.viewPost(row=1)

                except Exception as e:
                    print("Failed")
                    print(traceback.format_exc())
                    self.closeBootscreen()
                    self.printStatus()
                    msg = f'[ Admin CRITICAL Notification ]\n\nThere is Error in MANAGER Booting\n\nError Log: {traceback.format_exc()}'
                    self.sendPushOver(msg, self.admin_pushoverkey)
                    QMessageBox.critical(self, "Error", f"부팅 과정에서 오류가 발생했습니다\n\nError Log: {traceback.format_exc()}")
                    QMessageBox.information(self, "Information", f"관리자에게 에러 상황과 로그가 전달되었습니다\n\n프로그램을 종료합니다")
                    os._exit(0)

            loadProgram()

        except Exception as e:
            self.closeBootscreen()
            openConsole()
            print(traceback.format_exc())

    def __getattr__(self, name):
        # ClassA에 속성이 있으면 반환
        return getattr(self.toolmodule, name)

    ################################## Booting ##################################

    def initListWidget(self):
        try:
            """리스트 위젯의 특정 항목에만 아이콘 추가 및 텍스트 제거"""

            iconPath = os.path.join(os.path.dirname(__file__), 'source', 'setting.png')

            # 리스트 위젯의 모든 항목 가져오기
            for index in range(self.listWidget.count()):
                item = self.listWidget.item(index)
                if item.text() == "SETTING":
                    # SETTING 항목에 아이콘 추가 및 텍스트 제거
                    item.setIcon(QIcon(iconPath))
                    item.setText("")  # 텍스트 제거

            # 아이콘 크기 설정
            self.listWidget.setIconSize(QSize(25, 25))  # 아이콘 크기를 64x64로 설정
        except Exception as e:
            print(traceback.format_exc())

    def initSettings(self):
        try:
            self.settings = QSettings("BIGMACLAB", "BIGMACLAB_MANAGER")
            defaults = {
                'Theme': 'default',
                'ScreenSize': 'default',
                'OldPostUid': 'default',
                'AutoUpdate': 'default',
                'MyDB': 'default',
                'GPT_Key': 'default',
                'DB_Refresh': 'default',
                'BootTerminal': 'default',
                'DBKeywordSort': 'default',
                'ProcessConsole': 'default',
                'LLM_model': 'ChatGPT',
                'LLM_model_name': 'ChatGPT 4'
            }

            # 설정 초기화
            for key, value in defaults.items():
                if self.settings.value(key) is None:  # 값이 없을 경우 기본값 설정
                    self.settings.setValue(key, value)

            self.SETTING = {
                'Theme': self.settings.value("Theme", "default"),
                'ScreenSize': self.settings.value("ScreenSize", "default"),
                'OldPostUid': self.settings.value("OldPostUid", "default"),
                'AutoUpdate': self.settings.value("AutoUpdate", "default"),
                'MyDB': self.settings.value("MyDB", "default"),
                'GPT_Key': self.settings.value("GPT_Key", "default"),
                'DB_Refresh': self.settings.value("DB_Refresh", "default"),
                'BootTerminal': self.settings.value("BootTerminal", "default"),
                'DBKeywordSort': self.settings.value("DBKeywordSort", "default"),
                'ProcessConsole': self.settings.value("ProcessConsole", "default"),
                'LLM_model': self.settings.value("LLM_model", "ChatGPT"),
                'LLM_model_name': 'ChatGPT 4'
            }

        except Exception as e:
            print(traceback.format_exc())
            self.SETTING = defaults

    def initConfiguration(self):
        try:
            self.mySQLObj.connectDB('bigmaclab_manager_db')
            configDF = self.mySQLObj.TableToDataframe('configuration')
            self.CONFIG = dict(zip(configDF[configDF.columns[1]], configDF[configDF.columns[2]]))

            # LLM 모델 이름 설정
            self.LLM_list = json.loads(self.CONFIG['LLM_model'])
            self.SETTING['LLM_model_name'] = self.LLM_list[self.settings.value('LLM_model')]

        except Exception as e:
            print(traceback.format_exc())

    def initStatusbar(self):
        # 상태 표시줄 생성
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.leftLabel = QLabel('  ' + self.version)
        self.rightLabel = QLabel('')

        self.leftLabel.setToolTip("새 버전 확인을 위해 Ctrl+U")
        self.rightLabel.setToolTip("상태표시줄")
        self.leftLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.rightLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusbar.addPermanentWidget(self.leftLabel, 1)
        self.statusbar.addPermanentWidget(self.rightLabel, 1)

    def initShortcut(self):
        self.ctrld = QShortcut(QKeySequence("Ctrl+D"), self)
        self.ctrls = QShortcut(QKeySequence("Ctrl+S"), self)
        self.ctrlv = QShortcut(QKeySequence("Ctrl+V"), self)
        self.ctrlu = QShortcut(QKeySequence("Ctrl+U"), self)
        self.ctrll = QShortcut(QKeySequence("Ctrl+L"), self)
        self.ctrla = QShortcut(QKeySequence("Ctrl+A"), self)
        self.ctrli = QShortcut(QKeySequence("Ctrl+I"), self)
        self.ctrle = QShortcut(QKeySequence("Ctrl+E"), self)
        self.ctrlr = QShortcut(QKeySequence("Ctrl+R"), self)
        self.ctrlk = QShortcut(QKeySequence("Ctrl+K"), self)
        self.ctrlm = QShortcut(QKeySequence("Ctrl+M"), self)
        self.ctrlp = QShortcut(QKeySequence("Ctrl+P"), self)
        self.ctrlc = QShortcut(QKeySequence("Ctrl+C"), self)
        self.ctrlq = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.ctrlpp = QShortcut(QKeySequence("Ctrl+Shift+P"), self)

        self.cmdd = QShortcut(QKeySequence("Ctrl+ㅇ"), self)
        self.cmds = QShortcut(QKeySequence("Ctrl+ㄴ"), self)
        self.cmdv = QShortcut(QKeySequence("Ctrl+ㅍ"), self)
        self.cmdu = QShortcut(QKeySequence("Ctrl+ㅕ"), self)
        self.cmdl = QShortcut(QKeySequence("Ctrl+ㅣ"), self)
        self.cmda = QShortcut(QKeySequence("Ctrl+ㅁ"), self)
        self.cmdi = QShortcut(QKeySequence("Ctrl+ㅑ"), self)
        self.cmde = QShortcut(QKeySequence("Ctrl+ㄷ"), self)
        self.cmdr = QShortcut(QKeySequence("Ctrl+ㄱ"), self)
        self.cmdk = QShortcut(QKeySequence("Ctrl+ㅏ"), self)
        self.cmdm = QShortcut(QKeySequence("Ctrl+ㅡ"), self)
        self.cmdp = QShortcut(QKeySequence("Ctrl+ㅔ"), self)
        self.cmdc = QShortcut(QKeySequence("Ctrl+ㅊ"), self)
        self.cmdq = QShortcut(QKeySequence("Ctrl+ㅂ"), self)
        self.cmdpp = QShortcut(QKeySequence("Ctrl+Shift+ㅔ"), self)

        self.ctrlu.activated.connect(lambda: self.updateProgram(sc=True))
        self.ctrlq.activated.connect(lambda: self.close())
        self.ctrlp.activated.connect(lambda: self.developerMode(True))
        self.ctrlpp.activated.connect(lambda: self.developerMode(False))

        self.cmdu.activated.connect(lambda: self.updateProgram(sc=True))
        self.cmdq.activated.connect(lambda: self.close())
        self.cmdp.activated.connect(lambda: self.developerMode(True))
        self.cmdpp.activated.connect(lambda: self.developerMode(False))

    def closeBootscreen(self):
        try:
            self.splashDialog.accept()  # InfoDialog 닫기
            self.show()  # MainWindow 표시
        except:
            print(traceback.format_exc())

    def loginProgram(self):
        try:
            self.userDevice = socket.gethostname()

            # 이전에 발급된 토큰이 있는지 확인
            saved_token = self.settings.value('auth_token', '')
            if saved_token:
                headers = {"Authorization": f"Bearer {saved_token}"}
                res = requests.get(f"{self.server_api}/auth/login", headers=headers)
                if res.status_code == 200:
                    userData = res.json()['user']
                    self.user = userData['name']
                    self.userUid = userData['uid']
                    self.usermail = userData['email']
                    return True

            # 사용자 이름 입력 대화
            self.closeBootscreen()
            self.printStatus()

            inputDialogId = QInputDialog(self)
            inputDialogId.setWindowTitle('Login')
            inputDialogId.setLabelText('User Name:')
            inputDialogId.resize(300, 200)
            ok = inputDialogId.exec_()
            userName = inputDialogId.textValue()

            if not ok:
                QMessageBox.warning(self, 'Program Shutdown', '프로그램을 종료합니다')
                return False

            self.user = userName
                        
            res = requests.get(f"{self.server_api}/auth/request", params={"name": self.user}).json()
            self.printStatus()
            QMessageBox.information(self, "Information",
                                    f"{self.user}님의 메일로 인증번호가 전송되었습니다\n\n"
                                    "인증번호를 확인 후 입력하십시오")

            ok, password = self.checkPassword(string="메일 인증번호")
            if not ok:
                QMessageBox.warning(self, 'Error', '프로그램을 종료합니다')
                return False

            res = requests.post(f"{self.server_api}/auth/verify",
                                params={"name": self.user, "code": password, "device": self.userDevice}).json()
            userData = res['user']
            access_token = res['access_token']
            
            self.user = userData['name']
            self.usermail = userData['email']
            self.userUid = userData['uid']
            self.settings.setValue('auth_token', access_token)

        except Exception:
            self.closeBootscreen()
            QMessageBox.critical(self, "Error",
                                f"오류가 발생했습니다.\n\nError Log: {traceback.format_exc()}")
            return False
         
    def updateProgram(self, sc=False, auto=False):
        try:
            if platform.system() != "Windows":
                return
            def downloadFile(download_url, local_filename):
                response = requests.get(download_url, stream=True)
                totalSize = int(response.headers.get('content-length', 0))  # 파일의 총 크기 가져오기
                chunkSize = 8192  # 8KB씩 다운로드
                downloadSize = 0  # 다운로드된 크기 초기화

                with open(local_filename, 'wb') as f:
                    for chunk in response.iter_content(chunkSize=chunkSize):
                        if chunk:  # 빈 데이터 확인
                            f.write(chunk)
                            downloadSize += len(chunk)
                            percent_complete = (downloadSize / totalSize) * 100
                            print(f"\r{self.newVersion} Download: {percent_complete:.0f}%", end='')  # 퍼센트 출력

                print("\nDownload Complete")
                closeConsole()

            def update_process():
                openConsole("Version Update Process")
                msg = (
                    "[ Admin Notification ]\n\n"
                    f"{self.user} updated {currentVersion} -> {self.newVersion}\n\n{self.getUserLocation()}"
                )
                self.sendPushOver(msg, self.admin_pushoverkey)
                self.userLogging(f'Program Update ({currentVersion} -> {self.newVersion})', force=True)

                self.printStatus("버전 업데이트 중...")
                import subprocess
                downloadFile_path = os.path.join('C:/Temp', f"BIGMACLAB_MANAGER_{self.newVersion}.exe")
                downloadFile(f"https://knpu.re.kr:90/download/BIGMACLAB_MANAGER_{self.newVersion}.exe",
                              downloadFile_path)
                subprocess.Popen([downloadFile_path], shell=True)
                closeConsole()
                os._exit(0)

            # New version check
            currentVersion = version.parse(self.versionNum)
            self.newVersion = version.parse(self.managerBoardObj.checkNewVersion())
            if currentVersion < self.newVersion:
                if auto == 'auto':
                    self.closeBootscreen()
                    update_process()
                self.managerBoardObj.refreshVersionBoard()

                version_info_html = self.style_html + f"""
                    <table>
                        <tr><th>Item</th><th>Details</th></tr>
                        <tr><td><b>Version Num:</b></td><td>{self.managerBoardObj.version_data_for_table[0][0]}</td></tr>
                        <tr><td><b>Release Date:</b></td><td>{self.managerBoardObj.version_data_for_table[0][1]}</td></tr>
                        <tr><td><b>ChangeLog:</b></td><td>{self.managerBoardObj.version_data_for_table[0][2]}</td></tr>
                        <tr><td><b>Version Features:</b></td><td>{self.managerBoardObj.version_data_for_table[0][3]}</td></tr>
                        <tr><td><b>Version Status:</b></td><td>{self.managerBoardObj.version_data_for_table[0][4]}</td></tr>
                    </table>
                """

                dialog = QDialog(self)
                dialog.setWindowTitle(f"New Version Released")
                dialog.resize(350, 250)

                layout = QVBoxLayout()

                label = QLabel()
                label.setText(version_info_html)
                label.setWordWrap(True)
                label.setTextFormat(Qt.RichText)  # HTML 렌더링

                layout.addWidget(label, alignment=Qt.AlignHCenter)

                button_layout = QHBoxLayout()  # 수평 레이아웃

                # confirm_button과 cancel_button의 크기가 창의 너비에 맞게 비례하도록 설정
                confirm_button = QPushButton("Update")
                cancel_button = QPushButton("Cancel")

                # 버튼 클릭 이벤트 연결
                confirm_button.clicked.connect(dialog.accept)
                cancel_button.clicked.connect(dialog.reject)

                # 버튼 사이에 간격 추가
                button_layout.addWidget(confirm_button)
                button_layout.addWidget(cancel_button)

                layout.addLayout(button_layout)  # 버튼 레이아웃을 메인 레이아웃에 추가

                dialog.setLayout(layout)

                # 대화상자 실행
                if dialog.exec_() == QDialog.Accepted:
                    update_process()
                else:
                    QMessageBox.information(self, "Information", 'Ctrl+U 단축어로 프로그램 실행 중 업데이트 가능합니다')
                    return
            else:
                if sc == True:
                    reply = QMessageBox.question(self, "Reinstall", "현재 버전이 최신 버전입니다\n\n현재 버전을 재설치하시겠습니까?",
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        self.printStatus("버전 재설치 중...")
                        openConsole("Version Reinstall Process")
                        import subprocess
                        downloadFile_path = os.path.join('C:/Temp', f"BIGMACLAB_MANAGER_{self.newVersion}.exe")
                        downloadFile(f"https://knpu.re.kr:90/download/BIGMACLAB_MANAGER_{self.newVersion}.exe",
                                      downloadFile_path)
                        subprocess.Popen([downloadFile_path], shell=True)
                        closeConsole()
                        os._exit(0)
                    else:
                        return
                return
        except:
            print(traceback.format_exc())
            return

    def checkNewVersion(self):
        currentVersion = version.parse(self.versionNum)
        self.newVersion = version.parse(self.managerBoardObj.checkNewVersion())
        print("Done")
        if currentVersion < self.newVersion:
            return True
        else:
            return False

    def checkNewPost(self):
        print("\nV. Checking New Post... ", end='')
        if len(self.managerBoardObj.origin_post_data) == 0:
            return False
        new_post_uid = self.managerBoardObj.origin_post_data[0]['uid']
        new_post_writer = self.managerBoardObj.origin_post_data[0]['writerName']
        old_post_uid = self.SETTING['OldPostUid']
        print("Done")
        if new_post_uid == old_post_uid:
            return False
        elif old_post_uid == 'default':
            self.updateSettings('OldPostUid', new_post_uid)
            return False
        elif new_post_uid != old_post_uid and self.user != new_post_writer:
            self.updateSettings('OldPostUid', new_post_uid)
            return True

    def checkNetwork(self):
        while True:
            try:
                # Google을 기본으로 확인 (URL은 다른 사이트로 변경 가능)
                response = requests.get("http://www.google.com", timeout=5)
                break
            except requests.ConnectionError:
                self.printStatus()
                self.closeBootscreen()
                reply = QMessageBox.question(self, "Internet Connection Error",
                                             "인터넷에 연결되어 있지 않습니다\n\n인터넷 연결 후 재시도해주십시오\n\n재시도하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    continue
                else:
                    os._exit(0)
                    
        while True:
            try:
                # FastAPI 서버의 상태를 확인하는 핑 API 또는 기본 경로 사용
                response = requests.get(f"{self.server_api}/ping", timeout=5)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                self.printStatus()
                self.closeBootscreen()
                reply = QMessageBox.question(self, "서버 연결 실패",
                                            f"서버에 연결할 수 없습니다.\n\n관리자에게 문의하십시오\n\n재시도하시겠습니까?",
                                            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    continue
                else:
                    os._exit(0)

    def display(self, index):
        if index != 6:
            self.stackedWidget.setCurrentIndex(index)
        # self.updateProgram()
        # DATABASE
        if index == 0:
            self.managerDatabaseObj.setDatabaseShortcut()
            if self.SETTING['DB_Refresh'] == 'default':
                self.managerDatabaseObj.refreshDB()
            self.printStatus(f"{self.fullStorage} GB / 2 TB")
        # CRAWLER
        elif index == 1:
            self.initShortcutialize()
            self.printStatus(f"활성 크롤러 수: {self.activeCrawl}")
        # ANALYSIS
        elif index == 2:
            self.printStatus()
            self.managerAnalysisObj.analysis_shortcut_setting()
        # BOARD
        elif index == 3:
            self.managerBoardObj.setBoardShortcut()
            self.printStatus()
        # WEB
        elif index == 4:
            self.initShortcutialize()
            self.printStatus()
            #self.managerWebObj.web_open_webbrowser('https://knpu.re.kr', self.managerWebObj.web_web_layout)
        # USER
        elif index == 5:
            self.printStatus()
            self.managerUserObj.user_shortcut_setting()

        elif index == 6:
            self.userSettings()
            previous_index = self.stackedWidget.currentIndex()  # 현재 활성 화면의 인덱스
            self.listWidget.setCurrentRow(previous_index)  # 선택 상태를 이전 인덱스로 변경

        gc.collect()

    def makeFileFinder(self, main_window):
        class EmbeddedFileDialog(QFileDialog):
            def __init__(self, parent=None, localDirectory=None):
                super().__init__(parent)
                self.setFileMode(QFileDialog.ExistingFiles)
                self.setOptions(QFileDialog.DontUseNativeDialog)
                self.setNameFilters(
                    ["All Files (*.*)", "CSV Files (*.csv)", "Text Files (*.txt)", "Images (*.png *.jpg *.jpeg)"])
                self.currentChanged.connect(self.on_directory_change)
                self.accepted.connect(self.on_accepted)
                self.rejected.connect(self.on_rejected)
                self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.main = parent
                if localDirectory:
                    self.setDirectory(localDirectory)
                self.setup_double_click_event()

                # QTreeView 찾아서 헤더뷰 리사이즈 모드 설정
                # QFileDialog가 Detail 모드일 때 내부적으로 QTreeView를 사용하므로 findChildren 사용
                from PyQt5.QtWidgets import QTreeView, QHeaderView
                for treeview in self.findChildren(QTreeView):
                    # Size(1번 열)와 Kind(2번 열) 숨기기
                    treeview.setColumnHidden(1, True)  # Size 숨기기
                    treeview.setColumnHidden(2, True)  # Kind 숨기기
                    header = treeview.header()
                    # 파일명 컬럼(일반적으로 첫 번째 컬럼)만 크기 자동 조정
                    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                    # 나머지 컬럼들은 창 크기에 따라 비례적으로 늘어나도록 설정
                    for col in range(1, header.count()):
                        header.setSectionResizeMode(col, QHeaderView.Stretch)
            def setup_double_click_event(self):
                def handle_double_click(index: QModelIndex):
                    # 더블 클릭된 파일 경로 가져오기
                    file_path = self.selectedFiles()[0]  # 현재 선택된 파일
                    if file_path and os.path.isfile(file_path):  # 파일인지 확인
                        self.open_in_external_app(file_path)

                # QListView 또는 QTreeView 중 하나를 찾아서 더블 클릭 이벤트 연결
                for view in self.findChildren(QAbstractItemView):
                    view.doubleClicked.connect(handle_double_click)

            def open_in_external_app(self, file_path):
                try:
                    self.main.printStatus(f"{os.path.basename(file_path)} 여는 중...")
                    if os.name == 'nt':  # Windows
                        os.startfile(file_path)
                    elif os.name == 'posix':  # macOS, Linux
                        subprocess.run(["open" if os.uname().sysname == "Darwin" else "xdg-open", file_path])
                    self.main.printStatus()
                except Exception as e:
                    self.main.printStatus(f"파일 열기 실패")

            def on_directory_change(self, path):
                self.main.printStatus()

            def on_accepted(self):
                selected_files = self.selectedFiles()
                if selected_files:
                    self.selectFile(', '.join([os.path.basename(file) for file in selected_files]))
                if len(selected_files) == 0:
                    self.main.printStatus()
                else:
                    self.main.printStatus(f"파일 {len(selected_files)}개 선택됨")
                self.show()

            def on_rejected(self):
                self.show()

            def accept(self):
                selected_files = self.selectedFiles()
                if selected_files:
                    self.selectFile(', '.join([os.path.basename(file) for file in selected_files]))
                if len(selected_files) == 0:
                    self.main.printStatus()
                else:
                    self.main.printStatus(f"파일 {len(selected_files)}개 선택됨")
                self.show()

            def reject(self):
                self.show()

        return EmbeddedFileDialog(self, self.localDirectory)

    def Request(self, method, url, **kwargs):
        try:
            full_url = f"{self.server_api}/{url.lstrip('/')}"

            # 기본 헤더에 Authorization 추가
            self.api_headers = kwargs.get("headers", {})
            token = self.settings.value('auth_token', '')

            if token:
                self.api_headers["Authorization"] = f"Bearer {token}"
            kwargs["headers"] = self.api_headers  
            
            # 요청 메서드 분기
            method = method.lower()
            if method == 'get':
                response = requests.get(full_url, **kwargs)
            elif method == 'post':
                response = requests.post(full_url, **kwargs)
            elif method == 'put':
                response = requests.put(full_url, **kwargs)
            elif method == 'delete':
                response = requests.delete(full_url, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response

        except requests.exceptions.HTTPError as http_err:
            try:
                error_message = http_err.response.json().get("message", str(http_err))
            except Exception:
                error_message = str(http_err)
            raise Exception(f"[HTTP Error] {error_message}")
        except requests.exceptions.RequestException as err:
            raise Exception(f"[Request Failed] {str(err)}")


    
    #############################################################################

    def updateSettings(self, option_key, new_value):
        try:
            self.settings.setValue(option_key, new_value)  # 설정값 업데이트
            return True
        except Exception as e:
            print(traceback.format_exc())
            return False

    def userLogging(self, text='', booting=False, force=False):
        try:
            if (self.user == 'admin' and self.CONFIG['Logging'] == 'Off') or (self.CONFIG['Logging'] == 'Off' and force == False):
                return
            self.mySQLObj.connectDB(f'{self.user}_db')  # userDB 접속
            if booting == True:
                latest_record = self.mySQLObj.TableLastRow('manager_record')  # log의 마지막 행 불러옴
                # 'Date' 열을 datetime 형식으로 변환
                if latest_record != ():  # 테이블에 데이터가 있는 경우
                    # 테이블의 가장 마지막 행 데이터를 불러옴
                    latest_date = pd.to_datetime(latest_record[1])

                # 만약 테이블이 비어있는 경우
                else:
                    latest_date = None  # 최근 날짜를 None으로 설정

                # 오늘 날짜 가져오기
                today = pd.to_datetime(datetime.now().date())

                # 가장 최근 로그 날짜와 현재 날짜와 같은 경우
                if latest_date != today or latest_date is None:
                    self.mySQLObj.insertToTable('manager_record', [[str(datetime.now().date()), '', '', '']])
                    self.mySQLObj.commit()

            self.printStatus("Loading...")
            text = f'\n\n[{str(datetime.now().time())[:-7]}] : {text}'
            self.mySQLObj.updateTableCell('manager_record', -1, 'Log', text, add=True)
            self.printStatus()
        except Exception as e:
            print(traceback.format_exc())

    def userBugging(self, text=''):
        try:
            self.printStatus("Loading...")
            self.mySQLObj.connectDB(f'{self.user}_db')  # userDB 접속
            text = f'\n\n[{str(datetime.now().time())[:-7]}] : {text}'
            self.mySQLObj.updateTableCell('manager_record', -1, 'Bug', text, add=True)
            self.printStatus()
        except Exception as e:
            print(traceback.format_exc())

    def userSettings(self):
        try:
            self.userLogging(f'User Setting')
            dialog = Manager_Setting(self)
            if dialog.exec_() == QDialog.Accepted:
                QMessageBox.information(self, "Information", f"설정이 완료되었습니다")
                self.printStatus("설정 반영 중...")
                QApplication.instance().setStyleSheet(theme_option[self.SETTING['Theme']])
                self.updateStyleHtml()

                if self.SETTING['MyDB'] != 'default' or self.SETTING['DBKeywordSort'] != 'default':
                    self.managerDatabaseObj.refreshDB()
                self.printStatus()

        except Exception as e:
            self.programBugLog(traceback.format_exc())

    def getUserLocation(self, detail=False):
        try:
            response = requests.get("https://ipinfo.io")
            data = response.json()
            returnData = f"{self.version} | {self.userDevice} | {data.get("ip")} | {data.get("city")}"
            if detail == True:
                returnData = f"{data.get("ip")} | {data.get("city")} | {data.get('region')} | {data.get('country')} | {data.get('loc')} | {self.versionNum}"
            return returnData
        except requests.RequestException as e:
            return ""

    def initShortcutialize(self):
        shortcuts = [self.ctrld, self.ctrls, self.ctrlv, self.ctrla, self.ctrll, self.ctrle, self.ctrlr, self.ctrlk, self.ctrlm, self.ctrlc,
                     self.cmdd, self.cmds, self.cmdv, self.cmda, self.cmdl, self.cmde, self.cmdr, self.cmdk, self.cmdm, self.cmdc]
        for shortcut in shortcuts:
            try:
                shortcut.activated.disconnect()
            except TypeError:
                # 연결된 슬롯이 없는 경우 발생하는 에러를 무시
                pass

    def updateDB(self):
        sort_by = 'starttime' if self.SETTING['DBKeywordSort'] == 'default' else 'keyword'
            
        res = self.Request('get', f'/crawls/list?sort_by={sort_by}').json()
        
        self.db_list = res['data']
        self.fullStorage = res['fullStorage']
        self.activeCrawl = res['activeCrawl']
        
        currentDB = {
            'DBuids': [db['uid'] for db in self.db_list],
            'DBnames': [db['name'] for db in self.db_list],
            'DBdata': self.db_list,
            'DBtable': [(db['name'], db['crawlType'], db['keyword'], db['startDate'], db['endDate'], db['crawlOption'], db['status'], db['requester'], db['dbSize']) for db in self.db_list]
        }
            
        return currentDB

    def makeTable(self, widgetname, data, column, right_click_function=None, popupsize=None):
        def show_details(item):
            # 이미 창이 열려있는지 확인
            if hasattr(self, "details_dialog") and self.details_dialog.isVisible():
                return  # 창이 열려있다면 새로 열지 않음
            # 팝업 창 생성
            self.details_dialog = QDialog()
            self.details_dialog.setWindowTitle("상세 정보")
            if popupsize == None:
                self.details_dialog.resize(200, 150)
            elif popupsize == 'max':
                self.details_dialog.showMaximized()
            else:
                self.details_dialog.resize(popupsize[0], popupsize[1])

            # 레이아웃 설정
            layout = QVBoxLayout(self.details_dialog)

            # 스크롤 가능한 QTextEdit 위젯 생성
            text_edit = QTextEdit()
            text_edit.setText(item.text())
            text_edit.setReadOnly(True)  # 텍스트 편집 불가로 설정
            layout.addWidget(text_edit)

            # 확인 버튼 생성
            ok_button = QPushButton("확인")
            ok_button.clicked.connect(self.details_dialog.accept)  # 버튼 클릭 시 다이얼로그 닫기
            layout.addWidget(ok_button)

            shortcut = QShortcut(QKeySequence("Ctrl+W"), self.details_dialog)
            shortcut.activated.connect(self.details_dialog.close)

            shortcut2 = QShortcut(QKeySequence("Ctrl+ㅈ"), self.details_dialog)
            shortcut2.activated.connect(self.details_dialog.close)

            # 다이얼로그 실행
            self.details_dialog.exec_()

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

    def viewTable(self, dbname, tablename, popupsize=None):
        class SingleTableWindow(QMainWindow):
            def __init__(self, parent=None, targetDB=None, target_table=None, popupsize=None):
                super(SingleTableWindow, self).__init__(parent)
                self.setWindowTitle(f"{targetDB} -> {target_table}")
                self.setGeometry(100, 100, 1600, 1200)

                self.parent = parent  # 부모 객체 저장
                self.targetDB = targetDB  # 대상 데이터베이스 이름 저장
                self.target_table = target_table  # 대상 테이블 이름 저장

                self.popupsize = popupsize

                self.centralWidget = QWidget(self)
                self.setCentralWidget(self.centralWidget)

                self.layout = QVBoxLayout(self.centralWidget)

                # 상단 버튼 레이아웃
                self.button_layout = QHBoxLayout()

                # spacer 아이템 추가 (버튼을 오른쪽 끝에 배치)
                spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
                self.button_layout.addItem(spacer)

                # 닫기 버튼 추가
                self.close_button = QPushButton("닫기", self)
                self.close_button.setFixedWidth(80)
                self.close_button.clicked.connect(self.closeWindow)
                self.button_layout.addWidget(self.close_button)

                # Ctrl+W 단축키 추가
                ctrlw = QShortcut(QKeySequence("Ctrl+W"), self)
                ctrlw.activated.connect(self.closeWindow)

                cmdw = QShortcut(QKeySequence("Ctrl+ㅈ"), self)
                cmdw.activated.connect(self.closeWindow)

                # 버튼 레이아웃을 메인 레이아웃에 추가
                self.layout.addLayout(self.button_layout)

                # targetDB와 target_table이 주어지면 테이블 뷰를 초기화
                if targetDB is not None and target_table is not None:
                    self.init_viewTable(parent.mySQLObj, targetDB, target_table)

            def closeWindow(self):
                self.close()  # 창 닫기
                self.deleteLater()  # 객체 삭제
                gc.collect()

            def closeEvent(self, event):
                # 윈도우 창이 닫힐 때 closeWindow 메서드 호출
                self.closeWindow()
                event.accept()  # 창 닫기 이벤트 허용

            def init_viewTable(self, mySQLObj, targetDB, target_table):
                # targetDB에 연결
                mySQLObj.connectDB(targetDB)
                tableDF = mySQLObj.TableToDataframe(target_table)

                tableDF = tableDF.iloc[::-1].reset_index(drop=True)

                # 데이터프레임 값을 문자열로 변환하여 튜플 형태의 리스트로 저장
                self.tuple_list = [tuple(str(cell) for cell in row[1:]) for row in
                                   tableDF.itertuples(index=False, name=None)]

                # 테이블 위젯 생성
                new_table = QTableWidget(self.centralWidget)
                self.layout.addWidget(new_table)

                # column 정보를 리스트로 저장
                columns = list(tableDF.columns)
                columns.pop(0)
                # makeTable 함수를 호출하여 테이블 설정
                self.parent.makeTable(new_table, self.tuple_list, columns, popupsize=self.popupsize)

        try:
            def destory_table():
                del self.DBtable_window
                gc.collect()
            self.DBtable_window = SingleTableWindow(self, dbname, tablename, popupsize)
            self.DBtable_window.destroyed.connect(destory_table)
            self.DBtable_window.show()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def checkPassword(self, admin=False, string=""):
        while True:
            input_dialog = QInputDialog(self)
            if admin == False:
                if string == "":
                    input_dialog.setWindowTitle('Password')
                else:
                    input_dialog.setWindowTitle(string)
            else:
                input_dialog.setWindowTitle('Admin Mode')
            input_dialog.setLabelText('Enter password:')
            input_dialog.setTextEchoMode(QLineEdit.Password)
            input_dialog.resize(300, 200)  # 원하는 크기로 설정

            # 비밀번호 입력 창 띄우기
            ok = input_dialog.exec_()
            password = input_dialog.textValue()

            # 영어 알파벳만 있는지 확인
            if re.match("^[a-zA-Z0-9!@#$%^&*()_+=-]*$", password):
                return ok, password
            else:
                # 오류 메시지 표시
                QMessageBox.warning(self, "Invalid Input", "영어로만 입력 가능합니다")

    def updateStyleHtml(self):
        if self.SETTING['Theme'] != 'default':
            self.style_html = f"""
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
            self.style_html = f"""
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

    def printStatus(self, msg=''):
        for i in range(3):
            self.rightLabel.setText(msg)
            QCoreApplication.processEvents(QEventLoop.AllEvents, 0)

    def openFileExplorer(self, path):
        # 저장된 폴더를 파일 탐색기로 열기
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            os.system(f"open '{path}'")
        else:  # Linux and other OS
            os.system(f"xdg-open '{path}'")
        
    def programBugLog(self, text):
        print(text)
        self.printStatus("오류 발생")
        if self.user == 'admin':
            QMessageBox.critical(self, "Error", f"오류가 발생했습니다\n\nError Log: {text}")
        else:
            #QMessageBox.critical(self, "Error", f"오류가 발생했습니다")
            QMessageBox.critical(self, "Error", f"오류가 발생했습니다\n\nError Log: {text}")
        logToText(f"Exception: {text}")
        self.userBugging(text)
        reply = QMessageBox.question(self, 'Bug Report', "버그 리포트를 전송하시겠습니까?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self.managerBoardObj.addBug()
        self.printStatus()

    def closeEvent(self, event):
        # 프로그램 종료 시 실행할 코드
        reply = QMessageBox.question(self, 'Shutdown', "프로그램을 종료하시겠습니까?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            try:
                if self.CONFIG['Logging'] == 'On' and self.user != 'admin':
                    self.userLogging('Shutdown', force=True)
                    self.mySQLObj.connectDB(f'{self.user}_db')  # userDB 접속
                    self.mySQLObj.updateTableCell('manager_record', -1, 'D_Log', log_text, add=True)
                self.cleanUpTemp()
            except Exception as e:
                print(traceback.format_exc())
            event.accept()  # 창을 닫을지 결정 (accept는 창을 닫음)
        else:
            event.ignore()

    def cleanUpTemp(self):
        if platform.system() != "Windows":
            return
        try:
            folder_path = 'C:/Temp'

            # BIGMACLAB 또는 _MEI로 시작하는 파일 및 폴더 삭제
            for file_name in os.listdir(folder_path):
                if file_name.startswith('BIGMACLAB') or file_name.startswith('_MEI'):
                    file_path = os.path.join(folder_path, file_name)

                    # 폴더인지 파일인지 확인하고 삭제
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)  # 폴더 삭제
                        print(f"Deleted folder: {file_path}")
                    else:
                        os.remove(file_path)  # 파일 삭제
                        print(f"Deleted file: {file_path}")

            pattern = re.compile(r"BIGMACLAB_MANAGER_(\d+\.\d+\.\d+)\.exe")
            exe_file_path = os.path.join(os.environ['LOCALAPPDATA'], 'MANAGER')
            currentVersion = version.Version(self.versionNum)

            for file_name in os.listdir(exe_file_path):
                match = pattern.match(file_name)
                if match:
                    file_version = version.Version(match.group(1))  # 버전 추출 및 비교를 위해 Version 객체로 변환
                    # 현재 버전을 제외한 파일 삭제
                    if file_version != currentVersion:
                        file_path = os.path.join(exe_file_path, file_name)
                        os.remove(file_path)

        except Exception as e:
            print(e)

    def generateLLM(self, query, model):
        if model == 'ChatGPT':
            try:
                # OpenAI 클라이언트 초기화
                client = OpenAI(api_key=self.gpt_api_key)

                # 모델 이름 수정: gpt-4-turbo
                model = "gpt-4-turbo"

                # ChatGPT API 요청
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": query},
                    ]
                )

                # 응답 메시지 내용 추출
                content = response.choices[0].message.content
                return content

            except Exception as e:
                # 예외 발생 시 에러 메시지 반환
                return (0, traceback.format_exc())

        else:
            # 서버 URL
            url = "http://121.152.225.232:3333/api/process"

            # 전송할 데이터
            data = {
                "model_name": model,
                "question": query
            }

            try:
                # POST 요청 보내기
                response = requests.post(url, json=data)

                # 응답 확인
                if response.status_code == 200:
                    result = response.json()['result']
                    result = result.replace('<think>', '').replace('</think>', '')
                    return result
                else:
                    return f"Failed to get a valid response: {response.status_code} {response.text}"

            except requests.exceptions.RequestException as e:
                return f"Error communicating with the server: {e}"


    #################### DEVELOPER MODE ###################

    def developerMode(self, toggle):
        try:
            if toggle == True:
                openConsole("DEVELOPER MODE")
                toggleLogging(True)
                print(log_text)
            else:
                closeConsole()
                toggleLogging(False)
        except:
            pass

    def installEventFilter(self, widget):
        """재귀적으로 모든 자식 위젯에 EventLogger를 설치하는 함수"""
        widget.installEventFilter(self.eventLogger)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self.eventLogger)

# 로그 출력 제어 변수와 로그 저장 변수
logging_enabled = False  # 콘솔 출력 여부를 조절
log_text = ""  # 모든 로그 메시지를 저장하는 변수

def setUpLogging():
    """로그 설정 초기화"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logging.getLogger().setLevel(logging.CRITICAL)  # 초기에는 콘솔 출력 방지


def toggleLogging(enable):
    """
    콘솔에 로그를 출력할지 여부를 결정.
    인자로 True 또는 False를 받아 INFO 레벨과 CRITICAL 레벨로 전환.
    """
    global logging_enabled
    logging_enabled = enable
    logging.getLogger().setLevel(logging.DEBUG if logging_enabled else logging.CRITICAL)


def logToText(message):
    """
    모든 로그 메시지를 log_text에 저장하고, logging_enabled가 True일 경우 콘솔에도 출력.
    """
    global log_text
    timestamped_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}"  # 타임스탬프 추가
    log_text += f"{timestamped_message}\n"  # 모든 로그를 log_text에 기록
    if logging_enabled:
        print(timestamped_message)  # logging_enabled가 True일 때만 콘솔에 출력


# 예외 발생 시 logToText에 기록하는 함수
def exceptionHandler(exc_type, exc_value, exc_traceback):
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logToText(f"Exception: {error_message}")

# 전역 예외 처리기를 설정하여 모든 예외를 logToText에 기록
sys.excepthook = exceptionHandler

class EventLogger(QObject):
    """이벤트 로그를 생성하고 log_text에 모든 로그를 쌓아두는 클래스"""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            logToText(f"MouseButtonPress on {obj}")
        elif event.type() == QEvent.KeyPress:
            logToText(f"KeyPress: {event.key()} on {obj}")
        elif event.type() == QEvent.FocusIn:
            logToText(f"FocusIn on {obj}")
        elif event.type() == QEvent.FocusOut:
            logToText(f"FocusOut on {obj}")
        elif event.type() == QEvent.MouseButtonDblClick:
            logToText(f"Double-click on {obj}")
        elif event.type() == QEvent.Resize:
            logToText(f"{obj} resized")
        elif event.type() == QEvent.Close:
            logToText(f"{obj} closed")

        return super().eventFilter(obj, event)

#######################################################

if __name__ == '__main__':
    # 메인 윈도우 실행
    application = MainWindow(splashDialog)
    sys.exit(app.exec_())
