import os
import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QShortcut, QVBoxLayout, QTextEdit, QHeaderView, \
    QHBoxLayout, QAction, QLabel, QStatusBar, QDialog, QInputDialog, QLineEdit, QMessageBox, QFileDialog, QSizePolicy, \
    QPushButton
from PyQt5.QtCore import Qt, QTimer, QCoreApplication, QObject, QEvent
from PyQt5.QtGui import QKeySequence, QPixmap, QFont, QPainter, QBrush, QColor, QIcon
from openai import OpenAI
from mySQL import mySQL
from Manager_Database import Manager_Database
from Manager_Web import Manager_Web
from Manager_Board import Manager_Board
from Manager_User import Manager_User
from Manager_Analysis import Manager_Analysis
from Manager_Console import open_console, close_console
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from datetime import datetime
import platform
import requests
from packaging import version
import pandas as pd
from os import environ
from pathlib import Path
import socket
import gc
import warnings
import traceback
import re
import logging
import shutil

warnings.filterwarnings("ignore")

VERSION = '2.2.2'
DB_IP = '121.152.225.232'
LOCAL_IP = '192.168.0.3'

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, splash_dialog):
        self.versionNum = VERSION
        self.version = 'Version ' + self.versionNum

        super(MainWindow, self).__init__()
        ui_path = os.path.join(os.path.dirname(__file__), 'BIGMACLAB_MANAGER_GUI.ui')
        icon_path = os.path.join(os.path.dirname(__file__), 'exe_icon.png')
        uic.loadUi(ui_path, self)

        self.setWindowTitle("MANAGER")  # 창의 제목 설정
        self.setWindowIcon(QIcon(icon_path))

        if platform.system() == "Windows":
            self.resize(1400, 1000)
            # self.showMaximized()  # 전체 화면으로 창 열기
        else:
            self.resize(1400, 1000)

        self.splash_dialog = splash_dialog  # InfoDialog 객체를 받아옵니다
        self.setStyle()
        self.statusBar_init()
        self.decrypt_process()

        setup_logging()
        self.event_logger = EventLogger()
        self.install_event_filter_all_widgets(self)

        def load_program():
            try:
                self.check_internet_connection()
                # open_console("Booting Process")
                self.listWidget.currentRowChanged.connect(self.display)

                if platform.system() == "Windows":
                    local_appdata_path = os.getenv("LOCALAPPDATA")
                    desktop_path = os.path.join(os.getenv("USERPROFILE"), "Desktop")

                    self.default_directory = "C:/BIGMACLAB_MANAGER"
                    if not os.path.exists(self.default_directory):
                        os.makedirs(self.default_directory)
                else:
                    self.default_directory = '/Users/yojunsmacbookprp/Desktop/BIGMACLAB_MANAGER'

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
                if socket.gethostname() in ['DESKTOP-502IMU5', 'DESKTOP-0I9OM9K', 'BigMacServer']:
                    DB_ip = LOCAL_IP

                self.network_text = (
                    "\n\n[ DB 접속 반복 실패 시... ]\n"
                    "\n1. Wi-Fi 또는 유선 네트워크가 정상적으로 작동하는지 확인하십시오"
                    "\n2. 네트워크 호환성에 따라 DB 접속이 불가능한 경우가 있습니다. 다른 네트워크 연결을 시도해보십시오\n"
                )

                # Loading User info from DB
                while True:
                    try:
                        self.mySQL_obj = mySQL(host=DB_ip, user='admin', password=self.public_password, port=3306)
                        print("\nLoading User Info from DB... ", end='')
                        if self.mySQL_obj.showAllDB() == []:
                            raise
                        # DB 불러오기
                        self.Manager_User_obj = Manager_User(self)
                        self.userNameList = self.Manager_User_obj.userNameList  # User Table 유저 리스트
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
                            continue
                        else:
                            os._exit(0)

                # User Checking & Login Process
                print("\nChecking User... ", end='')
                if self.login_program() == False:
                    os._exit(0)

                # Loading Data from DB & Making object
                while True:
                    try:
                        print("\nLoading Data from DB... ", end='')
                        self.DB = self.update_DB()
                        self.Manager_Database_obj = Manager_Database(self)
                        self.Manager_Web_obj = Manager_Web(self)
                        self.Manager_Board_obj = Manager_Board(self)
                        self.Manager_Analysis_obj = Manager_Analysis(self)
                        self.Manager_userDB_generate = False
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
                            continue
                        else:
                            os._exit(0)

                self.close_bootscreen()
                self.shortcut_init()
                self.Manager_Database_obj.database_shortcut_setting()

                print(f"\n{self.user}님 환영합니다!")

                self.user_logging(f'Booting ({self.user_location()})', booting=True)
                self.update_program()

                # close_console()

            except Exception as e:
                print(traceback.format_exc())
                self.close_bootscreen()
                self.printStatus()
                msg = f'[ Admin CRITICAL Notification ]\n\nThere is Error in MANAGER Booting\n\nError Log: {traceback.format_exc()}'
                self.send_pushOver(msg, self.admin_pushoverkey)
                QMessageBox.critical(self, "Error", f"부팅 과정에서 오류가 발생했습니다\n\nError Log: {traceback.format_exc()}")
                QMessageBox.information(self, "Information", f"관리자에게 에러 상황과 로그가 전달되었습니다\n\n프로그램을 종료합니다")
                os._exit(0)

        self.listWidget.setCurrentRow(0)
        QTimer.singleShot(1, load_program)
        QTimer.singleShot(1000, lambda: self.printStatus(f"{self.fullstorage} GB / 2 TB"))

    def close_bootscreen(self):
        try:
            self.splash_dialog.accept()  # InfoDialog 닫기
            self.show()  # MainWindow 표시
        except:
            print(traceback.format_exc())

    def decrypt_process(self):
        current_position = os.path.dirname(__file__)

        # 암호화 키 로드
        def load_key():
            try:
                with open(os.path.join(current_position, 'env.key'), "rb") as key_file:
                    return key_file.read()
            except:
                secret_key = os.getenv("SECRET_KEY")
                return secret_key

        def decrypt_env_file(encrypted_file_path):
            key = load_key()
            fernet = Fernet(key)

            # 암호화된 파일 읽기
            with open(encrypted_file_path, "rb") as file:
                encrypted_data = file.read()

            # 파일 복호화 및 .decrypted_env 파일로 저장
            decrypted_data = fernet.decrypt(encrypted_data).decode("utf-8")
            with open(os.path.join(current_position, 'decrypted_env'), "w", encoding="utf-8") as dec_file:
                dec_file.write(decrypted_data)

        decrypt_env_file(os.path.join(current_position, 'encrypted_env'))
        load_dotenv(os.path.join(current_position, 'decrypted_env'))

        self.admin_password = os.getenv('ADMIN_PASSWORD')
        self.public_password = os.getenv('PUBLIC_PASSWORD')
        self.admin_pushoverkey = os.getenv('ADMIN_PUSHOVER')
        self.gpt_api_key = os.getenv('GPT_APIKEY')
        self.db_ip = os.getenv('DB_IP')

        if os.path.exists(os.path.join(current_position, 'decrypted_env')):
            os.remove(os.path.join(current_position, 'decrypted_env'))

    def user_logging(self, text='', booting=False):
        try:
            self.mySQL_obj.disconnectDB()
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

            text = f'\n\n[{str(datetime.now().time())[:-7]}] : {text}'
            self.mySQL_obj.updateTableCell('manager_record', -1, 'Log', text, add=True)
        except Exception as e:
            print(traceback.format_exc())

    def user_bugging(self, text=''):
        try:
            self.mySQL_obj.disconnectDB()
            self.mySQL_obj.connectDB(f'{self.user}_db')  # userDB 접속
            text = f'\n\n[{str(datetime.now().time())[:-7]}] : {text}'
            self.mySQL_obj.updateTableCell('manager_record', -1, 'Bug', text, add=True)
        except Exception as e:
            print(traceback.format_exc())

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

    def login_program(self):
        def admin_notify():
            msg = f'[ Admin Notification ]\n\nUnknown tried to connect\n\nLocation: {self.user_location(True)}'
            self.send_pushOver(msg, self.admin_pushoverkey)

        try:
            current_device = socket.gethostname()
            self.user_device = current_device
            if current_device in self.device_list:
                print("Done")
                self.user = self.user_list[self.device_list.index(current_device)]
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
                    admin_notify()
                    QMessageBox.warning(self, 'Unknown User', '등록되지 않은 사용자입니다\n\n프로그램을 종료합니다')
                    return False

                answer_password = self.admin_password if user_name == 'admin' else self.public_password
                admin_mode = True if user_name == 'admin' else False

                self.user = user_name
                ok, password = self.pw_check(admin_mode)
                if ok and password == answer_password:
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
                    QMessageBox.warning(self, 'Wrong Password', '비밀번호가 올바르지 않습니다\n\n프로그램을 종료합니다')
                    admin_notify()
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

    def update_program(self, sc=False):
        try:
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

            # New version check
            current_version = version.parse(self.versionNum)
            self.new_version = version.parse(self.Manager_Board_obj.board_version_newcheck())
            if current_version < self.new_version:
                self.Manager_Board_obj.board_version_refresh()
                version_info_html = f"""
                    <style>
                        table {{
                            width: 100%;
                            border-collapse: collapse;
                        }}
                        th, td {{
                            border: 1px solid #bdc3c7;
                            padding: 8px;
                            text-align: left;
                            font-family: Arial, sans-serif;
                        }}
                        th {{
                            background-color: #34495e;
                            color: white;
                        }}
                        td {{
                            color: #34495e;
                        }}
                        h4 {{
                            text-align: center;
                        }}
                    </style>
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
                    open_console("Version Download Process")
                    if platform.system() == "Windows":
                        msg = (
                            "[ Admin Notification ]\n\n"
                            f"{self.user} updated {current_version} -> {self.new_version}\n\n{self.user_location()}"
                        )
                        self.send_pushOver(msg, self.admin_pushoverkey)
                        self.user_logging(f'Program Update ({current_version} -> {self.new_version})')

                        self.printStatus("버전 업데이트 중...")
                        import subprocess
                        download_file_path = os.path.join('C:/Temp', f"BIGMACLAB_MANAGER_{self.new_version}.exe")
                        download_file(f"https://knpu.re.kr:90/download/BIGMACLAB_MANAGER_{self.new_version}.exe",
                                      download_file_path)
                        subprocess.Popen([download_file_path], shell=True)
                        close_console()
                        os._exit(0)
                else:
                    QMessageBox.information(self, "Information", 'Ctrl+U 단축어로 프로그램 실행 중 업데이트 가능합니다')
                    return
            else:
                if sc == True and platform.system() == "Windows":
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

    def statusBar_init(self):
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

    def menubar_init(self):
        import webbrowser
        def showInfoDialog():
            dialog = SplashDialog(self.version)
            dialog.exec_()

        menubar = self.menuBar()

        # 파일 메뉴 생성
        infoMenu = menubar.addMenu('&Info')
        # 액션 생성
        infoAct = QAction('About MANAGER', self)
        infoAct.triggered.connect(showInfoDialog)
        infoMenu.addAction(infoAct)

        helpMenu = menubar.addMenu('&Help')
        helpAct = QAction('Help', self)
        helpAct.triggered.connect(lambda: webbrowser.open('https://knpu.re.kr/tool'))

        helpMenu.addAction(helpAct)
        # editMenu.addAction(copyAct)
        # editMenu.addAction(pasteAct)

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
        self.ctrlpp = QShortcut(QKeySequence("Ctrl+Shift+P"), self)

        self.ctrlu.activated.connect(lambda: self.update_program(True))
        self.ctrlp.activated.connect(lambda: self.developer_mode(True))
        self.ctrlpp.activated.connect(lambda: self.developer_mode(False))

    def shortcut_initialize(self):
        shortcuts = [self.ctrld, self.ctrls, self.ctrlv, self.ctrla, self.ctrll, self.ctrle, self.ctrlr, self.ctrlk,
                     self.ctrlm]
        for shortcut in shortcuts:
            try:
                shortcut.activated.disconnect()
            except TypeError:
                # 연결된 슬롯이 없는 경우 발생하는 에러를 무시
                pass

    def update_DB(self):
        self.mySQL_obj.connectDB('crawler_db')
        db_list = self.mySQL_obj.TableToList('db_list')

        currentDB = {
            'DBdata': [],
            'DBlist': [],
            'DBinfo': []
        }

        self.fullstorage = 0
        self.activate_crawl = 0
        for DBdata in db_list:
            DB_name = DBdata[0]
            db_split = DB_name.split('_')
            crawltype = db_split[0]
            keyword = db_split[1]
            date = f"{db_split[2]}~{db_split[3]}"

            option = DBdata[1]
            starttime = DBdata[2]
            endtime = DBdata[3]

            if endtime == '-':
                endtime = '크롤링 중'
            elif endtime == 'X':
                endtime = '오류 중단'

            requester = DBdata[4]
            keyword = DBdata[5]
            size = float(DBdata[6])
            self.fullstorage += float(size)
            if size == 0:
                try:
                    size = self.mySQL_obj.showDBSize(DB_name)
                except:
                    size = 0
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

        for key in currentDB:
            currentDB[key].reverse()

        self.activate_crawl = len([item for item in currentDB['DBdata'] if item[6] == "크롤링 중"])
        self.fullstorage = round(self.fullstorage, 2)

        return currentDB

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

    def table_maker(self, widgetname, data, column, right_click_function=None):
        def show_details(item):
            # 이미 창이 열려있는지 확인
            if hasattr(self, "details_dialog") and self.details_dialog.isVisible():
                return  # 창이 열려있다면 새로 열지 않음

            # 팝업 창 생성
            self.details_dialog = QDialog()
            self.details_dialog.setWindowTitle("상세 정보")
            self.details_dialog.resize(600, 300)

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
                item.setToolTip(str(cell_data))  # Tooltip 설정
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

    def filefinder_maker(self, main_window):
        class EmbeddedFileDialog(QFileDialog):
            def __init__(self, parent=None, default_directory=None):
                super().__init__(parent)
                self.setFileMode(QFileDialog.ExistingFiles)
                self.setOptions(QFileDialog.DontUseNativeDialog)
                self.setNameFilters(["CSV Files (*.csv)"])  # 파일 필터 설정
                self.currentChanged.connect(self.on_directory_change)
                self.accepted.connect(self.on_accepted)
                self.rejected.connect(self.on_rejected)
                self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.main = main_window
                if default_directory:
                    self.setDirectory(default_directory)

            def on_directory_change(self, path):
                self.main.printStatus(f"{os.path.basename(path)} 선택됨")

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

    def setStyle(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f7f7f7;
                font-family: 'Tahoma';
                font-size: 14px;
            }
            QPushButton {
                background-color: #2c3e50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 13px;
                font-family: 'Tahoma';
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QLineEdit {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                font-family: 'Tahoma';
                font-size: 14px;
            }
            QTableWidget {

                border: 1px solid #bdc3c7;
                font-family: 'Tahoma';
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 8px;
                border: none;
                font-family: 'Tahoma';
                font-size: 14px;
            }
            QListWidget {
                background-color: #2c3e50;
                color: white;
                font-family: 'Tahoma';
                font-size: 14px;
                border: none;
                min-width: 150px;  /* 가로 크기 고정: 최소 크기 설정 */
                max-width: 150px;
            }
            QListWidget::item {
                height: 40px;  /* 각 아이템의 높이를 조정 */
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
                background-color: #f7f7f7;  /* Matches QMainWindow background */
            }
            QTabWidget::tab-bar {
                left: 5px;
            }
            QTabBar::tab {
                background: #2c3e50;  /* Matches QPushButton background */
                color: white;  /* Matches QPushButton text color */
                border: 1px solid #bdc3c7;
                border-bottom-color: #f7f7f7;  /* Matches QMainWindow background */
                border-radius: 4px;
                border-top-right-radius: 4px;
                padding: 10px;
                font-family: 'Tahoma';
                font-size: 14px;
                min-width: 100px;  /* 최소 가로 길이 설정 */
                max-width: 200px;  /* 최대 가로 길이 설정 */
            }
            QTabBar::tab:selected, QTabBar::tab:hover {
                background: #34495e;  /* Matches QPushButton hover background */
            }
            QTabBar::tab:selected {
                border-color: #9B9B9B;
                border-bottom-color: #f7f7f7;
            }
            QPushButton#pushButton_divide_DB {
                background-color: #2c3e50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Tahoma';
                font-size: 14px;
                min-width: 70px;  /* 최소 가로 길이 설정 */
                max-width: 100px;  /* 최대 가로 길이 설정 */
            }
            QPushButton#pushButton_divide_DB:hover {
                background-color: #34495e;
            }
            QLabel#label_status_divide_DB {
                background-color: #f7f7f7;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 8px;
                font-family: 'Tahoma';
                font-size: 14px;
            }
            """
        )

    def display(self, index):
        self.stackedWidget.setCurrentIndex(index)
        # self.update_program()
        # DATABASE
        if index == 0:
            self.Manager_Database_obj.database_shortcut_setting()
            self.Manager_Database_obj.database_refresh_DB()
            QTimer.singleShot(1000, lambda: self.printStatus(f"{self.fullstorage} GB / 2 TB"))
        # CRAWLER
        elif index == 1:
            self.shortcut_initialize()
            self.Manager_Web_obj.web_open_webbrowser('http://bigmaclab-crawler.kro.kr:81',
                                                     self.Manager_Web_obj.crawler_web_layout)
            QTimer.singleShot(1000, lambda: self.printStatus(f"활성 크롤러 수: {self.activate_crawl}"))
        # ANALYSIS
        elif index == 2:
            self.printStatus()
            self.Manager_Analysis_obj.analysis_shortcut_setting()
            self.Manager_Analysis_obj.dataprocess_refresh_DB()
        # BOARD
        elif index == 3:
            self.Manager_Board_obj.board_shortcut_setting()
            self.printStatus()
        # WEB
        elif index == 4:
            self.shortcut_initialize()
            self.printStatus()
            self.Manager_Web_obj.web_open_webbrowser('https://knpu.re.kr', self.Manager_Web_obj.web_web_layout)
        # USER
        elif index == 5:
            self.printStatus()
            if self.Manager_userDB_generate == False:
                self.Manager_User_obj.userDB_layout_maker()
                self.Manager_userDB_generate = True
            self.Manager_User_obj.user_shortcut_setting()

        gc.collect()

    def pw_check(self, admin=False):
        while True:
            input_dialog = QInputDialog(self)
            if admin == False:
                input_dialog.setWindowTitle('Password')
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

    def printStatus(self, msg=''):
        msg += ' '
        self.right_label.setText(msg)
        QtWidgets.QApplication.processEvents()

    def openFileExplorer(self, path):
        # 저장된 폴더를 파일 탐색기로 열기
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            os.system(f"open '{path}'")
        else:  # Linux and other OS
            os.system(f"xdg-open '{path}'")

    def send_pushOver(self, msg, user_key, image_path=False):
        app_key_list = ["a22qabchdf25zzkd1vjn12exjytsjx"]

        for app_key in app_key_list:
            try:
                # Pushover API 설정
                url = 'https://api.pushover.net/1/messages.json'
                # 메시지 내용
                message = {
                    'token': app_key,
                    'user': user_key,
                    'message': msg
                }
                # Pushover에 요청을 보냄
                if image_path == False:
                    response = requests.post(url, data=message)
                else:
                    response = requests.post(url, data=message, files={
                        "attachment": (
                            "image.png", open(image_path, "rb"),
                            "image/png")
                    })
                break
            except:
                continue

    def csvReader(self, csvPath):
        csv_data = pd.read_csv(csvPath, low_memory=False, index_col=0)
        csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
        return csv_data

    def chatgpt_generate(self, query):
        try:
            client = OpenAI(api_key=self.gpt_api_key)
            model = "gpt-4"
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": query},
                ]
            )
            content = response.choices[0].message.content
            return content
        except:
            return (0, "AI 분석에 오류가 발생하였습니다\n\nadmin에게 문의바랍니다")

    def program_bug_log(self, text):
        print(text)
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

    def closeEvent(self, event):
        # 프로그램 종료 시 실행할 코드
        reply = QMessageBox.question(self, 'Shutdown', "프로그램을 종료하시겠습니까?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            try:
                self.user_logging('Shutdown')
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
        except Exception as e:
            print(e)

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

class SplashDialog(QDialog):
    def __init__(self, version, booting=True):
        super().__init__()
        self.version = version
        if booting:
            self.setWindowFlags(Qt.FramelessWindowHint)  # 제목 표시줄 제거
        self.setAttribute(Qt.WA_TranslucentBackground)  # 배경을 투명하게 설정
        self.initUI()

    def initUI(self):
        # 창 크기 설정
        self.resize(450, 450)

        # 전체 레이아웃을 중앙 정렬로 설정
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(30, 30, 30, 30)  # 전체 여백 설정
        main_layout.setSpacing(15)  # 위젯 간격 확대

        # 프로그램 이름 라벨
        title_label = QLabel("MANAGER")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold;")  # 폰트 크기 확대
        main_layout.addWidget(title_label)

        # 이미지 라벨
        image_label = QLabel(self)
        pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'exe_icon.png'))
        pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 이미지 크기 유지
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(image_label)

        # 버전 정보 라벨
        version_label = QLabel(f"Version {self.version}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("font-size: 21px; color: black; margin-top: 5px;")  # 폰트 크기 유지
        main_layout.addWidget(version_label)

        # 상태 메시지 라벨
        self.status_label = QLabel("Loading...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 17px; color: gray; margin-top: 8px;")
        main_layout.addWidget(self.status_label)

        # 저작권 정보 라벨
        copyright_label = QLabel("Copyright © 2024 KNPU BIGMACLAB\nAll rights reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("font-size: 15px; color: gray; margin-top: 10px;")
        main_layout.addWidget(copyright_label)

    def paintEvent(self, event):
        # 둥근 모서리를 위한 QPainter 설정
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 안티앨리어싱 적용
        rect = self.rect()
        color = QColor(255, 255, 255)  # 배경색 설정 (흰색)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)  # 테두리를 없애기 위해 Pen 없음 설정
        painter.drawRoundedRect(rect, 30, 30)  # 모서리를 둥글게 그리기 (30px radius)


if __name__ == '__main__':
    environ["QT_DEVICE_PIXEL_RATIO"] = "0"
    environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    environ["QT_SCREEN_SCALE_FACTORS"] = "1"
    environ["QT_SCALE_FACTOR"] = "1"

    # High DPI 스케일링 활성화 (QApplication 생성 전 설정)
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QtWidgets.QApplication([])

    # 기본 폰트 설정 및 힌팅 설정
    font = QFont()
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    # 로딩 다이얼로그 표시
    splash_dialog = SplashDialog(version=VERSION)
    splash_dialog.show()

    # 메인 윈도우 실행
    application = MainWindow(splash_dialog)
    sys.exit(app.exec_())
