import os
import sys
from PyQt5 import QtWidgets, uic, QtGui, QtCore
from PyQt5.QtWidgets import QTableWidget, QScrollArea, QTableWidgetItem, QVBoxLayout, QHeaderView, QHBoxLayout, QAction, QLabel, QStatusBar, QDialog, QInputDialog, QLineEdit, QMessageBox, QFileDialog, QSizePolicy, QPushButton
from PyQt5.QtCore import Qt, QTimer, QCoreApplication
from openai import OpenAI
import shutil
import tempfile
from mySQL import mySQL
from Manager_Database import Manager_Database
from Manager_Web import Manager_Web
from Manager_Board import Manager_Board
from Manager_User import Manager_User
from Manager_Analysis import Manager_Analysis
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
import atexit
import ctypes
warnings.filterwarnings("ignore")

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        self.versionNum = '1.11.1'
        self.version = 'Version ' + self.versionNum
         
        super(MainWindow, self).__init__()
        ui_path = os.path.join(os.path.dirname(__file__), 'BIGMACLAB_MANAGER_GUI.ui')
        uic.loadUi(ui_path, self)

        self.setWindowTitle("BIGMACLAB MANAGER")  # 창의 제목 설정
        if platform.system() == "Windows":
            self.resize(1400, 1000)
            #self.showMaximized()  # 전체 화면으로 창 열기
        else:
            self.resize(1400, 1000)

        self.statusBar_init()
        self.fullstorage = 0
        self.admin_password = 'kingsman'
        self.admin_pushoverkey = 'uvz7oczixno7daxvgxmq65g2gbnsd5'
        self.gpt_api_key = "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"

        # 스타일시트 적용
        self.setStyle()

        # 사이드바 연결
        def load_program():
            #self.menubar_init()
            self.listWidget.currentRowChanged.connect(self.display)

            if platform.system() == "Windows":
                self.default_directory = 'C:/BIGMACLAB_MANAGER'
                if not os.path.exists(self.default_directory):
                    os.makedirs(self.default_directory)

                self.program_log_path = os.path.join(self.default_directory, 'manager_log.txt')

                if not Path(self.program_log_path).exists():
                    with open(self.program_log_path, "w") as log:
                        log.write(f"[ BIGMACLAB MANAGER LOG ]\n")
            else:
                self.default_directory = '/Users/yojunsmacbookprp/Desktop/BIGMACLAB_MANAGER'
                self.program_log_path = os.path.join(self.default_directory, '.manager_log.txt')

                if not Path(self.program_log_path).exists():
                    with open(self.program_log_path, "w") as log:
                        log.write(f"[ BIGMACLAB MANAGER LOG ]\n")

            self.readme_path = os.path.join(self.default_directory, 'README.txt')
            if not Path(self.readme_path).exists():
                with open(self.readme_path, "w") as txt:
                    text = (
                        "[ BIGMACLAB MANAGER README ]\n\n\n"
                        "C:/BIGMACLAB_MANAGER is default directory folder of this program. This folder is automatically built by program.\n\n"
                        "All files made in this program will be saved in this folder without any change.\n\n"
                        "manager_log.txt is VERY IMPORTANT FILE for bug tracking and logging, so I strongly recommend you to keep this file.\n\n\n\n"
                        "< Instructions >\n\n"
                        "- MANAGER: https://knpu.re.kr/tool\n"
                        "- KEMKIM: https://knpu.re.kr/kemkim"
                    )
                    txt.write(text)

            if os.path.isdir(self.default_directory) == False:
                os.mkdir(self.default_directory)

            DB_ip = '121.152.225.232'
            if socket.gethostname() in ['DESKTOP-502IMU5', 'DESKTOP-0I9OM9K', 'BigMacServer']:
                DB_ip = '192.168.0.3'

            self.network_text = (
                "\n\n[ DB 접속 반복 실패 시... ]\n"
                "\n1. Wi-Fi 또는 유선 네트워크가 정상적으로 작동하는지 확인하십시오"
                "\n2. 네트워크 호환성에 따라 DB 접속이 불가능한 경우가 있습니다. 다른 네트워크 연결을 시도해보십시오\n"
            )

            while True:
                try:
                    self.mySQL_obj = mySQL(host=DB_ip, user='admin', password='bigmaclab2022!', port=3306)
                    if self.mySQL_obj.showAllDB() == []:
                        raise
                    # DB 불러오기
                    self.Manager_User_obj = Manager_User(self)
                    self.userNameList = self.Manager_User_obj.userNameList
                    self.userPushOverKeyList = self.Manager_User_obj.userKeyList


                    break
                except:
                    reply = QMessageBox.question(self, 'Confirm Delete', f"DB 서버 접속에 실패했습니다\n네트워크 점검이 필요합니다{self.network_text}\n다시 시도하시겠습니까?",QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continue
                    else:
                        sys.exit()

            if self.login_program() == False:
                sys.exit()

            while True:
                try:
                    self.DB = self.update_DB({'DBlist':[], 'DBdata': [], 'DBinfo': []})
                    self.Manager_Database_obj = Manager_Database(self)
                    self.Manager_Web_obj = Manager_Web(self)
                    self.Manager_Board_obj = Manager_Board(self)
                    self.Manager_Analysis_generate = False
                    break
                except:
                    reply = QMessageBox.question(self, 'Confirm Delete', f"DB 서버 접속에 실패했습니다\n네트워크 점검이 필요합니다{self.network_text}\n\n다시 시도하시겠습니까?",QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continue
                    else:
                        sys.exit()

            def download_file(download_url, local_filename):
                response = requests.get(download_url, stream=True)
                with open(local_filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            # New version check
            current_version = version.parse(self.versionNum)
            new_version = version.parse(self.Manager_Board_obj.version_name_list[0])
            if current_version < new_version:
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
                dialog.setWindowTitle(f"New Version Update")
                dialog.resize(350, 250)

                layout = QVBoxLayout()

                label = QLabel()
                label.setText(version_info_html)
                label.setWordWrap(True)
                label.setTextFormat(QtCore.Qt.RichText)  # HTML 렌더링

                # QScrollArea를 사용하여 스크롤 가능하게 설정
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setWidget(label)

                layout.addWidget(scroll_area, alignment=QtCore.Qt.AlignHCenter)

                button_layout = QHBoxLayout()  # 수평 레이아웃

                # confirm_button과 cancel_button의 크기가 창의 너비에 맞게 비례하도록 설정
                confirm_button = QPushButton("Update")
                cancel_button = QPushButton("Cancel")

                # 두 버튼이 창의 가로 너비를 가득 채우도록 크기 정책 설정
                confirm_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                cancel_button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

                confirm_button.setFixedHeight(40)  # 버튼 높이 조정
                cancel_button.setFixedHeight(40)  # 버튼 높이 조정

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
                    if platform.system() == "Windows":
                        QMessageBox.information(self, "Information", "새로운 설치 프로그램은 C:/Temp 설치되며, 업데이트 후 자동 실행됩니다\n\n프로그램 재실행까지 잠시만 기다려주십시오")
                        msg = (
                            "[ Admin Notification ]\n\n"
                            f"{self.user} updated to {new_version} from {current_version}"
                        )
                        self.send_pushOver(msg, self.admin_pushoverkey)

                        self.printStatus("프로그램 업데이트 중...")
                        import subprocess
                        download_file_path = os.path.join('C:/Temp',
                                                          f"BIGMACLAB_MANAGER_{new_version}.exe")
                        download_file(f"https://knpu.re.kr:90/download/BIGMACLAB_MANAGER_{new_version}.exe",
                                      download_file_path)
                        subprocess.Popen([download_file_path], shell=True)
                        sys.exit()
                else:
                    pass

        self.listWidget.setCurrentRow(0)
        self.printStatus("프로그램 시작 중...")
        QTimer.singleShot(1, load_program)
        QTimer.singleShot(1000, lambda: self.printStatus(f"{self.fullstorage} GB / 8 TB"))
   
    def login_program(self):
        try:
            while True:
                try:
                    self.mySQL_obj.connectDB('bigmaclab_manager_db')
                    self.device_list = [item[0] for item in self.mySQL_obj.TableToList('device_list')]
                    self.name_list = [item[1] for item in self.mySQL_obj.TableToList('device_list')]
                    if len(self.device_list) > 5:
                        break
                except:
                    reply = QMessageBox.question(self, 'Confirm Delete',
                                                 f"DB 서버 접속에 실패했습니다\n네트워크 점검이 필요합니다{self.network_text}\n\n다시 시도하시겠습니까?",
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        continue
                    else:
                        return False

            current_device = socket.gethostname()
            if current_device in self.device_list:
                self.user = self.name_list[self.device_list.index(current_device)]
                return True
            else:
                input_dialog_id = QInputDialog(self)
                input_dialog_id.setWindowTitle('Login')
                input_dialog_id.setLabelText('User Name:')
                input_dialog_id.resize(300, 200)  # 원하는 크기로 설정
                ok_id = input_dialog_id.exec_()
                user_name = input_dialog_id.textValue()
                if not ok_id:
                    QMessageBox.warning(self, 'Error', '프로그램을 종료합니다')
                    return False
                elif  user_name not in self.userNameList:
                    QMessageBox.warning(self, 'Error', '등록되지 않은 사용자입니다\n\n프로그램을 종료합니다')
                    return False

                ok, password = self.pw_check()
                if ok and password == 'bigmaclab2022!':
                    reply = QMessageBox.question(self, 'Confirm Delete', f"BIGMACLAB MANAGER 서버에\n현재 디바이스({current_device})를 등록하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        self.mySQL_obj.insertToTable('device_list', [[current_device, user_name]])
                        self.mySQL_obj.commit()
                        QMessageBox.information(self, "Information", "디바이스가 등록되었습니다\n\n다음 실행 시 추가적인 로그인이 필요하지 않습니다")
                        msg = (
                            "[ New Device Added! ]\n\n"
                            f"User: {user_name}\n"
                            f"Device: {current_device}\n"
                        )
                        self.send_pushOver(msg, self.admin_pushoverkey)
                        return True
                    else:
                        QMessageBox.information(self, "Information", "디바이스가 등록되지 않았습니다\n\n다음 실행 시 추가적인 로그인이 필요합니다")
                        return True
                elif ok:
                    QMessageBox.warning(self, 'Error', '비밀번호가 올바르지 않습니다\n\n프로그램을 종료합니다')
                    return False
                else:
                    QMessageBox.warning(self, 'Error', '프로그램을 종료합니다')
                    return False
        except Exception as e:
            QMessageBox.information(self, "Information", f"오류가 발생했습니다. 프로그램을 종료합니다\nError Log: {traceback.format_exc()}")
            return False

    def statusBar_init(self):
        # 상태 표시줄 생성
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.left_label = QLabel('  ' + self.version)
        self.right_label = QLabel('')
        self.left_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.right_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusbar.addPermanentWidget(self.left_label, 1)
        self.statusbar.addPermanentWidget(self.right_label, 1)

    def menubar_init(self):
        import webbrowser
        def showInfoDialog():
            dialog = InfoDialog(self.version)
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
        #editMenu.addAction(copyAct)
        #editMenu.addAction(pasteAct)

    def update_DB(self, currentDB):

        def parse_date(date_str):
            if len(date_str) < 14:
                date_str = '2024/'+date_str
            for fmt in ('%m-%d %H:%M',  '%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M'):
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    pass
            raise ValueError(f"time data '{date_str}' does not match any known format")

        mySQL_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306)
        currentDB_list = currentDB['DBlist']
        newDB_list = mySQL_obj.showAllDB()
        newDB_list = [DB for DB in newDB_list if DB.count('_') == 5]

        delete_target_list = list(set(currentDB_list)-set(newDB_list))
        add_target_list    = list(set(newDB_list)-set(currentDB_list))

        # Delete
        currentDB_list_copy = currentDB_list.copy()
        for i in range(len(currentDB_list_copy)):
            DB_name = currentDB_list_copy[i]
            if DB_name in delete_target_list:
                index_to_remove = currentDB_list.index(DB_name)
                currentDB['DBlist'].pop(index_to_remove)
                currentDB['DBdata'].pop(index_to_remove)

        for i, DB_name in enumerate(add_target_list):
            currentDB['DBlist'].append(DB_name)

            db_split = DB_name.split('_')
            crawltype = db_split[0]
            date = f"{db_split[2]}~{db_split[3]}"

            self.mySQL_obj.connectDB(DB_name)
            db_info_df = self.mySQL_obj.TableToDataframe(DB_name + '_info')
            db_info = db_info_df.iloc[-1].tolist()
            option = db_info[1]
            starttime = db_info[2]
            starttime = parse_date(starttime).strftime('%Y-%m-%d %H:%M')
            endtime = db_info[3]

            if endtime == '-':
                endtime = '크롤링 중'
            else:
                endtime = parse_date(endtime).strftime('%Y-%m-%d %H:%M')
            requester = db_info[4]
            size = self.mySQL_obj.showDBSize(DB_name)
            self.fullstorage += float(size[0])
            size = f"{size[1]} MB" if size[0] < 1 else f"{size[0]} GB"

            try:
                keyword = db_info[5]
                crawlcom = db_info[6]
                crawlspeed = db_info[7]
                IntegratedDB = db_info[8]
                currentDB['DBinfo'].append((crawlcom, crawlspeed, IntegratedDB))
            except:
                keyword = db_split[1]
                currentDB['DBinfo'].append(('', '', ''))

            currentDB['DBdata'].append((DB_name, crawltype, keyword, date, option, starttime, endtime, requester, size))

        db_data = currentDB['DBdata']
        db_list = currentDB['DBlist']
        db_info = currentDB['DBinfo']

        # 다섯 번째 요소를 datetime 객체로 변환하여 정렬
        sorted_indices = sorted(range(len(db_data)), key=lambda i: parse_date(db_data[i][5]), reverse=True)

        # 정렬된 순서대로 새로운 리스트 생성
        sorted_db_data = [db_data[i] for i in sorted_indices]
        sorted_db_list = [db_list[i] for i in sorted_indices]
        sorted_db_info = [db_info[i] for i in sorted_indices]

        self.fullstorage = round(self.fullstorage, 2)

        return {'DBdata': sorted_db_data, 'DBlist': sorted_db_list, 'DBinfo': sorted_db_info}

    def table_maker(self, widgetname, data, column, right_click_function = None):
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
                widgetname.setItem(i, j, item)

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
        # DATABASE
        if index == 0:
            self.Manager_Database_obj.database_refresh_DB()
            QTimer.singleShot(1000, lambda: self.printStatus(f"{self.fullstorage} GB / 8 TB"))

        # CRAWLER
        elif index == 1:
            self.printStatus()
            self.Manager_Web_obj.web_open_webbrowser('http://bigmaclab-crawler.kro.kr:81', self.Manager_Web_obj.crawler_web_layout)
        # ANALYSIS
        elif index == 2:
            self.printStatus()
            if self.Manager_Analysis_generate == False:
                self.Manager_Analysis_obj = Manager_Analysis(self)
                self.Manager_Analysis_generate = True
            self.Manager_Analysis_obj.dataprocess_refresh_DB()
        # BOARD
        elif index == 3:
            self.printStatus()
            pass
        # WEB
        elif index == 4:
            self.printStatus()
            self.Manager_Web_obj.web_open_webbrowser('https://knpu.re.kr', self.Manager_Web_obj.web_web_layout)
        # USER
        elif index == 5:
            self.printStatus()
            pass
            
        gc.collect()

    def pw_check(self):
        input_dialog = QInputDialog(self)
        input_dialog.setWindowTitle('Password')
        input_dialog.setLabelText('Enter password:')
        input_dialog.setTextEchoMode(QLineEdit.Password)
        input_dialog.resize(300, 200)  # 원하는 크기로 설정

        # 비밀번호 입력 창 띄우기
        ok = input_dialog.exec_()
        password = input_dialog.textValue()

        return ok, password

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

    def send_pushOver(self, msg, user_key, image_path = False):
        app_key_list  = ["a22qabchdf25zzkd1vjn12exjytsjx"]

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

    def program_bug_log(self, text, boot=False):
        with open(self.program_log_path, "a") as file:
            # 이어서 기록할 내용
            file.write(f"Recorded in {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n")
            file.write(f"\n{text}")
        if boot == True:
            return
        reply = QMessageBox.question(self, 'Bug Report', "버그 리포트를 전송하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.Manager_Board_obj.board_add_bug()



class InfoDialog(QDialog):
    def __init__(self, version):
        super().__init__()
        self.version = version
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Info')
        self.resize(300, 250)

        layout = QVBoxLayout()

        # 긴 문자열
        long_text = """
        <p align="center">BIGMACLAB MANAGER</p>
        <p align="center">{version}</p>
        <p align="center">Copyright © 2024 KNPU BIGMACLAB<br>all rights reserved.</p>
        """.format(version=self.version)

        # QLabel에 HTML 형식으로 긴 문자열 추가
        info_label = QLabel(long_text, self)
        info_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(info_label)

        self.setLayout(layout)


if __name__ == '__main__':
    def cleanup_temp_dir():
       pass

    atexit.register(cleanup_temp_dir)

    temp_dir = tempfile.mkdtemp()
    shutil.rmtree(temp_dir, ignore_errors=True)
    environ["QT_DEVICE_PIXEL_RATIO"] = "0"
    environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    environ["QT_SCREEN_SCALE_FACTORS"] = "1"
    environ["QT_SCALE_FACTOR"] = "1"

    # High DPI 스케일링 활성화 (QApplication 생성 전 설정)
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QtWidgets.QApplication([])

    # 기본 폰트 설정 및 힌팅 설정
    font = QtGui.QFont()
    font.setHintingPreference(QtGui.QFont.PreferNoHinting)
    app.setFont(font)

    # 메인 윈도우 실행
    application = MainWindow()
    application.show()
    sys.exit(app.exec_())


