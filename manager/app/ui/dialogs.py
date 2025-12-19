from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QCheckBox, QGridLayout, QButtonGroup,
    QRadioButton, QPushButton, QScrollArea, QMessageBox, QWidget, QFormLayout,
    QTextEdit, QDialogButtonBox, QComboBox, QLabel, QDateEdit, QLineEdit, QHBoxLayout,
    QFileDialog, QInputDialog, QApplication
)
from services.api import *
from services.logging import *
from PySide6.QtGui import QKeySequence, QFont, QShortcut
from datetime import datetime

class BaseDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 공통 단축키
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.reject)
        QShortcut(QKeySequence("Ctrl+ㅈ"), self).activated.connect(self.reject)

    def showEvent(self, event):
        super().showEvent(event)
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)
        self.center_to_mainwindow()
    
    def center_to_mainwindow(self):
        main = QApplication.activeWindow()

        # 혹시 자기 자신이 activeWindow인 경우 대비
        if main is self or main is None:
            main = self.parent()

        if main:
            geo = main.frameGeometry()
            self.move(
                geo.center() - self.rect().center()
            )
    
    def add_label(self, layout, title, content, multiline=False, monospace=False, readonly=True):
        # 제목 라벨
        layout.addWidget(QLabel(f"<b>{title}</b>"))

        # 내용 길이 및 줄 수에 따라 위젯 선택
        is_multiline = "\n" in content or len(content) > 50
        if multiline:
            is_multiline = True

        if is_multiline:
            widget = QTextEdit(content)
            widget.setPlainText(str(content))
            widget.setReadOnly(readonly)
            if monospace:
                f = QFont("Consolas")
                f.setStyleHint(QFont.Monospace)
                widget.setFont(f)
                widget.setLineWrapMode(QTextEdit.NoWrap)
        else:
            widget = QLineEdit(content)
            widget.setReadOnly(readonly)
            if monospace:
                f = QFont("Consolas")
                f.setStyleHint(QFont.Monospace)
                widget.setFont(f)

        layout.addWidget(widget)
        return widget
    
    def add_buttons(self, *buttons):
        button_layout = QHBoxLayout()
        for btn in buttons:
            button_layout.addWidget(btn)
        self.layout().addLayout(button_layout)


class DBInfoDialog(BaseDialog):
    def __init__(self, parent, DBdata):
        super().__init__(parent)
        self.DBdata = DBdata
        self.setWindowTitle(f"{DBdata['name']}_Info")
        self.resize(540, 600)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ======== 크롤 옵션 처리 ========
        crawlType = self.DBdata['crawlType']
        crawlOption_int = int(self.DBdata['crawlOption'])

        CountText = self.DBdata['dataInfo']
        if CountText['totalArticleCnt'] == '0' and CountText['totalReplyCnt'] == '0' and CountText['totalRereplyCnt'] == '0':
            CountText = self.DBdata['status']
        else:
            CountText = (
                f"Article: {CountText['totalArticleCnt']}\n"
                f"Reply: {CountText['totalReplyCnt']}\n"
                f"Rereply: {CountText['totalRereplyCnt']}"
            )

        crawlOption = {
            'Naver News': {1: '기사 + 댓글', 2: '기사 + 댓글/대댓글', 3: '기사', 4: '기사 + 댓글(추가 정보)'},
            'Naver Blog': {1: '블로그 본문', 2: '블로그 본문 + 댓글/대댓글'},
            'Naver Cafe': {1: '카페 본문', 2: '카페 본문 + 댓글/대댓글'},
            'YouTube': {1: '영상 정보 + 댓글/대댓글 (100개 제한)', 2: '영상 정보 + 댓글/대댓글(무제한)'},
            'ChinaDaily': {1: '기사 + 댓글'},
            'ChinaSina': {1: '기사', 2: '기사 + 댓글'},
            'dcinside': {1: '게시글', 2: '게시글 + 댓글'}
        }.get(crawlType, {}).get(crawlOption_int, crawlOption_int)

        # ======== 시간 처리 ========
        starttime = self.DBdata['startTime']
        endtime = self.DBdata['endTime']

        try:
            duration = datetime.strptime(
                endtime, "%Y-%m-%d %H:%M") - datetime.strptime(starttime, "%Y-%m-%d %H:%M")
        except:
            duration = str(datetime.now() - datetime.strptime(starttime, "%Y-%m-%d %H:%M"))[:-7]
            if endtime == '오류 중단':
                duration = '오류 중단'

        if endtime != '오류 중단':
            endtime = endtime.replace('/', '-') if endtime != '크롤링 중' else endtime

        # ======== 라벨 추가 ========
        self.add_label(layout, "Name", self.DBdata['name'])
        self.add_label(layout, "Size", self.DBdata['dbSize'])
        self.add_label(layout, "Type", self.DBdata['crawlType'])
        self.add_label(layout, "Keyword", self.DBdata['keyword'])
        self.add_label(layout, "Period",
            f"{datetime.strptime(self.DBdata['startDate'], '%Y%m%d').strftime('%Y.%m.%d')} ~ "
            f"{datetime.strptime(self.DBdata['endDate'], '%Y%m%d').strftime('%Y.%m.%d')}"
        )
        self.add_label(layout, "Option", str(crawlOption))
        self.add_label(layout, "Start", starttime)
        self.add_label(layout, "End", endtime)
        self.add_label(layout, "Duration", str(duration))
        self.add_label(layout, "Requester", self.DBdata['requester'])
        self.add_label(layout, "Result", CountText)

        # ======== 버튼 추가 ========
        ok_btn = QPushButton("확인")
        ok_btn.clicked.connect(self.accept)
        self.add_buttons(ok_btn)


class LogViewerDialog(BaseDialog):
    def __init__(self, parent, uid, log_content):
        super().__init__(parent)
        self.setWindowTitle(f"Log - {uid}")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        text_widget = QTextEdit(self)
        text_widget.setReadOnly(True)
        text_widget.setText(log_content)
        layout.addWidget(text_widget)

        close_button = QPushButton("닫기", self)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)


class SaveDbDialog(BaseDialog):
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
        buttons = (
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.button_box)

        self.setLayout(self.layout)

        # 신호 연결
        self.radio_custom.toggled.connect(self.toggle_date_input)
        self.radio_filter.toggled.connect(self.toggle_word_input)
        
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

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


class AddVersionDialog(BaseDialog):
    def __init__(self, version):
        super().__init__()
        self.version = version
        self.data = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Add Version')
        self.resize(480, 520)

        layout = QVBoxLayout(self)

        # Version Num (QLineEdit)
        layout.addWidget(QLabel('<b>Version Num:</b>'))
        self.version_num_input = QLineEdit()
        self.version_num_input.setText(self.version)
        layout.addWidget(self.version_num_input)

        # ChangeLog (monospace=True, editable)
        self.changelog_input = self.add_label(layout, "ChangeLog:", "", readonly=False)

        # Version Features (일반 글꼴, editable)
        self.version_features_input = self.add_label(layout, "Version Features:", "", readonly=False)

        # Detail (monospace=True, editable)
        self.detail_input = self.add_label(layout, "Detail:", "", readonly=False, multiline=True)

        # Submit
        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

    def submit(self):
        version_num = self.version_num_input.text()
        changelog = self.changelog_input.text() 
        version_features = self.version_features_input.text()  
        detail = self.detail_input.toPlainText()  

        self.data = [version_num, changelog, version_features, detail]

        QMessageBox.information(
            self, 'Input Data',
            f'Version Num: {version_num}\n'
            f'ChangeLog: {changelog}\n'
            f'Version Features: {version_features}\n'
            f'Detail: {detail}'
        )
        self.accept()


