import os
import sys
import gc
import copy
import re
import warnings
import traceback
import subprocess
import shutil
import platform
import uuid
from io import BytesIO

import pandas as pd
from tqdm import tqdm
import requests
import zipfile
import bcrypt

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QDialog, QVBoxLayout, QTableWidget,
    QPushButton, QTabWidget,
    QFileDialog, QMessageBox, QSizePolicy, QSpacerItem, QHBoxLayout, QShortcut
)

from urllib.parse import unquote
from libs.console import *
from libs.viewer import *
from libs.path import *
from ui.table import *
from ui.status import *
from ui.finder import *
from ui.dialogs import *
from services.auth import *
from services.crawldb import *
from services.api import *
from services.logging import *
from core.setting import *
from core.shortcut import *
from config import *

warnings.filterwarnings("ignore")


class Manager_Database:
    def __init__(self, main_window):
        self.main = main_window
        self.DB = copy.deepcopy(self.main.DB)

        self.DBTableColumn = ['Type', 'Keyword',
                              'StartDate', 'EndDate', 'Option', 'Status', 'User', 'Size']
        makeTable(self.main, self.main.database_tablewidget,
                  self.DB['DBtable'], self.DBTableColumn, self.viewDBinfo)
        self.matchButton()

    def deleteDB(self):
        try:
            selectedRow = self.main.database_tablewidget.currentRow()
            if selectedRow >= 0:
                DBdata = self.DB['DBdata'][selectedRow]
                DBuid = DBdata['uid']
                DBname = DBdata['name']
                status = DBdata['status']
                owner = DBdata['requester']

                if owner != self.main.user and self.main.user != 'admin':
                    QMessageBox.warning(
                        self.main, "Information", f"DB와 사용자 정보가 일치하지 않습니다")
                    return

                if status == 'Working':
                    confirm_msg = f"현재 크롤링이 진행 중입니다.\n\n'{DBname}' 크롤링을 중단하고 DB를 삭제하시겠습니까?"
                else:
                    confirm_msg = f"'{DBname}'를 삭제하시겠습니까?"

                reply = QMessageBox.question(
                    self.main, 'Confirm Delete', confirm_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    Request('delete', f'crawls/{DBuid}')

                    if status == 'Working':
                        self.main.activeCrawl -= 1
                        QMessageBox.information(
                            self.main, "Information", f"크롤러 서버에 중단 요청을 전송했습니다")
                    else:
                        QMessageBox.information(
                            self.main, "Information", f"'{DBname}'가 삭제되었습니다")
                    userLogging(f'DATABASE -> delete_DB({DBname})')
                    self.refreshDB()

            printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def viewDB(self):

        class TableWindow(QMainWindow):
            def __init__(self, parent=None, DBuid=None, DBname=None):
                super(TableWindow, self).__init__(parent)
                self.setWindowTitle(DBname)
                self.resize(1600, 1200)

                self.main = parent  # 부모 객체를 저장하여 나중에 사용
                self.DBuid = DBuid  # targetDB를 저장하여 나중에 사용
                self.DBname = DBname  # DBname을 저장하여 나중에 사용

                self.centralWidget = QWidget(self)
                self.setCentralWidget(self.centralWidget)

                self.layout = QVBoxLayout(self.centralWidget)

                # 상단 버튼 레이아웃
                self.button_layout = QHBoxLayout()

                # spacer 아이템 추가 (버튼들을 오른쪽 끝에 배치하기 위해 앞에 추가)
                spacer = QSpacerItem(
                    40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
                self.button_layout.addItem(spacer)

                # 새로고침 버튼 추가
                self.refreshButton = QPushButton("새로고침", self)
                self.refreshButton.setFixedWidth(80)  # 가로 길이 조정
                self.refreshButton.clicked.connect(self.refresh_table)
                self.button_layout.addWidget(self.refreshButton)

                # 닫기 버튼 추가
                self.close_button = QPushButton("닫기", self)
                self.close_button.setFixedWidth(80)  # 가로 길이 조정
                self.close_button.clicked.connect(self.closeWindow)
                self.button_layout.addWidget(self.close_button)

                QShortcut(QKeySequence("Ctrl+W"),
                          self).activated.connect(self.closeWindow)
                QShortcut(QKeySequence("Ctrl+ㅈ"),
                          self).activated.connect(self.closeWindow)

                # 버튼 레이아웃을 메인 레이아웃에 추가
                self.layout.addLayout(self.button_layout)

                self.tabWidget_tables = QTabWidget(self)
                self.layout.addWidget(self.tabWidget_tables)

                # targetDB가 주어지면 테이블 뷰를 초기화
                if DBuid is not None:
                    self.init_viewTable(DBuid)

            def closeWindow(self):
                self.tabWidget_tables.clear()  # 탭 위젯 내용 삭제
                self.close()  # 창 닫기
                self.deleteLater()  # 객체 삭제
                gc.collect()

            def closeEvent(self, event):
                # 윈도우 창이 닫힐 때 closeWindow 메서드 호출
                self.closeWindow()
                event.accept()  # 창 닫기 이벤트를 허용

            def init_viewTable(self, DBuid):
                response = Request(
                    'get', f'crawls/{DBuid}/preview', stream=True)

                self.tabWidget_tables.clear()

                with zipfile.ZipFile(BytesIO(response.content)) as zf:
                    file_list = zf.namelist()
                    file_list.sort()

                    for file_name in file_list:
                        table_name = file_name.replace('.parquet', '')

                        with zf.open(file_name) as f:
                            df = pd.read_parquet(f)

                        if 'id' in df.columns:
                            df = df.drop(columns=['id'])

                        self.tuple_list = [
                            tuple(row) for row in df.itertuples(index=False, name=None)
                        ]

                        new_tab = QWidget()
                        new_tab_layout = QVBoxLayout(new_tab)
                        new_table = QTableWidget(new_tab)
                        new_tab_layout.addWidget(new_table)

                        makeTable(
                            self.main, new_table, self.tuple_list, list(
                                df.columns)
                        )

                        self.tabWidget_tables.addTab(
                            new_tab, table_name.split('_')[-1])

                        new_tab = None
                        new_table = None

            def refresh_table(self):
                # 테이블 뷰를 다시 초기화하여 데이터를 새로 로드
                self.init_viewTable(self.DBuid)

        try:
            reply = QMessageBox.question(
                self.main, 'Confirm View', 'DB 조회는 데이터의 처음과 마지막 50개의 행만 불러옵니다\n\n진행하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                printStatus(self.main, "불러오는 중...")

                def destory_table():
                    del self.DBtable_window
                    gc.collect()

                selectedRow = self.main.database_tablewidget.currentRow()
                if selectedRow >= 0:
                    DBdata = self.DB['DBdata'][selectedRow]
                    DBuid = DBdata['uid']
                    DBname = DBdata['name']
                    self.DBtable_window = TableWindow(self.main, DBuid, DBname)
                    self.DBtable_window.destroyed.connect(destory_table)
                    self.DBtable_window.show()

                printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def viewDBinfo(self, row):
        try:
            printStatus(self.main, "불러오는 중...")
            DBdata = self.DB['DBdata'][row]

            userLogging(f'DATABASE -> dbinfo_viewer({DBdata["name"]})')

            from ui.dialogs import DBInfoDialog
            dialog = DBInfoDialog(self.main, DBdata, self.main.style_html)
            printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")
            dialog.show()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def searchDB(self):
        try:
            search_text = self.main.database_searchDB_lineinput.text().lower()
            if not search_text or search_text == "":
                if get_setting('DBKeywordSort') == 'default':
                    set_setting('DBKeywordSort', 'on')
                    QMessageBox.information(
                        self.main, "Information", "DB 정렬 기준이 '키워드순'으로 변경되었습니다")
                    self.refreshDB()
                else:
                    set_setting('DBKeywordSort', 'default')
                    QMessageBox.information(
                        self.main, "Information", "DB 정렬 기준이 '최신순'으로 변경되었습니다")
                    self.refreshDB()
                return

            self.searchAdminMode(search_text)
            # 현재 선택된 행의 다음 행부터 검색 시작
            start_row = self.main.database_tablewidget.currentRow(
            ) + 1 if self.main.database_tablewidget.currentRow() != -1 else 0

            for row in range(start_row, self.main.database_tablewidget.rowCount()):
                match = False
                for col in range(self.main.database_tablewidget.columnCount()):
                    item = self.main.database_tablewidget.item(row, col)
                    if item and search_text in item.text().lower():
                        match = True
                        break

                if match:
                    self.main.database_tablewidget.selectRow(row)
                    return

            # 검색어가 처음부터 검색되도록 반복
            for row in range(0, start_row):
                match = False
                for col in range(self.main.database_tablewidget.columnCount()):
                    item = self.main.database_tablewidget.item(row, col)
                    if item and search_text in item.text().lower():
                        match = True
                        break

                if match:
                    self.main.database_tablewidget.selectRow(row)
                    return
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    
    def searchAdminMode(self, search_text):
        # ADMIN MODE
        try:
            if search_text == '/remove':
                reply = QMessageBox.question(self.main, 'Program Delete',
                                            f"'C:/MANAGER'를 비롯한 모든 구성요소가 제거됩니다\n\nMANAGER를 완전히 삭제하시겠습니까?",
                                            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    # ── 1) QSettings 값 제거 ─────────────────────
                    settings = QSettings("BIGMACLAB", "MANAGER")
                    settings.clear()
                    settings.sync()

                    # ── 2) 로컬 디렉토리 제거 ────────────────────
                    if os.path.exists(self.main.localDirectory):
                        shutil.rmtree(self.main.localDirectory)

                    # ── 3) 언인스톨러 실행 후 종료 ────────────────
                    exe_file_path = os.path.join(
                        os.environ['LOCALAPPDATA'], 'MANAGER', 'unins000.exe')
                    subprocess.Popen([exe_file_path], shell=True)
                    os._exit(0)

            if search_text == '/admin' and self.main.user != 'admin':
                ok, password = checkPassword(self.main, True)
                if not ok or bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')) == False:
                    QMessageBox.warning(
                        self.main, 'Wrong Password', "비밀번호가 올바르지 않습니다")
                    return
                self.main.user = 'admin'
                QMessageBox.information(
                    self.main, "Admin Mode", f"관리자 권한이 부여되었습니다")

            if search_text == '/update':
                self.main.updateProgram(sc=True)
                return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def initLLMChat(self):
        QMessageBox.information(self.main, "Not Supported", f"지원하지 않는 기능입니다")
        return
        try:
            printStatus(self.main, "LLM Chat 실행 중")
            if platform.system() == "Darwin":  # macOS인지 확인
                osascript_cmd = '''
                    tell application "iTerm"
                        activate
                        set newWindow to (create window with default profile)
                        tell current session of newWindow
                            write text "cd /Users/yojunsmacbookprp/Documents/GitHub/BIGMACLAB && source venv/bin/activate && cd .. && cd LLM_API && python3 LLM_Chat.py"
                        end tell
                    end tell
                '''
                subprocess.Popen(["osascript", "-e", osascript_cmd])
            else:
                script_path = os.path.join(os.path.dirname(
                    __file__), 'assets', "LLM_Chat.exe")
                subprocess.Popen([script_path])

            userLogging(f'LLM Chat ON')
            printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def saveDB(self):
        try:

            selectedRow = self.main.database_tablewidget.currentRow()
            if not selectedRow >= 0:
                return
            if self.DB['DBdata'][selectedRow]['status'] == 'Working':
                QMessageBox.warning(self.main, "Information", "현재 크롤링이 진행 중인 DB는 저장할 수 없습니다")
                return

            targetUid = self.DB['DBuids'][selectedRow]
            printStatus(self.main, "DB를 저장할 위치를 선택하여 주십시오")            

            folder_path = QFileDialog.getExistingDirectory(
                self.main, "DB를 저장할 위치를 선택하여 주십시오", self.main.localDirectory)
            if folder_path == '':
                printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")
                return
            printStatus(self.main, "DB 저장 옵션을 설정하여 주십시오")

            dialog = SaveDbDialog()
            option = {}

            if dialog.exec_() == QDialog.Accepted:
                pid = str(uuid.uuid4())
                option['pid'] = pid
                option['dateOption'] = 'all' if dialog.radio_all.isChecked() else 'part'
                option['start_date'] = dialog.start_date if dialog.start_date else ""
                option['end_date'] = dialog.end_date if dialog.end_date else ""
                incl_words = dialog.incl_word_list
                excl_words = dialog.excl_word_list
                option['filterOption'] = bool(incl_words or excl_words)
                option['incl_words'] = dialog.incl_word_list
                option['excl_words'] = dialog.excl_word_list
                option['include_all'] = dialog.include_all_option
                option['filename_edit'] = dialog.radio_name.isChecked()
            else:
                printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")
                return

            register_process(pid, f"Crawl DB Save")
            printStatus(self.main, "서버에서 데이터 처리 중...")
            viewer = open_viewer(pid)

            download_url = MANAGER_SERVER_API + f"/crawls/{targetUid}/save"
            response = requests.post(
                download_url,
                json=option,
                stream=True,
                headers=get_api_headers(),
                timeout=3600
            )
            response.raise_for_status()

            # 1) Content-Disposition 헤더에서 파일명 파싱
            content_disp = response.headers.get("Content-Disposition", "")

            # 2) 우선 filename="…" 시도
            m = re.search(r'filename="(?P<fname>[^"]+)"', content_disp)
            if m:
                zip_name = m.group("fname")
            else:
                # 3) 없으면 filename*=utf-8''… 로 시도
                m2 = re.search(
                    r"filename\*=utf-8''(?P<fname>[^;]+)", content_disp)
                if m2:
                    zip_name = unquote(m2.group("fname"))
                else:
                    zip_name = f"{targetUid}.zip"

            # 4) 이제 다운로드 & 압축 해제
            local_zip = os.path.join(folder_path, zip_name)
            total_size = int(response.headers.get("Content-Length", 0))

            close_viewer(viewer)
            openConsole("CSV로 저장")
            printStatus(self.main, "다운로드 중...")

            with open(safe_path(local_zip), "wb") as f, tqdm(
                total=total_size,
                file=sys.stdout,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="Downloading",
                dynamic_ncols=True,
                bar_format="{desc}: |{bar}| {percentage:3.0f}% • {n_fmt}/{total_fmt} {unit} • {rate_fmt}"
            ) as pbar:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

            printStatus(self.main, "다운로드 완료, 압축 해제 중...")
            print("\n다운로드 완료, 압축 해제 중...\n")

            # 압축 풀 폴더 이름은 zip 파일 이름(확장자 제외)
            base_folder = os.path.splitext(zip_name)[0]
            extract_path = os.path.join(folder_path, base_folder)
            os.makedirs(extract_path, exist_ok=True)

            with zipfile.ZipFile(local_zip, "r") as zf:
                zf.extractall(extract_path)

            os.remove(local_zip)

            closeConsole()
            openFileResult(
                self.main, f"DB 저장이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", extract_path)

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def refreshDB(self):
        try:
            printStatus(self.main, "새로고침 중...")

            self.DB = updateDB(self.main)
            makeTable(self.main, self.main.database_tablewidget,
                      self.DB['DBtable'], self.DBTableColumn)

            printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def matchButton(self):
        self.main.database_searchDB_button.clicked.connect(self.searchDB)
        self.main.database_chatgpt_button.clicked.connect(self.initLLMChat)
        self.main.database_searchDB_lineinput.returnPressed.connect(
            self.searchDB)
        self.main.database_searchDB_lineinput.setPlaceholderText(
            "검색어를 입력하고 Enter키나 검색 버튼을 누르세요...")

        self.main.database_saveDB_button.clicked.connect(self.saveDB)
        self.main.database_deleteDB_button.clicked.connect(self.deleteDB)
        self.main.database_viewDB_button.clicked.connect(self.viewDB)
        # self.main.database_mergeDB_button.clicked.connect(self.mergeDB)

        self.main.database_chatgpt_button.setToolTip("LLM ChatBot")
        self.main.database_saveDB_button.setToolTip("Ctrl+S")
        self.main.database_viewDB_button.setToolTip("Ctrl+V")
        self.main.database_deleteDB_button.setToolTip("Ctrl+D")

        self.main.database_searchDB_button.setText("")  # 텍스트 제거
        self.main.database_searchDB_button.setIcon(QIcon(os.path.join(
            # 아이콘 설정 (이미지 경로 지정)
            os.path.dirname(__file__), '..', 'assets', 'search.png')))
        self.main.database_searchDB_button.setIconSize(
            QSize(18, 18))  # 아이콘 크기 조정 (원하는 크기로 설정)

        self.main.database_chatgpt_button.setText("")  # 텍스트 제거
        self.main.database_chatgpt_button.setIcon(QIcon(os.path.join(os.path.dirname(
            # 아이콘 설정 (이미지 경로 지정)
            __file__), '..', 'assets', 'chatgpt_logo.png')))
        self.main.database_chatgpt_button.setIconSize(
            QSize(19, 19))  # 아이콘 크기 조정 (원하는 크기로 설정)

    def setDatabaseShortcut(self):
        resetShortcuts(self.main)
        self.main.ctrld.activated.connect(self.deleteDB)
        self.main.ctrls.activated.connect(self.saveDB)
        # self.main.ctrlm.activated.connect(self.mergeDB)
        self.main.ctrlv.activated.connect(self.viewDB)
        self.main.ctrlr.activated.connect(self.refreshDB)
        self.main.ctrlc.activated.connect(self.initLLMChat)

        self.main.cmdd.activated.connect(self.deleteDB)
        self.main.cmds.activated.connect(self.saveDB)
        # self.main.cmdm.activated.connect(self.mergeDB)
        self.main.cmdv.activated.connect(self.viewDB)
        self.main.cmdr.activated.connect(self.refreshDB)
        self.main.cmdc.activated.connect(self.initLLMChat)
