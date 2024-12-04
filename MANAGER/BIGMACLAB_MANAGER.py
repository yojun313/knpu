import os
import sys
from PyQt5 import uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QShortcut, QVBoxLayout, QTextEdit, QHeaderView, \
    QHBoxLayout, QLabel, QStatusBar, QDialog, QInputDialog, QLineEdit, QMessageBox, QFileDialog, QSizePolicy, \
    QPushButton, QMainWindow, QApplication, QSpacerItem, QStackedWidget, QListWidget
from PyQt5.QtCore import Qt, QTimer, QCoreApplication, QObject, QEvent, QSize
from PyQt5.QtGui import QKeySequence, QPixmap, QFont, QPainter, QBrush, QColor, QIcon
import speech_recognition as sr
import sounddevice as sd
from openai import OpenAI
from mySQL import mySQL
from Manager_Database import Manager_Database
from Manager_Web import Manager_Web
from Manager_Board import Manager_Board
from Manager_User import Manager_User
from Manager_Analysis import Manager_Analysis
from Manager_Console import open_console, close_console
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
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
import random
import warnings
import traceback
import re
import logging
import shutil
import textwrap
from gtts import gTTS
from playsound import playsound
import os
import tempfile

warnings.filterwarnings("ignore")

VERSION = '2.3.4'
DB_IP = '121.152.225.232'
LOCAL_IP = '192.168.0.3'