class AddBugDialog(BaseDialog):
    def __init__(self, main_window, version):
        super().__init__()
        self.main = main_window
        self.version = version
        self.data = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Bug Report')
        self.resize(480, 420)

        layout = QVBoxLayout(self)

        # User Name (QLineEdit)
        layout.addWidget(QLabel('<b>User Name:</b>'))
        self.user_input = QLineEdit()
        self.user_input.setText(getattr(self.main, "user", ""))
        layout.addWidget(self.user_input)

        # Bug Title (QLineEdit)
        layout.addWidget(QLabel('<b>Bug Title:</b>'))
        self.bug_title_input = QLineEdit()
        layout.addWidget(self.bug_title_input)

        # Bug Detail (BaseDialog.add_label → editable + monospace)
        self.bug_detail_input = self.add_label(
            layout,
            "Bug Detail:",
            "",
            readonly=False,
            multiline=True,
        )
        self.bug_detail_input.setPlaceholderText(
            '버그가 발생하는 상황과 조건, 어떤 버그가 일어나는지 자세히 작성해주세요\n오류 로그는 자동으로 전송됩니다'
        )

        # Submit
        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

    def submit(self):
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

        QMessageBox.information(
            self,
            'Input Data',
            f'User Name: {userName}\n'
            f'Version Num: {version_num}\n'
            f'Bug Title: {bug_title}\n'
            f'Bug Detail: {bug_detail}'
        )
        self.accept()


class AddPostDialog(BaseDialog):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.data = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Add Post')
        self.resize(480, 420)

        layout = QVBoxLayout(self)

        # Post Title (QLineEdit)
        layout.addWidget(QLabel('<b>Post Title:</b>'))
        self.post_title_input = QLineEdit()
        layout.addWidget(self.post_title_input)

        # Post Text (BaseDialog.add_label → editable + monospace)
        self.post_text_input = self.add_label(
            layout,
            "Post Text:",
            "",
            readonly=False,
            multiline=True,
        )

        # Post 버튼
        self.submit_button = QPushButton('Post')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

    def submit(self):
        post_title = self.post_title_input.text()
        post_text = self.post_text_input.toPlainText()

        self.data = {
            'post_title': post_title,
            'post_text': post_text,
        }

        QMessageBox.information(
            self,
            'New Post',
            f'Post Title: {post_title}\n'
            f'Post Text: {post_text}'
        )
        self.accept()


class ViewBugDialog(BaseDialog):
    def __init__(self, parent, bug_data: dict): 
        super().__init__(parent)
        self.setWindowTitle(f"Version {bug_data.get('versionName','')} Bug Details")
        self.resize(500, 600)

        self.bug_data = bug_data
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.add_label(layout, "User Name",   self.bug_data.get("writerName", ""))
        self.add_label(layout, "Version Num", self.bug_data.get("versionName", ""))
        self.add_label(layout, "Bug Title",   self.bug_data.get("bugTitle", ""))
        self.add_label(layout, "DateTime",    self.bug_data.get("datetime", ""))
        self.add_label(layout, "Bug Detail",  self.bug_data.get("bugText", ""), multiline=True)
        self.add_label(layout, "Program Log", self.bug_data.get("programLog", ""), multiline=True)


class ViewVersionDialog(BaseDialog):
    def __init__(self, parent, version_data, title=None):
        super().__init__(parent)
        self.version_data = version_data  # [num, date, changelog, features, detail]
        if not title:
            self.setWindowTitle(f"Version {version_data[0]} Details")
        else:
            self.setWindowTitle(title)
        self.resize(500, 500)
        self._build_ui()

    def _build_ui(self):
        self.layout = QVBoxLayout(self)

        self.add_label(self.layout, "Version Num",      self.version_data[0])
        self.add_label(self.layout, "Release Date",     self.version_data[1])
        self.add_label(self.layout, "ChangeLog",        self.version_data[2])
        self.add_label(self.layout, "Version Features", self.version_data[3])
        self.add_label(self.layout, "Detail",           self.version_data[4], multiline=True)
    
    def add_buttons(self, *buttons):
        button_layout = QHBoxLayout()
        for btn in buttons:
            button_layout.addWidget(btn)
        self.layout.addLayout(button_layout)


