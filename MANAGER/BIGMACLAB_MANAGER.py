##############################################################################################################
# Project Name: BIGMACLAB MANAGER
# Version: 2.X.X
# Developer: Moon Yo Jun (POSTECH, Computer Science and Engineering)
# Date Created: 2024-08-03
# Released: 2024-08-05
# Download: https://knpu.re.kr/tool
# Affiliation: BIGMACLAB(https://knpu.re.kr), Korea National Police University, Asan, Chungcheongnam-do
#
# Contact:
# - Email: yojun313@postech.ac.kr / moonyojun@gmail.com
# - Phone: +82-10-4072-9190
##############################################################################################################

VERSION = '2.5.4'

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
splash_dialog = SplashDialog(version=VERSION, theme=theme)
splash_dialog.show()

splash_dialog.update_status("Loading System Libraries")
import os
import sys
import subprocess
from openai import OpenAI
from mySQL import mySQL
from datetime import datetime
import requests
from packaging import version
import pandas as pd
from pathlib import Path
import socket
import gc
import random
import traceback
import re
import logging
import shutil

splash_dialog.update_status("Loading GUI Libraries")
from Manager_Settings import Manager_Setting
from Manager_ToolModule import ToolModule
from Manager_Database import Manager_Database
from Manager_Web import Manager_Web
from Manager_Board import Manager_Board
from Manager_User import Manager_User
from Manager_Analysis import Manager_Analysis
from Manager_Console import open_console, close_console
from PyQt5 import uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QShortcut, QVBoxLayout, QTextEdit, QHeaderView, \
    QHBoxLayout, QLabel, QStatusBar, QDialog, QInputDialog, QLineEdit, QMessageBox, QFileDialog, QSizePolicy, \
    QPushButton, QMainWindow, QSpacerItem, QAbstractItemView
from PyQt5.QtCore import Qt, QCoreApplication, QObject, QEvent, QSize, QModelIndex, QEventLoop
from PyQt5.QtGui import QKeySequence, QIcon

DB_IP = '121.152.225.232'
LOCAL_IP = '192.168.0.3'

