import os
import re
import gc
import shutil
import socket
import traceback
import platform
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
from packaging import version
from openai import OpenAI

from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QDialog, QInputDialog,
    QMessageBox, QPushButton, QMainWindow
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

from config import MANAGER_SERVER_API, VERSION, ASSETS_PATH
from libs.console import openConsole, closeConsole
from pages.page_analysis import Manager_Analysis
from pages.page_user import Manager_User
from pages.page_board import Manager_Board
from pages.page_web import Manager_Web
from pages.page_database import Manager_Database
from pages.page_settings import Manager_Setting
from core.boot import (
    initListWidget, initStatusbar, initShortcut,
    checkNetwork, checkNewPost, checkNewVersion
)
from services.auth import checkPassword
from services.crawldb import updateDB
from services.pushover import sendPushOver
from services.api import Request
from ui.style import theme_option
from ui.status import printStatus
from core.setting import get_setting, set_setting

class MainWindow(QMainWindow):

    def __init__(self, splashDialog):
        try:
            self.server_api = MANAGER_SERVER_API
            self.versionNum = VERSION
            self.version = f'Version {self.versionNum}'
            self.splashDialog = splashDialog

            super(MainWindow, self).__init__()
            uiPath = os.path.join(ASSETS_PATH,  'gui.ui')
            iconPath = os.path.join(ASSETS_PATH, 'exe_icon.png')

            uic.loadUi(uiPath, self)
            initListWidget(self)
            initStatusbar(self)
            
            self.updateStyleHtml()
            self.setWindowTitle("MANAGER")  # 창의 제목 설정
            self.setWindowIcon(QIcon(iconPath))
            self.resize(1400, 1000)
            self.installEventFilter(self)

            def loadProgram():
                try:
                    self.listWidget.setCurrentRow(0)
                    if get_setting('BootTerminal') == 'on':
                        openConsole("Boot Process")
                    self.startTime = datetime.now()
                    self.gpt_api_key = get_setting('GPT_Key')
                    checkNetwork(self)
                    self.listWidget.currentRowChanged.connect(self.display)

                    if platform.system() == "Windows":
                        localAppdataPath = os.getenv("LOCALAPPDATA")
                        self.programDirectory = os.path.join(
                            localAppdataPath, "MANAGER")
                        self.localDirectory = "C:/BIGMACLAB_MANAGER"
                        if not os.path.exists(self.localDirectory):
                            os.makedirs(self.localDirectory)
                    else:
                        self.programDirectory = os.path.dirname(__file__)
                        self.localDirectory = '/Users/yojunsmacbookprp/Documents/BIGMACLAB_MANAGER'
                        if not os.path.exists(self.localDirectory):
                            os.makedirs(self.localDirectory)

                    self.readmePath = os.path.join(
                        self.localDirectory, 'README.txt')
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
                    print("Done")

                    self.splashDialog.updateStatus("Checking New Version")
                    print("\nII. Checking New Version... ", end='')
                    if checkNewVersion(self) == True:
                        self.closeBootscreen()
                        self.updateProgram()
                    print("Done")

                    # Loading Data from DB & Making object
                    while True:
                        try:
                            print("\nIII. Loading Data... ", end='')
                            self.splashDialog.updateStatus("Loading Data")

                            self.DB = updateDB(self)
                            self.managerBoardObj = Manager_Board(self)
                            self.managerUserObj = Manager_User(self)
                            self.managerDatabaseObj = Manager_Database(self)
                            self.managerWebObj = Manager_Web(self)
                            self.managerAnalysisObj = Manager_Analysis(self)

                            print("Done")
                            break
                        except Exception as e:
                            print("Failed")
                            print(traceback.format_exc())
                            self.closeBootscreen()
                            printStatus(self)
                            reply = QMessageBox.warning(self, 'Connection Failed',
                                                        f"DB 서버 접속에 실패했습니다\n네트워크 점검이 필요합니다{self.networkText}\n\n다시 시도하시겠습니까?",
                                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                            if reply == QMessageBox.Yes:
                                printStatus(self, "접속 재시도 중...")
                                continue
                            else:
                                os._exit(0)

                    self.splashDialog.updateStatus(f"안녕하세요, {self.user}님!")
                    newpost = checkNewPost(self)
                    print(f"\n{self.user}님 환영합니다!")

                    initShortcut(self)
                    self.managerDatabaseObj.setDatabaseShortcut()
                    self.userLogging(f'Booting ({self.getUserLocation()})')

                    closeConsole()
                    self.closeBootscreen()

                    if get_setting('ScreenSize') == 'max':
                        self.showMaximized()
                    printStatus(self, f"{self.fullStorage} GB / 2 TB")

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
                    printStatus(self)
                    msg = f'[ Admin CRITICAL Notification ]\n\nThere is Error in MANAGER Booting\n\nError Log: {traceback.format_exc()}'
                    sendPushOver(msg)
                    QMessageBox.critical(
                        self, "Error", f"부팅 과정에서 오류가 발생했습니다\n\nError Log: {traceback.format_exc()}")
                    QMessageBox.information(
                        self, "Information", f"관리자에게 에러 상황과 로그가 전달되었습니다\n\n프로그램을 종료합니다")
                    os._exit(0)

            loadProgram()

        except Exception as e:
            self.closeBootscreen()
            openConsole()
            print(traceback.format_exc())

    ################################## Booting ##################################

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
            saved_token = get_setting('auth_token')
            
            if saved_token:
                headers = {"Authorization": f"Bearer {saved_token}"}
                res = requests.get(
                    f"{self.server_api}/auth/login", headers=headers)
                if res.status_code == 200:
                    userData = res.json()['user']
                    self.user = userData['name']
                    self.userUid = userData['uid']
                    self.usermail = userData['email']
                    return True

            # 사용자 이름 입력 대화
            self.closeBootscreen()
            printStatus(self, "로그인 중...")

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

            res = requests.get(f"{self.server_api}/auth/request",
                               params={"name": self.user}).json()
            printStatus(self)
            QMessageBox.information(self, "Information",
                                    f"{self.user}님의 메일로 인증번호가 전송되었습니다\n\n"
                                    "인증번호를 확인 후 입력하십시오")

            ok, password = checkPassword(self.main, string="메일 인증번호")
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
            set_setting('auth_token', access_token)

        except Exception:
            self.closeBootscreen()
            QMessageBox.critical(self, "Error",
                                 f"오류가 발생했습니다.\n\nError Log: {traceback.format_exc()}")
            return False

    def updateProgram(self, sc=False):
        try:
            def downloadFile(download_url, local_filename):
                response = requests.get(download_url, stream=True)
                totalSize = int(response.headers.get(
                    'content-length', 0))  # 파일의 총 크기 가져오기
                chunkSize = 8192  # 8KB씩 다운로드
                downloadSize = 0  # 다운로드된 크기 초기화

                with open(local_filename, 'wb') as f:
                    for chunk in response.iter_content(chunkSize=chunkSize):
                        if chunk:  # 빈 데이터 확인
                            f.write(chunk)
                            downloadSize += len(chunk)
                            percent_complete = (downloadSize / totalSize) * 100
                            # 퍼센트 출력
                            print(
                                f"\r{self.newVersion} Download: {percent_complete:.0f}%", end='')

                print("\nDownload Complete")
                closeConsole()

            def update_process():
                openConsole("Version Update Process")
                msg = (
                    "[ Admin Notification ]\n\n"
                    f"{self.user} updated {self.versionNum} -> {self.newVersion}\n\n{self.getUserLocation()}"
                )
                sendPushOver(msg)
                self.userLogging(
                    f'Program Update ({self.versionNum} -> {self.newVersion})')

                printStatus(self, "버전 업데이트 중...")
                import subprocess
                downloadFile_path = os.path.join(
                    'C:/Temp', f"BIGMACLAB_MANAGER_{self.newVersion}.exe")
                downloadFile(f"https://knpu.re.kr/download/BIGMACLAB_MANAGER_{self.newVersion}.exe",
                             downloadFile_path)
                subprocess.Popen([downloadFile_path], shell=True)
                closeConsole()
                os._exit(0)

            if checkNewVersion(self):
                if get_setting('AutoUpdate') == 'auto':
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
                    QMessageBox.information(
                        self, "Information", 'Ctrl+U 단축어로 프로그램 실행 중 업데이트 가능합니다')
                    return
            else:
                if sc == True:
                    reply = QMessageBox.question(self, "Reinstall", "현재 버전이 최신 버전입니다\n\n현재 버전을 재설치하시겠습니까?",
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        printStatus(self, "버전 재설치 중...")
                        openConsole("Version Reinstall Process")
                        import subprocess
                        downloadFile_path = os.path.join(
                            'C:/Temp', f"BIGMACLAB_MANAGER_{self.newVersion}.exe")
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

    def display(self, index):
        if index != 6:
            self.stackedWidget.setCurrentIndex(index)

        # DATABASE
        if index == 0:
            self.managerDatabaseObj.setDatabaseShortcut()
            if get_setting('DB_Refresh') == 'default':
                self.managerDatabaseObj.refreshDB()
            printStatus(self, f"{self.fullStorage} GB / 2 TB")
        # CRAWLER
        elif index == 1:
            printStatus(self, f"활성 크롤러 수: {self.activeCrawl}")
            self.resetShortcuts()
        # ANALYSIS
        elif index == 2:
            printStatus(self)
            self.managerAnalysisObj.analysis_shortcut_setting()
        # BOARD
        elif index == 3:
            printStatus(self)
            self.managerBoardObj.setBoardShortcut()
        # WEB
        elif index == 4:
            printStatus(self)
        # USER
        elif index == 5:
            printStatus(self)
            self.managerUserObj.user_shortcut_setting()

        elif index == 6:
            self.userSettings()
            previous_index = self.stackedWidget.currentIndex()  # 현재 활성 화면의 인덱스
            self.listWidget.setCurrentRow(previous_index)  # 선택 상태를 이전 인덱스로 변경

        gc.collect()

    #############################################################################

    def updateSettings(self, option_key, new_value):
        try:
            self.settings.setValue(option_key, new_value)  # 설정값 업데이트
            return True
        except Exception as e:
            print(traceback.format_exc())
            return False

    def userLogging(self, text=''):
        try:
            jsondata = {
                "message": text
            }
            Request('post', '/users/log', json=jsondata)
        except Exception as e:
            print(traceback.format_exc())

    def userBugging(self, text=''):
        try:
            jsondata = {
                "message": text
            }
            Request('post', '/users/bug', json=jsondata)
        except Exception as e:
            print(traceback.format_exc())

    def userSettings(self):
        try:
            self.userLogging(f'User Setting')
            dialog = Manager_Setting(self)
            if dialog.exec_() == QDialog.Accepted:
                QMessageBox.information(self, "Information", f"설정이 완료되었습니다")
                printStatus(self, "설정 반영 중...")
                QApplication.instance().setStyleSheet(theme_option[get_setting('Theme')])
                self.updateStyleHtml()

                self.managerDatabaseObj.refreshDB()
                printStatus(self)

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

    def resetShortcuts(self):
        shortcuts = [self.ctrld, self.ctrls, self.ctrlv, self.ctrla, self.ctrll, self.ctrle, self.ctrlr, self.ctrlk, self.ctrlm, self.ctrlc,
                     self.cmdd, self.cmds, self.cmdv, self.cmda, self.cmdl, self.cmde, self.cmdr, self.cmdk, self.cmdm, self.cmdc]
        for shortcut in shortcuts:
            try:
                shortcut.activated.disconnect()
            except TypeError:
                # 연결된 슬롯이 없는 경우 발생하는 에러를 무시
                pass

    def updateStyleHtml(self):
        if get_setting('Theme') != 'default':
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

    def programBugLog(self, text):
        print(text)
        printStatus(self, "오류 발생")
        QMessageBox.critical(self, "Error", f"오류가 발생했습니다\n\nError Log: {text}")

        self.userBugging(text)

        reply = QMessageBox.question(self, 'Bug Report', "버그 리포트를 전송하시겠습니까?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            self.managerBoardObj.addBug()

        printStatus(self)

    def closeEvent(self, event):
        # 프로그램 종료 시 실행할 코드
        reply = QMessageBox.question(self, 'Shutdown', "프로그램을 종료하시겠습니까?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            try:
                self.userLogging('Shutdown')
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
                    # 버전 추출 및 비교를 위해 Version 객체로 변환
                    file_version = version.Version(match.group(1))
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
                    result = result.replace(
                        '<think>', '').replace('</think>', '')
                    return result
                else:
                    return f"Failed to get a valid response: {response.status_code} {response.text}"

            except requests.exceptions.RequestException as e:
                return f"Error communicating with the server: {e}"

    def readCSV(self, csvPath):
        csv_data = pd.read_csv(csvPath, low_memory=False, index_col=0)
        csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
        return csv_data