class ViewPostDialog(BaseDialog):
    def __init__(self, parent, post_data: dict):
        super().__init__(parent)
        self.post_data = post_data
        self.setWindowTitle("Post View")
        self.resize(500, 500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.add_label(layout, "User Name", self.post_data.get("writerName", ""))
        self.add_label(layout, "Post Title", self.post_data.get("title", ""))
        self.add_label(layout, "DateTime", self.post_data.get("datetime", ""))
        self.add_label(layout, "Post Text", self.post_data.get("text", ""), multiline=True)


class EditVersionDialog(BaseDialog):
    def __init__(self, version_data):
        super().__init__()
        self.version_data = version_data     # dict 형태
        self.data = None                     # 결과 저장
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Edit Version')
        self.resize(480, 520)

        # 컨테이너 위젯 생성
        container = QDialog()
        layout = QVBoxLayout(container)

        # Version Num
        layout.addWidget(QLabel('<b>Version Num:</b>'))
        self.version_num_input = QLineEdit()
        self.version_num_input.setText(self.version_data[0])
        layout.addWidget(self.version_num_input)

        # ChangeLog
        self.changelog_input = self.add_label(
            layout, "ChangeLog:", 
            self.version_data[2], 
            readonly=False
        )

        # Version Features
        self.version_features_input = self.add_label(
            layout, "Version Features:", 
            self.version_data[3], 
            readonly=False
        )

        # Detail (multiline)
        self.detail_input = self.add_label(
            layout, "Detail:", 
            self.version_data[4], 
            readonly=False, 
            multiline=True
        )

        # Submit button
        self.submit_button = QPushButton('Edit')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

        # ScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        # Final layout
        final_layout = QVBoxLayout()
        final_layout.addWidget(scroll)
        self.setLayout(final_layout)

        # TAB 키를 QTextEdit에서 빠져나가도록 설정
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def submit(self):
        version_num = self.version_num_input.text()
        changelog = self.changelog_input.text()
        version_features = self.version_features_input.text()
        detail = self.detail_input.toPlainText()

        # 반환 데이터
        self.data = {
            "versionName": version_num,
            "changeLog": changelog,
            "features": version_features,
            "details": detail
        }

        QMessageBox.information(
            self, "Updated",
            f"Version Num: {version_num}\n"
            f"ChangeLog: {changelog}\n"
            f"Features: {version_features}\n"
            f"Detail: {detail}"
        )

        self.accept()


class EditPostDialog(BaseDialog):
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
        
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

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


class StatAnalysisDialog(BaseDialog):
    """
    • 1차 : 분석 종류(체크박스) – 데이터 타입별로 구성
    • 2차 : 데이터 출처(콤보박스)
    ※ ‘혐오도 분석’은 모든 타입에 공통으로 제공.
    """

    def __init__(self, filename: str = ""):
        super().__init__()
        self.setWindowTitle("Select Options")
        self.filename = filename.lower()
        self._initializing = True  # 초기 세팅 중 플래그

        # ───────── 레이아웃 ─────────
        main_layout = QVBoxLayout(self)

        main_layout.addWidget(QLabel("Choose Data Type:"))
        self.combobox = QComboBox()
        self.combobox.addItems(["Naver News", "Naver Blog", "Naver Cafe", "Google YouTube"])
        self.combobox.currentIndexChanged.connect(self.update_checkboxes)
        main_layout.addWidget(self.combobox)

        self.checkbox_group: list[QCheckBox] = []

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

        self.update_checkboxes()  # 초기 체크박스 세팅
        self._initializing = False  # 초기 세팅 끝

    def update_checkboxes(self):
        for cb in self.checkbox_group:
            self.layout().removeWidget(cb)
            cb.deleteLater()
        self.checkbox_group.clear()

        # ── 초기화 중일 때만 콤보 자동 세팅
        if self._initializing:
            source_map = {
                "navernews": "Naver News",
                "naverblog": "Naver Blog",
                "navercafe": "Naver Cafe",
                "youtube": "Google YouTube"
            }
            for key, combo_label in source_map.items():
                if key in self.filename:
                    idx = self.combobox.findText(combo_label)
                    if idx != -1:
                        self.combobox.blockSignals(True)
                        self.combobox.setCurrentIndex(idx)
                        self.combobox.blockSignals(False)
                    break

        # ── 현재 콤보박스 값에 따라 체크박스 옵션 생성
        src = self.combobox.currentText()
        if src == "Naver News":
            specific = ["article 분석", "statistics 분석", "reply 분석", "rereply 분석"]
        elif src == "Naver Blog":
            specific = ["article 분석", "reply 분석"]
        elif src == "Naver Cafe":
            specific = ["article 분석", "reply 분석"]
        else:
            specific = ["article 분석", "reply 분석", "rereply 분석"]

        all_labels = specific + ["혐오도 분석"]

        # ── 기본 선택 우선순위 (초기 세팅 시에만 적용)
        default_label = None
        if self._initializing:
            priority = [
                ("hate", "혐오도 분석"),
                ("혐오", "혐오도 분석"),
                ("reply", "reply 분석"),
                ("rereply", "rereply 분석"),
                ("statistics", "statistics 분석"),
                ("article", "article 분석"),
            ]
            for key, label in priority:
                if key in self.filename:
                    default_label = label
                    break

        # ── 단일 선택 체크박스 로직
        def on_checkbox_clicked(clicked_cb):
            for cb in self.checkbox_group:
                if cb is not clicked_cb:
                    cb.setChecked(False)

        for label in all_labels:
            cb = QCheckBox(label)
            if self._initializing and label == default_label:
                cb.setChecked(True)
            cb.clicked.connect(lambda _, c=cb: on_checkbox_clicked(c))
            self.checkbox_group.append(cb)
            self.layout().insertWidget(self.layout().count() - 1, cb)


class WordcloudDialog(BaseDialog):
    def __init__(self, tokenfile_name):
        super().__init__()
        self.tokenfile_name = tokenfile_name
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        try:
            self.startdate = QDate.fromString(
                self.tokenfile_name.split('_')[3], "yyyyMMdd")
            self.enddate = QDate.fromString(
                self.tokenfile_name.split('_')[4], "yyyyMMdd")
        except:
            self.startdate = QDate.currentDate()
            self.enddate = QDate.currentDate()

        self.setWindowTitle('WORDCLOUD OPTION')
        self.resize(300, 250)  # 창 크기를 조정

        layout = QVBoxLayout()

        # 레이아웃의 마진과 간격 조정
        # (left, top, right, bottom) 여백 설정
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)  # 위젯 간 간격 설정

        # 각 입력 필드를 위한 QLabel 및 QDateEdit 생성
        self.startdate_label = QLabel('분석 시작 일자를 선택하세요: ')
        self.startdate_input = QDateEdit(calendarPopup=True)
        self.startdate_input.setDisplayFormat('yyyyMMdd')
        self.startdate_input.setDate(self.startdate)
        layout.addWidget(self.startdate_label)
        layout.addWidget(self.startdate_input)

        self.enddate_label = QLabel('분석 종료 일자를 선택하세요: ')
        self.enddate_input = QDateEdit(calendarPopup=True)
        self.enddate_input.setDisplayFormat('yyyyMMdd')
        self.enddate_input.setDate(self.enddate)
        layout.addWidget(self.enddate_label)
        layout.addWidget(self.enddate_input)

        # 새로운 드롭다운 메뉴(QComboBox) 생성
        self.period_option_label = QLabel('분석 주기 선택: ')
        layout.addWidget(self.period_option_label)

        self.period_option_menu = QComboBox()
        self.period_option_menu.addItem('전 기간 통합 분석')
        self.period_option_menu.addItem('1년 (Yearly)')
        self.period_option_menu.addItem('6개월 (Half-Yearly)')
        self.period_option_menu.addItem('3개월 (Quarterly)')
        self.period_option_menu.addItem('1개월 (Monthly)')
        self.period_option_menu.addItem('1주 (Weekly)')
        self.period_option_menu.addItem('1일 (Daily)')
        layout.addWidget(self.period_option_menu)

        self.topword_label = QLabel('최대 단어 개수를 입력하세요: ')
        self.topword_input = QLineEdit()
        self.topword_input.setText('200')  # 기본값 설정
        layout.addWidget(self.topword_label)
        layout.addWidget(self.topword_input)

        # 체크박스 생성
        self.except_checkbox_label = QLabel(
            '제외 단어 리스트를 추가하시겠습니까? ')
        layout.addWidget(self.except_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.except_yes_checkbox = QCheckBox('Yes')
        self.except_no_checkbox = QCheckBox('No')

        self.except_yes_checkbox.setChecked(
            False)  # Yes 체크박스 기본 체크
        self.except_no_checkbox.setChecked(
            True)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.except_yes_checkbox.toggled.connect(
            lambda: self.except_no_checkbox.setChecked(
                False) if self.except_yes_checkbox.isChecked() else None)
        self.except_no_checkbox.toggled.connect(
            lambda: self.except_yes_checkbox.setChecked(
                False) if self.except_no_checkbox.isChecked() else None)

        checkbox_layout.addWidget(self.except_yes_checkbox)
        checkbox_layout.addWidget(self.except_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 체크박스 생성
        self.eng_checkbox_label = QLabel('단어를 영문 변환하시겠습니까? ')
        layout.addWidget(self.eng_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.eng_yes_checkbox = QCheckBox('Yes')
        self.eng_no_checkbox = QCheckBox('No')

        self.eng_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
        self.eng_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.eng_yes_checkbox.toggled.connect(
            lambda: self.eng_no_checkbox.setChecked(
                False) if self.eng_yes_checkbox.isChecked() else None)
        self.eng_no_checkbox.toggled.connect(
            lambda: self.eng_yes_checkbox.setChecked(
                False) if self.eng_no_checkbox.isChecked() else None)

        checkbox_layout.addWidget(self.eng_yes_checkbox)
        checkbox_layout.addWidget(self.eng_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 확인 버튼 생성 및 클릭 시 동작 연결
        self.submit_button = QPushButton('분석 실행')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)
        
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def submit(self):
        period = self.period_option_menu.currentText()
        match period:
            case '전 기간 통합 분석':
                period = 'total'
            case '1년 (Yearly)':
                period = '1y'
            case '6개월 (Half-Yearly)':
                period = '6m'
            case '3개월 (Quarterly)':
                period = '3m'
            case '1개월 (Monthly)':
                period = '1m'
            case '1주 (Weekly)':
                period = '1w'
            case '1일 (Daily)':
                period = '1d'
        startdate = self.startdate_input.text()
        enddate = self.enddate_input.text()
        maxword = self.topword_input.text()
        except_yes_selected = self.except_yes_checkbox.isChecked()
        eng_yes_selected = self.eng_yes_checkbox.isChecked()

        self.data = {
            'startdate': startdate,
            'enddate': enddate,
            'period': period,
            'maxword': maxword,
            'except_yes_selected': except_yes_selected,
            'eng_yes_selected': eng_yes_selected
        }
        self.accept()


class SelectKemkimDialog(BaseDialog):
    def __init__(self, kimkem_file, rekimkem_file, interpret_kimkem):
        super().__init__()
        self.kimkem_file = kimkem_file
        self.rekimkem_file = rekimkem_file
        self.interpret_kimkem = interpret_kimkem
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        self.setWindowTitle('KEMKIM Start')
        self.resize(300, 100)  # 창 크기를 조정
        # 레이아웃 생성
        layout = QVBoxLayout()

        # 버튼 생성
        btn1 = QPushButton('새로운 KEMKIM 분석', self)
        btn2 = QPushButton('KEMKIM 그래프 조정', self)
        btn3 = QPushButton('KEMKIM 키워드 해석', self)

        # 버튼에 이벤트 연결
        btn1.clicked.connect(self.run_kimkem_file)
        btn2.clicked.connect(self.run_rekimkem_file)
        btn3.clicked.connect(self.run_interpretkimkem_file)

        # 버튼 배치를 위한 가로 레이아웃
        button_layout = QVBoxLayout()
        button_layout.addWidget(btn1)
        button_layout.addWidget(btn2)
        button_layout.addWidget(btn3)

        # 레이아웃에 버튼 레이아웃 추가
        layout.addLayout(button_layout)

        # 레이아웃을 다이얼로그에 설정
        self.setLayout(layout)
        
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def run_kimkem_file(self):
        self.accept()
        self.kimkem_file()

    def run_rekimkem_file(self):
        self.accept()
        self.rekimkem_file()

    def run_interpretkimkem_file(self):
        self.accept()
        self.interpret_kimkem()


class RunKemkimDialog(BaseDialog):
    def __init__(self, tokenfile_name):
        super().__init__()
        self.tokenfile_name = tokenfile_name
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        try:
            self.startdate = QDate.fromString(
                self.tokenfile_name.split('_')[3], "yyyyMMdd")
            self.enddate = QDate.fromString(
                self.tokenfile_name.split('_')[4], "yyyyMMdd")
        except:
            self.startdate = QDate.currentDate()
            self.enddate = QDate.currentDate()

        self.setWindowTitle('KEM KIM OPTION')
        self.resize(300, 250)  # 창 크기를 조정

        layout = QVBoxLayout()

        # 레이아웃의 마진과 간격 조정
        # (left, top, right, bottom) 여백 설정
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)  # 위젯 간 간격 설정

        # 각 입력 필드를 위한 QLabel 및 QDateEdit 생성
        self.startdate_label = QLabel('분석 시작 일자를 선택하세요: ')
        self.startdate_input = QDateEdit(calendarPopup=True)
        self.startdate_input.setDisplayFormat('yyyyMMdd')
        self.startdate_input.setDate(self.startdate)
        layout.addWidget(self.startdate_label)
        layout.addWidget(self.startdate_input)

        self.enddate_label = QLabel('분석 종료 일자를 선택하세요: ')
        self.enddate_input = QDateEdit(calendarPopup=True)
        self.enddate_input.setDisplayFormat('yyyyMMdd')
        self.enddate_input.setDate(self.enddate)
        layout.addWidget(self.enddate_label)
        layout.addWidget(self.enddate_input)

        # 새로운 드롭다운 메뉴(QComboBox) 생성
        self.period_option_label = QLabel('분석 주기 선택: ')
        layout.addWidget(self.period_option_label)

        self.period_option_menu = QComboBox()
        self.period_option_menu.addItem('1년 (Yearly)')
        self.period_option_menu.addItem('6개월 (Half-Yearly)')
        self.period_option_menu.addItem('3개월 (Quarterly)')
        self.period_option_menu.addItem('1개월 (Monthly)')
        self.period_option_menu.addItem('1주 (Weekly)')
        self.period_option_menu.addItem('1일 (Daily)')
        layout.addWidget(self.period_option_menu)

        self.topword_label = QLabel('상위 단어 개수를 입력하세요: ')
        self.topword_input = QLineEdit()
        self.topword_input.setText('500')  # 기본값 설정
        layout.addWidget(self.topword_label)
        layout.addWidget(self.topword_input)

        # Time Weight 입력 필드 생성 및 레이아웃에 추가
        self.weight_label = QLabel('시간 가중치(tw)를 입력하세요: ')
        self.weight_input = QLineEdit()
        self.weight_input.setText('0.1')  # 기본값 설정
        layout.addWidget(self.weight_label)
        layout.addWidget(self.weight_input)

        # Period Option Menu 선택 시 시간 가중치 변경 함수 연결
        self.period_option_menu.currentIndexChanged.connect(
            self.update_weight)

        self.wordcnt_label = QLabel('그래프 애니메이션에 띄울 단어의 개수를 입력하세요: ')
        self.wordcnt_input = QLineEdit()
        self.wordcnt_input.setText('10')  # 기본값 설정
        layout.addWidget(self.wordcnt_label)
        layout.addWidget(self.wordcnt_input)

        # 비일관 필터링 체크박스 생성
        self.filter_checkbox_label = QLabel('비일관 데이터를 필터링하시겠습니까? ')
        layout.addWidget(self.filter_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.filter_yes_checkbox = QCheckBox('Yes')
        self.filter_no_checkbox = QCheckBox('No')

        self.filter_yes_checkbox.setChecked(True)  # Yes 체크박스 기본 체크
        self.filter_no_checkbox.setChecked(False)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.filter_yes_checkbox.toggled.connect(
            lambda: self.filter_no_checkbox.setChecked(
                False) if self.filter_yes_checkbox.isChecked() else None)
        self.filter_no_checkbox.toggled.connect(
            lambda: self.filter_yes_checkbox.setChecked(
                False) if self.filter_no_checkbox.isChecked() else None)

        checkbox_layout.addWidget(self.filter_yes_checkbox)
        checkbox_layout.addWidget(self.filter_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 추적 데이터 기준 연도 설정
        self.trace_standard_label = QLabel('추적 데이터 계산 기준 연도를 설정하십시오 ')
        layout.addWidget(self.trace_standard_label)

        checkbox_layout = QHBoxLayout()
        self.trace_prevyear_checkbox = QCheckBox('직전 기간')
        self.trace_startyear_checkbox = QCheckBox('시작 기간')

        self.trace_prevyear_checkbox.setChecked(True)  # Yes 체크박스 기본 체크
        self.trace_startyear_checkbox.setChecked(
            False)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.trace_prevyear_checkbox.toggled.connect(
            lambda: self.trace_startyear_checkbox.setChecked(
                False) if self.trace_prevyear_checkbox.isChecked() else None)
        self.trace_startyear_checkbox.toggled.connect(
            lambda: self.trace_prevyear_checkbox.setChecked(
                False) if self.trace_startyear_checkbox.isChecked() else None)

        checkbox_layout.addWidget(self.trace_prevyear_checkbox)
        checkbox_layout.addWidget(self.trace_startyear_checkbox)
        layout.addLayout(checkbox_layout)

        # 애니메이션 체크박스 생성
        self.ani_checkbox_label = QLabel('추적 데이터를 시각화하시겠습니까? ')
        layout.addWidget(self.ani_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.ani_yes_checkbox = QCheckBox('Yes')
        self.ani_no_checkbox = QCheckBox('No')

        self.ani_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
        self.ani_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.ani_yes_checkbox.toggled.connect(
            lambda: self.ani_no_checkbox.setChecked(False) if self.ani_yes_checkbox.isChecked() else None)
        self.ani_no_checkbox.toggled.connect(
            lambda: self.ani_yes_checkbox.setChecked(False) if self.ani_no_checkbox.isChecked() else None)

        checkbox_layout.addWidget(self.ani_yes_checkbox)
        checkbox_layout.addWidget(self.ani_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 체크박스 생성
        self.except_checkbox_label = QLabel('제외 단어 리스트를 추가하시겠습니까? ')
        layout.addWidget(self.except_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.except_yes_checkbox = QCheckBox('Yes')
        self.except_no_checkbox = QCheckBox('No')

        self.except_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
        self.except_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.except_yes_checkbox.toggled.connect(
            lambda: self.except_no_checkbox.setChecked(
                False) if self.except_yes_checkbox.isChecked() else None)
        self.except_no_checkbox.toggled.connect(
            lambda: self.except_yes_checkbox.setChecked(
                False) if self.except_no_checkbox.isChecked() else None)

        checkbox_layout.addWidget(self.except_yes_checkbox)
        checkbox_layout.addWidget(self.except_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 드롭다운 메뉴(QComboBox) 생성
        self.dropdown_label = QLabel('분할 기준: ')
        layout.addWidget(self.dropdown_label)

        self.dropdown_menu = QComboBox()
        self.dropdown_menu.addItem('평균(Mean)')
        self.dropdown_menu.addItem('중앙값(Median)')
        self.dropdown_menu.addItem('직접 입력: 상위( )%')
        layout.addWidget(self.dropdown_menu)

        # 추가 입력창 (QLineEdit), 초기에는 숨김
        self.additional_input_label = QLabel('숫자를 입력하세요')
        self.additional_input = QLineEdit()
        self.additional_input.setPlaceholderText('입력')
        self.additional_input_label.hide()
        self.additional_input.hide()
        layout.addWidget(self.additional_input_label)
        layout.addWidget(self.additional_input)

        # 드롭다운 메뉴의 항목 변경 시 추가 입력창을 표시/숨김
        self.dropdown_menu.currentIndexChanged.connect(
            self.handle_dropdown_change)

        # 확인 버튼 생성 및 클릭 시 동작 연결
        self.submit_button = QPushButton('분석 실행')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)
        
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def handle_dropdown_change(self, index):
        # 특정 옵션이 선택되면 추가 입력창을 표시, 그렇지 않으면 숨김
        if self.dropdown_menu.currentText() == '직접 입력: 상위( )%':
            self.additional_input_label.show()
            self.additional_input.show()
        else:
            self.additional_input_label.hide()
            self.additional_input.hide()

    def update_weight(self):
        period = self.period_option_menu.currentText()
        if period == '1 (Yearly)':
            self.weight_input.setText('0.1')
        elif period == '6개월 (Half-Yearly)':
            self.weight_input.setText('0.05')
        elif period == '3개월 (Quarterly)':
            self.weight_input.setText('0.025')
        elif period == '1개월 (Monthly)':
            self.weight_input.setText('0.008')
        elif period == '1주 (Weekly)':
            self.weight_input.setText('0.002')
        elif period == '1일 (Daily)':
            self.weight_input.setText('0.0003')

    def submit(self):
        # 입력된 데이터를 확인하고 처리
        startdate = self.startdate_input.text()
        enddate = self.enddate_input.text()
        period = self.period_option_menu.currentText()
        match period:
            case '1년 (Yearly)':
                period = '1y'
            case '6개월 (Half-Yearly)':
                period = '6m'
            case '3개월 (Quarterly)':
                period = '3m'
            case '1개월 (Monthly)':
                period = '1m'
            case '1주 (Weekly)':
                period = '1w'
            case '1일 (Daily)':
                period = '1d'

        topword = self.topword_input.text()
        weight = self.weight_input.text()
        graph_wordcnt = self.wordcnt_input.text()
        trace_standard_selected = 'startyear' if self.trace_startyear_checkbox.isChecked() else 'prevyear'
        filter_yes_selected = self.filter_yes_checkbox.isChecked()
        ani_yes_selected = self.ani_yes_checkbox.isChecked()
        except_yes_selected = self.except_yes_checkbox.isChecked()
        split_option = self.dropdown_menu.currentText()
        split_custom = self.additional_input.text(
        ) if self.additional_input.isVisible() else None

        self.data = {
            'startDate': startdate,
            'endDate': enddate,
            'period': period,
            'topword': topword,
            'weight': weight,
            'graph_wordcnt': graph_wordcnt,
            'filter_yes_selected': filter_yes_selected,
            'trace_standard_selected': trace_standard_selected,
            'ani_yes_selected': ani_yes_selected,
            'except_yes_selected': except_yes_selected,
            'split_option': split_option,
            'split_custom': split_custom
        }
        self.accept()


class InterpretKemkimDialog(BaseDialog):
    def __init__(self, words):
        super().__init__()
        self.words = words
        self.selected_words = []
        self.initUI()

    def initUI(self):
        # 메인 레이아웃을 감쌀 위젯 생성
        container_widget = QDialog()
        main_layout = QVBoxLayout(container_widget)

        # 체크박스를 배치할 각 그룹 박스 생성
        groups = ["Strong Signal", "Weak Signal",
                  "Latent Signal", "Well-known Signal"]

        self.checkboxes = []
        self.select_all_checkboxes = {}
        for group_name, words in zip(groups, self.words):
            group_box = QGroupBox(group_name)
            group_layout = QVBoxLayout()

            # '모두 선택' 체크박스 추가
            select_all_checkbox = QCheckBox("모두 선택", group_box)
            select_all_checkbox.stateChanged.connect(
                self.create_select_all_handler(group_name))
            group_layout.addWidget(select_all_checkbox)
            self.select_all_checkboxes[group_name] = select_all_checkbox

            sorted_words = sorted(words)
            num_columns = 10  # 한 행에 최대 10개의 체크박스

            # 그리드 레이아웃 설정
            grid_layout = QGridLayout()
            grid_layout.setHorizontalSpacing(5)  # 수평 간격 설정
            grid_layout.setVerticalSpacing(10)  # 수직 간격 설정
            # 각 열이 동일한 비율로 확장되도록 설정
            for col in range(num_columns):
                grid_layout.setColumnStretch(col, 1)

            for i, word in enumerate(sorted_words):
                checkbox = QCheckBox(word, group_box)
                checkbox.stateChanged.connect(
                    self.create_individual_handler(group_name))
                self.checkboxes.append(checkbox)
                row = i // num_columns
                col = i % num_columns
                grid_layout.addWidget(checkbox, row, col)

            group_layout.addLayout(grid_layout)
            group_box.setLayout(group_layout)
            main_layout.addWidget(group_box)

        # 라디오 버튼 추가
        self.radio_button_group = QButtonGroup(self)

        radio_all = QRadioButton("모두 포함", self)
        radio_part = QRadioButton("개별 포함", self)

        self.radio_button_group.addButton(radio_all)
        self.radio_button_group.addButton(radio_part)

        main_layout.addWidget(radio_all)
        main_layout.addWidget(radio_part)

        # 기본값 설정 (첫 번째 옵션 선택)
        radio_all.setChecked(True)

        # 선택된 단어 출력 버튼 추가
        btn = QPushButton('포함 단어 결정', self)
        btn.clicked.connect(self.show_selected_words)
        main_layout.addWidget(btn)

        # QScrollArea 설정
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container_widget)  # 위젯을 스크롤 영역에 추가

        # 기존의 main_layout을 scroll_area에 추가
        final_layout = QVBoxLayout()
        final_layout.addWidget(scroll_area)

        # 창 설정
        self.setLayout(final_layout)
        self.setWindowTitle('크롤링 데이터 CSV 필터링 기준 단어를 선택하세요')
        self.resize(800, 600)
        self.show()
        
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def create_select_all_handler(self, group_name):
        def select_all_handler(state):

            try:
                checked = (state == Qt.CheckState.Checked.value)
            except AttributeError:
                checked = (state == Qt.Checked)

            group_checkboxes = [
                cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
            ]

            for checkbox in group_checkboxes:
                checkbox.blockSignals(True)
                checkbox.setChecked(checked)
                checkbox.blockSignals(False)

        return select_all_handler


    def create_individual_handler(self, group_name):
        def individual_handler():
            group_checkboxes = [
                cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
            ]
            all_checked = all(cb.isChecked()
                              for cb in group_checkboxes)
            if not all_checked:
                self.select_all_checkboxes[group_name].blockSignals(
                    True)
                self.select_all_checkboxes[group_name].setChecked(
                    False)
                self.select_all_checkboxes[group_name].blockSignals(
                    False)

        return individual_handler

    def show_selected_words(self):
        # 선택된 단어들을 그룹별로 분류하여 2차원 리스트로 저장
        selected_words_by_group = []

        groups = ["Strong Signal", "Weak Signal",
                  "Latent Signal", "Well-known Signal"]

        for group_name in groups:
            group_checkboxes = [
                cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
            ]
            selected_words = [cb.text()
                              for cb in group_checkboxes if cb.isChecked()]
            selected_words_by_group.append(selected_words)

        self.selected_words = selected_words_by_group
        self.selected_option = self.radio_button_group.checkedButton().text()

        # 선택된 단어를 메시지 박스로 출력
        selected_words_str = '\n'.join(
            f"{group}: {', '.join(words)}" for group, words in zip(groups, self.selected_words))
        QMessageBox.information(self, '선택한 단어', selected_words_str)
        self.accept()


class ModifyKemkimDialog(BaseDialog):
    def __init__(self, words):
        super().__init__()
        self.words = words
        self.selected_words = []
        self.initUI()

    def initUI(self):
        # 메인 레이아웃을 감쌀 위젯 생성
        container_widget = QDialog()
        main_layout = QVBoxLayout(container_widget)

        self.info_label = QLabel('제외할 키워드를 선택하세요\n')
        main_layout.addWidget(self.info_label)

        # 체크박스를 배치할 각 그룹 박스 생성
        groups = ["Strong Signal", "Weak Signal",
                  "Latent Signal", "Well-known Signal"]

        self.checkboxes = []
        self.select_all_checkboxes = {}
        for group_name, words in zip(groups, self.words):
            group_box = QGroupBox(group_name)
            group_layout = QVBoxLayout()

            # '모두 선택' 체크박스 추가
            select_all_checkbox = QCheckBox("모두 선택", self)
            select_all_checkbox.stateChanged.connect(
                self.create_select_all_handler(group_name))
            group_layout.addWidget(select_all_checkbox)
            self.select_all_checkboxes[group_name] = select_all_checkbox

            sorted_words = sorted(words)
            num_columns = 10  # 한 행에 최대 10개의 체크박스

            # 그리드 레이아웃 설정
            grid_layout = QGridLayout()
            grid_layout.setHorizontalSpacing(5)  # 수평 간격 설정
            grid_layout.setVerticalSpacing(10)  # 수직 간격 설정
            # 각 열이 동일한 비율로 확장되도록 설정
            for col in range(num_columns):
                grid_layout.setColumnStretch(col, 1)

            for i, word in enumerate(sorted_words):
                checkbox = QCheckBox(word, self)
                checkbox.stateChanged.connect(
                    self.create_individual_handler(group_name))
                self.checkboxes.append(checkbox)
                row = i // num_columns
                col = i % num_columns
                grid_layout.addWidget(checkbox, row, col)

            group_layout.addLayout(grid_layout)
            group_box.setLayout(group_layout)
            main_layout.addWidget(group_box)

        # 그리드 레이아웃 사용
        grid_layout = QGridLayout()

        # 첫 번째 열 (왼쪽)
        self.x_size_label = QLabel('그래프 가로 스케일: ')
        self.x_size_input = QLineEdit()
        self.x_size_input.setText('100')  # 기본값 설정
        grid_layout.addWidget(self.x_size_label, 0, 0)
        grid_layout.addWidget(self.x_size_input, 0, 1)

        self.y_size_label = QLabel('그래프 세로 스케일: ')
        self.y_size_input = QLineEdit()
        self.y_size_input.setText('100')  # 기본값 설정
        grid_layout.addWidget(self.y_size_label, 0, 2)
        grid_layout.addWidget(self.y_size_input, 0, 3)

        self.font_size_label = QLabel('그래프 폰트 크기: ')
        self.font_size_input = QLineEdit()
        self.font_size_input.setText('50')  # 기본값 설정
        grid_layout.addWidget(self.font_size_label, 1, 0)
        grid_layout.addWidget(self.font_size_input, 1, 1)

        # 두 번째 열 (오른쪽)
        self.dot_size_label = QLabel('그래프 점 크기: ')
        self.dot_size_input = QLineEdit()
        self.dot_size_input.setText('20')  # 기본값 설정
        grid_layout.addWidget(self.dot_size_label, 1, 2)
        grid_layout.addWidget(self.dot_size_input, 1, 3)

        self.label_size_label = QLabel('그래프 레이블 글자 크기: ')
        self.label_size_input = QLineEdit()
        self.label_size_input.setText('12')  # 기본값 설정
        grid_layout.addWidget(self.label_size_label, 2, 0)
        grid_layout.addWidget(self.label_size_input, 2, 1)

        self.grade_size_label = QLabel('그래프 눈금 글자 크기: ')
        self.grade_size_input = QLineEdit()
        self.grade_size_input.setText('10')  # 기본값 설정
        grid_layout.addWidget(self.grade_size_label, 2, 2)
        grid_layout.addWidget(self.grade_size_input, 2, 3)

        main_layout.addLayout(grid_layout)

        # 애니메이션 체크박스 생성
        self.eng_checkbox_label = QLabel('\n키워드를 영어로 변환하시겠습니까? ')
        main_layout.addWidget(self.eng_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.eng_no_checkbox = QCheckBox('변환 안함')
        self.eng_auto_checkbox = QCheckBox('자동 변환')
        self.eng_manual_checkbox = QCheckBox('수동 변환')

        # QButtonGroup을 사용하여 배타적 선택 적용
        self.checkbox_group = QButtonGroup(self)
        self.checkbox_group.addButton(self.eng_no_checkbox)
        self.checkbox_group.addButton(self.eng_auto_checkbox)
        self.checkbox_group.addButton(self.eng_manual_checkbox)

        # 배타적 선택 활성화 (라디오 버튼처럼 동작)
        self.checkbox_group.setExclusive(True)

        # 기본 선택 설정
        self.eng_no_checkbox.setChecked(True)  # "변환 안함" 기본 선택

        # 레이아웃에 추가
        checkbox_layout.addWidget(self.eng_no_checkbox)
        checkbox_layout.addWidget(self.eng_auto_checkbox)
        checkbox_layout.addWidget(self.eng_manual_checkbox)
        main_layout.addLayout(checkbox_layout)

        # 선택된 단어 출력 버튼 추가
        btn = QPushButton('그래프 설정 완료', self)
        btn.clicked.connect(self.show_selected_words)
        main_layout.addWidget(btn)

        # QScrollArea 설정
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container_widget)  # 위젯을 스크롤 영역에 추가

        # 기존의 main_layout을 scroll_area에 추가
        final_layout = QVBoxLayout()
        final_layout.addWidget(scroll_area)

        # 창 설정
        self.setLayout(final_layout)
        self.setWindowTitle('KEMKIM 그래프 조정')
        self.resize(800, 600)
        self.show()
        
        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def create_select_all_handler(self, group_name):
        def select_all_handler(state):

            try:
                checked = (state == Qt.CheckState.Checked.value)
            except AttributeError:
                checked = (state == Qt.Checked)

            group_checkboxes = [
                cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
            ]

            for checkbox in group_checkboxes:
                checkbox.blockSignals(True)
                checkbox.setChecked(checked)
                checkbox.blockSignals(False)

        return select_all_handler

    def create_individual_handler(self, group_name):
        def individual_handler():
            group_checkboxes = [
                cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
            ]
            all_checked = all(cb.isChecked()
                              for cb in group_checkboxes)
            if not all_checked:
                self.select_all_checkboxes[group_name].blockSignals(
                    True)
                self.select_all_checkboxes[group_name].setChecked(
                    False)
                self.select_all_checkboxes[group_name].blockSignals(
                    False)

        return individual_handler

    def show_selected_words(self):
        # 선택된 단어를 리스트에 추가
        self.selected_words = [cb.text()
                               for cb in self.checkboxes if cb.isChecked()]
        self.size_input = (self.x_size_input.text(), self.y_size_input.text(), self.font_size_input.text(
        ), self.dot_size_input.text(), self.label_size_input.text(), self.grade_size_input.text())
        self.eng_auto_checked = self.eng_auto_checkbox.isChecked()
        self.eng_manual_checked = self.eng_manual_checkbox.isChecked()
        self.eng_no_checked = self.eng_no_checkbox.isChecked()

        # 선택된 단어를 메시지 박스로 출력
        if self.selected_words == []:
            QMessageBox.information(self, '선택한 단어', '선택된 단어가 없습니다')
        else:
            QMessageBox.information(
                self, '선택한 단어', ', '.join(self.selected_words))
        self.accept()


class SelectTokenizeDialog(BaseDialog):
    def __init__(self, tokenize_file, modify_token, common_token):
        super().__init__()
        self.tokenize_file = tokenize_file
        self.modify_token = modify_token
        self.common_token = common_token
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        self.setWindowTitle('Tokenization')
        self.resize(300, 100)  # 창 크기를 조정
        # 레이아웃 생성
        layout = QVBoxLayout()

        # 버튼 생성
        btn1 = QPushButton('파일 토큰화', self)
        btn2 = QPushButton('토큰 파일 조정', self)
        btn3 = QPushButton('교집합 토큰 추출', self)

        # 버튼에 이벤트 연결
        btn1.clicked.connect(self.run_tokenize_file)
        btn2.clicked.connect(self.run_modify_token)
        btn3.clicked.connect(self.run_common_token)

        # 버튼 배치를 위한 가로 레이아웃
        button_layout = QVBoxLayout()
        button_layout.addWidget(btn1)
        button_layout.addWidget(btn2)
        button_layout.addWidget(btn3)

        # 레이아웃에 버튼 레이아웃 추가
        layout.addLayout(button_layout)

        # 레이아웃을 다이얼로그에 설정
        self.setLayout(layout)

    def run_tokenize_file(self):
        self.accept()
        self.tokenize_file()

    def run_modify_token(self):
        self.accept()
        self.modify_token()

    def run_common_token(self):
        self.accept()
        self.common_token()


class SelectColumnsDialog(BaseDialog):
    def __init__(self, column_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("열 선택")
        self.resize(400, 300)

        self.selected_columns = []
        self.checkboxes = []

        # ───────── 전체 레이아웃 ─────────
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("분석 대상 열을 선택하세요:"))

        # ───────── 스크롤 영역 ─────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # ───────── 체크박스 생성 ─────────
        for col in column_names:
            checkbox = QCheckBox(col)
            # ➊ 'text' 가 포함된 열은 기본 선택
            if "text" in col.lower():
                checkbox.setChecked(True)
            scroll_layout.addWidget(checkbox)
            self.checkboxes.append(checkbox)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # ───────── 확인 / 취소 버튼 ─────────
        button_layout = QHBoxLayout()
        ok_button = QPushButton("확인")
        cancel_button = QPushButton("취소")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    # 선택된 열 반환
    def get_selected_columns(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]


class SelectEtcAnalysisDialog(BaseDialog):
    def __init__(self, analyze_hate):
        super().__init__()
        self.analyze_hate = analyze_hate
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        layout = QVBoxLayout()

        # 기존 혐오도 분석 버튼
        hate_btn = QPushButton("혐오도 분석")
        hate_btn.clicked.connect(self.run_analyze_hate)
        layout.addWidget(hate_btn)

        self.setLayout(layout)

    def run_analyze_hate(self):
        self.accept()
        self.analyze_hate()
        
    def run_analyze_topic(self):
        self.accept()
        self.analyze_topic()


class EditHomeMemberDialog(BaseDialog):
    def __init__(self, data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("멤버 편집" if data else "멤버 추가")
        self.resize(400, 600)
        self.data = data or {}
        vbox = QVBoxLayout(self)

        def add_row(label: str, widget):
            vbox.addWidget(QLabel(label))
            vbox.addWidget(widget)

        # ----- 필드 -----
        self.in_name = QLineEdit(self.data.get("name", ""))
        self.in_pos = QLineEdit(self.data.get("position", ""))
        self.in_aff = QLineEdit(self.data.get("affiliation", ""))
        self.in_section = QLineEdit(self.data.get("section", ""))
        self.in_email = QLineEdit(self.data.get("email", ""))
        self.in_school = QTextEdit()
        self.in_school.setPlainText("\n".join(self.data.get("학력", [])))
        self.in_career = QTextEdit()
        self.in_career.setPlainText("\n".join(self.data.get("경력", [])))
        self.in_research = QTextEdit()
        self.in_research.setPlainText("\n".join(self.data.get("연구", [])))

        for lbl, wid in [
            ("이름", self.in_name), ("포지션", self.in_pos),
            ("소속", self.in_aff), ("구분(section)", self.in_section),
            ("이메일", self.in_email), ("학력(줄바꿈 구분)", self.in_school), ("경력(줄바꿈 구분)", self.in_career),
            ("연구(줄바꿈 구분)", self.in_research)
        ]:
            add_row(lbl, wid)

        # 이미지 선택
        img_row = QHBoxLayout()
        self.img_btn = QPushButton("프로필 이미지 선택")
        self.img_btn.clicked.connect(self.pick_image)
        img_row.addWidget(self.img_btn)
        vbox.addLayout(img_row)

        # OK / Cancel
        ok = QPushButton("저장")
        cancel = QPushButton("취소")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        vbox.addWidget(ok)
        vbox.addWidget(cancel)

        self.new_image_url = None

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            folder_name = f"members"
            object_name = self.data.get("name", "")
            if not object_name:
                object_name, ok = QInputDialog.getText(None, '파일명 입력', '성함을 입력하세요:', text='merged_file')
                if not ok or not object_name:
                    return
            try:
                url = upload_homepage_image(path, folder_name, object_name)
                self.new_image_url = url
                QMessageBox.information(self, "완료", "업로드 성공")
            except Exception as e:
                QMessageBox.warning(self, "실패", str(e))

    def get_payload(self):
        payload = {
            "name": self.in_name.text().strip(),
            "position": self.in_pos.text().strip(),
            "affiliation": self.in_aff.text().strip(),
            "section": self.in_section.text().strip(),
            "email": self.in_email.text().strip(),
            "학력": self.in_school.toPlainText().strip().splitlines(),
            "경력": self.in_career.toPlainText().strip().splitlines(),
            "연구": self.in_research.toPlainText().strip().splitlines(),
        }
        # image 필드 지정
        if self.new_image_url:
            payload["image"] = self.new_image_url
        elif self.data.get("image"):
            payload["image"] = self.data["image"]
        else:
            payload["image"] = ""  # 비어 있으면 서버가 기본 이미지 지정하게

        return payload


class EditHomeNewsDialog(BaseDialog):
    def __init__(self, data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("뉴스 편집" if data else "뉴스 추가")
        self.resize(400, 400)
        self.data = data or {}
        self.new_image_url = None

        vbox = QVBoxLayout(self)

        def add_row(label: str, widget):
            vbox.addWidget(QLabel(label))
            vbox.addWidget(widget)

        self.in_title = QLineEdit(self.data.get("title", ""))
        self.in_content = QTextEdit(self.data.get("content", ""))
        self.in_date = QLineEdit(self.data.get("date", ""))
        self.in_url = QLineEdit(self.data.get("url", ""))

        for lbl, wid in [
            ("제목", self.in_title),
            ("내용", self.in_content),
            ("날짜 (YYYY.MM 또는 YYYY.MM.DD)", self.in_date),
            ("원본 기사 URL", self.in_url),
        ]:
            add_row(lbl, wid)

        # 이미지 업로드
        self.img_btn = QPushButton("썸네일 이미지 선택")
        self.img_btn.clicked.connect(self.pick_image)
        vbox.addWidget(self.img_btn)

        # OK/Cancel
        ok = QPushButton("저장")
        cancel = QPushButton("취소")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        vbox.addWidget(ok)
        vbox.addWidget(cancel)

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            fname = f"news"
            try:
                self.new_image_url = upload_homepage_image(path, fname)
                QMessageBox.information(self, "완료", "업로드 성공")
            except Exception as e:
                QMessageBox.warning(self, "실패", str(e))

    def get_payload(self):
        payload = {
            "title": self.in_title.text().strip(),
            "content": self.in_content.toPlainText().strip(),
            "date": self.in_date.text().strip(),
            "url": self.in_url.text().strip(),
        }
        if self.new_image_url:
            payload["image"] = self.new_image_url
        elif self.data.get("image"):
            payload["image"] = self.data["image"]
        return payload


class EditHomePaperDialog(BaseDialog):
    def __init__(self, data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("논문 편집" if data else "논문 추가")
        self.resize(400, 450)
        self.data = data or {}

        vbox = QVBoxLayout(self)

        def add_row(label: str, widget):
            vbox.addWidget(QLabel(label))
            vbox.addWidget(widget)

        self.in_year = QLineEdit(str(self.data.get("year", "")))
        self.in_title = QLineEdit(self.data.get("title", ""))

        # authors: 콤마로 구분된 문자열로 보여주기
        raw_authors = self.data.get("authors", [])
        if isinstance(raw_authors, list):
            authors_text = ", ".join(raw_authors)
        else:
            authors_text = str(raw_authors)
        self.in_authors = QLineEdit(authors_text)

        self.in_conf = QLineEdit(self.data.get("conference", ""))
        self.in_link = QLineEdit(self.data.get("link", ""))

        for lbl, wid in [
            ("연도 (예: 2025)", self.in_year),
            ("제목", self.in_title),
            ("저자들 (쉼표로 구분)", self.in_authors),
            ("컨퍼런스/저널", self.in_conf),
            ("논문 링크(URL)", self.in_link),
        ]:
            add_row(lbl, wid)

        ok = QPushButton("저장")
        cancel = QPushButton("취소")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        vbox.addWidget(ok)
        vbox.addWidget(cancel)

    def get_payload(self) -> dict:
        try:
            year = int(self.in_year.text().strip())
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "연도는 숫자로 입력해주세요.")
            return {}

        # authors: 쉼표 기준으로 분리하고 공백 제거
        authors_raw = self.in_authors.text().strip()
        authors_list = [a.strip() for a in authors_raw.split(",") if a.strip()]

        payload = {
            "title": self.in_title.text().strip(),
            "authors": authors_list,
            "conference": self.in_conf.text().strip(),
            "link": self.in_link.text().strip(),
        }
        return {"year": year, "paper": payload}


class ViewHomePaperDialog(BaseDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("논문 정보")
        self.resize(500, 400)
        layout = QVBoxLayout(self)

        self.add_label(layout, "제목", data.get("title", ""))
        self.add_label(layout, "저자", ", ".join(data.get("authors", [])))
        self.add_label(layout, "컨퍼런스/저널", data.get("conference", ""))
        self.add_label(layout, "링크", data.get("link", ""))
        self.add_label(layout, "연도", str(data.get("year", "")))
    

class ViewHomeMemberDialog(BaseDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("멤버 정보")
        self.resize(500, 400)
        layout = QVBoxLayout(self)

        self.add_label(layout, "성명", data.get("name", ""))
        self.add_label(layout, "직책", data.get("position", ""))
        self.add_label(layout, "소속", data.get("affiliation", ""))
        self.add_label(layout, "이메일", data.get("email", ""))
        self.add_label(layout, "학력", "\n".join(data.get("학력", [])) if isinstance(data.get("학력", []), list) else str(data.get("학력", "")), multiline=True)
        self.add_label(layout, "경력", "\n".join(data.get("경력", [])) if isinstance(data.get("경력", []), list) else str(data.get("경력", "")), multiline=True)
        self.add_label(layout, "연구", "\n".join(data.get("연구", [])) if isinstance(data.get("연구", []), list) else str(data.get("연구", "")), multiline=True)


class ViewHomeNewsDialog(BaseDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("뉴스 정보")
        self.resize(500, 400)
        layout = QVBoxLayout(self)

        self.add_label(layout, "제목", data.get("title", ""))
        self.add_label(layout, "날짜", data.get("date", ""))
        self.add_label(layout, "URL", data.get("url", ""))        
        self.add_label(layout, "내용", data.get("content", ""), multiline=True)
