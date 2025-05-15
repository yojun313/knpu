import traceback
import warnings
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QTextEdit, QScrollArea, QShortcut
)
import bcrypt
from ui.table import makeTable
from services.auth import checkPassword
from ui.status import printStatus
from config import ADMIN_PASSWORD
from services.api import Request

warnings.filterwarnings("ignore")


class Manager_Board:
    def __init__(self, main_window):
        self.main = main_window
        self.refreshVersionBoard()
        self.refreshBugBoard()
        self.refreshPostBoard()
        self.matchButton()
        self.main.tabWidget_board.currentChanged.connect(self.updateShortcut)

    def refreshVersionBoard(self):
        try:
            def sort_by_version(two_dim_list):
                # 버전 번호를 파싱하여 비교하는 함수
                def version_key(version_str):
                    return [int(part) for part in version_str.split('.')]

                sorted_list = sorted(
                    two_dim_list, key=lambda x: version_key(x[0]), reverse=True)
                return sorted_list

            self.origin_version_data = Request(
                'get', '/board/version').json()['data']

            self.version_data = [[item['versionName'], item['releaseDate'], item['changeLog'], item['features'], item['status'], item['details']]
                                 for item in self.origin_version_data]
            self.version_data = sort_by_version(self.version_data)

            self.version_data_for_table = [sub_list[:-1]
                                           for sub_list in self.version_data]
            self.version_table_column = [
                'Version Num', 'Release Date', 'ChangeLog', 'Version Features', 'Version Status']
            makeTable(self.main, self.main.board_version_tableWidget,
                      self.version_data_for_table, self.version_table_column)
            self.version_name_list = [version_data[0]
                                      for version_data in self.version_data_for_table]

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def addVersion(self):
        try:
            if self.main.user != 'admin':
                ok, password = checkPassword(self.main, True)
                if not ok or bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')) == False:
                    return

            # QDialog를 상속받은 클래스 생성
            class VersionInputDialog(QDialog):
                def __init__(self, version):
                    super().__init__()
                    self.version = version
                    self.initUI()
                    self.data = None  # 데이터를 저장할 속성 추가

                def initUI(self):
                    self.setWindowTitle('Add Version')
                    self.resize(400, 400)

                    # 컨테이너 위젯 생성
                    container_widget = QDialog()
                    layout = QVBoxLayout(container_widget)

                    # 각 입력 필드를 위한 QLabel 및 QTextEdit 생성
                    self.version_num_label = QLabel('Version Num:')
                    self.version_num_input = QLineEdit()
                    self.version_num_input.setText(self.version)
                    layout.addWidget(self.version_num_label)
                    layout.addWidget(self.version_num_input)

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
                    # 컨테이너 위젯을 스크롤 영역에 추가
                    scroll_area.setWidget(container_widget)

                    # 최종 레이아웃 설정
                    final_layout = QVBoxLayout()
                    final_layout.addWidget(scroll_area)
                    self.setLayout(final_layout)

                def submit(self):
                    # 입력된 데이터를 확인하고 처리
                    version_num = self.version_num_input.text()
                    changelog = self.changelog_input.toPlainText()
                    version_features = self.version_features_input.toPlainText()
                    version_status = self.version_status_input.text()
                    detail = self.detail_input.toPlainText()

                    self.data = [version_num, changelog,
                                 version_features, version_status, detail]

                    QMessageBox.information(self, 'Input Data',
                                            f'Version Num: {version_num}\nChangeLog: {changelog}\nVersion Features: {version_features}\nVersion Status: {version_status}\nDetail: {detail}')
                    self.accept()

            dialog = VersionInputDialog(self.main.versionNum)
            dialog.exec_()

            # 데이터를 addVersion 함수에서 사용
            if dialog.data:
                version_data = dialog.data
                data = {
                    "versionName": version_data[0],
                    "changeLog": version_data[1],
                    "features": version_data[2],
                    "status": version_data[3],
                    "details": version_data[4],
                    'sendPushOver': False,
                }

                reply = QMessageBox.question(
                    self.main, 'Confirm Notification', "업데이트 알림을 전송하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    data['sendPushOver'] = True

                Request('post', '/board/version/add', json=data)
            self.refreshVersionBoard()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def deleteVersion(self):
        try:
            if self.main.user != 'admin':
                ok, password = checkPassword(self.main, True)
                if not ok or bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')) == False:
                    return

            selectedRow = self.main.board_version_tableWidget.currentRow()
            if selectedRow >= 0:
                reply = QMessageBox.question(
                    self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    version = self.version_name_list[selectedRow]
                    Request('delete', f'/board/version/{version}')

            self.refreshVersionBoard()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def viewVersion(self):
        try:
            self.main.userLogging(f'BOARD -> viewVersion')

            selectedRow = self.main.board_version_tableWidget.currentRow()
            if selectedRow >= 0:
                printStatus(self.main, "불러오는 중...")
                version_data = self.version_data[selectedRow]

                # 다이얼로그 생성
                dialog = QDialog(self.main)
                dialog.setWindowTitle(f'Version {version_data[0]} Details')
                dialog.resize(400, 400)

                layout = QVBoxLayout()

                # HTML을 사용하여 디테일 표시
                details_html = self.main.style_html + f"""
                    <div class="version-details">
                        <table>
                            <tr>
                                <th>Item</th>
                                <th>Details</th>
                            </tr>
                            <tr>
                                <td><b>Version Num:</b></td>
                                <td>{version_data[0]}</td>
                            </tr>
                            <tr>
                                <td><b>Release Date:</b></td>
                                <td>{version_data[1]}</td>
                            </tr>
                            <tr>
                                <td><b>ChangeLog:</b></td>
                                <td>{version_data[2]}</td>
                            </tr>
                            <tr>
                                <td><b>Version Features:</b></td>
                                <td>{version_data[3]}</td>
                            </tr>
                            <tr>
                                <td><b>Version Status:</b></td>
                                <td>{version_data[4]}</td>
                            </tr>
                            <tr>
                                <td><b>Detail:</b></td>
                                <td class="detail-content">{version_data[5]}</td>
                            </tr>
                        </table>
                    </div>
                """
                detail_label = QLabel(details_html)
                detail_label.setWordWrap(True)

                # QScrollArea를 사용하여 스크롤 가능하게 설정
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setWidget(detail_label)

                layout.addWidget(scroll_area, alignment=Qt.AlignHCenter)

                # 닫기 버튼 추가
                close_button = QPushButton('Close')
                close_button.clicked.connect(dialog.accept)
                layout.addWidget(close_button)

                ctrlw = QShortcut(QKeySequence("Ctrl+W"), dialog)
                ctrlw.activated.connect(dialog.accept)

                cmdw = QShortcut(QKeySequence("Ctrl+ㅈ"), dialog)
                cmdw.activated.connect(dialog.accept)

                dialog.setLayout(layout)
                printStatus(self.main)
                # 다이얼로그 실행
                dialog.exec_()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def refreshBugBoard(self):
        try:
            self.origin_bug_data = Request(
                'get', '/board/bug').json()['data']
            self.bug_data_for_table = [
                [sub_list['writerName'], sub_list['versionName'],
                    sub_list['bugTitle'], sub_list['datetime']]
                for sub_list in self.origin_bug_data]
            self.bug_table_column = [
                'User', 'Version Num', 'Title', 'DateTime']
            makeTable(self.main, self.main.board_bug_tableWidget,
                      self.bug_data_for_table, self.bug_table_column)
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def addBug(self):
        try:
            # QDialog를 상속받은 클래스 생성
            class BugInputDialog(QDialog):
                def __init__(self, main_window, version):
                    super().__init__()
                    self.main = main_window
                    self.initUI()
                    self.data = None  # 데이터를 저장할 속성 추가
                    self.version = version

                def initUI(self):
                    self.setWindowTitle('Bug Report')
                    self.resize(400, 400)

                    # 컨테이너 위젯 생성
                    container_widget = QDialog()
                    layout = QVBoxLayout(container_widget)

                    # 각 입력 필드를 위한 QLabel 및 QLineEdit, QTextEdit 생성
                    self.user_label = QLabel('User Name:')
                    self.user_input = QLineEdit()
                    self.user_input.setText(self.main.user)
                    layout.addWidget(self.user_label)
                    layout.addWidget(self.user_input)

                    self.bug_title_label = QLabel('Bug Title:')
                    self.bug_title_input = QLineEdit()
                    layout.addWidget(self.bug_title_label)
                    layout.addWidget(self.bug_title_input)

                    self.bug_detail_label = QLabel('Bug Detail:')
                    self.bug_detail_input = QTextEdit()
                    self.bug_detail_input.setPlaceholderText(
                        '버그가 발생하는 상황과 조건, 어떤 버그가 일어나는지 자세히 작성해주세요\n오류 로그는 자동으로 전송됩니다')
                    layout.addWidget(self.bug_detail_label)
                    layout.addWidget(self.bug_detail_input)

                    # 확인 버튼 생성 및 클릭 시 동작 연결
                    self.submit_button = QPushButton('Submit')
                    self.submit_button.clicked.connect(self.submit)
                    layout.addWidget(self.submit_button)

                    # QScrollArea 설정
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    # 컨테이너 위젯을 스크롤 영역에 추가
                    scroll_area.setWidget(container_widget)

                    # 최종 레이아웃 설정
                    final_layout = QVBoxLayout()
                    final_layout.addWidget(scroll_area)
                    self.setLayout(final_layout)

                def submit(self):
                    # 입력된 데이터를 확인하고 처리
                    userName = self.user_input.text()
                    version_num = self.version
                    bug_title = self.bug_title_input.text()
                    bug_detail = self.bug_detail_input.toPlainText()

                    self.data = {
                        'userName': userName,
                        'version_num': version_num,
                        'bug_title': bug_title,
                        'bug_detail': bug_detail
                    }

                    QMessageBox.information(self, 'Input Data',
                                            f'User Name: {userName}\nVersion Num: {version_num}\nBug Title: {bug_title}\nBug Detail: {bug_detail}')
                    self.accept()

            dialog = BugInputDialog(self.main, self.main.versionNum)
            dialog.exec_()

            # 데이터를 addVersion 함수에서 사용
            if dialog.data:
                bug_data = dialog.data
                bug_data = list(bug_data.values())

                json_data = {
                    "writerUid": self.main.userUid,
                    "versionName": bug_data[1],
                    "bugTitle": bug_data[2],
                    "bugText": bug_data[3],
                    "programLog": "",
                }

                Request('post', '/board/bug/add', json=json_data)
                self.refreshBugBoard()
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def deleteBug(self):
        try:
            selectedRow = self.main.board_bug_tableWidget.currentRow()
            if selectedRow >= 0:
                bug = self.origin_bug_data[selectedRow]

                if bug['writerUid'] == self.main.userUid or self.main.user == 'admin':
                    reply = QMessageBox.question(
                        self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        printStatus(self.main, "삭제 중...")
                        Request('delete', f'/board/bug/{bug["uid"]}')
                        self.refreshBugBoard()
                        printStatus(self.main)
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"작성자만 삭제할 수 있습니다")
                    return

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def viewBug(self):
        try:
            self.main.userLogging(f'BOARD -> viewBug')

            selectedRow = self.main.board_bug_tableWidget.currentRow()
            if selectedRow >= 0:
                printStatus(self.main, "불러오는 중...")
                bug_data = self.origin_bug_data[selectedRow]
                printStatus(self.main)

                # 다이얼로그 생성
                dialog = QDialog(self.main)
                dialog.setWindowTitle(
                    f'Version {bug_data['versionName']} Bug Details')
                dialog.resize(400, 600)

                layout = QVBoxLayout()

                # HTML을 사용하여 디테일 표시
                details_html = self.main.style_html + f"""
                    <div class="bug-details">
                        <table>
                            <tr>
                                <th>Item</th>
                                <th>Details</th>
                            </tr>
                            <tr>
                                <td><b>User Name:</b></td>
                                <td>{bug_data['writerName']}</td>
                            </tr>
                            <tr>
                                <td><b>Version Num:</b></td>
                                <td>{bug_data['versionName']}</td>
                            </tr>
                            <tr>
                                <td><b>Bug Title:</b></td>
                                <td>{bug_data['bugTitle']}</td>
                            </tr>
                            <tr>
                                <td><b>DateTime:</b></td>
                                <td>{bug_data['datetime']}</td>
                            </tr>
                            <tr>
                                <td><b>Bug Detail:</b></td>
                                <td class="detail-content">{bug_data['bugText']}</td>
                            </tr>
                            <tr>
                                <td><b>Program Log:</b></td>
                                <td class="detail-content">{bug_data['programLog']}</td>
                            </tr>
                        </table>
                    </div>
                    """

                detail_label = QLabel(details_html)
                detail_label.setWordWrap(True)

                # QScrollArea를 사용하여 스크롤 가능하게 설정
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setWidget(detail_label)

                layout.addWidget(scroll_area, alignment=Qt.AlignHCenter)

                # 닫기 버튼 추가
                close_button = QPushButton('Close')
                close_button.clicked.connect(dialog.accept)
                layout.addWidget(close_button)

                ctrlw = QShortcut(QKeySequence("Ctrl+W"), dialog)
                ctrlw.activated.connect(dialog.accept)

                cmdw = QShortcut(QKeySequence("Ctrl+ㅈ"), dialog)
                cmdw.activated.connect(dialog.accept)

                dialog.setLayout(layout)
                printStatus(self.main)

                # 다이얼로그 실행
                dialog.exec_()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def refreshPostBoard(self):
        try:
            self.origin_post_data = Request(
                'get', '/board/post').json()['data']
            self.post_data_for_table = [
                [sub_list['writerName'], sub_list['title'],
                    sub_list['datetime'], str(sub_list['viewCnt'])]
                for sub_list in self.origin_post_data
            ]
            self.post_table_column = [
                'User', 'Title', 'DateTime', 'View Count']
            makeTable(self.main, self.main.board_post_tableWidget,
                      self.post_data_for_table, self.post_table_column)
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def addPost(self):
        try:
            # QDialog를 상속받은 클래스 생성
            self.main.userLogging(f'BOARD -> addPost')

            class PostInputDialog(QDialog):
                def __init__(self, main_window):
                    super().__init__()
                    self.main = main_window
                    self.initUI()
                    self.data = None  # 데이터를 저장할 속성 추가

                def initUI(self):
                    self.setWindowTitle('Add Post')
                    self.resize(400, 400)

                    # 컨테이너 위젯 생성
                    container_widget = QDialog()
                    layout = QVBoxLayout(container_widget)

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
                    # 컨테이너 위젯을 스크롤 영역에 추가
                    scroll_area.setWidget(container_widget)

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

                    QMessageBox.information(self, 'New Post',
                                            f'Post Title: {post_title}\nPost Text: {post_text}')
                    self.accept()

            dialog = PostInputDialog(self.main)
            dialog.exec_()

            if dialog.data:
                post_data = dialog.data
                post_data = list(post_data.values())

                json_data = {
                    "writerUid": self.main.userUid,
                    "title": post_data[0],
                    "text": post_data[1],
                    "sendPushOver": False,
                }

                reply = QMessageBox.question(
                    self.main, 'Confirm Notification', "현재 게시글에 대한 전체 알림을 전송하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    json_data['sendPushOver'] = True

                Request('post', '/board/post/add', json=json_data)
                self.refreshPostBoard()
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def viewPost(self, row=0):
        try:
            selectedRow = self.main.board_post_tableWidget.currentRow()
            if row != 0:
                selectedRow = row
            if selectedRow >= 0:
                printStatus(self.main, "불러오는 중...")
                post_data = self.origin_post_data[selectedRow]

                Request('get', f'/board/post/{post_data["uid"]}')

                printStatus(self.main)
                # 다이얼로그 생성
                dialog = QDialog(self.main)
                dialog.setWindowTitle(f'Post View')
                dialog.resize(400, 400)

                layout = QVBoxLayout()

                # HTML을 사용하여 디테일 표시
                details_html = self.main.style_html + f"""
                    <div class="post-details">
                        <table>
                            <tr>
                                <th>Item</th>
                                <th>Details</th>
                            </tr>
                            <tr>
                                <td><b>User Name:</b></td>
                                <td>{post_data['writerName']}</td>
                            </tr>
                            <tr>
                                <td><b>Post Title:</b></td>
                                <td>{post_data['title']}</td>
                            </tr>
                            <tr>
                                <td><b>DateTime:</b></td>
                                <td>{post_data['datetime']}</td>
                            </tr>
                            <tr>
                                <td><b>Post Text:</b></td>
                                <td class="detail-content">{post_data['text']}</td>
                            </tr>
                        </table>
                    </div>
                    """
                detail_label = QLabel(details_html)
                detail_label.setWordWrap(True)

                # QScrollArea를 사용하여 스크롤 가능하게 설정
                scroll_area = QScrollArea()
                scroll_area.setWidgetResizable(True)
                scroll_area.setWidget(detail_label)

                layout.addWidget(scroll_area, alignment=Qt.AlignHCenter)

                # 닫기 버튼 추가
                close_button = QPushButton('Close')
                close_button.clicked.connect(dialog.accept)
                layout.addWidget(close_button)

                ctrlw = QShortcut(QKeySequence("Ctrl+W"), dialog)
                ctrlw.activated.connect(dialog.accept)

                cmdw = QShortcut(QKeySequence("Ctrl+ㅈ"), dialog)
                cmdw.activated.connect(dialog.accept)

                dialog.setLayout(layout)
                printStatus(self.main)
                # 다이얼로그 실행
                dialog.exec_()
                self.refreshPostBoard()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def deletePost(self):
        try:
            selectedRow = self.main.board_post_tableWidget.currentRow()
            if selectedRow >= 0:
                post = self.origin_post_data[selectedRow]

                if post['writerUid'] == self.main.userUid or self.main.user == 'admin':
                    reply = QMessageBox.question(
                        self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        printStatus(self.main, "삭제 중...")
                        Request(
                            'delete', f'/board/post/{post["uid"]}')
                        self.refreshPostBoard()
                        printStatus(self.main)
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"작성자만 삭제할 수 있습니다")
                    return

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def editPost(self):
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
                    self.resize(400, 400)

                    # 컨테이너 위젯 생성
                    container_widget = QDialog()
                    layout = QVBoxLayout(container_widget)

                    # 게시물 제목 입력 필드
                    self.post_title_label = QLabel('Post Title:')
                    self.post_title_input = QLineEdit()
                    self.post_title_input.setText(self.post_data['title'])
                    layout.addWidget(self.post_title_label)
                    layout.addWidget(self.post_title_input)

                    # 게시물 내용 입력 필드
                    self.post_text_label = QLabel('Post Text:')
                    self.post_text_input = QTextEdit()
                    self.post_text_input.setText(self.post_data['text'])
                    layout.addWidget(self.post_text_label)
                    layout.addWidget(self.post_text_input)

                    # 확인 버튼 생성 및 클릭 시 동작 연결
                    self.submit_button = QPushButton('Edit')
                    self.submit_button.clicked.connect(self.submit)
                    layout.addWidget(self.submit_button)

                    # QScrollArea 설정
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    # 컨테이너 위젯을 스크롤 영역에 추가
                    scroll_area.setWidget(container_widget)

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

            selectedRow = self.main.board_post_tableWidget.currentRow()
            if selectedRow >= 0:
                post = self.origin_post_data[selectedRow]
                postUid = post['uid']
                if post['writerUid'] == self.main.userUid or self.main.user == 'admin':
                    prev_post_data = self.origin_post_data[selectedRow]

                    dialog = PostInputDialog(prev_post_data)
                    dialog.exec_()

                    if dialog.data:
                        post_data = dialog.data
                        post_data = list(post_data.values())

                        json_data = {
                            "writerUid": self.main.userUid,
                            "title": post_data[0],
                            "text": post_data[1],
                            "sendPushOver": False,
                        }
                        Request(
                            'put', f'/board/post/{postUid}', json=json_data)
                        self.refreshPostBoard()
                        QMessageBox.information(
                            self.main, "Information", f"게시물이 수정되었습니다")
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"비밀번호가 일치하지 않습니다")
                    printStatus(self.main)
                    return
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def matchButton(self):
        self.main.board_deleteversion_button.clicked.connect(
            self.deleteVersion)
        self.main.board_addversion_button.clicked.connect(self.addVersion)
        self.main.board_detailversion_button.clicked.connect(self.viewVersion)

        self.main.board_addbug_button.clicked.connect(self.addBug)
        self.main.board_deletebug_button.clicked.connect(self.deleteBug)
        self.main.board_detailbug_button.clicked.connect(self.viewBug)

        self.main.board_addpost_button.clicked.connect(self.addPost)
        self.main.board_detailpost_button.clicked.connect(self.viewPost)
        self.main.board_deletepost_button.clicked.connect(self.deletePost)
        self.main.board_editpost_button.clicked.connect(self.editPost)

        self.main.board_deleteversion_button.setToolTip("Ctrl+D")
        self.main.board_addversion_button.setToolTip("Ctrl+A")
        self.main.board_detailversion_button.setToolTip("Ctrl+V")
        self.main.board_addbug_button.setToolTip("Ctrl+A")
        self.main.board_deletebug_button.setToolTip("Ctrl+D")
        self.main.board_detailbug_button.setToolTip("Ctrl+V")
        self.main.board_addpost_button.setToolTip("Ctrl+A")
        self.main.board_detailpost_button.setToolTip("Ctrl+V")
        self.main.board_deletepost_button.setToolTip("Ctrl+D")
        self.main.board_editpost_button.setToolTip("Ctrl+E")

    def setBoardShortcut(self):
        self.updateShortcut(0)
        self.main.tabWidget_board.currentChanged.connect(self.updateShortcut)

    def updateShortcut(self, index):
        self.main.resetShortcuts()

        # 패치 노트 탭
        if index == 0:
            self.main.ctrld.activated.connect(self.deleteVersion)
            self.main.ctrlv.activated.connect(self.viewVersion)
            self.main.ctrla.activated.connect(self.addVersion)

            self.main.cmdd.activated.connect(self.deleteVersion)
            self.main.cmdv.activated.connect(self.viewVersion)
            self.main.cmda.activated.connect(self.addVersion)

        # 버그 리포트 탭
        if index == 1:
            self.main.ctrld.activated.connect(self.deleteBug)
            self.main.ctrlv.activated.connect(self.viewBug)
            self.main.ctrla.activated.connect(self.addBug)

            self.main.cmdd.activated.connect(self.deleteBug)
            self.main.cmdv.activated.connect(self.viewBug)
            self.main.cmda.activated.connect(self.addBug)

        # 자유 게시판 탭
        if index == 2:
            self.main.ctrld.activated.connect(self.deletePost)
            self.main.ctrlv.activated.connect(self.viewPost)
            self.main.ctrla.activated.connect(self.addPost)
            self.main.ctrle.activated.connect(self.editPost)

            self.main.cmdd.activated.connect(self.deletePost)
            self.main.cmdv.activated.connect(self.viewPost)
            self.main.cmda.activated.connect(self.addPost)
            self.main.cmde.activated.connect(self.editPost)
