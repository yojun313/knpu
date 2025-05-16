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
from datetime import datetime
from pathlib import Path
from io import BytesIO

import pandas as pd
from tqdm import tqdm
import requests
import zipfile
import bcrypt

from PyQt5.QtCore import QDate, QSize
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QDialog, QVBoxLayout, QFormLayout, QTableWidget,
    QButtonGroup, QPushButton, QDialogButtonBox, QRadioButton, QLabel, QTabWidget,
    QLineEdit, QFileDialog, QMessageBox, QSizePolicy, QSpacerItem, QHBoxLayout, QShortcut
)

from urllib.parse import unquote

from libs.console import openConsole, closeConsole
from libs.viewer import open_viewer, close_viewer, register_process
from ui.table import makeTable
from ui.status import printStatus
from ui.finder import openFileExplorer

from services.auth import checkPassword
from services.crawldb import updateDB
from services.api import Request, api_headers
from services.logging import userLogging, programBugLog

from core.setting import get_setting, update_settings, set_setting
from core.shortcut import resetShortcuts

from config import ADMIN_PASSWORD, MANAGER_SERVER_API

warnings.filterwarnings("ignore")

class Manager_Database:
    def __init__(self, main_window):
        self.main = main_window
        self.DB = copy.deepcopy(self.main.DB)

        self.DBTableColumn = ['Database', 'Type', 'Keyword',
                              'StartDate', 'EndDate', 'Option', 'Status', 'User', 'Size']
        makeTable(self.main, self.main.database_tablewidget,
                  self.DB['DBtable'], self.DBTableColumn, self.viewDBinfo)
        self.matchButton()
        self.chatgpt_mode = False
        self.console_open = False

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
                    for file_name in zf.namelist():
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

            userLogging(
                f'DATABASE -> dbinfo_viewer({DBdata['name']})')

            # 다이얼로그 생성
            dialog = QDialog(self.main)
            dialog.setWindowTitle(f'{DBdata['name']}_Info')
            dialog.resize(540, 600)

            layout = QVBoxLayout()

            crawlType = DBdata['crawlType']
            crawlOption_int = int(DBdata['crawlOption'])

            CountText = DBdata['dataInfo']
            if CountText['totalArticleCnt'] == '0' and CountText['totalReplyCnt'] == '0' and CountText['totalRereplyCnt'] == '0':
                CountText = DBdata['status']
            else:
                CountText = f"Aricle: {CountText['totalArticleCnt']}\nReply: {CountText['totalReplyCnt']}\nRereply: {CountText['totalRereplyCnt']}"

            match crawlType:
                case 'Naver News':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '기사 + 댓글'
                        case 2:
                            crawlOption = '기사 + 댓글/대댓글'
                        case 3:
                            crawlOption = '기사'
                        case 4:
                            crawlOption = '기사 + 댓글(추가 정보)'

                case 'Naver Blog':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '블로그 본문'
                        case 2:
                            crawlOption = '블로그 본문 + 댓글/대댓글'

                case 'Naver Cafe':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '카페 본문'
                        case 2:
                            crawlOption = '카페 본문 + 댓글/대댓글'

                case 'YouTube':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '영상 정보 + 댓글/대댓글 (100개 제한)'
                        case 2:
                            crawlOption = '영상 정보 + 댓글/대댓글(무제한)'

                case 'ChinaDaily':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '기사 + 댓글'

                case 'ChinaSina':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '기사'
                        case 2:
                            crawlOption = '기사 + 댓글'

                case 'dcinside':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '게시글'
                        case 2:
                            crawlOption = '게시글 + 댓글'
                case _:
                    crawlOption = crawlOption_int

            starttime = DBdata['startTime']
            endtime = DBdata['endTime']

            try:
                ElapsedTime = datetime.strptime(
                    endtime, "%Y-%m-%d %H:%M") - datetime.strptime(starttime, "%Y-%m-%d %H:%M")
            except:
                ElapsedTime = str(
                    datetime.now() - datetime.strptime(starttime, "%Y-%m-%d %H:%M"))[:-7]
                if endtime == '오류 중단':
                    ElapsedTime = '오류 중단'

            if endtime != '오류 중단':
                endtime = endtime.replace(
                    '/', '-') if endtime != '크롤링 중' else endtime

            details_html = self.main.style_html + f"""
                <div class="version-details">
                    <table>
                        <tr>
                            <th>Item</th>
                            <th>Details</th>
                        </tr>
                        <tr>
                            <td><b>DB Name:</b></td>
                            <td>{DBdata['name']}</td>
                        </tr>
                        <tr>
                            <td><b>DB Size:</b></td>
                            <td>{DBdata['dbSize']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Type:</b></td>
                            <td>{DBdata['crawlType']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Keyword:</b></td>
                            <td>{DBdata['keyword']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Period:</b></td>
                            <td>{DBdata['startDate']} ~ {DBdata['endDate']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Option:</b></td>
                            <td>{crawlOption}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Start:</b></td>
                            <td>{starttime}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl End:</b></td>
                            <td>{endtime}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl ElapsedTime:</b></td>
                            <td>{ElapsedTime}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Requester:</b></td>
                            <td>{DBdata['requester']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Server:</b></td>
                            <td>{DBdata['crawlCom']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Speed:</b></td>
                            <td>{DBdata['crawlSpeed']}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Result:</b></td>
                            <td class="detail-content">{CountText}</td>
                        </tr>
                    </table>
                </div>
            """

            detail_label = QLabel(details_html)
            detail_label.setWordWrap(True)

            layout.addWidget(detail_label)

            # 닫기 버튼 추가
            close_button = QPushButton('Close')
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)

            ctrlw = QShortcut(QKeySequence("Ctrl+W"), dialog)
            ctrlw.activated.connect(dialog.accept)

            cmdw = QShortcut(QKeySequence("Ctrl+ㅈ"), dialog)
            cmdw.activated.connect(dialog.accept)

            dialog.setLayout(layout)
            printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")
            # 다이얼로그 실행
            dialog.show()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def searchDB(self):
        try:
            search_text = self.main.database_searchDB_lineinput.text().lower()
            if not search_text or search_text == "":
                if get_setting['DBKeywordSort'] == 'default':
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
                                             f"'C:/BIGMACLAB_MANAGER'를 비롯한 모든 구성요소가 제거됩니다\n\nMANAGER를 완전히 삭제하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:

                    if os.path.exists(self.main.localDirectory):
                        shutil.rmtree(self.main.localDirectory)
                    exe_file_path = os.path.join(
                        os.environ['LOCALAPPDATA'], 'MANAGER', 'unins000.exe')
                    subprocess.Popen([exe_file_path], shell=True)
                    os._exit(0)

            if search_text == '/admin-mode' and self.main.user != 'admin':
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
            if search_text == '/crawllog':
                self.main.viewTable('crawler_db', 'crawl_log', 'max')
                return
            if search_text == '/dblist':
                self.main.viewTable('crawler_db', 'db_list')
                return
            if search_text == '/config':
                self.main.viewTable('bigmaclab_manager_db', 'configuration')
                return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def initLLMChat(self):
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
            class OptionDialog(QDialog):
                def __init__(self):
                    super().__init__()
                    self.setWindowTitle('Select Options')
                    self.resize(250, 150)  # 초기 크기 설정

                    self.incl_word_list = []
                    self.excl_word_list = []
                    self.include_all_option = False

                    # 다이얼로그 레이아웃
                    self.layout = QVBoxLayout()

                    # 라디오 버튼 그룹 생성
                    self.radio_all = QRadioButton('전체 기간')
                    self.radio_custom = QRadioButton('기간 설정')
                    self.radio_all.setChecked(True)  # 기본으로 "전체 저장" 선택

                    self.layout.addWidget(QLabel('Choose Date Option:'))
                    self.layout.addWidget(self.radio_all)
                    self.layout.addWidget(self.radio_custom)

                    # 기간 입력 폼 (처음엔 숨김)
                    self.date_input_form = QWidget()
                    self.date_input_form_layout = QFormLayout()

                    self.start_date_input = QLineEdit()
                    self.start_date_input.setPlaceholderText('YYYYMMDD')
                    self.end_date_input = QLineEdit()
                    self.end_date_input.setPlaceholderText('YYYYMMDD')

                    self.date_input_form_layout.addRow(
                        '시작 날짜:', self.start_date_input)
                    self.date_input_form_layout.addRow(
                        '종료 날짜:', self.end_date_input)
                    self.date_input_form.setLayout(self.date_input_form_layout)
                    self.date_input_form.setVisible(False)

                    self.layout.addWidget(self.date_input_form)

                    # 라디오 버튼 그룹 생성
                    self.radio_nofliter = QRadioButton('필터링 안함')
                    self.radio_filter = QRadioButton('필터링 설정')
                    self.radio_nofliter.setChecked(True)  # 기본으로 "전체 저장" 선택

                    self.layout.addWidget(QLabel('Choose Filter Option:'))
                    self.layout.addWidget(self.radio_nofliter)
                    self.layout.addWidget(self.radio_filter)

                    # QButtonGroup 생성하여 라디오 버튼 그룹화
                    self.filter_group = QButtonGroup()
                    self.filter_group.addButton(self.radio_nofliter)
                    self.filter_group.addButton(self.radio_filter)

                    # 단어 입력 폼 (처음엔 숨김)
                    self.word_input_form = QWidget()
                    self.word_input_form_layout = QFormLayout()

                    self.incl_word_input = QLineEdit()
                    self.incl_word_input.setPlaceholderText('ex) 사과, 바나나')
                    self.excl_word_input = QLineEdit()
                    self.excl_word_input.setPlaceholderText('ex) 당근, 오이')

                    self.word_input_form_layout.addRow(
                        '포함 문자:', self.incl_word_input)
                    self.word_input_form_layout.addRow(
                        '제외 문자:', self.excl_word_input)
                    self.word_input_form.setLayout(self.word_input_form_layout)
                    self.word_input_form.setVisible(False)

                    # 포함 옵션 선택 (All 포함 vs Any 포함)
                    self.include_option_group = QButtonGroup()
                    self.include_all = QRadioButton('모두 포함/제외 (All)')
                    self.include_any = QRadioButton('개별 포함/제외 (Any)')
                    self.include_all.setToolTip("입력한 단어를 모두 포함/제외한 행을 선택")
                    self.include_any.setToolTip("입력한 단어를 개별 포함/제외한 행을 선택")
                    self.include_all.setChecked(True)  # 기본 선택: Any 포함

                    self.word_input_form_layout.addRow(QLabel('포함 옵션:'))
                    self.word_input_form_layout.addWidget(self.include_all)
                    self.word_input_form_layout.addWidget(self.include_any)

                    # 이름에 필터링 설정 포함할지
                    self.radio_name = QRadioButton('포함 설정')
                    self.radio_name.setToolTip("예) (+사과,바나나 _ -당근,오이 _all)")
                    self.radio_noname = QRadioButton('포함 안함')
                    self.radio_name.setChecked(True)  # 기본으로 "전체 저장" 선택

                    self.word_input_form_layout.addRow(QLabel('폴더명에 필터링 항목:'))
                    self.word_input_form_layout.addWidget(self.radio_name)
                    self.word_input_form_layout.addWidget(self.radio_noname)

                    # QButtonGroup 생성하여 라디오 버튼 그룹화
                    self.filter_name_group = QButtonGroup()
                    self.filter_name_group.addButton(self.radio_name)
                    self.filter_name_group.addButton(self.radio_noname)
                    self.word_input_form_layout.addWidget(self.radio_name)
                    self.word_input_form_layout.addWidget(self.radio_noname)

                    self.word_input_form.setLayout(self.word_input_form_layout)
                    self.word_input_form.setVisible(False)

                    self.layout.addWidget(self.word_input_form)

                    # 다이얼로그의 OK/Cancel 버튼
                    self.button_box = QDialogButtonBox(
                        QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    self.button_box.accepted.connect(self.accept)
                    self.button_box.rejected.connect(self.reject)

                    self.layout.addWidget(self.button_box)

                    self.setLayout(self.layout)

                    # 신호 연결
                    self.radio_custom.toggled.connect(self.toggle_date_input)
                    self.radio_filter.toggled.connect(self.toggle_word_input)

                def toggle_date_input(self, checked):
                    # "기간 설정" 라디오 버튼이 선택되면 날짜 입력 필드 표시
                    self.date_input_form.setVisible(checked)
                    self.adjust_dialog_size()

                def toggle_word_input(self, checked):
                    # "필터링 설정" 라디오 버튼이 선택되면 단어 입력 필드 표시
                    self.word_input_form.setVisible(checked)
                    self.adjust_dialog_size()

                def adjust_dialog_size(self):
                    """다이얼로그 크기를 현재 내용에 맞게 조정"""
                    self.adjustSize()  # 다이얼로그 크기를 내용에 맞게 자동 조정

                def accept(self):
                    # 확인 버튼을 눌렀을 때 데이터 유효성 검사
                    self.start_date = None
                    self.end_date = None

                    if self.radio_custom.isChecked():
                        date_format = "yyyyMMdd"
                        self.start_date = QDate.fromString(
                            self.start_date_input.text(), date_format)
                        self.end_date = QDate.fromString(
                            self.end_date_input.text(), date_format)

                        if not (self.start_date.isValid() and self.end_date.isValid()):
                            QMessageBox.warning(
                                self, 'Wrong Form', '잘못된 날짜 형식입니다.')
                            return  # 확인 동작을 취소함

                        self.start_date = self.start_date.toString(date_format)
                        self.end_date = self.end_date.toString(date_format)

                    if self.radio_filter.isChecked():
                        try:
                            incl_word_str = self.incl_word_input.text()
                            excl_word_str = self.excl_word_input.text()

                            if incl_word_str == '':
                                self.incl_word_list = []
                            else:
                                self.incl_word_list = incl_word_str.split(', ')

                            if excl_word_str == '':
                                self.excl_word_list = []
                            else:
                                self.excl_word_list = excl_word_str.split(', ')

                            if self.include_all.isChecked():
                                self.include_all_option = True
                            else:
                                self.include_all_option = False

                            if self.radio_name.isChecked():
                                self.include = True

                        except:
                            QMessageBox.warning(
                                self, 'Wrong Input', '잘못된 필터링 입력입니다')
                            return  # 확인 동작을 취소함

                    super().accept()  # 정상적인 경우에만 다이얼로그를 종료함

            selectedRow = self.main.database_tablewidget.currentRow()
            if not selectedRow >= 0:
                return
            printStatus(self.main, "DB를 저장할 위치를 선택하여 주십시오")

            targetUid = self.DB['DBuids'][selectedRow]

            folder_path = QFileDialog.getExistingDirectory(
                self.main, "DB를 저장할 위치를 선택하여 주십시오", self.main.localDirectory)
            if folder_path == '':
                printStatus(self.main, f"{self.main.fullStorage} GB / 2 TB")
                return
            printStatus(self.main, "DB 저장 옵션을 설정하여 주십시오")
            dialog = OptionDialog()
            option = {}

            if dialog.exec_() == QDialog.Accepted:

                openConsole("DB 저장")

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

            register_process(pid, f"Crawl DB Save")
            viewer = open_viewer(pid)

            download_url = MANAGER_SERVER_API + f"/crawls/{targetUid}/save"
            response = requests.post(
                download_url,
                json=option,
                stream=True,
                headers=api_headers,
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

            with open(local_zip, "wb") as f, tqdm(
                total=total_size,
                file=sys.stdout,
                unit="B", unit_scale=True, unit_divisor=1024,
                desc="Downloading DB",
                ascii=True, ncols=80,
                bar_format="{desc}: |{bar}| {percentage:3.0f}% [{n_fmt}/{total_fmt} {unit}] @ {rate_fmt}",
                dynamic_ncols=True
            ) as pbar:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

            printStatus(self.main, "다운로드 완료, 압축 해제 중…")
            print("\n다운로드 완료, 압축 해제 중...\n")

            # 압축 풀 폴더 이름은 zip 파일 이름(확장자 제외)
            base_folder = os.path.splitext(zip_name)[0]
            extract_path = os.path.join(folder_path, base_folder)
            os.makedirs(extract_path, exist_ok=True)

            with zipfile.ZipFile(local_zip, "r") as zf:
                zf.extractall(extract_path)

            os.remove(local_zip)

            printStatus(self.main)
            closeConsole()

            reply = QMessageBox.question(self.main, 'Notification', f"DB 저장이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                openFileExplorer(extract_path)

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