class MainWindow(QMainWindow):

    def __init__(self, splash_dialog):
        try:
            self.versionNum = VERSION
            self.version = f'Version {self.versionNum}'
            self.splash_dialog = splash_dialog

            self.toolmodule = ToolModule()

            super(MainWindow, self).__init__()
            ui_path = os.path.join(os.path.dirname(__file__), 'source', 'BIGMACLAB_MANAGER_GUI.ui')
            icon_path = os.path.join(os.path.dirname(__file__), 'source', 'exe_icon.png')

            uic.loadUi(ui_path, self)
            self.initialize_settings()
            self.initialize_listwidget()
            self.update_style_html()
            self.setWindowTitle("MANAGER")  # 창의 제목 설정
            self.setWindowIcon(QIcon(icon_path))

            self.resize(1400, 1000)

            self.initialize_statusBar()
            self.decrypt_process()

            setup_logging()
            self.event_logger = EventLogger()
            self.install_event_filter_all_widgets(self)

            def load_program():
                try:
                    self.listWidget.setCurrentRow(0)
                    if self.SETTING['BootTerminal'] == 'on':
                        open_console("Boot Process")
                    self.startTime = datetime.now()
                    self.gpt_api_key = self.SETTING['GPT_Key']
                    self.CONFIG = {
                        'Logging': 'On'
                    }
                    self.check_internet_connection()
                    self.listWidget.currentRowChanged.connect(self.display)

                    if platform.system() == "Windows":
                        local_appdata_path = os.getenv("LOCALAPPDATA")
                        desktop_path = os.path.join(os.getenv("USERPROFILE"), "Desktop")

                        self.program_directory = os.path.join(local_appdata_path, "MANAGER")
                        self.default_directory = "C:/BIGMACLAB_MANAGER"
                        if not os.path.exists(self.default_directory):
                            os.makedirs(self.default_directory)
                        if os.path.exists(os.path.join(self.program_directory, 'settings.env')):
                            os.remove(os.path.join(self.program_directory, 'settings.env'))
                    else:
                        self.program_directory = os.path.dirname(__file__)
                        self.default_directory = '/Users/yojunsmacbookprp/Documents/BIGMACLAB_MANAGER'

                    self.readme_path = os.path.join(self.default_directory, 'README.txt')
                    if not Path(self.readme_path).exists():
                        with open(self.readme_path, "w") as txt:
                            text = (
                                "[ BIGMACLAB MANAGER README ]\n\n\n"
                                "C:/BIGMACLAB_MANAGER is default directory folder of this program. This folder is automatically built by program.\n\n"
                                "All files made in this program will be saved in this folder without any change.\n\n\n\n"
                                "< Instructions >\n\n"
                                "- MANAGER: https://knpu.re.kr/tool\n"
                                "- KEMKIM: https://knpu.re.kr/kemkim"
                            )
                            txt.write(text)

                    if os.path.isdir(self.default_directory) == False:
                        os.mkdir(self.default_directory)

                    DB_ip = DB_IP
                    if socket.gethostname() in ['DESKTOP-502IMU5', 'DESKTOP-0I9OM9K', 'BigMacServer', 'BIGMACLAB-Z8']:
                        DB_ip = LOCAL_IP

                    self.network_text = (
                        "\n\n[ DB 접속 반복 실패 시... ]\n"
                        "\n1. Wi-Fi 또는 유선 네트워크가 정상적으로 동작하는지 확인하십시오"
                        "\n2. 네트워크 호환성에 따라 DB 접속이 불가능한 경우가 있습니다. 다른 네트워크 연결을 시도해보십시오\n"
                    )

                    # Loading User info from DB
                    while True:
                        try:
                            self.mySQL_obj = mySQL(host=DB_ip, user='admin', password=self.public_password, port=3306)
                            print("\nI. Loading User Info from DB... ", end='')
                            self.splash_dialog.update_status("Loading User Info from DB")
                            if self.mySQL_obj.showAllDB() == []:
                                raise
                            # DB 불러오기
                            self.Manager_User_obj = Manager_User(self)
                            self.userNameList = self.Manager_User_obj.userNameList  # User Table 유저 리스트
                            self.userMailList = self.Manager_User_obj.userMailList
                            self.user_list = self.Manager_User_obj.user_list  # Device Table 유저 리스트
                            self.device_list = self.Manager_User_obj.device_list
                            self.userPushOverKeyList = self.Manager_User_obj.userKeyList
                            print("Done")
                            break
                        except Exception as e:
                            print("Failed")
                            print(traceback.format_exc())
                            self.close_bootscreen()
                            self.printStatus()
                            reply = QMessageBox.warning(self, 'Connection Failed',
                                                        f"DB 서버 접속에 실패했습니다\n네트워크 점검이 필요합니다{self.network_text}\n다시 시도하시겠습니까?",
                                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                            if reply == QMessageBox.Yes:
                                self.printStatus("접속 재시도 중...")
                                continue
                            else:
                                os._exit(0)

                    # User Checking & Login Process
                    print("\nII. Checking User... ", end='')
                    self.splash_dialog.update_status("Checking User")
                    if self.login_program() == False:
                        os._exit(0)

                    # Loading Data from DB & Making object
                    while True:
                        try:
                            print("\nIII. Loading Data from DB... ", end='')
                            self.splash_dialog.update_status("Loading Data from DB")
                            self.Manager_User_obj.userDB_layout_maker()
                            self.Manager_Board_obj = Manager_Board(self)
                            self.DB = self.update_DB()
                            self.Manager_Database_obj = Manager_Database(self)
                            self.Manager_Web_obj = Manager_Web(self)
                            self.Manager_Analysis_obj = Manager_Analysis(self)
                            print("Done")
                            break
                        except Exception as e:
                            print("Failed")
                            print(traceback.format_exc())
                            self.close_bootscreen()
                            self.printStatus()
                            reply = QMessageBox.warning(self, 'Connection Failed',
                                                        f"DB 서버 접속에 실패했습니다\n네트워크 점검이 필요합니다{self.network_text}\n\n다시 시도하시겠습니까?",
                                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                            if reply == QMessageBox.Yes:
                                self.printStatus("접속 재시도 중...")
                                continue
                            else:
                                os._exit(0)

                    self.splash_dialog.update_status(f"안녕하세요, {self.user}님!")
                    newpost = self.newpost_check()
                    newversion = self.newversion_check()
                    print(f"\n{self.user}님 환영합니다!")

                    self.shortcut_init()
                    self.Manager_Database_obj.database_shortcut_setting()
                    self.user_logging(f'Booting ({self.user_location()})', booting=True, force=True)
                    self.initialize_configuration()

                    close_console()
                    self.close_bootscreen()

                    if self.SETTING['ScreenSize'] == 'max':
                        self.showMaximized()
                    self.printStatus(f"{self.fullstorage} GB / 2 TB")

                    # After Booting

                    if newpost == True:
                        reply = QMessageBox.question(self, "New Post", "새로운 게시물이 업로드되었습니다\n\n확인하시겠습니까?",
                                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                        if reply == QMessageBox.Yes:
                            self.Manager_Board_obj.board_view_post(0)
                    if newversion == True:
                        self.update_program(auto=self.SETTING['AutoUpdate'])

                except Exception as e:
                    print("Failed")
                    print(traceback.format_exc())
                    self.close_bootscreen()
                    self.printStatus()
                    msg = f'[ Admin CRITICAL Notification ]\n\nThere is Error in MANAGER Booting\n\nError Log: {traceback.format_exc()}'
                    self.send_pushOver(msg, self.admin_pushoverkey)
                    QMessageBox.critical(self, "Error", f"부팅 과정에서 오류가 발생했습니다\n\nError Log: {traceback.format_exc()}")
                    QMessageBox.information(self, "Information", f"관리자에게 에러 상황과 로그가 전달되었습니다\n\n프로그램을 종료합니다")
                    os._exit(0)

            load_program()

        except Exception as e:
            self.close_bootscreen()
            open_console()
            print(traceback.format_exc())

    def __getattr__(self, name):
        # ClassA에 속성이 있으면 반환
        return getattr(self.toolmodule, name)

    ################################## Booting ##################################

    def initialize_listwidget(self):
        try:
            """리스트 위젯의 특정 항목에만 아이콘 추가 및 텍스트 제거"""

            icon_path = os.path.join(os.path.dirname(__file__), 'source', 'setting.png')

            # 리스트 위젯의 모든 항목 가져오기
            for index in range(self.listWidget.count()):
                item = self.listWidget.item(index)
                if item.text() == "SETTING":
                    # SETTING 항목에 아이콘 추가 및 텍스트 제거
                    item.setIcon(QIcon(icon_path))
                    item.setText("")  # 텍스트 제거

            # 아이콘 크기 설정
            self.listWidget.setIconSize(QSize(25, 25))  # 아이콘 크기를 64x64로 설정
        except Exception as e:
            print(traceback.format_exc())

    def initialize_settings(self):
        try:
            self.settings = QSettings("BIGMACLAB", "BIGMACLAB_MANAGER")
            defaults = {
                'Theme': 'default',
                'ScreenSize': 'default',
                'OldPostTitle': 'default',
                'AutoUpdate': 'default',
                'MyDB': 'default',
                'GPT_Key': 'default',
                'DB_Refresh': 'default',
                'GPT_TTS': 'default',
                'BootTerminal': 'default',
                'DBKeywordSort': 'default',
                'ProcessConsole': 'default',
            }

            # 설정 초기화
            for key, value in defaults.items():
                if self.settings.value(key) is None:  # 값이 없을 경우 기본값 설정
                    self.settings.setValue(key, value)

            self.SETTING = {
                'Theme': self.settings.value("Theme", "default"),
                'ScreenSize': self.settings.value("ScreenSize", "default"),
                'OldPostTitle': self.settings.value("OldPostTitle", "default"),
                'AutoUpdate': self.settings.value("AutoUpdate", "default"),
                'MyDB': self.settings.value("MyDB", "default"),
                'GPT_Key': self.settings.value("GPT_Key", "default"),
                'DB_Refresh': self.settings.value("DB_Refresh", "default"),
                'GPT_TTS': self.settings.value("GPT_TTS", "default"),
                'BootTerminal': self.settings.value("BootTerminal", "default"),
                'DBKeywordSort': self.settings.value("DBKeywordSort", "default"),
                'ProcessConsole': self.settings.value("ProcessConsole", "default"),
            }

        except Exception as e:
            print(traceback.format_exc())
            self.SETTING = defaults

    def initialize_configuration(self):
        try:
            self.mySQL_obj.connectDB('bigmaclab_manager_db')
            configDF = self.mySQL_obj.TableToDataframe('configuration')
            self.CONFIG = dict(zip(configDF[configDF.columns[1]], configDF[configDF.columns[2]]))

            return self.CONFIG
        except Exception as e:
            print(traceback.format_exc())

    def initialize_statusBar(self):
        # 상태 표시줄 생성
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.left_label = QLabel('  ' + self.version)
        self.right_label = QLabel('')

        self.left_label.setToolTip("새 버전 확인을 위해 Ctrl+U")
        self.right_label.setToolTip("상태표시줄")
        self.left_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.right_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusbar.addPermanentWidget(self.left_label, 1)
        self.statusbar.addPermanentWidget(self.right_label, 1)

    def shortcut_init(self):
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

        self.ctrlu.activated.connect(lambda: self.update_program(sc=True))
        self.ctrlq.activated.connect(lambda: self.close())
        self.ctrlp.activated.connect(lambda: self.developer_mode(True))
        self.ctrlpp.activated.connect(lambda: self.developer_mode(False))

        self.cmdu.activated.connect(lambda: self.update_program(sc=True))
        self.cmdq.activated.connect(lambda: self.close())
        self.cmdp.activated.connect(lambda: self.developer_mode(True))
        self.cmdpp.activated.connect(lambda: self.developer_mode(False))

    def close_bootscreen(self):
        try:
            self.splash_dialog.accept()  # InfoDialog 닫기
            self.show()  # MainWindow 표시
        except:
            print(traceback.format_exc())

    def login_program(self):
        def admin_notify(username):
            msg = f'[ Admin Notification ]\n\nUnknown tried to connect\n\nName: {username}\n\nLocation: {self.user_location(True)}'
            self.send_pushOver(msg, self.admin_pushoverkey)

        try:
            current_device = socket.gethostname()
            self.user_device = current_device
            if current_device in self.device_list:
                print("Done")
                self.user = self.user_list[self.device_list.index(current_device)]
                self.usermail = self.userMailList[self.userNameList.index(self.user)]
                return True
            else:
                self.close_bootscreen()
                self.printStatus()
                input_dialog_id = QInputDialog(self)
                input_dialog_id.setWindowTitle('Login')
                input_dialog_id.setLabelText('User Name:')
                input_dialog_id.resize(300, 200)  # 원하는 크기로 설정
                ok_id = input_dialog_id.exec_()
                user_name = input_dialog_id.textValue()
                if not ok_id:
                    QMessageBox.warning(self, 'Program Shutdown', '프로그램을 종료합니다')
                    return False
                elif user_name not in self.userNameList:
                    admin_notify(user_name)
                    QMessageBox.warning(self, 'Unknown User', '등록되지 않은 사용자입니다\n\n프로그램을 종료합니다')
                    return False

                self.user = user_name
                self.usermail = self.userMailList[self.userNameList.index(user_name)]
                self.printStatus("인증번호 전송 중...")

                random_pw = ''.join(random.choices('0123456789', k=6))
                msg = (
                    f"사용자: {self.user}\n"
                    f"디바이스: {current_device}\n"
                    f"인증 위치: {self.user_location()}\n\n"
                    f"인증 번호 '{random_pw}'를 입력하십시오"
                )
                self.send_email(self.usermail, "[MANAGER] 디바이스 등록 인증번호", msg)
                self.printStatus()
                QMessageBox.information(self, "Information", f"{self.user}님의 메일 {self.usermail}로 인증번호가 전송되었습니다\n\n인증번호를 확인 후 다음 창에서 입력하십시오")

                ok, password = self.pw_check(string="메일 인증번호")
                if ok and password == random_pw:
                    reply = QMessageBox.question(self, 'Device Registration',
                                                 f"BIGMACLAB MANAGER 서버에\n현재 디바이스({current_device})를 등록하시겠습니까?",
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        self.mySQL_obj.insertToTable('device_list', [[current_device, user_name]])
                        self.mySQL_obj.commit()
                        QMessageBox.information(self, "Information", "디바이스가 등록되었습니다\n\n다음 실행 시 추가적인 로그인이 필요하지 않습니다")
                        msg = (
                            "[ New Device Added! ]\n\n"
                            f"User: {user_name}\n"
                            f"Device: {current_device}\n"
                            f"Location: {self.user_location()}"
                        )
                        self.send_pushOver(msg, self.admin_pushoverkey)
                        self.Manager_User_obj.device_init_table()
                        return True
                    else:
                        QMessageBox.information(self, "Information", "디바이스가 등록되지 않았습니다\n\n다음 실행 시 추가적인 로그인이 필요합니다")
                        return True
                elif ok:
                    self.printStatus("인증 실패")
                    QMessageBox.warning(self, 'Wrong Password', '인증번호가 올바르지 않습니다\n\n프로그램을 종료합니다')
                    admin_notify(self.user)
                    return False
                else:
                    QMessageBox.warning(self, 'Error', '프로그램을 종료합니다')
                    return False
        except Exception as e:
            self.close_bootscreen()
            QMessageBox.critical(self, "Error", f"오류가 발생했습니다.\n\nError Log: {traceback.format_exc()}")
            QMessageBox.information(self, "Information",
                                    f"관리자에게 문의바랍니다\n\nEmail: yojun313@postech.ac.kr\nTel: 010-4072-9190\n\n프로그램을 종료합니다")
            return False

    def update_program(self, sc=False, auto=False):
        try:
            if platform.system() != "Windows":
                return
            def download_file(download_url, local_filename):
                response = requests.get(download_url, stream=True)
                total_size = int(response.headers.get('content-length', 0))  # 파일의 총 크기 가져오기
                chunk_size = 8192  # 8KB씩 다운로드
                downloaded_size = 0  # 다운로드된 크기 초기화

                with open(local_filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:  # 빈 데이터 확인
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            percent_complete = (downloaded_size / total_size) * 100
                            print(f"\r{self.new_version} Download: {percent_complete:.0f}%", end='')  # 퍼센트 출력

                print("\nDownload Complete")
                close_console()

            def update_process():
                open_console("Version Update Process")
                msg = (
                    "[ Admin Notification ]\n\n"
                    f"{self.user} updated {current_version} -> {self.new_version}\n\n{self.user_location()}"
                )
                self.send_pushOver(msg, self.admin_pushoverkey)
                self.user_logging(f'Program Update ({current_version} -> {self.new_version})', force=True)

                self.printStatus("버전 업데이트 중...")
                import subprocess
                download_file_path = os.path.join('C:/Temp', f"BIGMACLAB_MANAGER_{self.new_version}.exe")
                download_file(f"https://knpu.re.kr:90/download/BIGMACLAB_MANAGER_{self.new_version}.exe",
                              download_file_path)
                subprocess.Popen([download_file_path], shell=True)
                close_console()
                os._exit(0)

            # New version check
            current_version = version.parse(self.versionNum)
            self.new_version = version.parse(self.Manager_Board_obj.board_version_newcheck())
            if current_version < self.new_version:
                if auto == 'auto':
                    self.close_bootscreen()
                    update_process()
                self.Manager_Board_obj.board_version_refresh()

                version_info_html = self.style_html + f"""
                    <table>
                        <tr><th>Item</th><th>Details</th></tr>
                        <tr><td><b>Version Num:</b></td><td>{self.Manager_Board_obj.version_data_for_table[0][0]}</td></tr>
                        <tr><td><b>Release Date:</b></td><td>{self.Manager_Board_obj.version_data_for_table[0][1]}</td></tr>
                        <tr><td><b>ChangeLog:</b></td><td>{self.Manager_Board_obj.version_data_for_table[0][2]}</td></tr>
                        <tr><td><b>Version Features:</b></td><td>{self.Manager_Board_obj.version_data_for_table[0][3]}</td></tr>
                        <tr><td><b>Version Status:</b></td><td>{self.Manager_Board_obj.version_data_for_table[0][4]}</td></tr>
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
                        open_console("Version Reinstall Process")
                        import subprocess
                        download_file_path = os.path.join('C:/Temp', f"BIGMACLAB_MANAGER_{self.new_version}.exe")
                        download_file(f"https://knpu.re.kr:90/download/BIGMACLAB_MANAGER_{self.new_version}.exe",
                                      download_file_path)
                        subprocess.Popen([download_file_path], shell=True)
                        close_console()
                        os._exit(0)
                    else:
                        return
                return
        except:
            print(traceback.format_exc())
            return

    def newversion_check(self):
        print("\nV. Checking New Version...", end='')
        current_version = version.parse(self.versionNum)
        self.new_version = version.parse(self.Manager_Board_obj.board_version_newcheck())
        print("Done")
        if current_version < self.new_version:
            return True
        else:
            return False

    def newpost_check(self):
        print("\nIV. Checking New Post... ", end='')
        new_post_text = self.Manager_Board_obj.post_data[0][1]
        new_post_writer = self.Manager_Board_obj.post_data[0][0]
        old_post_text = self.SETTING['OldPostTitle']
        print("Done")
        if new_post_text == old_post_text:
            return False
        elif old_post_text == 'default':
            self.update_settings('OldPostTitle', new_post_text)
            return False
        elif new_post_text != old_post_text and self.user != new_post_writer:
            self.update_settings('OldPostTitle', new_post_text)
            return True

    def check_internet_connection(self):
        while True:
            try:
                # Google을 기본으로 확인 (URL은 다른 사이트로 변경 가능)
                response = requests.get("http://www.google.com", timeout=5)
                return response.status_code == 200
            except requests.ConnectionError:
                self.printStatus()
                self.close_bootscreen()
                reply = QMessageBox.question(self, "Internet Connection Error",
                                             "인터넷에 연결되어 있지 않습니다\n\n인터넷 연결 후 재시도해주십시오\n\n재시도하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    continue
                else:
                    os._exit(0)

    def display(self, index):
        if index != 6:
            self.stackedWidget.setCurrentIndex(index)
        # self.update_program()
        # DATABASE
        if index == 0:
            self.Manager_Database_obj.database_shortcut_setting()
            if self.SETTING['DB_Refresh'] == 'default':
                self.Manager_Database_obj.database_refresh_DB()
            self.printStatus(f"{self.fullstorage} GB / 2 TB")
        # CRAWLER
        elif index == 1:
            self.shortcut_initialize()
            self.printStatus(f"활성 크롤러 수: {self.activate_crawl}")
        # ANALYSIS
        elif index == 2:
            self.printStatus()
            self.Manager_Analysis_obj.analysis_shortcut_setting()
        # BOARD
        elif index == 3:
            self.Manager_Board_obj.board_shortcut_setting()
            self.printStatus()
        # WEB
        elif index == 4:
            self.shortcut_initialize()
            self.printStatus()
            #self.Manager_Web_obj.web_open_webbrowser('https://knpu.re.kr', self.Manager_Web_obj.web_web_layout)
        # USER
        elif index == 5:
            self.printStatus()
            self.Manager_User_obj.user_shortcut_setting()

        elif index == 6:
            self.user_settings()
            previous_index = self.stackedWidget.currentIndex()  # 현재 활성 화면의 인덱스
            self.listWidget.setCurrentRow(previous_index)  # 선택 상태를 이전 인덱스로 변경

        gc.collect()

    def filefinder_maker(self, main_window):
        class EmbeddedFileDialog(QFileDialog):
            def __init__(self, parent=None, default_directory=None):
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
                if default_directory:
                    self.setDirectory(default_directory)
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

        return EmbeddedFileDialog(self, self.default_directory)

    #############################################################################

    def update_settings(self, option_key, new_value):
        try:
            self.settings.setValue(option_key, new_value)  # 설정값 업데이트
            return True
        except Exception as e:
            print(traceback.format_exc())
            return False

    def user_logging(self, text='', booting=False, force=False):
        try:
            if (self.user == 'admin' and self.CONFIG['Logging'] == 'Off') or (self.CONFIG['Logging'] == 'Off' and force == False):
                return
            self.mySQL_obj.connectDB(f'{self.user}_db')  # userDB 접속
            if booting == True:
                latest_record = self.mySQL_obj.TableLastRow('manager_record')  # log의 마지막 행 불러옴
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
                    self.mySQL_obj.insertToTable('manager_record', [[str(datetime.now().date()), '', '', '']])
                    self.mySQL_obj.commit()

            self.printStatus("Loading...")
            text = f'\n\n[{str(datetime.now().time())[:-7]}] : {text}'
            self.mySQL_obj.updateTableCell('manager_record', -1, 'Log', text, add=True)
            self.printStatus()
        except Exception as e:
            print(traceback.format_exc())

    def user_bugging(self, text=''):
        try:
            self.printStatus("Loading...")
            self.mySQL_obj.connectDB(f'{self.user}_db')  # userDB 접속
            text = f'\n\n[{str(datetime.now().time())[:-7]}] : {text}'
            self.mySQL_obj.updateTableCell('manager_record', -1, 'Bug', text, add=True)
            self.printStatus()
        except Exception as e:
            print(traceback.format_exc())

    def user_settings(self):
        try:
            self.user_logging(f'User Setting')
            dialog = Manager_Setting(self)
            if dialog.exec_() == QDialog.Accepted:
                QMessageBox.information(self, "Information", f"설정이 완료되었습니다")
                self.printStatus("설정 반영 중...")
                QApplication.instance().setStyleSheet(theme_option[self.SETTING['Theme']])
                self.update_style_html()

                if self.SETTING['MyDB'] != 'default' or self.SETTING['DBKeywordSort'] != 'default':
                    self.Manager_Database_obj.database_refresh_DB()
                self.printStatus()

        except Exception as e:
            self.program_bug_log(traceback.format_exc())

    def user_location(self, detail=False):
        try:
            response = requests.get("https://ipinfo.io")
            data = response.json()
            returnData = f"{self.version} | {self.user_device} | {data.get("ip")} | {data.get("city")}"
            if detail == True:
                returnData = f"{data.get("ip")} | {data.get("city")} | {data.get('region')} | {data.get('country')} | {data.get('loc')} | {self.versionNum}"
            return returnData
        except requests.RequestException as e:
            return ""

    def shortcut_initialize(self):
        shortcuts = [self.ctrld, self.ctrls, self.ctrlv, self.ctrla, self.ctrll, self.ctrle, self.ctrlr, self.ctrlk, self.ctrlm, self.ctrlc,
                     self.cmdd, self.cmds, self.cmdv, self.cmda, self.cmdl, self.cmde, self.cmdr, self.cmdk, self.cmdm, self.cmdc]
        for shortcut in shortcuts:
            try:
                shortcut.activated.disconnect()
            except TypeError:
                # 연결된 슬롯이 없는 경우 발생하는 에러를 무시
                pass
    '''
    def update_DB(self):
        def sort_currentDB_by_keyword(currentDB):
            # 세 리스트를 묶어서 keyword에서 따옴표를 제거한 기준으로 정렬
            sorted_data = sorted(
                zip(currentDB['DBlist'], currentDB['DBdata'], currentDB['DBinfo'], currentDB['DBtable']),
                key=lambda x: x[1][2].replace('"', '')  # x[1][2]는 keyword, 따옴표 제거 후 정렬
            )

            # 정렬된 결과를 각각의 리스트로 풀어서 저장
            currentDB['DBlist'], currentDB['DBdata'], currentDB['DBinfo'], currentDB['DBtable'] = zip(*sorted_data)

            # zip 결과를 tuple로 반환하므로 list로 변환
            currentDB['DBlist'] = list(currentDB['DBlist'])
            currentDB['DBdata'] = list(currentDB['DBdata'])
            currentDB['DBinfo'] = list(currentDB['DBinfo'])
            currentDB['DBtable'] = list(currentDB['DBtable'])

            return currentDB

        def sort_currentDB_by_starttime(currentDB):
            # starttime을 기준으로 정렬하고 리스트를 역순으로 반환
            sorted_data = sorted(
                zip(currentDB['DBlist'], currentDB['DBdata'], currentDB['DBinfo'], currentDB['DBtable']),
                key=lambda x: datetime.strptime(x[1][5], '%Y-%m-%d %H:%M')  # x[1][5]는 starttime
            )[::-1]  # 정렬된 리스트를 뒤집음 (reverse 효과)

            # 정렬된 결과를 리스트로 분리
            currentDB['DBlist'], currentDB['DBdata'], currentDB['DBinfo'], currentDB['DBtable'] = map(list, zip(*sorted_data))

            return currentDB

        self.mySQL_obj.connectDB('crawler_db')
        db_list = self.mySQL_obj.TableToList('db_list')

        currentDB = {
            'DBdata': [],
            'DBlist': [],
            'DBinfo': [],
            'DBtable': []
        }

        self.fullstorage = 0
        self.activate_crawl = 0
        for DBdata in db_list:
            DB_name = DBdata[0]
            db_split = DB_name.split('_')
            crawltype = db_split[0]

            match crawltype:
                case 'navernews':
                    crawltype = 'Naver News'
                case 'naverblog':
                    crawltype = 'Naver Blog'
                case 'navercafe':
                    crawltype = 'Naver Cafe'
                case 'youtube':
                    crawltype = 'YouTube'

            keyword = db_split[1]
            date = f"{db_split[2]}~{db_split[3]}"

            option = DBdata[1]
            starttime = DBdata[2]
            endtime = DBdata[3]

            if endtime == '-' or endtime == '크롤링 중':
                endtime = '크롤링 중'
            elif endtime == 'X':
                endtime = '오류 중단'

            requester = DBdata[4]
            if requester == 'admin' and self.user != 'admin':
                continue

            if self.SETTING['MyDB'] == 'mydb' and requester != self.user:
                continue

            keyword = DBdata[5]
            size = float(DBdata[6])
            self.fullstorage += float(size)
            if size == 0:
                try:
                    size = self.mySQL_obj.showDBSize(DB_name)
                    if size == None:
                        size = (0,0)
                except:
                    size = (0, 0)
                self.fullstorage += float(size[0])
                size = f"{size[1]} MB" if size[0] < 1 else f"{size[0]} GB"
            else:
                size = f"{int(size * 1024)} MB" if size < 1 else f"{size} GB"
            crawlcom = DBdata[7]
            crawlspeed = DBdata[8]
            datainfo = DBdata[9]

            currentDB['DBlist'].append(DB_name)
            currentDB['DBdata'].append((DB_name, crawltype, keyword, date, option, starttime, endtime, requester, size))
            currentDB['DBinfo'].append((crawlcom, crawlspeed, datainfo))

            status = endtime
            if endtime == '크롤링 중':
                status = "Working"
            elif endtime == "오류 중단":
                status = "Error"
            else:
                status = "Done"

            currentDB['DBtable'].append((DB_name, crawltype, keyword, db_split[2], db_split[3], option, status, requester, size))



        self.activate_crawl = len([item for item in currentDB['DBdata'] if item[6] == "크롤링 중"])
        self.fullstorage = round(self.fullstorage, 2)

        if self.SETTING['DBKeywordSort'] != 'default':
            currentDB = sort_currentDB_by_keyword(currentDB)
        else:
            currentDB = sort_currentDB_by_starttime(currentDB)

        return currentDB
    '''

    def update_DB(self):
        def sort_currentDB_by_keyword(currentDB):
            # keyword를 기준으로 정렬 (따옴표 제거 후 비교)
            sorted_data = sorted(
                zip(currentDB['DBlist'], currentDB['DBdata'], currentDB['DBtable']),
                key=lambda x: x[1]['Keyword'].replace('"', '')  # Keyword 값에서 따옴표 제거 후 정렬
            )

            # 정렬된 결과를 리스트로 분리
            currentDB['DBlist'], currentDB['DBdata'], currentDB['DBtable'] = map(list, zip(*sorted_data))

            return currentDB
        def sort_currentDB_by_starttime(currentDB):
            # starttime을 기준으로 정렬하고 리스트를 역순으로 반환
            sorted_data = sorted(
                zip(currentDB['DBlist'], currentDB['DBdata'], currentDB['DBtable']),
                key=lambda x: datetime.strptime(x[1]['Starttime'], '%Y-%m-%d %H:%M') if x[1]['Starttime'] != '-' else datetime.min
            )[::-1]  # 정렬된 리스트를 뒤집음 (reverse 효과)

            # 정렬된 결과를 리스트로 분리
            currentDB['DBlist'], currentDB['DBdata'], currentDB['DBtable'] = map(list, zip(*sorted_data))

            return currentDB

        self.mySQL_obj.connectDB('crawler_db')
        db_list = self.mySQL_obj.TableToList('db_list')

        currentDB = {
            'DBlist': [],
            'DBdata': [],
            'DBtable': []
        }

        self.fullstorage = 0
        self.activate_crawl = 0

        for DBdata in db_list:
            DB_name = DBdata[0]
            db_split = DB_name.split('_')
            crawltype = db_split[0]

            match crawltype:
                case 'navernews':
                    crawltype = 'Naver News'
                case 'naverblog':
                    crawltype = 'Naver Blog'
                case 'navercafe':
                    crawltype = 'Naver Cafe'
                case 'youtube':
                    crawltype = 'YouTube'

            startdate = db_split[2]
            enddate   = db_split[3]
            option    = DBdata[1]
            starttime = DBdata[2]
            endtime   = DBdata[3]

            status = "Done"
            if endtime == '-' or endtime == '크롤링 중':
                endtime = '크롤링 중'
                status  = 'Working'
            elif endtime == 'X':
                endtime = '오류 중단'
                status  = "Error"

            requester = DBdata[4]
            if requester == 'admin' and self.user != 'admin':
                continue

            if self.SETTING['MyDB'] == 'mydb' and requester != self.user:
                continue

            keyword = DBdata[5]
            size    = float(DBdata[6])
            self.fullstorage += float(size)
            if size == 0:
                try:
                    size = self.mySQL_obj.showDBSize(DB_name)
                    if size is None:
                        size = (0, 0)
                except:
                    size = (0, 0)
                self.fullstorage += float(size[0])
                size = f"{size[1]} MB" if size[0] < 1 else f"{size[0]} GB"
            else:
                size = f"{int(size * 1024)} MB" if size < 1 else f"{size} GB"
            crawlcom   = DBdata[7]
            crawlspeed = DBdata[8]
            datainfo   = DBdata[9]

            DBdata = {
                'DB': DB_name,
                'Crawltype': crawltype,
                'Keyword': keyword,
                'Startdate': startdate,
                'Enddate': enddate,
                'Option': option,
                'Starttime': starttime,
                'Endtime': endtime,
                'Status': status,
                'Requester': requester,
                'Size': size,
                'Crawlcom': crawlcom,
                'Crawlspeed': crawlspeed,
                'Datainfo': datainfo
            }

            currentDB['DBlist'].append(DB_name)
            currentDB['DBdata'].append(DBdata)
            currentDB['DBtable'].append((DB_name, crawltype, keyword, db_split[2], db_split[3], option, status, requester, size))

        self.activate_crawl = len([item for item in currentDB['DBdata'] if item['Status'] == "Working"])
        self.fullstorage = round(self.fullstorage, 2)

        if self.SETTING['DBKeywordSort'] != 'default':
            currentDB = sort_currentDB_by_keyword(currentDB)
        else:
            currentDB = sort_currentDB_by_starttime(currentDB)

        return currentDB

    def table_maker(self, widgetname, data, column, right_click_function=None, popupsize=None):
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

    def table_view(self, dbname, tablename, popupsize=None):
        class SingleTableWindow(QMainWindow):
            def __init__(self, parent=None, target_db=None, target_table=None, popupsize=None):
                super(SingleTableWindow, self).__init__(parent)
                self.setWindowTitle(f"{target_db} -> {target_table}")
                self.setGeometry(100, 100, 1600, 1200)

                self.parent = parent  # 부모 객체 저장
                self.target_db = target_db  # 대상 데이터베이스 이름 저장
                self.target_table = target_table  # 대상 테이블 이름 저장

                self.popupsize = popupsize

                self.central_widget = QWidget(self)
                self.setCentralWidget(self.central_widget)

                self.layout = QVBoxLayout(self.central_widget)

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

                # target_db와 target_table이 주어지면 테이블 뷰를 초기화
                if target_db is not None and target_table is not None:
                    self.init_table_view(parent.mySQL_obj, target_db, target_table)

            def closeWindow(self):
                self.close()  # 창 닫기
                self.deleteLater()  # 객체 삭제
                gc.collect()

            def closeEvent(self, event):
                # 윈도우 창이 닫힐 때 closeWindow 메서드 호출
                self.closeWindow()
                event.accept()  # 창 닫기 이벤트 허용

            def init_table_view(self, mySQL_obj, target_db, target_table):
                # target_db에 연결
                mySQL_obj.connectDB(target_db)
                tableDF = mySQL_obj.TableToDataframe(target_table)

                tableDF = tableDF.iloc[::-1].reset_index(drop=True)

                # 데이터프레임 값을 문자열로 변환하여 튜플 형태의 리스트로 저장
                self.tuple_list = [tuple(str(cell) for cell in row[1:]) for row in
                                   tableDF.itertuples(index=False, name=None)]

                # 테이블 위젯 생성
                new_table = QTableWidget(self.central_widget)
                self.layout.addWidget(new_table)

                # column 정보를 리스트로 저장
                columns = list(tableDF.columns)
                columns.pop(0)
                # table_maker 함수를 호출하여 테이블 설정
                self.parent.table_maker(new_table, self.tuple_list, columns, popupsize=self.popupsize)

        try:
            def destory_table():
                del self.DBtable_window
                gc.collect()
            self.DBtable_window = SingleTableWindow(self, dbname, tablename, popupsize)
            self.DBtable_window.destroyed.connect(destory_table)
            self.DBtable_window.show()

        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def pw_check(self, admin=False, string=""):
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

    def update_style_html(self):
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
            self.right_label.setText(msg)
            QCoreApplication.processEvents(QEventLoop.AllEvents, 0)

    def openFileExplorer(self, path):
        # 저장된 폴더를 파일 탐색기로 열기
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            os.system(f"open '{path}'")
        else:  # Linux and other OS
            os.system(f"xdg-open '{path}'")
        
    def program_bug_log(self, text):
        print(text)
        self.printStatus("오류 발생")
        if self.user == 'admin':
            QMessageBox.critical(self, "Error", f"오류가 발생했습니다\n\nError Log: {text}")
        else:
            QMessageBox.critical(self, "Error", f"오류가 발생했습니다")
        log_to_text(f"Exception: {text}")
        self.user_bugging(text)
        reply = QMessageBox.question(self, 'Bug Report', "버그 리포트를 전송하시겠습니까?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self.Manager_Board_obj.board_add_bug()
        self.printStatus()

    def closeEvent(self, event):
        # 프로그램 종료 시 실행할 코드
        reply = QMessageBox.question(self, 'Shutdown', "프로그램을 종료하시겠습니까?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            try:
                if self.CONFIG['Logging'] == 'On' and self.user != 'admin':
                    self.user_logging('Shutdown', force=True)
                    self.mySQL_obj.connectDB(f'{self.user}_db')  # userDB 접속
                    self.mySQL_obj.updateTableCell('manager_record', -1, 'D_Log', log_text, add=True)
                self.temp_cleanup()
            except Exception as e:
                print(traceback.format_exc())
            event.accept()  # 창을 닫을지 결정 (accept는 창을 닫음)
        else:
            event.ignore()

    def temp_cleanup(self):
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
            current_version = version.Version(self.versionNum)

            for file_name in os.listdir(exe_file_path):
                match = pattern.match(file_name)
                if match:
                    file_version = version.Version(match.group(1))  # 버전 추출 및 비교를 위해 Version 객체로 변환
                    # 현재 버전을 제외한 파일 삭제
                    if file_version != current_version:
                        file_path = os.path.join(exe_file_path, file_name)
                        os.remove(file_path)

        except Exception as e:
            print(e)

    def chatgpt_generate(self, query):
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

    #################### DEVELOPER MODE ###################

    def developer_mode(self, toggle):
        try:
            if toggle == True:
                open_console("DEVELOPER MODE")
                toggle_logging(True)
                print(log_text)
            else:
                close_console()
                toggle_logging(False)
        except:
            pass

    def install_event_filter_all_widgets(self, widget):
        """재귀적으로 모든 자식 위젯에 EventLogger를 설치하는 함수"""
        widget.installEventFilter(self.event_logger)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self.event_logger)

# 로그 출력 제어 변수와 로그 저장 변수
logging_enabled = False  # 콘솔 출력 여부를 조절
log_text = ""  # 모든 로그 메시지를 저장하는 변수

def setup_logging():
    """로그 설정 초기화"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    logging.getLogger().setLevel(logging.CRITICAL)  # 초기에는 콘솔 출력 방지


def toggle_logging(enable):
    """
    콘솔에 로그를 출력할지 여부를 결정.
    인자로 True 또는 False를 받아 INFO 레벨과 CRITICAL 레벨로 전환.
    """
    global logging_enabled
    logging_enabled = enable
    logging.getLogger().setLevel(logging.DEBUG if logging_enabled else logging.CRITICAL)


def log_to_text(message):
    """
    모든 로그 메시지를 log_text에 저장하고, logging_enabled가 True일 경우 콘솔에도 출력.
    """
    global log_text
    timestamped_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}"  # 타임스탬프 추가
    log_text += f"{timestamped_message}\n"  # 모든 로그를 log_text에 기록
    if logging_enabled:
        print(timestamped_message)  # logging_enabled가 True일 때만 콘솔에 출력


# 예외 발생 시 log_to_text에 기록하는 함수
def exception_handler(exc_type, exc_value, exc_traceback):
    error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_to_text(f"Exception: {error_message}")

# 전역 예외 처리기를 설정하여 모든 예외를 log_to_text에 기록
sys.excepthook = exception_handler

class EventLogger(QObject):
    """이벤트 로그를 생성하고 log_text에 모든 로그를 쌓아두는 클래스"""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            log_to_text(f"MouseButtonPress on {obj}")
        elif event.type() == QEvent.KeyPress:
            log_to_text(f"KeyPress: {event.key()} on {obj}")
        elif event.type() == QEvent.FocusIn:
            log_to_text(f"FocusIn on {obj}")
        elif event.type() == QEvent.FocusOut:
            log_to_text(f"FocusOut on {obj}")
        elif event.type() == QEvent.MouseButtonDblClick:
            log_to_text(f"Double-click on {obj}")
        elif event.type() == QEvent.Resize:
            log_to_text(f"{obj} resized")
        elif event.type() == QEvent.Close:
            log_to_text(f"{obj} closed")

        return super().eventFilter(obj, event)

#######################################################

if __name__ == '__main__':
    # 메인 윈도우 실행
    application = MainWindow(splash_dialog)
    sys.exit(app.exec_())