class MainWindow(QMainWindow):
    def __init__(self, splash_dialog):
        try:
            self.versionNum = VERSION
            self.version = 'Version ' + self.versionNum
            self.splash_dialog = splash_dialog
            self.recognizer = sr.Recognizer()

            super(MainWindow, self).__init__()
            ui_path = os.path.join(os.path.dirname(__file__), 'source', 'BIGMACLAB_MANAGER_GUI.ui')
            icon_path = os.path.join(os.path.dirname(__file__), 'source', 'exe_icon.png')

            uic.loadUi(ui_path, self)
            self.initialize_settings()
            self.initialize_listwidget()
            self.setWindowTitle("MANAGER")  # 창의 제목 설정
            self.setWindowIcon(QIcon(icon_path))

            if self.SETTING['ScreenSize'] == 'max':
                self.close_bootscreen()
                self.showMaximized()
            else:
                self.resize(1400, 1000)

            self.setStyle()
            self.statusBar_init()
            self.decrypt_process()

            setup_logging()
            self.event_logger = EventLogger()
            self.install_event_filter_all_widgets(self)

            def load_program():
                try:
                    self.startTime = datetime.now()
                    self.gpt_api_key = self.SETTING['GPT_Key']
                    self.CONFIG = {
                        'Logging': 'Off'
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
                    else:
                        self.program_directory = os.path.dirname(__file__)
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
                        "\n1. Wi-Fi 또는 유선 네트워크가 정상적으로 동작하는지 확인하십시오"
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
                            self.Manager_User_obj.userDB_layout_maker()
                            self.Manager_Board_obj = Manager_Board(self)
                            self.update_program(auto = self.SETTING['AutoUpdate'])
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
                                continue
                            else:
                                os._exit(0)

                    self.close_bootscreen()
                    self.shortcut_init()
                    self.Manager_Database_obj.database_shortcut_setting()

                    print(f"\n{self.user}님 환영합니다!")

                    self.user_logging(f'Booting ({self.user_location()})', booting=True)
                    self.check_configuration()
                    self.update_program()
                    self.newpost_check()

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

            self.listWidget.setCurrentRow(0)
            QTimer.singleShot(1, load_program)
            QTimer.singleShot(1000, lambda: self.printStatus(f"{self.fullstorage} GB / 2 TB"))
        except Exception as e:
            self.close_bootscreen()
            open_console()
            print(traceback.format_exc())

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
            env_content = textwrap.dedent("""\
                #Setting
                OPTION_1=default
                OPTION_2=default
                OPTION_3=default
                OPTION_4=default
                OPTION_5=default
                OPTION_6=default
                OPTION_7=default
                OPTION_8=default
                OPTION_9=default
                OPTION_10=default
                OPTION_11=default
                OPTION_12=default
                OPTION_13=default
                OPTION_14=default
                OPTION_15=default
                OPTION_16=default
                OPTION_17=default
                OPTION_18=default
                OPTION_19=default
                OPTION_21=default 
                OPTION_22=default 
                OPTION_23=default 
                OPTION_24=default 
                OPTION_25=default 
                OPTION_26=default 
                OPTION_27=default 
                OPTION_28=default 
                OPTION_29=default 
                OPTION_30=default 
                OPTION_31=default 
                OPTION_32=default 
                OPTION_33=default 
                OPTION_34=default 
                OPTION_35=default 
                OPTION_36=default 
                OPTION_37=default 
                OPTION_38=default 
                OPTION_39=default 
                OPTION_40=default 
                OPTION_41=default 
                OPTION_42=default 
                OPTION_43=default 
                OPTION_44=default 
                OPTION_45=default 
                OPTION_46=default 
                OPTION_47=default 
                OPTION_48=default
                OPTION_49=default 
                OPTION_50=default
            """)
            if platform.system() == 'Windows':
                setting_folder_path = os.path.join(os.environ['LOCALAPPDATA'], 'MANAGER')
                if not os.path.exists(setting_folder_path):
                    os.makedirs(setting_folder_path)
                self.setting_path = os.path.join(setting_folder_path, 'settings.env')
                if not os.path.exists(self.setting_path):
                    # 파일 쓰기
                    with open(self.setting_path, "w", encoding="utf-8") as env_file:
                        env_file.write(env_content)

                load_dotenv(self.setting_path)
            else:
                self.setting_path = os.path.join(os.path.dirname(__file__), 'settings.env')
                if not os.path.exists(self.setting_path):
                    # 파일 쓰기
                    with open(self.setting_path, "w", encoding="utf-8") as env_file:
                        env_file.write(env_content)
                load_dotenv(self.setting_path)
            self.SETTING = {
                'path': self.setting_path,
                'Theme': os.getenv("OPTION_1"),
                'ScreenSize': os.getenv("OPTION_2"),
                'OldPostTitle': os.getenv("OPTION_3"),
                'AutoUpdate': os.getenv("OPTION_4"),
                'MyDB': os.getenv("OPTION_5"),
                'GPT_Key': os.getenv("OPTION_6"),
                'DB_Refresh': os.getenv("OPTION_7"),
            }
        except Exception as e:
            print(traceback.format_exc())
            self.SETTING = {
                'path': 'default',
                'Theme': 'default',
                'ScreenSize': 'default',
                'OldPostTitle': 'default',
                'AutoUpdate': 'default',
                'MyDB': 'default',
                'GPT_Key': 'default',
                'DB_Refresh': 'default',
            }

    def update_settings(self, option_key, new_value):
        try:
            option_key = f"OPTION_{option_key}"
            file_path = self.SETTING['path']
            # .env 파일 읽기
            lines = []
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding="utf-8") as file:
                    lines = file.readlines()

            # 변경된 내용을 다시 작성
            with open(file_path, 'w', encoding="utf-8") as file:
                key_found = False
                for line in lines:
                    key, sep, value = line.partition("=")
                    key = key.strip()
                    if key == option_key:  # 키가 존재하면 값을 변경
                        file.write(f"{option_key}={new_value}\n")
                        key_found = True
                    else:  # 키가 다르면 기존 내용 유지
                        file.write(line)

                if not key_found:  # 키가 없으면 새로 추가
                    file.write(f"{option_key}={new_value}\n")

            return True
        except Exception as e:
            print(traceback.format_exc())
            return False

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
                with open(os.path.join(current_position, 'source', 'env.key'), "rb") as key_file:
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

        decrypt_env_file(os.path.join(current_position, 'source', 'encrypted_env'))
        load_dotenv(os.path.join(current_position, 'decrypted_env'))

        self.admin_password = os.getenv('ADMIN_PASSWORD')
        self.public_password = os.getenv('PUBLIC_PASSWORD')
        self.admin_pushoverkey = os.getenv('ADMIN_PUSHOVER')
        self.db_ip = os.getenv('DB_IP')

        if os.path.exists(os.path.join(current_position, 'decrypted_env')):
            os.remove(os.path.join(current_position, 'decrypted_env'))

    def user_logging(self, text='', booting=False):
        try:
            if self.CONFIG['Logging'] == 'Off':
                return
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

    def check_configuration(self):
        try:
            self.mySQL_obj.connectDB('bigmaclab_manager_db')
            configDF = self.mySQL_obj.TableToDataframe('configuration')
            self.CONFIG = dict(zip(configDF[configDF.columns[1]], configDF[configDF.columns[2]]))

            return self.CONFIG
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

    def user_settings(self):
        try:
            self.user_logging(f'User Setting')
            dialog = SettingsDialog(self, self.SETTING)
            if dialog.exec_() == QDialog.Accepted:
                QMessageBox.information(self, "Information", f"설정이 완료되었습니다")
                if self.SETTING['Theme'] == 'default':
                    self.setLightStyle()
                else:
                    self.setDarkStyle()
                self.Manager_Analysis_obj.file_dialog.set_theme()


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

                random_pw = ''.join(random.choices('0123456789', k=6))
                msg = (
                    f"사용자: {self.user}\n"
                    f"디바이스: {current_device}\n"
                    f"인증 위치: {self.user_location()}\n\n"
                    f"인증 번호 '{random_pw}'를 입력하십시오"
                )
                self.send_email(self.usermail, "[MANAGER] 디바이스 등록 인증번호", msg)
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
                self.user_logging(f'Program Update ({current_version} -> {self.new_version})')

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
                elif auto == 'default':
                    return
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
                    update_process()
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

    def newpost_check(self):
        new_post_text = self.Manager_Board_obj.post_data[0][1]
        new_post_writer = self.Manager_Board_obj.post_data[0][0]
        old_post_text = self.SETTING['OldPostTitle']
        if new_post_text == old_post_text:
            return
        elif old_post_text == 'default':
            self.update_settings(3, new_post_text)
        elif new_post_text != old_post_text:
            if self.user != new_post_writer:
                reply = QMessageBox.question(self, "New Post", "새로운 게시물이 업로드되었습니다\n\n확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.Manager_Board_obj.board_view_post(0)
            self.update_settings(3, new_post_text)

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
        self.cmdpp = QShortcut(QKeySequence("Ctrl+Shift+ㅔ"), self)

        self.ctrlu.activated.connect(lambda: self.update_program(True))
        self.ctrlp.activated.connect(lambda: self.developer_mode(True))
        self.ctrlpp.activated.connect(lambda: self.developer_mode(False))

        self.cmdu.activated.connect(lambda: self.update_program(True))
        self.cmdp.activated.connect(lambda: self.developer_mode(True))
        self.cmdpp.activated.connect(lambda: self.developer_mode(False))

    def shortcut_initialize(self):
        shortcuts = [self.ctrld, self.ctrls, self.ctrlv, self.ctrla, self.ctrll, self.ctrle, self.ctrlr, self.ctrlk, self.ctrlm, self.ctrlc,
                     self.cmdd, self.cmds, self.cmdv, self.cmda, self.cmdl, self.cmde, self.cmdr, self.cmdk, self.cmdm, self.cmdc]
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
                self.set_theme()
                if default_directory:
                    self.setDirectory(default_directory)

            def set_theme(self):
                if self.main.SETTING['Theme'] == 'dark':
                    # 스타일 시트를 추가하여 다크 테마 적용
                    self.setStyleSheet("""
                        QFileDialog {
                            background-color: #2e2e2e;
                            color: #ffffff;
                        }
                        QTreeView, QListView {
                            background-color: #2e2e2e;
                            color: #ffffff;
                        }
                        QLineEdit {
                            background-color: #3a3a3a;
                            color: #ffffff;
                            border: 1px solid #3a3a3a;
                        }
                        QPushButton {
                            background-color: #444444;
                            color: #ffffff;
                            border: 1px solid #3a3a3a;
                            padding: 5px;
                        }
                        QPushButton:hover {
                            background-color: #555555;
                        }
                        QScrollBar:vertical, QScrollBar:horizontal {
                            background: #2a2a2a;
                            border: 1px solid #3a3a3a;
                        }
                        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                            background: #3a3a3a;
                            border-radius: 4px;
                        }
                        QScrollBar::add-line, QScrollBar::sub-line {
                            background: #2a2a2a;
                        }
                    """)
                else:
                    self.setStyleSheet("""
                        QFileDialog {
                            background-color: #ffffff;
                            color: #000000;
                        }
                        QTreeView, QListView {
                            background-color: #f8f8f8;
                            color: #000000;
                        }
                        QLineEdit {
                            background-color: #ffffff;
                            color: #000000;
                            border: 1px solid #d0d0d0;
                        }
                        QPushButton {
                            background-color: #e0e0e0;
                            color: #000000;
                            border: 1px solid #d0d0d0;
                            padding: 5px;
                        }
                        QPushButton:hover {
                            background-color: #d8d8d8;
                        }
                        QScrollBar:vertical, QScrollBar:horizontal {
                            background: #f0f0f0;
                            border: 1px solid #d0d0d0;
                        }
                        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                            background: #d0d0d0;
                            border-radius: 4px;
                        }
                        QScrollBar::add-line, QScrollBar::sub-line {
                            background: #f0f0f0;
                        }
                    """)

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

        if self.SETTING['Theme'] == 'default':
            self.setLightStyle()
        else:
            self.setDarkStyle()

    def setLightStyle(self):
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
            """
        )

    def setDarkStyle(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #2b2b2b;
                font-family: 'Tahoma';
                font-size: 14px;
                color: #eaeaea;  /* 기본 텍스트 색상 */
            }
            QPushButton {
                background-color: #34495e;
                color: #eaeaea;  /* 버튼 텍스트 색상 */
                border: none;
                border-radius: 5px;
                padding: 13px;
                font-family: 'Tahoma';
                font-size: 15px;
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
                font-family: 'Tahoma';
                font-size: 14px;
            }
            QLabel {
                color: #eaeaea;  /* 라벨 기본 텍스트 색상 */
                font-family: 'Tahoma';
                font-size: 14px;
            }
            QTableWidget {
                background-color: #2b2b2b;  /* 테이블 전체 배경 */
                gridline-color: #5a5a5a;  /* 셀 간격선 색상 */
                color: #eaeaea;  /* 셀 텍스트 색상 */
                font-family: 'Tahoma';
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
                font-family: 'Tahoma';
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
                background-color: #3a539b;
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
                font-family: 'Tahoma';
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
                font-family: 'Tahoma';
                font-size: 14px;
            }
            QMessageBox {
                background-color: #2b2b2b;  /* 메시지 박스 배경색 */
                color: #eaeaea;  /* 메시지 텍스트 색상 */
                font-family: 'Tahoma';
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
            """
        )

    def display(self, index):
        if index != 6:
            self.stackedWidget.setCurrentIndex(index)
        # self.update_program()
        # DATABASE
        if index == 0:
            self.Manager_Database_obj.database_shortcut_setting()
            if self.SETTING['DB_Refresh'] == 'default':
                self.Manager_Database_obj.database_refresh_DB()
            QTimer.singleShot(1000, lambda: self.printStatus(f"{self.fullstorage} GB / 2 TB"))
        # CRAWLER
        elif index == 1:
            self.shortcut_initialize()
            QTimer.singleShot(1000, lambda: self.printStatus(f"활성 크롤러 수: {self.activate_crawl}"))
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

    def printStatus(self, msg=''):
        msg += ' '
        self.right_label.setText(msg)
        QApplication.processEvents()

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

    def send_email(self, receiver, title, text):
        sender = "knpubigmac2024@gmail.com"
        MailPassword = 'vygn nrmh erpf trji'

        msg = MIMEMultipart()
        msg['Subject'] = title
        msg['From'] = sender
        msg['To'] = receiver

        msg.attach(MIMEText(text, 'plain'))

        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        # SMTP 연결 및 메일 보내기
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, MailPassword)
            server.sendmail(sender, receiver, msg.as_string())

    def csvReader(self, csvPath): 
        csv_data = pd.read_csv(csvPath, low_memory=False, index_col=0)
        csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
        return csv_data

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

    def microphone(self):
        with sr.Microphone() as source:
            audio = self.recognizer.listen(source)

        # Google Web Speech API를 사용하여 음성 인식
        try:
            return self.recognizer.recognize_google(audio, language='ko-KR')
        except sr.UnknownValueError:
            print(f"오류 발생\n{traceback.format_exc()}")
            return "음성 인식 실패"
        except sr.RequestError as e:
            print(f"오류 발생\n{traceback.format_exc()}")
            return "음성 인식 실패"

    def speecher(self, text):
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as temp_file:
                # gTTS를 사용해 텍스트를 음성으로 변환
                tts = gTTS(text=text, lang='ko')
                tts.save(temp_file.name)  # 임시 파일에 저장

                # 음성 파일 재생
                playsound(temp_file.name)
        except Exception as e:
            print(f"오류가 발생했습니다: {e}")
        
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
                if self.CONFIG['Logging'] == 'On':
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
    def __init__(self, version, theme="light", booting=True):
        super().__init__()

        if platform.system() == 'Windows':
            setting_path = os.path.join(os.path.join(os.environ['LOCALAPPDATA'], 'MANAGER'), 'settings.env')
            if os.path.exists(setting_path):
                load_dotenv(setting_path, encoding='utf-8')
                self.theme = os.getenv("OPTION_1")
            else:
                self.theme = 'default'
        else:
            setting_path = os.path.join(os.path.dirname(__file__), 'settings.env')
            load_dotenv(setting_path, encoding='utf-8')
            self.theme = os.getenv("OPTION_1")

        self.version = version
        if booting:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)  # 최상위 창 설정
        self.setAttribute(Qt.WA_TranslucentBackground)  # 배경을 투명하게 설정
        self.initUI()

    def initUI(self):
        # 창 크기 설정
        self.resize(450, 450)

        # 테마 색상 설정
        if self.theme == "dark":
            bg_color = QColor(45, 45, 45)  # 다크 배경색
            text_color = "white"
            gray_color = "lightgray"
        else:
            bg_color = QColor(255, 255, 255)  # 디폴트 배경색 (흰색)
            text_color = "black"
            gray_color = "gray"

        # 전체 레이아웃을 중앙 정렬로 설정
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(30, 30, 30, 30)  # 전체 여백 설정
        main_layout.setSpacing(15)  # 위젯 간격 확대

        # 프로그램 이름 라벨
        title_label = QLabel("MANAGER")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {text_color};")  # 폰트 크기 확대
        main_layout.addWidget(title_label)

        # 이미지 라벨
        image_label = QLabel(self)
        pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'source', 'exe_icon.png'))
        pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 이미지 크기 유지
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(image_label)

        # 버전 정보 라벨
        version_label = QLabel(f"Version {self.version}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet(f"font-size: 21px; color: {text_color}; margin-top: 5px;")  # 폰트 크기 유지
        main_layout.addWidget(version_label)

        # 상태 메시지 라벨
        self.status_label = QLabel("Loading...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font-size: 17px; color: {gray_color}; margin-top: 8px;")
        main_layout.addWidget(self.status_label)

        # 저작권 정보 라벨
        copyright_label = QLabel("Copyright © 2024 KNPU BIGMACLAB\nAll rights reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet(f"font-size: 15px; color: {gray_color}; margin-top: 10px;")
        main_layout.addWidget(copyright_label)

        # 배경 색상 저장
        self.bg_color = bg_color

    def paintEvent(self, event):
        # 둥근 모서리를 위한 QPainter 설정
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 안티앨리어싱 적용
        rect = self.rect()
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(Qt.NoPen)  # 테두리를 없애기 위해 Pen 없음 설정
        painter.drawRoundedRect(rect, 30, 30)  # 모서리를 둥글게 그리기 (30px radius)

class SettingsDialog(QDialog):
    def __init__(self, main, setting):
        super().__init__()
        self.main = main
        self.setting_path = setting['path']
        self.setWindowTitle("Settings")
        self.resize(800, 400)

        # 메인 레이아웃 생성
        main_layout = QVBoxLayout()  # QVBoxLayout으로 변경하여 아래쪽에 버튼 섹션 추가 가능

        # 상단 레이아웃 (카테고리 목록과 설정 페이지)
        content_layout = QHBoxLayout()

        # 왼쪽: 카테고리 목록
        self.category_list = QListWidget()
        self.category_list.addItem("앱 설정")
        self.category_list.addItem("DB 설정")
        self.category_list.addItem("정보")
        self.category_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                font-size: 14px;
                background-color: #f4f4f4; /* 리스트 전체 배경색 */
                border-radius: 8px; /* 둥근 모서리 */
            }
            QListWidget::item {
                padding: 10px;
                margin: 5px; /* 항목 간 간격 */
                background-color: #ffffff; /* 항목 기본 배경색 */
                border: 1px solid #ddd; /* 항목 테두리 */
                border-radius: 6px; /* 항목 둥근 모서리 */
            }
            QListWidget::item:hover {
                background-color: #34495e; /* 항목에 호버했을 때 배경색 */
                color: white;
            }
            QListWidget::item:selected {
                background-color: #34495e; /* 선택된 항목 배경색 */
                color: white; /* 선택된 항목 텍스트 색상 */
            }
        """)
        self.category_list.currentRowChanged.connect(self.display_category)
        self.category_list.setCurrentRow(0)  # 첫 번째 항목을 기본 선택

        # 오른쪽: 설정 내용 (Stacked Widget)
        self.stacked_widget = QStackedWidget()

        # 앱 설정 페이지 추가
        self.app_settings_page = self.create_app_settings_page(setting)
        self.stacked_widget.addWidget(self.app_settings_page)

        # DB 설정 페이지 추가
        self.db_settings_page = self.create_db_settings_page(setting)
        self.stacked_widget.addWidget(self.db_settings_page)

        # info 설정 페이지 추가
        self.info_settings_page = self.create_info_settings_page(setting)
        self.stacked_widget.addWidget(self.info_settings_page)

        # 콘텐츠 레이아웃 구성
        content_layout.addWidget(self.category_list, 2)
        content_layout.addWidget(self.stacked_widget, 6)

        # 저장 및 취소 버튼 섹션
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50; /* 기본 배경색 */
                color: white; /* 텍스트 색상 */
                font-size: 14px; /* 폰트 크기 */
                padding: 10px 20px; /* 내부 여백 */
                border-radius: 8px; /* 둥근 모서리 */
                border: none; /* 테두리 제거 */
            }
            QPushButton:hover {
                background-color: #34495e; /* 호버 시 배경색 */
            }
        """)
        save_button.clicked.connect(self.save_settings)  # 저장 버튼 클릭 이벤트 연결

        # 취소 버튼
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50; /* 기본 배경색 */
                color: white; /* 텍스트 색상 */
                font-size: 14px; /* 폰트 크기 */
                padding: 10px 20px; /* 내부 여백 */
                border-radius: 8px; /* 둥근 모서리 */
                border: none; /* 테두리 제거 */
            }
            QPushButton:hover {
                background-color: #34495e; /* 호버 시 배경색 */
            }
        """)
        cancel_button.clicked.connect(self.reject)  # 취소 버튼 클릭 이벤트 연결

        close_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        close_shortcut.activated.connect(self.reject)
        close_shortcut_mac = QShortcut(QKeySequence("Ctrl+ㅈ"), self)
        close_shortcut_mac.activated.connect(self.reject)
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_settings)
        save_shortcut_mac = QShortcut(QKeySequence("Ctrl+ㄴ"), self)
        save_shortcut_mac.activated.connect(self.save_settings)



        button_layout.addStretch()  # 버튼을 오른쪽으로 정렬
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        # 메인 레이아웃 구성
        main_layout.addLayout(content_layout)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def create_app_settings_page(self, setting):
        """
        앱 설정 페이지 생성
        """
        app_layout = QVBoxLayout()
        app_layout.setSpacing(10)  # 섹션 간 간격
        app_layout.setContentsMargins(10, 10, 10, 10)  # 여백 설정

        ################################################################################
        # 앱 테마 설정 섹션
        theme_layout = QHBoxLayout()
        theme_label = QLabel("앱 테마 설정:")
        theme_label.setAlignment(Qt.AlignLeft)
        theme_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        theme_label.setToolTip("MANAGER의 색 테마를 설정합니다")

        self.light_mode_toggle = QPushButton("라이트 모드")
        self.dark_mode_toggle = QPushButton("다크 모드")

        self.init_toggle_style(self.light_mode_toggle, setting['Theme'] == 'default')
        self.init_toggle_style(self.dark_mode_toggle, setting['Theme'] != 'default')

        self.light_mode_toggle.clicked.connect(
            lambda: self.update_toggle(self.light_mode_toggle, self.dark_mode_toggle)
        )
        self.dark_mode_toggle.clicked.connect(
            lambda: self.update_toggle(self.dark_mode_toggle, self.light_mode_toggle)
        )

        theme_buttons_layout = QHBoxLayout()
        theme_buttons_layout.setSpacing(10)
        theme_buttons_layout.addWidget(self.light_mode_toggle)
        theme_buttons_layout.addWidget(self.dark_mode_toggle)

        theme_layout.addWidget(theme_label, 1)
        theme_layout.addLayout(theme_buttons_layout, 2)

        app_layout.addLayout(theme_layout)
        ################################################################################

        ################################################################################
        # 부팅 스크린 사이즈 설정 섹션
        screen_size_layout = QHBoxLayout()
        screen_size_label = QLabel("부팅 시 창 크기:")
        screen_size_label.setAlignment(Qt.AlignLeft)
        screen_size_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        screen_size_label.setToolTip("MANAGER 부팅 시 기본 창 크기를 설정합니다")

        self.default_size_toggle = QPushButton("기본값")
        self.maximized_toggle = QPushButton("최대화")

        self.init_toggle_style(self.default_size_toggle, setting['ScreenSize'] == 'default')
        self.init_toggle_style(self.maximized_toggle, setting['ScreenSize'] != 'default')

        self.default_size_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_size_toggle, self.maximized_toggle)
        )
        self.maximized_toggle.clicked.connect(
            lambda: self.update_toggle(self.maximized_toggle, self.default_size_toggle)
        )

        screen_size_buttons_layout = QHBoxLayout()
        screen_size_buttons_layout.setSpacing(10)
        screen_size_buttons_layout.addWidget(self.default_size_toggle)
        screen_size_buttons_layout.addWidget(self.maximized_toggle)

        screen_size_layout.addWidget(screen_size_label, 1)
        screen_size_layout.addLayout(screen_size_buttons_layout, 2)

        app_layout.addLayout(screen_size_layout)
        ################################################################################

        ################################################################################
        # 자동 업데이트 설정 섹션
        auto_update_layout = QHBoxLayout()
        auto_update_label = QLabel("자동 업데이트:")
        auto_update_label.setAlignment(Qt.AlignLeft)
        auto_update_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        auto_update_label.setToolTip("MANAGER 부팅 시 자동 업데이트 여부를 설정합니다")

        self.default_update_toggle = QPushButton("끄기")
        self.auto_update_toggle = QPushButton("켜기")

        self.init_toggle_style(self.default_update_toggle, setting['AutoUpdate'] == 'default')
        self.init_toggle_style(self.auto_update_toggle, setting['AutoUpdate'] != 'default')

        self.default_update_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_update_toggle, self.auto_update_toggle)
        )
        self.auto_update_toggle.clicked.connect(
            lambda: self.update_toggle(self.auto_update_toggle, self.default_update_toggle)
        )

        auto_update_buttons_layout = QHBoxLayout()
        auto_update_buttons_layout.setSpacing(10)
        auto_update_buttons_layout.addWidget(self.default_update_toggle)
        auto_update_buttons_layout.addWidget(self.auto_update_toggle)

        auto_update_layout.addWidget(auto_update_label, 1)
        auto_update_layout.addLayout(auto_update_buttons_layout, 2)

        app_layout.addLayout(auto_update_layout)
        ################################################################################

        ################################################################################
        # ChatGPT API Key 입력 섹션
        def open_details_url():
            """자세히 버튼 클릭 시 URL 열기"""
            import webbrowser
            url = "https://hyunicecream.tistory.com/78"  # 원하는 URL 입력
            webbrowser.open(url)

        def disable_api_key_input():
            """API Key 입력창 비활성화"""
            api_key = self.api_key_input.text()
            if api_key:
                self.api_key_input.setDisabled(True)  # 입력창 비활성화
                self.save_api_key_button.setEnabled(False)  # 저장 버튼 비활성화
                self.edit_api_key_button.setEnabled(True)  # 수정 버튼 활성화
                setting['APIKey'] = api_key  # 설정에 저장
                QMessageBox.information(self, "성공", "API Key가 저장되었습니다.")
            else:
                QMessageBox.warning(self, "경고", "API Key를 입력하세요.")

        def enable_api_key_input():
            """API Key 입력창 활성화"""
            self.api_key_input.setDisabled(False)  # 입력창 활성화
            self.save_api_key_button.setEnabled(True)  # 저장 버튼 활성화
            self.edit_api_key_button.setEnabled(False)  # 수정 버튼 비활성화

        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("ChatGPT API:")
        api_key_label.setAlignment(Qt.AlignLeft)
        api_key_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        api_key_label.setToolTip("ChatGPT 기능을 사용하기 위한 API Key를 설정합니다")

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Key")
        self.api_key_input.setStyleSheet("font-size: 14px; padding: 5px;")
        if setting['GPT_Key'] != 'default' and len(setting['GPT_Key']) >= 20:
            self.api_key_input.setText(setting['GPT_Key'])  # 기존 값이 있으면 표시
            self.api_key_input.setDisabled(True)
        else:
            self.api_key_input.setEnabled(True)

        # 저장 버튼
        self.save_api_key_button = QPushButton("저장")
        self.save_api_key_button.clicked.connect(disable_api_key_input)

        # 수정 버튼
        self.edit_api_key_button = QPushButton("수정")
        self.edit_api_key_button.clicked.connect(enable_api_key_input)

        # 자세히 버튼
        self.details_button = QPushButton("자세히")
        self.details_button.clicked.connect(open_details_url)

        # 버튼 레이아웃
        api_key_buttons_layout = QHBoxLayout()
        api_key_buttons_layout.setSpacing(10)
        api_key_buttons_layout.addWidget(self.save_api_key_button, 1)
        api_key_buttons_layout.addWidget(self.edit_api_key_button, 1)
        api_key_buttons_layout.addWidget(self.details_button, 1)

        # 전체 레이아웃
        api_key_input_layout = QHBoxLayout()
        api_key_input_layout.setSpacing(10)
        api_key_input_layout.addWidget(self.api_key_input, 3)
        api_key_input_layout.addLayout(api_key_buttons_layout, 1)

        api_key_layout.addWidget(api_key_label, 1)
        api_key_layout.addLayout(api_key_input_layout, 2)

        app_layout.addLayout(api_key_layout)

        ################################################################################

        # 아래쪽 여유 공간 추가
        app_layout.addStretch()

        app_settings_widget = QWidget()
        app_settings_widget.setLayout(app_layout)
        return app_settings_widget

    def create_db_settings_page(self, setting):

        # DB 설정 페이지 생성
        db_layout = QVBoxLayout()
        db_layout.setSpacing(10)  # 섹션 간 간격 설정
        db_layout.setContentsMargins(10, 10, 10, 10)  # 여백 설정

        ################################################################################
        # 내 DB만 표시 설정 섹션
        db_display_layout = QHBoxLayout()
        mydb_label = QLabel("내 DB만 표시:")
        mydb_label.setAlignment(Qt.AlignLeft)
        mydb_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        mydb_label.setToolTip("DB 목록에서 자신이 크롤링한 DB만 표시할지 여부를 설정합니다")

        self.default_mydb_toggle = QPushButton("끄기")
        self.auto_mydb_toggle = QPushButton("켜기")

        self.init_toggle_style(self.default_mydb_toggle, setting['MyDB'] == 'default')
        self.init_toggle_style(self.auto_mydb_toggle, setting['MyDB'] != 'default')

        self.default_mydb_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_mydb_toggle, self.auto_mydb_toggle)
        )
        self.auto_mydb_toggle.clicked.connect(
            lambda: self.update_toggle(self.auto_mydb_toggle, self.default_mydb_toggle)
        )

        db_display_buttons_layout = QHBoxLayout()
        db_display_buttons_layout.setSpacing(10)  # 버튼 간 간격 설정
        db_display_buttons_layout.addWidget(self.default_mydb_toggle)
        db_display_buttons_layout.addWidget(self.auto_mydb_toggle)

        db_display_layout.addWidget(mydb_label, 1)
        db_display_layout.addLayout(db_display_buttons_layout, 2)

        db_layout.addLayout(db_display_layout)
        ################################################################################

        ################################################################################
        # 내 DB만 표시 설정 섹션
        db_refresh_layout = QHBoxLayout()
        db_refresh_label = QLabel("DB 자동 새로고침:")
        db_refresh_label.setAlignment(Qt.AlignLeft)
        db_refresh_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        db_refresh_label.setToolTip("DATABASE 섹션으로 이동 시 자동으로 DB 목록을 새로고침할지 여부를 설정합니다\n'Ctrl+R'로 수동 새로고침 가능합니다")

        self.default_dbrefresh_toggle = QPushButton("켜기")
        self.off_dbrefresh_toggle = QPushButton("끄기")

        self.init_toggle_style(self.default_dbrefresh_toggle, setting['DB_Refresh'] == 'default')
        self.init_toggle_style(self.off_dbrefresh_toggle, setting['DB_Refresh'] != 'default')

        self.default_dbrefresh_toggle.clicked.connect(
            lambda: self.update_toggle(self.default_dbrefresh_toggle, self.off_dbrefresh_toggle)
        )
        self.off_dbrefresh_toggle.clicked.connect(
            lambda: self.update_toggle(self.off_dbrefresh_toggle, self.default_dbrefresh_toggle)
        )

        db_refresh_buttons_layout = QHBoxLayout()
        db_refresh_buttons_layout.setSpacing(10)  # 버튼 간 간격 설정
        db_refresh_buttons_layout.addWidget(self.default_dbrefresh_toggle)
        db_refresh_buttons_layout.addWidget(self.off_dbrefresh_toggle)

        db_refresh_layout.addWidget(db_refresh_label, 1)
        db_refresh_layout.addLayout(db_refresh_buttons_layout, 2)

        db_layout.addLayout(db_refresh_layout)
        ################################################################################

        # 아래쪽 여유 공간 추가
        db_layout.addStretch()

        db_settings_widget = QWidget()
        db_settings_widget.setLayout(db_layout)
        return db_settings_widget

    def create_info_settings_page(self, setting):
        def wrap_text_by_words(text, max_line_length):
            split = '/'
            if platform.system() == 'Windows':
                split = '\\'
            """
            문자열을 '/' 단위로 나누고 줄바꿈(\n)을 추가하는 함수.
            '/'를 유지합니다.
            """
            words = text.split(split)  # '/'를 기준으로 나누기
            current_line = ""
            lines = []

            for word in words:
                word_with_slash = word + split  # '/'를 다시 추가
                if len(current_line) + len(word_with_slash) <= max_line_length:
                    current_line += word_with_slash
                else:
                    lines.append(current_line.strip())
                    current_line = word_with_slash
            if current_line:
                lines.append(current_line.strip())

            return "\n".join(lines)

        def update_runtime():
            """실시간으로 구동 시간을 정수 형식으로 업데이트하는 메서드"""
            elapsed_time = datetime.now() - self.main.startTime
            total_seconds = int(elapsed_time.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.manager_time_label.setText(f"구동 시간: {hours}시간 {minutes}분 {seconds}초")

        ################################################################################
        # 사용자 정보 페이지 레이아웃 생성
        info_layout = QVBoxLayout()
        info_layout.setSpacing(20)
        info_layout.setContentsMargins(20, 20, 20, 20)

        ################################################################################
        # 사용자 정보 표시 섹션
        user_info_section = QVBoxLayout()
        user_title_label = QLabel("사용자 정보")
        user_title_label.setStyleSheet(
            """
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50; 
            margin-bottom: 10px;
            """
        )
        user_title_label.setAlignment(Qt.AlignLeft)

        # 사용자 정보 추가 (예: 이름, 이메일, 디바이스)
        user_name_label = QLabel(f"이름: {self.main.user}")
        user_name_label.setStyleSheet("font-size: 15px; color: #34495E; padding-bottom: 5px;")

        user_email_label = QLabel(f"이메일: {self.main.usermail}")
        user_email_label.setStyleSheet("font-size: 15px; color: #34495E; padding-bottom: 5px;")

        user_device_label = QLabel(f"디바이스: {self.main.user_device}")
        user_device_label.setStyleSheet("font-size: 15px; color: #34495E; padding-bottom: 5px;")

        if self.main.gpt_api_key == 'default' or len(self.main.gpt_api_key) < 20:
            GPT_key_label = QLabel(f"ChatGPT API Key: 없음")
        else:
            GPT_key_label = QLabel(f"ChatGPT Key: {self.main.gpt_api_key[:40]}...")
        GPT_key_label.setStyleSheet("font-size: 15px; color: #34495E; padding-bottom: 5px;")

        # 사용자 정보 섹션 레이아웃 구성
        user_info_section.addWidget(user_title_label)
        user_info_section.addWidget(user_name_label)
        user_info_section.addWidget(user_email_label)
        user_info_section.addWidget(user_device_label)
        user_info_section.addWidget(GPT_key_label)

        # 사용자 정보 섹션에 구분선 추가
        user_info_separator = QLabel()
        user_info_separator.setStyleSheet("border: 1px solid #E0E0E0; margin: 15px 0;")

        info_layout.addLayout(user_info_section)
        info_layout.addWidget(user_info_separator)
        ################################################################################

        ################################################################################
        # MANAGER 정보 표시 섹션
        manager_info_section = QVBoxLayout()
        manager_title_label = QLabel("MANAGER 정보")
        manager_title_label.setStyleSheet(
            """
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50; 
            margin-bottom: 10px;
            """
        )
        manager_title_label.setAlignment(Qt.AlignLeft)

        # MANAGER 정보 추가
        manager_version_label = QLabel(f"버전: {self.main.versionNum}")
        manager_version_label.setStyleSheet("font-size: 15px; color: #34495E; padding-bottom: 5px;")

        manager_location_label = QLabel(f"앱 경로: {wrap_text_by_words(self.main.program_directory, 40)}")
        manager_location_label.setStyleSheet("font-size: 15px; color: #34495E; padding-bottom: 5px;")

        # 실시간 업데이트를 위한 구동 시간 라벨
        self.manager_time_label = QLabel("구동 시간: 계산 중...")
        self.manager_time_label.setStyleSheet("font-size: 15px; color: #34495E; padding-bottom: 5px;")

        # MANAGER 정보 섹션 레이아웃 구성
        manager_info_section.addWidget(manager_title_label)
        manager_info_section.addWidget(manager_version_label)
        manager_info_section.addWidget(manager_location_label)
        manager_info_section.addWidget(self.manager_time_label)

        info_layout.addLayout(manager_info_section)
        ################################################################################

        # 아래쪽 여유 공간 추가
        info_layout.addStretch()

        # 위젯 설정
        info_settings_widget = QWidget()
        info_settings_widget.setLayout(info_layout)

        # 타이머 설정: 1초마다 구동 시간 업데이트
        self.timer = QTimer()
        self.timer.timeout.connect(update_runtime)
        self.timer.start(1000)

        return info_settings_widget

    def display_category(self, index):
        """
        카테고리에 따라 해당 설정 페이지 표시
        """
        self.stacked_widget.setCurrentIndex(index)

    def init_toggle_style(self, button, is_selected):
        """
        토글 버튼 스타일 초기화
        """
        if is_selected:
            button.setStyleSheet("background-color: #2c3e50; font-weight: bold; color: #eaeaea;")
        else:
            button.setStyleSheet("background-color: lightgray;")

    def update_toggle(self, selected_button, other_button):
        """
        선택된 버튼과 비선택 버튼 스타일 업데이트
        """
        self.init_toggle_style(selected_button, True)
        self.init_toggle_style(other_button, False)

    def save_settings(self):
        # 선택된 설정 가져오기
        theme = 'default' if self.light_mode_toggle.styleSheet().find("#2c3e50") != -1 else 'dark'
        screen_size = 'default' if self.default_size_toggle.styleSheet().find("#2c3e50") != -1 else 'max'
        auto_update = 'default' if self.default_update_toggle.styleSheet().find("#2c3e50") != -1 else 'auto'
        my_db = 'default' if self.default_mydb_toggle.styleSheet().find("#2c3e50") != -1 else 'mydb'
        db_refresh = 'default' if self.default_dbrefresh_toggle.styleSheet().find("#2c3e50") != -1 else 'off'
        api_key = self.api_key_input.text()
        api_key.replace('\n', '').replace(' ', '')

        self.main.SETTING['Theme'] = theme
        self.main.SETTING['ScreenSize'] = screen_size
        self.main.SETTING['AutoUpdate'] = auto_update
        self.main.SETTING['MyDB'] = my_db
        self.main.SETTING['GPT_Key'] = api_key
        self.main.SETTING['DB_Refresh'] = db_refresh
        self.main.gpt_api_key = api_key

        options = {
            "theme": {"key": 1, "value": theme},  # 테마 설정
            "screensize": {"key": 2, "value": screen_size},  # 스크린 사이즈 설정
            "autoupdate": {"key": 4, "value": auto_update},  # 자동 업데이트 설정
            "mydb": {"key": 5, "value": my_db},  # 내 DB만 보기 설정
            "GPT_Key": {"key": 6, "value": api_key},
            "DB_Refresh": {"key": 7, "value": db_refresh}
        }
        for option in options.values():
            self.main.update_settings(option['key'], option['value'])

        self.accept()

if __name__ == '__main__':
    environ["QT_DEVICE_PIXEL_RATIO"] = "0"
    environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    environ["QT_SCREEN_SCALE_FACTORS"] = "1"
    environ["QT_SCALE_FACTOR"] = "1"

    # High DPI 스케일링 활성화 (QApplication 생성 전 설정)
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication([])

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
