from PyQt5.QtCore import QTimer, QRegExp
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QTextEdit, QScrollArea, QWidget
from PyQt5.QtGui import QRegExpValidator
from datetime import datetime
import warnings
import os
import traceback
warnings.filterwarnings("ignore")

class Manager_Board:
    def __init__(self, main_window):
        self.main = main_window
        self.board_version_refresh()
        self.board_bug_refresh()
        self.board_post_refresh()
        self.board_buttonMatch()


    def board_buttonMatch(self):
        self.main.board_deleteversion_button.clicked.connect(self.board_delete_version)
        self.main.board_addversion_button.clicked.connect(self.board_add_version)
        self.main.board_detailversion_button.clicked.connect(self.board_view_version)

        self.main.board_addbug_button.clicked.connect(self.board_add_bug)
        self.main.board_deletebug_button.clicked.connect(self.board_delete_bug)
        self.main.board_detailbug_button.clicked.connect(self.board_view_bug)

        self.main.board_addpost_button.clicked.connect(self.board_add_post)
        self.main.board_detailpost_button.clicked.connect(self.board_view_post)
        self.main.board_deletepost_button.clicked.connect(self.board_delete_post)
        self.main.board_editpost_button.clicked.connect(self.board_edit_post)

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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())
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

                        # 컨테이너 위젯 생성
                        container_widget = QWidget()
                        layout = QVBoxLayout(container_widget)

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

                        # QScrollArea 설정
                        scroll_area = QScrollArea()
                        scroll_area.setWidgetResizable(True)
                        scroll_area.setWidget(container_widget)  # 컨테이너 위젯을 스크롤 영역에 추가

                        # 최종 레이아웃 설정
                        final_layout = QVBoxLayout()
                        final_layout.addWidget(scroll_area)
                        self.setLayout(final_layout)

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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())
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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())
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
                    dialog.setGeometry(100, 100, 400, 600)

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

                    # QLabel을 QTextEdit으로 변경하여 HTML을 설정하고 스크롤 가능하게 설정
                    detail_text_edit = QTextEdit()
                    detail_text_edit.setReadOnly(True)
                    detail_text_edit.setHtml(details_html)

                    # QScrollArea를 사용하여 스크롤 가능하게 설정
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setWidget(detail_text_edit)

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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())
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
            self.bug_data_for_table = [sub_list[:-2] for sub_list in self.bug_data]
            self.bug_table_column = ['User', 'Version Num', 'Title', 'DateTime']
            self.main.table_maker(self.main.board_bug_tableWidget, self.bug_data_for_table,
                                  self.bug_table_column)
            self.bug_title_list = [bug_data[2] for bug_data in self.bug_data_for_table]
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())
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

                    # 컨테이너 위젯 생성
                    container_widget = QWidget()
                    layout = QVBoxLayout(container_widget)

                    # 각 입력 필드를 위한 QLabel 및 QLineEdit, QTextEdit 생성
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
                    self.bug_detail_input.setPlaceholderText('버그가 발생하는 상황과 조건, 어떤 버그가 일어나는지 자세히 작성해주세요')
                    layout.addWidget(self.bug_detail_label)
                    layout.addWidget(self.bug_detail_input)

                    # 확인 버튼 생성 및 클릭 시 동작 연결
                    self.submit_button = QPushButton('Submit')
                    self.submit_button.clicked.connect(self.submit)
                    layout.addWidget(self.submit_button)

                    # QScrollArea 설정
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setWidget(container_widget)  # 컨테이너 위젯을 스크롤 영역에 추가

                    # 최종 레이아웃 설정
                    final_layout = QVBoxLayout()
                    final_layout.addWidget(scroll_area)
                    self.setLayout(final_layout)

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
                with open(self.main.program_log_path, 'r') as log:
                    log_record = log.read()
                bug_data.append(log_record)
                self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                self.main.mySQL_obj.insertToTable('version_bug', bug_data)
                self.main.mySQL_obj.commit()
                self.board_bug_refresh()

                if os.path.exists(self.main.program_log_path):
                    os.remove(self.main.program_log_path)
                with open(self.main.program_log_path, "w") as log:
                    log.write(f"Recorded in {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")

                msg = (
                    "[BIGMACLAB MANAGER] New Bug Added!\n"
                    f"User: {bug_data[0]}\n"
                    f"Version: {bug_data[1]}\n"
                    f"Title: {bug_data[2]}\n"
                    f"Datetime: {bug_data[3]}\n"
                    f"Detail: \n{bug_data[4]}\n"
                    f"log: \n{bug_data[5]}\n"
                )
                self.main.send_pushOver(msg, self.main.admin_pushoverkey)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())
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
            self.main.program_bug_log(traceback.format_exc())
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
                    dialog.setGeometry(100, 100, 400, 600)

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
                        <p><b>Program Log:</b></p>
                        <p class="detail-content">{bug_data[5]}</p>
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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def board_post_refresh(self):
        try:
            def sort_by_date(two_dim_list):
                # 날짜 문자열을 파싱하여 비교하는 함수
                def date_key(date_str):
                    return datetime.strptime(date_str, "%Y.%m.%d %H:%M")

                sorted_list = sorted(two_dim_list, key=lambda x: date_key(x[2]), reverse=True)
                return sorted_list

            self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
            self.post_data = sort_by_date(self.main.mySQL_obj.TableToList('free_board'))
            self.post_data_for_table = [sub_list[:-1] for sub_list in self.post_data]
            self.post_table_column = ['User', 'Title', 'DateTime', 'ViewCount']
            self.main.table_maker(self.main.board_post_tableWidget, self.post_data_for_table,
                                  self.post_table_column)
            self.post_title_list = [post_data[1] for post_data in self.post_data_for_table]
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def board_add_post(self):
        try:
            # QDialog를 상속받은 클래스 생성
            class PostInputDialog(QDialog):
                def __init__(self):
                    super().__init__()
                    self.initUI()
                    self.data = None  # 데이터를 저장할 속성 추가

                def initUI(self):
                    self.setWindowTitle('Add Post')
                    self.setGeometry(100, 100, 400, 400)

                    # 컨테이너 위젯 생성
                    container_widget = QWidget()
                    layout = QVBoxLayout(container_widget)

                    # 사용자 이름 입력 필드
                    self.user_label = QLabel('User Name:')
                    self.user_input = QLineEdit()
                    layout.addWidget(self.user_label)
                    layout.addWidget(self.user_input)

                    # 비밀번호 입력 필드
                    self.password_label = QLabel('Password (수정 및 삭제용):')
                    self.password_input = QLineEdit()
                    self.password_input.setEchoMode(QLineEdit.Password)  # 비밀번호 입력 필드로 설정

                    # 영어 알파벳만 입력 가능하도록 제한 (영문 대소문자 포함)
                    reg_exp = QRegExp("[a-zA-Z]*")
                    validator = QRegExpValidator(reg_exp, self.password_input)
                    self.password_input.setValidator(validator)

                    layout.addWidget(self.password_label)
                    layout.addWidget(self.password_input)

                    # 비밀번호 확인 입력 필드
                    self.confirm_password_label = QLabel('Confirm Password:')
                    self.confirm_password_input = QLineEdit()
                    self.confirm_password_input.setEchoMode(QLineEdit.Password)  # 비밀번호 확인 입력 필드로 설정

                    # 영어 알파벳만 입력 가능하도록 제한 (영문 대소문자 포함)
                    self.confirm_password_input.setValidator(validator)

                    layout.addWidget(self.confirm_password_label)
                    layout.addWidget(self.confirm_password_input)

                    # 비밀번호 불일치 경고 메시지
                    self.password_warning_label = QLabel('')
                    self.password_warning_label.setStyleSheet('color: red')  # 경고 메시지를 빨간색으로 설정
                    layout.addWidget(self.password_warning_label)

                    # 비밀번호 필드 변경 시 일치 여부 확인
                    self.password_input.textChanged.connect(self.check_password_match)
                    self.confirm_password_input.textChanged.connect(self.check_password_match)

                    # 게시물 제목 입력 필드
                    self.post_title_label = QLabel('Post Title:')
                    self.post_title_input = QLineEdit()
                    layout.addWidget(self.post_title_label)
                    layout.addWidget(self.post_title_input)

                    # 게시물 내용 입력 필드
                    self.post_text_label = QLabel('Post Text:')
                    self.post_text_input = QTextEdit()
                    layout.addWidget(self.post_text_label)
                    layout.addWidget(self.post_text_input)

                    # 확인 버튼 생성 및 클릭 시 동작 연결
                    self.submit_button = QPushButton('Post')
                    self.submit_button.clicked.connect(self.submit)
                    layout.addWidget(self.submit_button)

                    # QScrollArea 설정
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setWidget(container_widget)  # 컨테이너 위젯을 스크롤 영역에 추가

                    # 최종 레이아웃 설정
                    final_layout = QVBoxLayout()
                    final_layout.addWidget(scroll_area)
                    self.setLayout(final_layout)

                def check_password_match(self):
                    password = self.password_input.text()
                    confirm_password = self.confirm_password_input.text()

                    if password != confirm_password:
                        self.password_warning_label.setText('Passwords do not match.')
                        self.submit_button.setEnabled(False)  # 제출 버튼 비활성화
                    else:
                        self.password_warning_label.setText('')
                        self.submit_button.setEnabled(True)  # 제출 버튼 활성화

                def submit(self):
                    # 입력된 데이터를 확인하고 처리
                    user_name = self.user_input.text()
                    pw = self.password_input.text()
                    post_title = self.post_title_input.text()
                    post_date = datetime.now().strftime("%Y.%m.%d %H:%M")
                    post_text = self.post_text_input.toPlainText()


                    self.data = {
                        'user_name': user_name,
                        'post_title': post_title,
                        'post_date': post_date,
                        'ViewCount': 0,
                        'post_text': post_text,
                        'pw': pw,
                    }

                    QMessageBox.information(self, 'Input Data',
                                            f'User Name: {user_name}\nPost Title: {post_title}\nPost Date: {post_date}\nPost Text: {post_text}')
                    self.accept()

            dialog = PostInputDialog()
            dialog.exec_()

            # 데이터를 board_add_version 함수에서 사용
            if dialog.data:
                post_data = dialog.data
                post_data = list(post_data.values())
                self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                self.main.mySQL_obj.insertToTable('free_board', post_data)
                self.main.mySQL_obj.commit()
                self.board_post_refresh()

                msg = (
                    "[BIGMACLAB MANAGER] New Post Added!\n"
                    f"User: {post_data[0]}\n"
                    f"Post Title: {post_data[1]}\n"
                    f"Post Date: {post_data[2]}\n"
                    f"Post Text: {post_data[4]}\n"
                )
                self.main.send_pushOver(msg, self.main.admin_pushoverkey)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def board_view_post(self):
        try:
            self.main.printStatus("불러오는 중...")
            def view_post():
                selected_row = self.main.board_post_tableWidget.currentRow()
                if selected_row >= 0:
                    post_data = self.post_data[selected_row]

                    viewcount = int(post_data[3])
                    viewcount += 1
                    self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                    self.main.mySQL_obj.updateTableCell('free_board', selected_row, 'ViewCount', viewcount)

                    # 다이얼로그 생성
                    dialog = QDialog(self.main)
                    dialog.setWindowTitle(f'Post View')
                    dialog.setGeometry(100, 100, 400, 600)

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
                        .post-details {{
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
                    <div class="post-details">
                        <h2>Post View</h2>
                        <p><b>User Name:</b> {post_data[0]}</p>
                        <p><b>Post Title:</b> {post_data[1]}</p>
                        <p><b>DateTime:</b> {post_data[2]}</p>
                        <p><b>Post Text:</b></p>
                        <p class="detail-content">{post_data[4]}</p>
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
                    self.board_post_refresh()

            QTimer.singleShot(1, view_post)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def board_delete_post(self):
        try:
            self.main.printStatus("삭제 중...")
            def delete_post():
                selected_row = self.main.board_post_tableWidget.currentRow()
                if selected_row >= 0:
                    ok, password = self.main.pw_check()
                    if password == self.post_data[selected_row][5]:
                        self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                        self.main.mySQL_obj.deleteTableRowByColumn('free_board', self.post_title_list[selected_row], 'Title')
                        self.board_post_refresh()
                        QMessageBox.information(self.main, "Information", f"게시물이 삭제되었습니다")
                    else:
                        QMessageBox.information(self.main, "Information", f"비밀번호가 일치하지 않습니다")
                        self.main.printStatus()
                        return

            QTimer.singleShot(1, delete_post)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
            self.main.program_bug_log(traceback.format_exc())

    def board_edit_post(self):
        try:
            # QDialog를 상속받은 클래스 생성
            class PostInputDialog(QDialog):
                def __init__(self, post_data):
                    super().__init__()
                    self.post_data = post_data
                    self.initUI()
                    self.data = None  # 데이터를 저장할 속성 추가
                def initUI(self):
                    self.setWindowTitle('Edit Post')
                    self.setGeometry(100, 100, 400, 400)

                    # 컨테이너 위젯 생성
                    container_widget = QWidget()
                    layout = QVBoxLayout(container_widget)

                    # 게시물 제목 입력 필드
                    self.post_title_label = QLabel('Post Title:')
                    self.post_title_input = QLineEdit()
                    self.post_title_input.setText(self.post_data[1])
                    layout.addWidget(self.post_title_label)
                    layout.addWidget(self.post_title_input)

                    # 게시물 내용 입력 필드
                    self.post_text_label = QLabel('Post Text:')
                    self.post_text_input = QTextEdit()
                    self.post_text_input.setText(self.post_data[4])
                    layout.addWidget(self.post_text_label)
                    layout.addWidget(self.post_text_input)

                    # 확인 버튼 생성 및 클릭 시 동작 연결
                    self.submit_button = QPushButton('Edit')
                    self.submit_button.clicked.connect(self.submit)
                    layout.addWidget(self.submit_button)

                    # QScrollArea 설정
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setWidget(container_widget)  # 컨테이너 위젯을 스크롤 영역에 추가

                    # 최종 레이아웃 설정
                    final_layout = QVBoxLayout()
                    final_layout.addWidget(scroll_area)
                    self.setLayout(final_layout)

                def submit(self):
                    # 입력된 데이터를 확인하고 처리
                    post_title = self.post_title_input.text()
                    post_text = self.post_text_input.toPlainText()

                    self.data = {
                        'post_title': post_title,
                        'post_text': post_text,
                    }

                    QMessageBox.information(self, 'Input Data',
                                            f'Post Title: {post_title}\nPost Text: {post_text}')
                    self.accept()

            selected_row = self.main.board_post_tableWidget.currentRow()
            if selected_row >= 0:
                ok, password = self.main.pw_check()
                if password == self.post_data[selected_row][5]:
                    prev_post_data = self.post_data[selected_row]

                    dialog = PostInputDialog(prev_post_data)
                    dialog.exec_()

                    # 데이터를 board_add_version 함수에서 사용
                    if dialog.data:
                        post_data = dialog.data
                        post_data = list(post_data.values())
                        self.main.mySQL_obj.connectDB('bigmaclab_manager_db')
                        self.main.mySQL_obj.updateTableCell('free_board', selected_row, 'Title', post_data[0])
                        self.main.mySQL_obj.updateTableCell('free_board', selected_row, 'Text', post_data[1])
                        self.board_post_refresh()
                        QMessageBox.information(self.main, "Information", f"게시물이 수정되었습니다")
                else:
                    QMessageBox.information(self.main, "Information", f"비밀번호가 일치하지 않습니다")
                    self.main.printStatus()
                    return
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())