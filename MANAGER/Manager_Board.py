from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QTextEdit, QScrollArea
from datetime import datetime

class Manager_Board:
    def __init__(self, main_window):
        self.main = main_window
        self.board_version_refresh()
        self.board_bug_refresh()
        self.board_buttonMatch()

    def board_buttonMatch(self):
        self.main.board_deleteversion_button.clicked.connect(self.board_delete_version)
        self.main.board_addversion_button.clicked.connect(self.board_add_version)
        self.main.board_detailversion_button.clicked.connect(self.board_view_version)

        self.main.board_addbug_button.clicked.connect(self.board_add_bug)
        self.main.board_deletebug_button.clicked.connect(self.board_delete_bug)
        self.main.board_detailbug_button.clicked.connect(self.board_view_bug)
    def board_version_refresh(self):
        try:
            def sort_by_version(two_dim_list):
                # 버전 번호를 파싱하여 비교하는 함수
                def version_key(version_str):
                    return [int(part) for part in version_str.split('.')]

                sorted_list = sorted(two_dim_list, key=lambda x: version_key(x[0]), reverse=True)
                return sorted_list

            self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
            self.version_data = sort_by_version(self.main.mySQL_obj.TableToList('version_info'))
            self.version_data_for_table = [sub_list[:-1] for sub_list in self.version_data]
            self.version_table_column = ['Version Num', 'Release Date', 'ChangeLog', 'Version Features', 'Version Status']
            self.main.table_maker(self.main.board_version_tableWidget, self.version_data_for_table,self.version_table_column)
            self.version_name_list = [version_data[0] for version_data in self.version_data_for_table]
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
    def board_add_version(self):
        try:
            ok, password = self.main.admin_check()

            # 비밀번호 검증
            if ok and password == self.main.admin_password:
                # QDialog를 상속받은 클래스 생성
                class VersionInputDialog(QDialog):
                    def __init__(self):
                        super().__init__()
                        self.initUI()
                        self.data = None  # 데이터를 저장할 속성 추가

                    def initUI(self):
                        self.setWindowTitle('Add Version')
                        self.setGeometry(100, 100, 400, 400)

                        layout = QVBoxLayout()

                        # 각 입력 필드를 위한 QLabel 및 QTextEdit 생성
                        self.version_num_label = QLabel('Version Num:')
                        self.version_num_input = QLineEdit()
                        layout.addWidget(self.version_num_label)
                        layout.addWidget(self.version_num_input)

                        self.release_date_label = QLabel('Release Date:')
                        self.release_date_input = QLineEdit()
                        layout.addWidget(self.release_date_label)
                        layout.addWidget(self.release_date_input)

                        self.changelog_label = QLabel('ChangeLog:')
                        self.changelog_input = QTextEdit()
                        layout.addWidget(self.changelog_label)
                        layout.addWidget(self.changelog_input)

                        self.version_features_label = QLabel('Version Features:')
                        self.version_features_input = QTextEdit()
                        layout.addWidget(self.version_features_label)
                        layout.addWidget(self.version_features_input)

                        self.version_status_label = QLabel('Version Status:')
                        self.version_status_input = QLineEdit()
                        layout.addWidget(self.version_status_label)
                        layout.addWidget(self.version_status_input)

                        self.detail_label = QLabel('Detail:')
                        self.detail_input = QTextEdit()
                        layout.addWidget(self.detail_label)
                        layout.addWidget(self.detail_input)

                        # 확인 버튼 생성 및 클릭 시 동작 연결
                        self.submit_button = QPushButton('Submit')
                        self.submit_button.clicked.connect(self.submit)
                        layout.addWidget(self.submit_button)

                        self.setLayout(layout)

                    def submit(self):
                        # 입력된 데이터를 확인하고 처리
                        version_num = self.version_num_input.text()
                        release_date = self.release_date_input.text()
                        changelog = self.changelog_input.toPlainText()
                        version_features = self.version_features_input.toPlainText()
                        version_status = self.version_status_input.text()
                        detail = self.detail_input.toPlainText()

                        self.data = {
                            'version_num': version_num,
                            'release_date': release_date,
                            'changelog': changelog,
                            'version_features': version_features,
                            'version_status': version_status,
                            'detail': detail
                        }

                        QMessageBox.information(self, 'Input Data',
                                                f'Version Num: {version_num}\nRelease Date: {release_date}\nChangeLog: {changelog}\nVersion Features: {version_features}\nVersion Status: {version_status}\nDetail: {detail}')
                        self.accept()

                dialog = VersionInputDialog()
                dialog.exec_()

                # 데이터를 board_add_version 함수에서 사용
                if dialog.data:
                    version_data = dialog.data
                    version_data = list(version_data.values())
                    self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                    self.main.mySQL_obj.insertToTable('version_info', version_data)
                    self.main.mySQL_obj.commit()
                    self.board_version_refresh()

                    msg = (
                        "[BIGMACLAB MANAGER] New Version Added!\n\n"
                        f"Version Num: {version_data[0]}\n"
                        f"Release Date: {version_data[1]}\n"
                        f"ChangeLog: {version_data[2]}\n"
                        f"Version Features: {version_data[3]}\n"
                        f"Version Status: {version_data[4]}\n"
                        f"Version Detail: \n{version_data[5]}\n"
                    )
                    for key in self.main.userPushOverKeyList:
                        self.main.send_pushOver(msg, key)
            elif ok:
                QMessageBox.warning(self.main, 'Error', 'Incorrect password. Please try again.')
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
    def board_delete_version(self):
        try:
            ok, password = self.main.admin_check()
            # 비밀번호 검증
            if ok and password == self.main.admin_password:
                self.main.printStatus("삭제 중...")
                def delete_version():
                    selected_row = self.main.board_version_tableWidget.currentRow()
                    if selected_row >= 0:
                        print(self.version_name_list[selected_row])
                        self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                        self.main.mySQL_obj.deleteTableRowByColumn('version_info', self.version_name_list[selected_row], 'Version Num')
                        self.board_version_refresh()

                QTimer.singleShot(1, delete_version)
                QTimer.singleShot(1, self.main.printStatus)
            elif ok:
                QMessageBox.warning(self.main, 'Error', 'Incorrect password. Please try again.')
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
    def board_view_version(self):
        try:
            self.main.printStatus("불러오는 중...")
            def view_version():
                selected_row = self.main.board_version_tableWidget.currentRow()
                if selected_row >= 0:
                    version_data = self.version_data[selected_row]

                    # 다이얼로그 생성
                    dialog = QDialog(self.main)
                    dialog.setWindowTitle(f'Version {version_data[0]} Details')
                    dialog.setGeometry(100, 100, 400, 300)

                    layout = QVBoxLayout()

                    # HTML을 사용하여 디테일 표시
                    details_html = f"""
                    <style>
                        h2 {{
                            color: #2c3e50;
                            text-align: center;
                        }}
                        p {{
                            font-family: Arial, sans-serif;
                            font-size: 14px;
                            line-height: 1.5;
                            margin: 5px 0;
                        }}
                        b {{
                            color: #34495e;
                        }}
                        .version-details {{
                            padding: 10px;
                            border: 1px solid #bdc3c7;
                            border-radius: 5px;
                            background-color: #ecf0f1;
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
                        <h2>Version Details</h2>
                        <p><b>Version Num:</b> {version_data[0]}</p>
                        <p><b>Release Date:</b> {version_data[1]}</p>
                        <p><b>ChangeLog:</b> {version_data[2]}</p>
                        <p><b>Version Features:</b> {version_data[3]}</p>
                        <p><b>Version Status:</b> {version_data[4]}</p>
                        <p><b>Detail:</b></p>
                        <p class="detail-content">{version_data[5]}</p>
                    </div>
                    """

                    detail_label = QLabel(details_html)
                    detail_label.setWordWrap(True)

                    # QScrollArea를 사용하여 스크롤 가능하게 설정
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setWidget(detail_label)

                    layout.addWidget(scroll_area)

                    # 닫기 버튼 추가
                    close_button = QPushButton('Close')
                    close_button.clicked.connect(dialog.accept)
                    layout.addWidget(close_button)

                    dialog.setLayout(layout)

                    # 다이얼로그 실행
                    dialog.exec_()

            QTimer.singleShot(1, view_version)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
    def board_bug_refresh(self):
        try:
            def sort_by_date(two_dim_list):
                # 날짜 문자열을 파싱하여 비교하는 함수
                def date_key(date_str):
                    return datetime.strptime(date_str, "%Y.%m.%d %H:%M")

                sorted_list = sorted(two_dim_list, key=lambda x: date_key(x[3]), reverse=True)
                return sorted_list

            self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
            self.bug_data = sort_by_date(self.main.mySQL_obj.TableToList('version_bug'))
            self.bug_data_for_table = [sub_list[:-1] for sub_list in self.bug_data]
            self.bug_table_column = ['User', 'Version Num', 'Title', 'DateTime']
            self.main.table_maker(self.main.board_bug_tableWidget, self.bug_data_for_table,
                                  self.bug_table_column)
            self.bug_title_list = [bug_data[2] for bug_data in self.bug_data_for_table]
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
    def board_add_bug(self):
        try:
            # QDialog를 상속받은 클래스 생성
            class BugInputDialog(QDialog):
                def __init__(self, version):
                    super().__init__()
                    self.initUI()
                    self.data = None  # 데이터를 저장할 속성 추가
                    self.version = version

                def initUI(self):
                    self.setWindowTitle('Add Bug')
                    self.setGeometry(100, 100, 400, 400)

                    layout = QVBoxLayout()

                    # 각 입력 필드를 위한 QLabel 및 QTextEdit 생성
                    self.user_label = QLabel('User Name:')
                    self.user_input = QLineEdit()
                    layout.addWidget(self.user_label)
                    layout.addWidget(self.user_input)

                    self.bug_title_label = QLabel('Bug Title:')
                    self.bug_title_input = QLineEdit()
                    layout.addWidget(self.bug_title_label)
                    layout.addWidget(self.bug_title_input)

                    self.bug_detail_label = QLabel('Bug Detail:')
                    self.bug_detail_input = QTextEdit()
                    layout.addWidget(self.bug_detail_label)
                    layout.addWidget(self.bug_detail_input)

                    # 확인 버튼 생성 및 클릭 시 동작 연결
                    self.submit_button = QPushButton('Submit')
                    self.submit_button.clicked.connect(self.submit)
                    layout.addWidget(self.submit_button)

                    self.setLayout(layout)

                def submit(self):
                    # 입력된 데이터를 확인하고 처리
                    user_name = self.user_input.text()
                    version_num = self.version
                    bug_title = self.bug_title_input.text()
                    bug_date = datetime.now().strftime("%Y.%m.%d %H:%M")
                    bug_detail = self.bug_detail_input.toPlainText()

                    self.data = {
                        'user_name': user_name,
                        'version_num': version_num,
                        'bug_title': bug_title,
                        'bug_date': bug_date,
                        'bug_detail': bug_detail
                    }

                    QMessageBox.information(self, 'Input Data',
                                            f'User Name: {user_name}\nVersion Num: {version_num}\nBug Title: {bug_title}\nDateTime: {bug_date}\nBug Detail: {bug_detail}')
                    self.accept()

            dialog = BugInputDialog(self.main.versionNum)
            dialog.exec_()

            # 데이터를 board_add_version 함수에서 사용
            if dialog.data:
                bug_data = dialog.data
                bug_data = list(bug_data.values())
                self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                self.main.mySQL_obj.insertToTable('version_bug', bug_data)
                self.main.mySQL_obj.commit()
                self.board_bug_refresh()

                msg = (
                    "[BIGMACLAB MANAGER] New Bug Added!\n"
                    f"User: {bug_data[0]}\n"
                    f"Version: {bug_data[1]}\n"
                    f"Title: {bug_data[2]}\n"
                    f"Datetime: {bug_data[3]}\n"
                    f"Detail: \n{bug_data[4]}\n"
                )
                self.main.send_pushOver(msg, self.main.admin_pushoverkey)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
    def board_delete_bug(self):
        try:
            self.main.printStatus("삭제 중...")
            def delete_bug():
                reply = QMessageBox.question(self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No,
                                             QMessageBox.No)
                if reply == QMessageBox.Yes:
                    selected_row = self.main.board_bug_tableWidget.currentRow()
                    if selected_row >= 0:
                        self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                        self.main.mySQL_obj.deleteTableRowByColumn('version_bug', self.bug_title_list[selected_row], 'Bug Title')
                        self.board_bug_refresh()

            QTimer.singleShot(1, delete_bug)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
    def board_view_bug(self):
        try:
            self.main.printStatus("불러오는 중...")
            def view_bug():
                selected_row = self.main.board_bug_tableWidget.currentRow()
                if selected_row >= 0:
                    bug_data = self.bug_data[selected_row]

                    # 다이얼로그 생성
                    dialog = QDialog(self.main)
                    dialog.setWindowTitle(f'Bug {bug_data[1]} Details')
                    dialog.setGeometry(100, 100, 400, 300)

                    layout = QVBoxLayout()

                    # HTML을 사용하여 디테일 표시
                    details_html = f"""
                    <style>
                        h2 {{
                            color: #2c3e50;
                            text-align: center;
                        }}
                        p {{
                            font-family: Arial, sans-serif;
                            font-size: 14px;
                            line-height: 1.5;
                            margin: 5px 0;
                        }}
                        b {{
                            color: #34495e;
                        }}
                        .bug-details {{
                            padding: 10px;
                            border: 1px solid #bdc3c7;
                            border-radius: 5px;
                            background-color: #ecf0f1;
                        }}
                        .detail-content {{
                            white-space: pre-wrap;
                            margin-top: 5px;
                            font-family: Arial, sans-serif;
                            font-size: 14px;
                            color: #34495e;
                        }}
                    </style>
                    <div class="bug-details">
                        <h2>Bug Details</h2>
                        <p><b>User Name:</b> {bug_data[0]}</p>
                        <p><b>Version Num:</b> {bug_data[1]}</p>
                        <p><b>Bug Title:</b> {bug_data[2]}</p>
                        <p><b>DateTime:</b> {bug_data[3]}</p>
                        <p><b>Bug Detail:</b></p>
                        <p class="detail-content">{bug_data[4]}</p>
                    </div>
                    """
                    detail_label = QLabel(details_html)
                    detail_label.setWordWrap(True)

                    # QScrollArea를 사용하여 스크롤 가능하게 설정
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setWidget(detail_label)

                    layout.addWidget(scroll_area)

                    # 닫기 버튼 추가
                    close_button = QPushButton('Close')
                    close_button.clicked.connect(dialog.accept)
                    layout.addWidget(close_button)

                    dialog.setLayout(layout)

                    # 다이얼로그 실행
                    dialog.exec_()

            QTimer.singleShot(1, view_bug)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")


