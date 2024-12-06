import os
import sys
import gc
import copy
import re
import warnings
import traceback
import pandas as pd
from tqdm import tqdm
from datetime import datetime
import platform
from PyQt5.QtCore import QTimer, QDate, QSize
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5.QtWidgets import (
    QWidget, QMainWindow, QDialog, QVBoxLayout, QFormLayout, QTableWidget,
    QButtonGroup, QPushButton, QDialogButtonBox, QRadioButton, QLabel, QTabWidget,
    QLineEdit, QFileDialog, QMessageBox, QSizePolicy, QSpacerItem, QHBoxLayout, QShortcut
)
from Manager_Console import open_console, close_console

warnings.filterwarnings("ignore")
class Manager_Database:
    
    def __init__(self, main_window):
        self.main = main_window
        self.DB = copy.deepcopy(self.main.DB)
        self.DB_table_column = ['Name', 'Type', 'Keyword', 'Period', 'Option', 'Crawl Start', 'Crawl End', 'Requester', 'Size']
        self.main.table_maker(self.main.database_tablewidget, self.DB['DBdata'], self.DB_table_column, self.database_dbinfo_viewer)
        self.database_buttonMatch()
        self.chatgpt_mode = False
        self.console_open = False

    def database_delete_DB(self):
        try:
            self.main.printStatus("삭제 중...")
            def delete_database():
                selected_row = self.main.database_tablewidget.currentRow()
                if selected_row >= 0:
                    target_db = self.DB['DBlist'][selected_row]
                    self.main.mySQL_obj.connectDB(target_db)
                    endtime = self.DB['DBdata'][selected_row][6]
                    owner = self.DB['DBdata'][selected_row][7]

                    if owner != self.main.user and self.main.user != 'admin':
                        QMessageBox.warning(self.main, "Information", f"DB와 사용자 정보가 일치하지 않습니다")
                        return

                    if endtime == '크롤링 중':
                        confirm_msg = f"현재 크롤링이 진행 중입니다.\n\n'{target_db}' 크롤링을 중단하고 DB를 삭제하시겠습니까?"
                    else:
                        confirm_msg = f"'{target_db}'를 삭제하시겠습니까?"

                    reply = QMessageBox.question(self.main, 'Confirm Delete', confirm_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        self.main.mySQL_obj.dropDB(target_db)
                        self.database_refresh_DB()
                        self.main.mySQL_obj.connectDB('crawler_db')
                        self.main.mySQL_obj.deleteTableRowByColumn('db_list', target_db, 'DBname')
                        if endtime == '-':
                            self.main.activate_crawl -= 1
                            QMessageBox.information(self.main, "Information", f"크롤러 서버에 중단 요청을 전송했습니다")
                        else:
                            QMessageBox.information(self.main, "Information", f"'{target_db}'가 삭제되었습니다")
                        self.main.user_logging(f'DATABASE -> delete_DB({target_db})')

            QTimer.singleShot(1, delete_database)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def database_view_DB(self):

        class TableWindow(QMainWindow):
            def __init__(self, parent=None, target_db=None):
                super(TableWindow, self).__init__(parent)
                self.setWindowTitle(target_db)
                self.resize(1600, 1200)

                self.parent = parent  # 부모 객체를 저장하여 나중에 사용
                self.target_db = target_db  # target_db를 저장하여 나중에 사용

                self.central_widget = QWidget(self)
                self.setCentralWidget(self.central_widget)

                self.layout = QVBoxLayout(self.central_widget)

                # 상단 버튼 레이아웃
                self.button_layout = QHBoxLayout()

                # spacer 아이템 추가 (버튼들을 오른쪽 끝에 배치하기 위해 앞에 추가)
                spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
                self.button_layout.addItem(spacer)

                # 새로고침 버튼 추가
                self.refresh_button = QPushButton("새로고침", self)
                self.refresh_button.setFixedWidth(80)  # 가로 길이 조정
                self.refresh_button.clicked.connect(self.refresh_table)
                self.button_layout.addWidget(self.refresh_button)

                # 닫기 버튼 추가
                self.close_button = QPushButton("닫기", self)
                self.close_button.setFixedWidth(80)  # 가로 길이 조정
                self.close_button.clicked.connect(self.closeWindow)
                self.button_layout.addWidget(self.close_button)

                # 버튼 레이아웃을 메인 레이아웃에 추가
                self.layout.addLayout(self.button_layout)

                self.tabWidget_tables = QTabWidget(self)
                self.layout.addWidget(self.tabWidget_tables)

                # target_db가 주어지면 테이블 뷰를 초기화
                if target_db is not None:
                    self.init_table_view(parent.mySQL_obj, target_db)

            def closeWindow(self):
                self.tabWidget_tables.clear()  # 탭 위젯 내용 삭제
                self.close()  # 창 닫기
                self.deleteLater()  # 객체 삭제
                gc.collect()

            def closeEvent(self, event):
                # 윈도우 창이 닫힐 때 closeWindow 메서드 호출
                self.closeWindow()
                event.accept()  # 창 닫기 이벤트를 허용

            def init_table_view(self, mySQL_obj, target_db):
                # target_db에 연결
                mySQL_obj.connectDB(target_db)

                tableNameList = mySQL_obj.showAllTable(target_db)
                self.tabWidget_tables.clear()  # 기존 탭 내용 초기화

                for tableName in tableNameList:
                    if 'info' in tableName or 'token' in tableName:
                        continue
                    tableDF_begin = mySQL_obj.TableToDataframe(tableName, ':50')
                    tableDF_end = mySQL_obj.TableToDataframe(tableName, ':-50')
                    tableDF = pd.concat([tableDF_begin, tableDF_end], axis=0)
                    tableDF = tableDF.drop(columns=['id'])

                    # 데이터프레임 값을 튜플 형태의 리스트로 변환
                    self.tuple_list = [tuple(row) for row in tableDF.itertuples(index=False, name=None)]

                    # 새로운 탭 생성
                    new_tab = QWidget()
                    new_tab_layout = QVBoxLayout(new_tab)
                    new_table = QTableWidget(new_tab)
                    new_tab_layout.addWidget(new_table)

                    # table_maker 함수를 호출하여 테이블 설정
                    self.parent.table_maker(new_table, self.tuple_list, list(tableDF.columns))

                    # 탭 위젯에 추가
                    self.tabWidget_tables.addTab(new_tab, tableName.split('_')[-1])

                    # 메모리 해제
                    new_tab = None
                    new_table = None

            def refresh_table(self):
                # 테이블 뷰를 다시 초기화하여 데이터를 새로 로드
                self.init_table_view(self.parent.mySQL_obj, self.target_db)

        try:
            reply = QMessageBox.question(self.main, 'Confirm View', 'DB 조회는 데이터의 처음과 마지막 50개의 행만 불러옵니다\n\n진행하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.printStatus("불러오는 중...")

                def destory_table():
                    del self.DBtable_window
                    gc.collect()

                def load_database():
                    selected_row = self.main.database_tablewidget.currentRow()
                    if selected_row >= 0:
                        target_DB = self.DB['DBlist'][selected_row]
                        self.main.user_logging(f'DATABASE -> view_DB({target_DB})')
                        self.DBtable_window = TableWindow(self.main, target_DB)
                        self.DBtable_window.destroyed.connect(destory_table)
                        self.DBtable_window.show()

                QTimer.singleShot(1, load_database)
                QTimer.singleShot(1, self.main.printStatus)

        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def database_dbinfo_viewer(self, row):
        try:
            DBdata = self.DB['DBdata'][row]
            DBname = self.DB['DBlist'][row]
            DBinfo = self.DB['DBinfo'][row]

            self.main.user_logging(f'DATABASE -> dbinfo_viewer({DBname})')

            # 다이얼로그 생성
            dialog = QDialog(self.main)
            dialog.setWindowTitle(f'{DBname}_Info')
            dialog.resize(540, 600)

            layout = QVBoxLayout()

            crawlType = DBdata[1]
            crawlOption_int = int(DBdata[4])

            json_str = DBinfo[2]
            numbers = re.findall(r'\d+', json_str)
            try:
                CountText = (
                    f"Article Count: {numbers[1]}\n"
                    f"Reply Count: {numbers[2]}\n"
                    f"Rereply Count: {numbers[3]}\n"
                )
                if numbers[1] == '0' and numbers[2] == '0' and numbers[3] == '0':
                    CountText = "크롤링 중..."
            except:
                CountText = "크롤링 중..."
                if DBdata[6] == '오류 중단':
                    CountText = '오류 중단'


            match crawlType:
                case 'navernews':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '기사 + 댓글'
                        case 2:
                            crawlOption = '기사 + 댓글/대댓글'
                        case 3:
                            crawlOption = '기사'

                case 'naverblog':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '블로그 본문'
                        case 2:
                            crawlOption = '블로그 본문 + 댓글/대댓글'

                case 'navercafe':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '카페 본문'
                        case 2:
                            crawlOption = '카페 본문 + 댓글/대댓글'

                case 'youtube':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '영상 정보 + 댓글/대댓글 (100개 제한)'
                        case 2:
                            crawlOption = '영상 정보 + 댓글/대댓글(무제한)'

                case 'chinadaily':
                    match crawlOption_int:
                        case 1:
                            crawlOption = '기사 + 댓글'

                case 'chinasina':
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

            starttime = DBdata[5]
            endtime = DBdata[6]

            try:
                ElapsedTime = datetime.strptime(endtime, "%Y-%m-%d %H:%M") - datetime.strptime(starttime,"%Y-%m-%d %H:%M")
            except:
                ElapsedTime = str(datetime.now() - datetime.strptime(starttime, "%Y-%m-%d %H:%M"))[:-7]
                if endtime == '오류 중단':
                    ElapsedTime = '오류 중단'

            if endtime != '오류 중단':
                endtime = endtime.replace('/', '-') if endtime != '크롤링 중' else endtime

            # HTML을 사용하여 디테일 표시
            details_html = f"""
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
                        color: #34495e;
                    }}
                    .detail-content {{
                        white-space: pre-wrap;
                        margin-top: 5px;
                        font-family: Arial, sans-serif;
                        font-size: 14px;
                        color: #34495e;
                    }}
                </style>
                <div class="version-details">
                    <table>
                        <tr>
                            <th>Item</th>
                            <th>Details</th>
                        </tr>
                        <tr>
                            <td><b>DB Name:</b></td>
                            <td>{DBdata[0]}</td>
                        </tr>
                        <tr>
                            <td><b>DB Size:</b></td>
                            <td>{DBdata[8]}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Type:</b></td>
                            <td>{DBdata[1]}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Keyword:</b></td>
                            <td>{DBdata[2]}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Period:</b></td>
                            <td>{DBdata[3]}</td>
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
                            <td>{DBdata[7]}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Server:</b></td>
                            <td>{DBinfo[0]}</td>
                        </tr>
                        <tr>
                            <td><b>Crawl Speed:</b></td>
                            <td>{DBinfo[1]}</td>
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

            # 다이얼로그 실행
            dialog.show()

        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def database_search_DB(self):
        try:
            search_text = self.main.database_searchDB_lineinput.text().lower()
            if not search_text or search_text == "":
                return

            self.database_search_admin_mode(search_text)
            # 현재 선택된 행의 다음 행부터 검색 시작
            start_row = self.main.database_tablewidget.currentRow() + 1 if self.main.database_tablewidget.currentRow() != -1 else 0

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
            self.main.program_bug_log(traceback.format_exc())

    def database_search_admin_mode(self, search_text):
        # ADMIN MODE
        try:
            if search_text == './remove_all' and platform.system() == 'Windows':
                reply = QMessageBox.question(self.main, 'Program Delete',
                                             f"'C:/BIGMACLAB_MANAGER'를 비롯한 모든 구성요소가 제거됩니다\n\nMANAGER를 완전히 삭제하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    import subprocess
                    import shutil
                    if os.path.exists(self.main.default_directory):
                        # 폴더 삭제
                        shutil.rmtree(self.main.default_directory)
                    if os.path.exists(self.main.SETTING['path']):
                        os.remove(self.main.SETTING['path'])
                    exe_file_path = os.path.join(os.environ['LOCALAPPDATA'], 'MANAGER', 'unins000.exe')
                    subprocess.Popen([exe_file_path], shell=True)
                    os._exit(0)

            if search_text == './admin-mode' and self.main.user != 'admin':
                ok, password = self.main.pw_check(True)
                if ok or password == self.main.admin_password:
                    self.main.user = 'admin'
                    QMessageBox.information(self.main, "Admin Mode", f"관리자 권한이 부여되었습니다")
                else:
                    QMessageBox.warning(self.main, 'Wrong Password', "비밀번호가 올바르지 않습니다")

            if search_text == './toggle-logging':
                mode_changed = 'On' if self.main.CONFIG['Logging'] == 'Off' else 'Off'
                self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                self.main.mySQL_obj.updateTableCellByCondition('configuration', 'Setting', 'Logging', 'Config', mode_changed)
                self.main.mySQL_obj.commit()
                self.main.CONFIG['Logging'] = 'On' if self.main.CONFIG['Logging'] == 'Off' else 'Off'
                QMessageBox.information(self.main, "Information", f"Logging 설정을 '{mode_changed}'으로 변경했습니다")
                return
            if search_text == './update':
                self.main.update_program(sc=True)
                return
            if search_text == './crawllog':
                self.main.table_view('crawler_db', 'crawl_log', 'max')
                return
            if search_text == './dblist':
                self.main.table_view('crawler_db', 'db_list')
                return
            if search_text == './configure':
                self.main.table_view('bigmaclab_manager_db', 'configuration')
                return
            if 'log' in search_text:
                match = re.match(r'\./(.+)_log', search_text)
                name = match.group(1)
                self.main.table_view(f'{name}_db', 'manager_record', 'max')
                return
            if 'error' in search_text:  # ./error_db 이름
                # 패턴 매칭
                match = re.search(r"(?<=./error_)(.*)", search_text)
                dbname = match.group(1)
                self.main.mySQL_obj.connectDB('crawler_db')
                self.main.mySQL_obj.updateTableCellByCondition('db_list', 'DBname', dbname, 'Endtime', '오류 중단')
                self.main.mySQL_obj.updateTableCellByCondition('db_list', 'DBname', dbname, 'Datainfo', '오류 중단')
                self.main.mySQL_obj.commit()
                QMessageBox.information(self.main, "Information", f"{dbname} 상태를 변경했습니다")
                self.database_refresh_DB()
        except:
            pass

    def database_search_chatgpt_toggle(self):
        if self.chatgpt_mode == False:
            if self.main.gpt_api_key == 'default' or len(self.main.gpt_api_key) < 20:
                QMessageBox.information(self.main, 'Notification', f'API Key가 설정되지 않았습니다\n\n환경설정에서 ChatGPT API Key를 입력해주십시오')
                return
            self.main.user_logging(f'User --> ChatGPT Mode ON')
            self.chatgpt_mode = True
            self.main.database_searchDB_button.clicked.disconnect()
            self.main.database_searchDB_lineinput.returnPressed.disconnect()
            self.main.database_searchDB_button.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'source', 'microphone.png')))  # 아이콘 설정 (이미지 경로 지정)
            self.main.database_searchDB_button.setIconSize(QSize(18, 18))  # 아이콘 크기 조정 (원하는 크기로 설정)
            self.main.database_searchDB_button.clicked.connect(lambda: self.database_search_chatgpt(True))
            self.main.database_searchDB_lineinput.returnPressed.connect(self.database_search_chatgpt)
            self.main.database_searchDB_lineinput.setPlaceholderText("ChatGPT 에게 질문을 입력하고 Enter키를 누르세요 / 음성인식 버튼을 클릭하고 음성으로 질문하세요...")
            QMessageBox.information(self.main, "ChatGPT Mode", f"입력란이 ChatGPT 프롬프트로 설정되었습니다\n\n다시 클릭하시면 DB 검색으로 설정됩니다")
            return
        if self.chatgpt_mode == True:
            if self.console_open == True:
                close_console()
            self.chatgpt_mode = False
            self.main.user_logging(f'User --> ChatGPT Mode OFF')
            self.main.database_searchDB_button.clicked.disconnect()
            self.main.database_searchDB_lineinput.returnPressed.disconnect()
            self.main.database_searchDB_button.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'source', 'search.png')))  # 아이콘 설정 (이미지 경로 지정)
            self.main.database_searchDB_button.setIconSize(QSize(18, 18))  # 아이콘 크기 조정 (원하는 크기로 설정)
            self.main.database_searchDB_button.clicked.connect(self.database_search_DB)
            self.main.database_searchDB_lineinput.returnPressed.connect(self.database_search_DB)
            self.main.database_searchDB_lineinput.setPlaceholderText("검색어를 입력하고 Enter키나 검색 버튼을 누르세요...")
            QMessageBox.information(self.main, "Search Mode", f"입력란이 DB 검색으로 설정되었습니다\n\n다시 클릭하시면 DB 검색으로 설정됩니다")
            return

    def database_search_chatgpt(self, speech=False):
        def add_to_log(message):
            """출력 메시지를 로그에 추가"""
            self.log += message + "\n"

        if speech == True:
            if self.console_open == False:
                open_console("MANAGER ChatGPT")
                print("System > 콘솔창을 닫으면 프로그램 전체가 종료되므로 콘솔 창을 닫기 위해서는 ChatGPT 버튼을 클릭하거나 입력란에 '닫기' 또는 'quit'을 입력하여 주십시오. '저장' 또는 'save'를 입력하면 프롬프트 기록을 저장할 수 있습니다\n")
                self.console_open = True
                self.log = ''
            print("System > 음성 인식 중...\n")
            search_text = self.main.microphone()
        else:
            search_text = self.main.database_searchDB_lineinput.text()
        self.main.database_searchDB_lineinput.clear()
        if self.console_open == False:
            open_console("MANAGER ChatGPT")
            print("System > 콘솔창을 닫으면 프로그램 전체가 종료되므로 콘솔 창을 닫기 위해서는 ChatGPT 버튼을 클릭하거나 입력란에 '닫기' 또는 'quit'을 입력하여 주십시오. '저장' 또는 'save'를 입력하면 프롬프트 기록을 저장할 수 있습니다\n")
            self.console_open = True
            self.log = ''
        if search_text == '닫기' or search_text.lower() == 'quit':
            close_console()
            self.console_open = False
            return
        if search_text == "저장" or search_text.lower() == 'save':
            reply = QMessageBox.question(self.main, 'Notification', f"ChatGPT 프롬프트를 저장하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                folder_path = QFileDialog.getExistingDirectory(self.main, "Select Directory", self.main.default_directory)
                if folder_path == '':
                    return
                if folder_path:
                    file_path = os.path.join(folder_path, f"{datetime.now().strftime("%Y%m%d_%H%M")}_GPT_log.txt")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(self.log)
                    reply = QMessageBox.question(self.main, 'Notification', f"프롬프트 저장이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        self.main.openFileExplorer(os.path.dirname(file_path))
            else:
                return
            return
        if search_text == "음성 인식 실패":
            return

        print(f"User > {search_text}\n")
        add_to_log(f"User > {search_text}\n")
        # "ChatGPT > 답변 생성 중..." 출력
        print("ChatGPT > 답변 생성 중...", end='\r')
        answer = self.main.chatgpt_generate(search_text)
        if type(answer) != str:
            print(f"ChatGPT > 답변 생성 중 오류 발생\n")
            print(f"System > {answer[1]}\n")
            add_to_log(f"System > {answer[1]}\n")
        else:
            print(f"ChatGPT > {answer}\n")
            add_to_log(f"ChatGPT > {answer}\n")
        if speech == True and self.main.SETTING['GPT_TTS'] == 'default':
            self.main.speecher(answer)

        print("User > ", end='\r')

    def database_save_DB(self):
        try:
            class OptionDialog(QDialog):
                def __init__(self):
                    super().__init__()
                    self.setWindowTitle('Select Options')
                    self.resize(250, 150)  # 너비 400, 높이 300

                    self.incl_word_list = []
                    self.excl_word_list = []

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

                    self.date_input_form_layout.addRow('시작 날짜:', self.start_date_input)
                    self.date_input_form_layout.addRow('종료 날짜:', self.end_date_input)
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

                    self.word_input_form_layout.addRow('포함 문자:', self.incl_word_input)
                    self.word_input_form_layout.addRow('제외 문자:', self.excl_word_input)
                    self.word_input_form.setLayout(self.word_input_form_layout)
                    self.word_input_form.setVisible(False)

                    self.layout.addWidget(self.word_input_form)

                    # 다이얼로그의 OK/Cancel 버튼
                    self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
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

                def toggle_word_input(self, checked):
                    # "기간 설정" 라디오 버튼이 선택되면 날짜 입력 필드 표시
                    self.word_input_form.setVisible(checked)

                def accept(self):
                    # 확인 버튼을 눌렀을 때 데이터 유효성 검사
                    if self.radio_custom.isChecked():
                        date_format = "yyyyMMdd"
                        start_date = QDate.fromString(self.start_date_input.text(), date_format)
                        end_date = QDate.fromString(self.end_date_input.text(), date_format)

                        if not (start_date.isValid() and end_date.isValid()):
                            QMessageBox.warning(self, 'Wrong Form', '잘못된 날짜 형식입니다.')
                            return  # 확인 동작을 취소함

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
                        except:
                            QMessageBox.warning(self, 'Wrong Input', '잘못된 필터링 입력입니다')
                            return  # 확인 동작을 취소함

                    super().accept()  # 정상적인 경우에만 다이얼로그를 종료함

            def replace_dates_in_filename(filename, new_start_date, new_end_date):
                pattern = r"_(\d{8})_(\d{8})_"
                new_filename = re.sub(pattern, f"_{new_start_date}_{new_end_date}_", filename)
                return new_filename

            def select_database():
                selected_row = self.main.database_tablewidget.currentRow()
                if not selected_row >= 0:
                    return
                self.main.printStatus("DB를 저장할 위치를 선택하여 주십시오")

                target_db = self.DB['DBlist'][selected_row]

                QMessageBox.information(self.main, "Directory Setting", f"DB를 저장할 위치를 선택하여 주십시오")
                folder_path = QFileDialog.getExistingDirectory(self.main, "Select Directory", self.main.default_directory)
                if folder_path == '':
                    self.main.printStatus()
                    return
                if folder_path:
                    self.main.printStatus("DB 저장 옵션을 설정하여 주십시오")
                    dialog = OptionDialog()
                    date_options = {}

                    if dialog.exec_() == QDialog.Accepted:

                        filter_options = {
                            'incl_words': dialog.incl_word_list,
                            'excl_words': dialog.excl_word_list,
                        }

                        # 선택된 라디오 버튼 확인 날짜 범위 부분
                        if dialog.radio_all.isChecked():
                            date_options['option'] = 'all'
                        elif dialog.radio_custom.isChecked():
                            date_options['option'] = 'part'

                        # 기간 설정이 선택된 경우, 입력된 날짜 가져오기
                        if date_options['option'] == 'part':
                            date_format = "yyyyMMdd"
                            start_date = QDate.fromString(dialog.start_date_input.text(), date_format)
                            end_date = QDate.fromString(dialog.end_date_input.text(), date_format)

                            if start_date.isValid() and end_date.isValid():
                                date_options['start_date'] = start_date.toString(date_format)
                                date_options['end_date'] = end_date.toString(date_format)
                            else:
                                QMessageBox.warning(dialog, 'Wrong Form', '잘못된 날짜 형식입니다.')
                                date_options['option'] = None  # 잘못된 날짜가 입력된 경우 선택 옵션을 None으로 설정

                    if date_options == {}:
                        self.main.printStatus()
                        return

                    if date_options['option'] == 'part':
                        self.main.printStatus(f"{replace_dates_in_filename(target_db, date_options['start_date'], date_options['end_date'])} 저장 중...")
                    else:
                        self.main.printStatus(f"{target_db} 저장 중...")
                    QTimer.singleShot(1000, lambda: save_database(target_db, folder_path, date_options, filter_options))

            def save_database(target_db, folder_path, date_options, filter_options):
                open_console('CSV로 저장')
                dbname = target_db
                dbpath = os.path.join(folder_path, dbname)

                # 선택된 옵션에 따라 날짜를 형식화하고 DB 이름과 경로 수정
                if date_options.get('option') == 'part':
                    start_date = date_options['start_date']
                    end_date = date_options['end_date']
                    start_date_formed = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
                    end_date_formed = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
                    dbname = replace_dates_in_filename(target_db, start_date, end_date)
                    dbpath = os.path.join(folder_path, dbname)

                # 필터 옵션 설정 확인
                filterOption = bool(filter_options['incl_words'] != [] or filter_options['excl_words'] != [])
                incl_words = filter_options.get('incl_words', [])
                excl_words = filter_options.get('excl_words', [])

                # 폴더 생성 로직 최적화
                while True:
                    try:
                        os.makedirs(os.path.join(dbpath, 'token_data'), exist_ok=False)
                        break
                    except FileExistsError:
                        dbpath += "_copy"

                statisticsURL = []
                self.main.user_logging(f'DATABASE -> save_DB({target_db})')
                self.main.mySQL_obj.connectDB(target_db)

                # 불필요한 정렬 조건 제거
                tableList = [table for table in sorted(self.main.mySQL_obj.showAllTable(target_db)) if 'info' not in table]
                tableList = sorted(tableList, key=lambda x: ('article' not in x, 'statistics' not in x, x))

                # 필터 옵션이 있는 경우 DB_info.txt 작성
                if filterOption:
                    with open(os.path.join(dbpath, 'DB_info.txt'), 'w+') as info:
                        info.write(
                            f"Filter Option: {filterOption}\n"
                            f"Include Words: {', '.join(incl_words)}\n"
                            f"Exclude Words: {', '.join(excl_words)}"
                        )

                print(f"DB: {target_db}\n")

                # 옵션 출력
                if date_options.get('option') == 'part' or filterOption:
                    print('< Option >\n')
                    if date_options.get('option') == 'part':
                        print(f'Period: {start_date_formed} ~ {end_date_formed}')
                    if filterOption:
                        print(f'Include Words: {", ".join(incl_words)}')
                        print(f'Exclude Words: {", ".join(excl_words)}')
                    print('')
                for tableName in tqdm(tableList, desc="Download", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' ='):
                    edited_tableName = replace_dates_in_filename(tableName, start_date, end_date) if date_options['option'] == 'part' else tableName
                    # 테이블 데이터를 DataFrame으로 변환
                    if date_options['option'] == 'part':
                        tableDF = self.main.mySQL_obj.TableToDataframeByDate(tableName, start_date_formed, end_date_formed)
                    else:
                        tableDF = self.main.mySQL_obj.TableToDataframe(tableName)

                    if filterOption == True and 'article' in tableName:
                        tableDF = tableDF[tableDF['Article Text'].apply(lambda cell: any(word in str(cell) for word in incl_words))]
                        tableDF = tableDF[tableDF['Article Text'].apply(lambda cell: all(word not in str(cell) for word in excl_words))]
                        articleURL = tableDF['Article URL'].tolist()

                    # statistics 테이블 처리
                    if 'statistics' in tableName:
                        if filterOption == True:
                            tableDF = tableDF[tableDF['Article URL'].isin(articleURL)]
                        statisticsURL = tableDF['Article URL'].tolist()
                        save_path = os.path.join(dbpath, 'token_data' if 'token' in tableName else '', f"{edited_tableName}.csv")
                        tableDF.to_csv(save_path, index=False, encoding='utf-8-sig', header=True)
                        continue

                    if 'reply' in tableName:
                        if filterOption == True:
                            tableDF = tableDF[tableDF['Article URL'].isin(articleURL)]

                    # reply 테이블 처리
                    if 'reply' in tableName and 'statisticsURL' in locals() and 'navernews' in target_db:
                        if filterOption == True:
                            filteredDF = tableDF[tableDF['Article URL'].isin(articleURL)]
                        filteredDF = tableDF[tableDF['Article URL'].isin(statisticsURL)]
                        save_path = os.path.join(dbpath, 'token_data' if 'token' in tableName else '', f"{edited_tableName + '_statistics'}.csv")
                        filteredDF.to_csv(save_path, index=False, encoding='utf-8-sig', header=True)

                    # 기타 테이블 처리
                    save_dir = os.path.join(dbpath, 'token_data' if 'token' in tableName else '')
                    tableDF.to_csv(os.path.join(save_dir, f"{edited_tableName}.csv"), index=False, encoding='utf-8-sig', header=True)
                    tableDF = None
                    gc.collect()

                close_console()
                reply = QMessageBox.question(self.main, 'Notification', f"{dbname} 저장이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.main.openFileExplorer(dbpath)
                self.main.printStatus()

            select_database()

        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def database_refresh_DB(self):
        try:
            self.main.printStatus("새로고침 중")
            def refresh_database():
                self.DB = self.main.update_DB()
                self.main.table_maker(self.main.database_tablewidget, self.DB['DBdata'], self.DB_table_column)

            QTimer.singleShot(1, refresh_database)
            QTimer.singleShot(1, self.main.printStatus)
            QTimer.singleShot(1000, lambda: self.main.printStatus(f"{self.main.fullstorage} GB / 2 TB"))
        except Exception as e:
            self.main.program_bug_log(traceback.format_exc())

    def database_buttonMatch(self):
        self.main.database_searchDB_button.clicked.connect(self.database_search_DB)
        self.main.database_chatgpt_button.clicked.connect(self.database_search_chatgpt_toggle)
        self.main.database_searchDB_lineinput.returnPressed.connect(self.database_search_DB)
        self.main.database_searchDB_lineinput.setPlaceholderText("검색어를 입력하고 Enter키나 검색 버튼을 누르세요...")

        self.main.database_saveDB_button.clicked.connect(self.database_save_DB)
        self.main.database_deleteDB_button.clicked.connect(self.database_delete_DB)
        self.main.database_viewDB_button.clicked.connect(self.database_view_DB)

        self.main.database_chatgpt_button.setToolTip("ChatGPT Mode")
        self.main.database_saveDB_button.setToolTip("Ctrl+S")
        self.main.database_viewDB_button.setToolTip("Ctrl+V")
        self.main.database_deleteDB_button.setToolTip("Ctrl+D")

        self.main.database_searchDB_button.setText("")  # 텍스트 제거
        self.main.database_searchDB_button.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'source', 'search.png')))  # 아이콘 설정 (이미지 경로 지정)
        self.main.database_searchDB_button.setIconSize(QSize(18, 18))  # 아이콘 크기 조정 (원하는 크기로 설정)

    def database_shortcut_setting(self):
        self.main.shortcut_initialize()
        self.main.ctrld.activated.connect(self.database_delete_DB)
        self.main.ctrls.activated.connect(self.database_save_DB)
        self.main.ctrlv.activated.connect(self.database_view_DB)
        self.main.ctrlr.activated.connect(self.database_refresh_DB)
        self.main.ctrlc.activated.connect(self.database_search_chatgpt_toggle)

        self.main.cmdd.activated.connect(self.database_delete_DB)
        self.main.cmds.activated.connect(self.database_save_DB)
        self.main.cmdv.activated.connect(self.database_view_DB)
        self.main.cmdr.activated.connect(self.database_refresh_DB)
        self.main.cmdc.activated.connect(self.database_search_chatgpt_toggle)

