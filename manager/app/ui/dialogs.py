from PySide6.QtCore import Qt, QDate, QBuffer, QByteArray
from PySide6.QtGui import QPixmap, QImageReader
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGroupBox,
    QCheckBox,
    QGridLayout,
    QButtonGroup,
    QRadioButton,
    QPushButton,
    QScrollArea,
    QMessageBox,
    QWidget,
    QFormLayout,
    QTextEdit,
    QDialogButtonBox,
    QComboBox,
    QLabel,
    QDateEdit,
    QLineEdit,
    QHBoxLayout,
    QFileDialog,
    QInputDialog,
    QApplication,
    QDoubleSpinBox,
    QSpinBox,
)
from config import HOMEPAGE_EDIT_API
from services.api import upload_homepage_image
from PySide6.QtGui import QKeySequence, QFont, QShortcut, QFontMetrics, QPixmap
from datetime import datetime
from services.api import Request
from typing import Callable
import httpx
import requests
import uuid
import os


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
            self.move(geo.center() - self.rect().center())

    def add_label(
        self, layout, title, content, multiline=False, monospace=False, readonly=True
    ):
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

    def make_path_widgets(
        self,
        initial_path: str = "",
        on_selected: Callable[[str], None] | None = None,
        button_text: str = "경로 변경",
        dialog_title: str = "저장 경로 선택",
        placeholder: str = "선택되지 않음",
    ):
        """Create a path selection button and label.

        Returns: (button, label)
        If a path is chosen, the label is updated and `on_selected(path)` is called if provided.
        """
        btn = QPushButton(button_text)
        btn.setFixedWidth(100)
        label = QLabel(initial_path if initial_path else placeholder)
        label.setWordWrap(True)
        label.setStyleSheet(
            "color: #444; background: #f0f0f0; padding: 5px; border-radius: 3px;"
        )

        def _on_click():
            path = QFileDialog.getExistingDirectory(
                self, dialog_title, initial_path or ""
            )
            if path:
                label.setText(path)
                if on_selected:
                    try:
                        on_selected(path)
                    except Exception:
                        pass

        btn.clicked.connect(_on_click)
        return btn, label


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
        crawlType = self.DBdata["crawlType"]
        crawlOption_int = int(self.DBdata["crawlOption"])

        CountStat = self.DBdata["stat"]
        CountText = (
            f"Article: {CountStat['article']}\n"
            f"Reply: {CountStat['cmt']}\n"
            f"Rereply: {CountStat['reply']}"
        )

        crawlOption = {
            "Naver News": {
                1: "기사 + 댓글",
                2: "기사 + 댓글/대댓글",
                3: "기사",
                4: "기사 + 댓글(추가 정보)",
            },
            "Naver Blog": {1: "블로그 본문", 2: "블로그 본문 + 댓글/대댓글"},
            "Naver Cafe": {1: "카페 본문", 2: "카페 본문 + 댓글/대댓글"},
            "YouTube": {
                1: "영상 정보 + 댓글/대댓글 (100개 제한)",
                2: "영상 정보 + 댓글/대댓글(무제한)",
            },
            "ChinaDaily": {1: "기사 + 댓글"},
            "ChinaSina": {1: "기사", 2: "기사 + 댓글"},
            "dcinside": {1: "게시글", 2: "게시글 + 댓글"},
        }.get(crawlType, {}).get(crawlOption_int, crawlOption_int)

        # ======== 시간 처리 ========
        starttime = self.DBdata["startTime"]
        endtime = self.DBdata["endTime"]

        try:
            duration = datetime.strptime(endtime, "%Y-%m-%d %H:%M") - datetime.strptime(
                starttime, "%Y-%m-%d %H:%M"
            )
        except:
            duration = str(
                datetime.now() - datetime.strptime(starttime, "%Y-%m-%d %H:%M")
            )[:-7]
            if endtime == "오류 중단":
                duration = "오류 중단"

        if endtime != "오류 중단":
            endtime = endtime.replace("/", "-") if endtime != "크롤링 중" else endtime

        # ======== 라벨 추가 ========
        self.add_label(layout, "Name", self.DBdata["name"])
        self.add_label(layout, "Size", self.DBdata["dbSize"])
        self.add_label(layout, "Type", self.DBdata["crawlType"])
        self.add_label(layout, "Keyword", self.DBdata["keyword"])
        self.add_label(
            layout,
            "Period",
            f"{datetime.strptime(self.DBdata['startDate'], '%Y%m%d').strftime('%Y.%m.%d')} ~ "
            f"{datetime.strptime(self.DBdata['endDate'], '%Y%m%d').strftime('%Y.%m.%d')}",
        )
        self.add_label(layout, "Option", str(crawlOption))
        self.add_label(layout, "Start", starttime)
        self.add_label(layout, "End", endtime)
        self.add_label(layout, "Duration", str(duration))
        self.add_label(layout, "Requester", self.DBdata["requester"])
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
        self.setWindowTitle("Select Options")
        self.resize(250, 150)  # 초기 크기 설정

        self.incl_word_list = []
        self.excl_word_list = []
        self.include_all_option = False

        # 다이얼로그 레이아웃
        self.layout = QVBoxLayout()

        # 라디오 버튼 그룹 생성
        self.radio_all = QRadioButton("전체 기간")
        self.radio_custom = QRadioButton("기간 설정")
        self.radio_all.setChecked(True)  # 기본으로 "전체 저장" 선택

        self.layout.addWidget(QLabel("Choose Date Option:"))
        self.layout.addWidget(self.radio_all)
        self.layout.addWidget(self.radio_custom)

        # 기간 입력 폼 (처음엔 숨김)
        self.date_input_form = QWidget()
        self.date_input_form_layout = QFormLayout()

        self.start_date_input = QLineEdit()
        self.start_date_input.setPlaceholderText("YYYYMMDD")
        self.end_date_input = QLineEdit()
        self.end_date_input.setPlaceholderText("YYYYMMDD")

        self.date_input_form_layout.addRow("시작 날짜:", self.start_date_input)
        self.date_input_form_layout.addRow("종료 날짜:", self.end_date_input)
        self.date_input_form.setLayout(self.date_input_form_layout)
        self.date_input_form.setVisible(False)

        self.layout.addWidget(self.date_input_form)

        # 라디오 버튼 그룹 생성
        self.radio_nofliter = QRadioButton("필터링 안함")
        self.radio_filter = QRadioButton("필터링 설정")
        self.radio_nofliter.setChecked(True)  # 기본으로 "전체 저장" 선택

        self.layout.addWidget(QLabel("Choose Filter Option:"))
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
        self.incl_word_input.setPlaceholderText("ex) 사과, 바나나")
        self.excl_word_input = QLineEdit()
        self.excl_word_input.setPlaceholderText("ex) 당근, 오이")

        self.word_input_form_layout.addRow("포함 문자:", self.incl_word_input)
        self.word_input_form_layout.addRow("제외 문자:", self.excl_word_input)
        self.word_input_form.setLayout(self.word_input_form_layout)
        self.word_input_form.setVisible(False)

        # 포함 옵션 선택 (All 포함 vs Any 포함)
        self.include_option_group = QButtonGroup()
        self.include_all = QRadioButton("모두 포함/제외 (All)")
        self.include_any = QRadioButton("개별 포함/제외 (Any)")
        self.include_all.setToolTip("입력한 단어를 모두 포함/제외한 행을 선택")
        self.include_any.setToolTip("입력한 단어를 개별 포함/제외한 행을 선택")
        self.include_all.setChecked(True)  # 기본 선택: Any 포함

        self.word_input_form_layout.addRow(QLabel("포함 옵션:"))
        self.word_input_form_layout.addWidget(self.include_all)
        self.word_input_form_layout.addWidget(self.include_any)

        # 이름에 필터링 설정 포함할지
        self.radio_name = QRadioButton("포함 설정")
        self.radio_name.setToolTip("예) (+사과,바나나 _ -당근,오이 _all)")
        self.radio_noname = QRadioButton("포함 안함")
        self.radio_name.setChecked(True)  # 기본으로 "전체 저장" 선택

        self.word_input_form_layout.addRow(QLabel("폴더명에 필터링 항목:"))
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
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
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
                self.start_date_input.text(), date_format
            )
            self.end_date = QDate.fromString(self.end_date_input.text(), date_format)

            if not (self.start_date.isValid() and self.end_date.isValid()):
                QMessageBox.warning(self, "Wrong Form", "잘못된 날짜 형식입니다.")
                return  # 확인 동작을 취소함

            self.start_date = self.start_date.toString(date_format)
            self.end_date = self.end_date.toString(date_format)

        if self.radio_filter.isChecked():
            try:
                incl_word_str = self.incl_word_input.text()
                excl_word_str = self.excl_word_input.text()

                if incl_word_str == "":
                    self.incl_word_list = []
                else:
                    self.incl_word_list = incl_word_str.split(", ")

                if excl_word_str == "":
                    self.excl_word_list = []
                else:
                    self.excl_word_list = excl_word_str.split(", ")

                if self.include_all.isChecked():
                    self.include_all_option = True
                else:
                    self.include_all_option = False

                if self.radio_name.isChecked():
                    self.include = True

            except:
                QMessageBox.warning(self, "Wrong Input", "잘못된 필터링 입력입니다")
                return  # 확인 동작을 취소함

        super().accept()  # 정상적인 경우에만 다이얼로그를 종료함


class AddVersionDialog(BaseDialog):
    def __init__(self, version):
        super().__init__()
        self.version = version
        self.data = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Add Version")
        self.resize(480, 550)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Version Num:</b>"))
        self.version_num_input = QLineEdit()
        self.version_num_input.setText(self.version)
        layout.addWidget(self.version_num_input)

        self.changelog_input = self.add_label(layout, "ChangeLog:", "", readonly=False)

        self.version_features_input = self.add_label(
            layout, "Version Features:", "", readonly=False
        )

        self.detail_input = self.add_label(
            layout, "Detail:", "", readonly=False, multiline=True
        )

        self.full_update_checkbox = QCheckBox("설치 파일 업데이트")
        layout.addWidget(self.full_update_checkbox)

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

    def submit(self):
        version_num = self.version_num_input.text()
        changelog = self.changelog_input.text()
        version_features = self.version_features_input.text()
        detail = self.detail_input.toPlainText()
        is_full_update = self.full_update_checkbox.isChecked()

        self.data = {
            "versionName": version_num,
            "changeLog": changelog,
            "features": version_features,
            "details": detail,
            "fullUpdate": is_full_update,
        }

        QMessageBox.information(
            self,
            "Input Data",
            f"Version Num: {version_num}\n"
            f"ChangeLog: {changelog}\n"
            f"Version Features: {version_features}\n"
            f"Detail: {detail}\n"
            f"Full Update: {is_full_update}",
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
        self.setWindowTitle("Bug Report")
        self.resize(480, 420)

        layout = QVBoxLayout(self)

        # User Name (QLineEdit)
        layout.addWidget(QLabel("<b>User Name:</b>"))
        self.user_input = QLineEdit()
        self.user_input.setText(getattr(self.main, "user", ""))
        layout.addWidget(self.user_input)

        # Bug Title (QLineEdit)
        layout.addWidget(QLabel("<b>Bug Title:</b>"))
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
            "버그가 발생하는 상황과 조건, 어떤 버그가 일어나는지 자세히 작성해주세요\n오류 로그는 자동으로 전송됩니다"
        )

        # Submit
        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

    def submit(self):
        userName = self.user_input.text().strip()
        version_num = self.version
        bug_title = self.bug_title_input.text().strip()
        bug_detail = self.bug_detail_input.toPlainText().strip()

        if not bug_title:
            QMessageBox.warning(self, "입력 오류", "버그 제목을 입력해주세요.")
            self.bug_title_input.setFocus()
            return

        if not bug_detail:
            QMessageBox.warning(
                self, "입력 오류", "버그 상세 내용을 자세히 입력해주세요."
            )
            self.bug_detail_input.setFocus()
            return

        self.data = {
            "userName": userName,
            "versionName": version_num,
            "bugTitle": bug_title,
            "bugText": bug_detail,
        }

        QMessageBox.information(
            self, "제출 완료", "버그 리포트가 성공적으로 작성되었습니다."
        )

        self.accept()


class AddPostDialog(BaseDialog):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.data = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Add Post")
        self.resize(480, 420)

        layout = QVBoxLayout(self)

        # Post Title (QLineEdit)
        layout.addWidget(QLabel("<b>Post Title:</b>"))
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
        self.submit_button = QPushButton("Post")
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

    def submit(self):
        post_title = self.post_title_input.text()
        post_text = self.post_text_input.toPlainText()

        self.data = {
            "title": post_title,
            "text": post_text,
        }

        QMessageBox.information(
            self, "New Post", f"Post Title: {post_title}\nPost Text: {post_text}"
        )
        self.accept()


class ViewBugDialog(BaseDialog):
    def __init__(self, parent, bug_data: dict):
        super().__init__(parent)
        self.setWindowTitle(f"Version {bug_data.get('versionName', '')} Bug Details")
        self.resize(500, 600)

        self.bug_data = bug_data
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.add_label(layout, "User Name", self.bug_data.get("writerName", ""))
        self.add_label(layout, "Version Num", self.bug_data.get("versionName", ""))
        self.add_label(layout, "Bug Title", self.bug_data.get("bugTitle", ""))
        self.add_label(layout, "DateTime", self.bug_data.get("datetime", ""))
        self.add_label(
            layout, "Bug Detail", self.bug_data.get("bugText", ""), multiline=True
        )
        self.add_label(
            layout, "Program Log", self.bug_data.get("programLog", ""), multiline=True
        )


class ViewVersionDialog(BaseDialog):
    def __init__(self, parent, version_data, title=None):
        super().__init__(parent)
        self.version_data = version_data  # [num, date, changelog, features, detail]
        if not title:
            self.setWindowTitle(f"Version {version_data['versionName']} Details")
        else:
            self.setWindowTitle(title)
        self.resize(500, 500)
        self._build_ui()

    def _build_ui(self):
        self.layout = QVBoxLayout(self)

        self.add_label(self.layout, "Version Num", self.version_data["versionName"])
        self.add_label(self.layout, "Publisher", self.version_data["publisher"])
        self.add_label(self.layout, "Release Date", self.version_data["releaseDate"])
        self.add_label(self.layout, "ChangeLog", self.version_data["changeLog"])
        self.add_label(self.layout, "Version Features", self.version_data["features"])
        self.add_label(
            self.layout, "Detail", self.version_data["details"], multiline=True
        )
        is_full = self.version_data.get("fullUpdate", False)
        full_update_text = "N" if is_full else "Y"
        self.add_label(self.layout, "Fast Update", full_update_text)

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
        self.add_label(
            layout, "Post Text", self.post_data.get("text", ""), multiline=True
        )


class EditVersionDialog(BaseDialog):
    def __init__(self, version_data):
        super().__init__()
        self.version_data = version_data  # dict 형태
        self.data = None  # 결과 저장
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Edit Version")
        self.resize(480, 520)

        container = QDialog()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("<b>Version Num:</b>"))
        self.version_num_input = QLineEdit()
        self.version_num_input.setText(self.version_data["versionName"])
        layout.addWidget(self.version_num_input)

        self.changelog_input = self.add_label(
            layout, "ChangeLog:", self.version_data["changeLog"], readonly=False
        )

        self.version_features_input = self.add_label(
            layout, "Version Features:", self.version_data["features"], readonly=False
        )

        self.detail_input = self.add_label(
            layout,
            "Detail:",
            self.version_data["details"],
            readonly=False,
            multiline=True,
        )

        self.full_update_checkbox = QCheckBox("설치 파일 업데이트")
        is_full = self.version_data.get("fullUpdate", False)
        self.full_update_checkbox.setChecked(is_full)
        layout.addWidget(self.full_update_checkbox)
        # --------------------------------------

        self.submit_button = QPushButton("Edit")
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        final_layout = QVBoxLayout()
        final_layout.addWidget(scroll)
        self.setLayout(final_layout)

        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def submit(self):
        version_num = self.version_num_input.text()
        changelog = self.changelog_input.text()
        version_features = self.version_features_input.text()
        detail = self.detail_input.toPlainText()
        is_full_update = self.full_update_checkbox.isChecked()

        self.data = {
            "versionName": version_num,
            "changeLog": changelog,
            "features": version_features,
            "details": detail,
            "fullUpdate": is_full_update,
        }

        QMessageBox.information(
            self,
            "Updated",
            f"Version Num: {version_num}\n"
            f"ChangeLog: {changelog}\n"
            f"Features: {version_features}\n"
            f"Detail: {detail}\n"
            f"Full Update: {is_full_update}",
        )

        self.accept()


class EditPostDialog(BaseDialog):
    def __init__(self, post_data):
        super().__init__()
        self.post_data = post_data
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        self.setWindowTitle("Edit Post")
        self.resize(400, 400)

        # 컨테이너 위젯 생성
        container_widget = QDialog()
        layout = QVBoxLayout(container_widget)

        # 게시물 제목 입력 필드
        self.post_title_label = QLabel("Post Title:")
        self.post_title_input = QLineEdit()
        self.post_title_input.setText(self.post_data["title"])
        layout.addWidget(self.post_title_label)
        layout.addWidget(self.post_title_input)

        # 게시물 내용 입력 필드
        self.post_text_label = QLabel("Post Text:")
        self.post_text_input = QTextEdit()
        self.post_text_input.setText(self.post_data["text"])
        layout.addWidget(self.post_text_label)
        layout.addWidget(self.post_text_input)

        # 확인 버튼 생성 및 클릭 시 동작 연결
        self.submit_button = QPushButton("Edit")
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
            "title": post_title,
            "text": post_text,
        }

        QMessageBox.information(
            self, "Input Data", f"Post Title: {post_title}\nPost Text: {post_text}"
        )
        self.accept()


def load_pixmap_exif_safe(source) -> QPixmap:
    """파일 경로(str) 또는 바이트(bytes)로부터 QPixmap을 생성하되, 스마트폰 촬영
    사진에 흔한 EXIF Orientation 태그를 반영해 90/180/270도로 뒤집혀 보이는 문제를
    방지한다. QPixmap(path)/loadFromData()는 기본적으로 EXIF 방향을 무시한다."""
    reader = QImageReader()
    if isinstance(source, (bytes, bytearray)):
        buf = QBuffer()
        buf.setData(QByteArray(source))
        buf.open(QBuffer.OpenModeFlag.ReadOnly)
        reader.setDevice(buf)
    else:
        reader.setFileName(source)
    reader.setAutoTransform(True)
    return QPixmap.fromImage(reader.read())


def _load_thumbnail_pixmap(source: str, is_url: bool) -> QPixmap:
    """기존 사진(URL)은 네트워크로, 새로 고른 사진(로컬 경로)은 디스크에서 로드"""
    if is_url:
        try:
            resp = httpx.get(source, timeout=10)
            if resp.status_code == 200:
                return load_pixmap_exif_safe(resp.content)
        except Exception:
            pass
        return QPixmap()
    return load_pixmap_exif_safe(source)


def _build_photo_grid(grid_layout: QGridLayout, entries, on_remove: Callable | None = None):
    """entries: [(source, is_url), ...]. on_remove(index)가 주어지면 각 칸에 제거 버튼을 붙임(None이면 읽기 전용)."""
    while grid_layout.count():
        item = grid_layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

    cols = 3
    for i, (source, is_url) in enumerate(entries):
        cell = QWidget()
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(2, 2, 2, 2)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(120, 90)
        img_label.setStyleSheet(
            "border: 1px solid #dcdcdc; background-color: #f9f9f9;"
        )
        pixmap = _load_thumbnail_pixmap(source, is_url)
        if not pixmap.isNull():
            img_label.setPixmap(
                pixmap.scaled(
                    116,
                    86,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            img_label.setText("로드 실패")
        cell_layout.addWidget(img_label)

        if i == 0:
            badge = QLabel("대표 이미지")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet("color: #0d6efd; font-size: 10px; font-weight: bold;")
            cell_layout.addWidget(badge)

        if on_remove is not None:
            remove_btn = QPushButton("제거")
            remove_btn.setStyleSheet("font-size: 10px; padding: 2px;")
            remove_btn.clicked.connect(lambda _checked, idx=i: on_remove(idx))
            cell_layout.addWidget(remove_btn)

        grid_layout.addWidget(cell, i // cols, i % cols)


class EditGalleryPostDialog(BaseDialog):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.data = data or {}
        self.existing_photos = list(self.data.get("photos", []))
        self.removed_photos = []
        self.photo_paths = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle("갤러리 게시글 관리")
        self.resize(520, 680)
        layout = QVBoxLayout(self)

        def add_row(label: str, widget):
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)

        self.title_input = QLineEdit(self.data.get("title", ""))
        self.content_input = QTextEdit()
        self.content_input.setPlainText(self.data.get("content", ""))

        default_date = self.data.get("date") or datetime.now().strftime("%Y.%m.%d")
        self.date_input = QLineEdit(default_date)

        for lbl, wid in [
            ("제목", self.title_input),
            ("본문", self.content_input),
            ("날짜 (YYYY.MM.DD)", self.date_input),
        ]:
            add_row(lbl, wid)

        layout.addSpacing(10)
        layout.addWidget(
            QLabel("<b>사진 (첫 번째 사진이 대표 이미지로 사용됩니다):</b>")
        )

        self.photo_scroll = QScrollArea()
        self.photo_scroll.setWidgetResizable(True)
        self.photo_scroll.setFixedHeight(220)
        photo_container = QWidget()
        self.photo_grid = QGridLayout(photo_container)
        self.photo_scroll.setWidget(photo_container)
        layout.addWidget(self.photo_scroll)

        self.select_btn = QPushButton("이미지 추가 (여러 장 선택 가능)")
        self.select_btn.clicked.connect(self.selectImages)
        layout.addWidget(self.select_btn)

        self.refresh_photo_grid()

        layout.addStretch()

        self.submit_button = QPushButton("저장하기")
        self.submit_button.setStyleSheet(
            "background-color: #0d6efd; color: white; font-weight: bold; padding: 8px;"
        )
        self.submit_button.clicked.connect(self.accept)
        layout.addWidget(self.submit_button)

    def refresh_photo_grid(self):
        entries = [(url, True) for url in self.existing_photos] + [
            (p, False) for p in self.photo_paths
        ]
        _build_photo_grid(self.photo_grid, entries, on_remove=self.remove_photo_at)

    def remove_photo_at(self, index: int):
        if index < len(self.existing_photos):
            self.removed_photos.append(self.existing_photos.pop(index))
        else:
            self.photo_paths.pop(index - len(self.existing_photos))
        self.refresh_photo_grid()

    def selectImages(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "이미지 선택 (여러 장 가능)",
            "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.gif)",
        )
        if file_paths:
            self.photo_paths.extend(file_paths)
            self.refresh_photo_grid()

    def accept(self):
        if len(self.existing_photos) + len(self.photo_paths) < 1:
            QMessageBox.warning(self, "알림", "사진을 최소 1장 이상 등록해야 합니다.")
            return
        super().accept()

    def get_payload(self):
        return {
            "title": self.title_input.text().strip(),
            "content": self.content_input.toPlainText().strip(),
            "date": self.date_input.text().strip(),
        }


class MergeOptionDialog(BaseDialog):
    def __init__(self, parent=None, base_dir=""):
        super().__init__(parent)
        self.setWindowTitle("CSV 병합 설정")
        self.resize(520, 260)
        self.data = None

        self.csv_paths = []
        self.base_dir = base_dir or ""
        self.save_dir = ""
        self._default_dir = ""  # 기본 저장 경로(미선택일 때 표시용)

        layout = QVBoxLayout(self)

        # CSV 선택
        layout.addWidget(QLabel("CSV 파일 선택 (2개 이상):"))
        file_layout = QHBoxLayout()
        self.file_label = QLabel("선택된 파일: 0개")
        self.file_btn = QPushButton("CSV 선택")
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_btn)
        layout.addLayout(file_layout)
        self.file_btn.clicked.connect(self.select_csvs)

        # 병합 파일명
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setText("merged_file")
        form.addRow("병합 파일명", self.name_edit)
        layout.addLayout(form)

        # 저장 경로
        path_layout = QHBoxLayout()
        self.path_label = QLabel("저장 경로: 선택되지 않음")
        self.path_label.setMinimumWidth(1)  # elide 계산이 안정적으로 되도록
        self.path_btn = QPushButton("경로 선택")
        path_layout.addWidget(self.path_label, 1)  # 라벨이 남는 공간을 먹게(중요)
        path_layout.addWidget(self.path_btn)
        layout.addLayout(path_layout)
        self.path_btn.clicked.connect(self.select_path)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def elide_path(self, text: str):
        fm = QFontMetrics(self.path_label.font())
        elided = fm.elidedText(text, Qt.ElideMiddle, self.path_label.width())
        self.path_label.setText(elided)

    def _refresh_path_label(self):
        if self.save_dir:
            full_text = f"저장 경로: {self.save_dir}"
        elif self._default_dir:
            full_text = f"저장 경로: (미선택) 기본={self._default_dir}"
        else:
            full_text = "저장 경로: 선택되지 않음"
        self.elide_path(full_text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_path_label()

    def select_csvs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "CSV 파일 선택 (2개 이상)", self.base_dir, "CSV Files (*.csv)"
        )
        if paths:
            self.csv_paths = paths
            self.file_label.setText(f"선택된 파일: {len(paths)}개")
            self.base_dir = os.path.dirname(paths[0])  # 다음 선택 편의

            if not self.save_dir:
                self._default_dir = self.base_dir
                self._refresh_path_label()

    def select_path(self):
        path = QFileDialog.getExistingDirectory(self, "저장 경로 선택", self.base_dir)
        if path:
            self.save_dir = path
            self._default_dir = ""
            self._refresh_path_label()

    def accept(self):
        if not self.csv_paths:
            QMessageBox.warning(self, "입력 오류", "CSV 파일을 선택하세요.")
            return

        wrong = [p for p in self.csv_paths if not p.lower().endswith(".csv")]
        if wrong:
            QMessageBox.warning(
                self,
                "Wrong Format",
                f"{os.path.basename(wrong[0])}는 CSV 파일이 아닙니다",
            )
            return

        if len(self.csv_paths) < 2:
            QMessageBox.warning(
                self, "Wrong Selection", "2개 이상의 CSV 파일 선택이 필요합니다"
            )
            return

        mergedfilename = self.name_edit.text().strip()
        if not mergedfilename:
            QMessageBox.warning(self, "입력 오류", "병합 파일명을 입력하세요.")
            return

        save_dir = self.save_dir or os.path.dirname(self.csv_paths[0])

        self.data = {
            "selected_directory": self.csv_paths,
            "mergedfilename": mergedfilename,
            "save_dir": save_dir,
        }
        super().accept()


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
        self.combobox.addItems(
            ["Naver News", "Naver Blog", "Naver Cafe", "Google YouTube"]
        )
        self.combobox.currentIndexChanged.connect(self.update_checkboxes)
        main_layout.addWidget(self.combobox)

        self.checkbox_group: list[QCheckBox] = []

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
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
                "youtube": "Google YouTube",
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
                self.tokenfile_name.split("_")[3], "yyyyMMdd"
            )
            self.enddate = QDate.fromString(
                self.tokenfile_name.split("_")[4], "yyyyMMdd"
            )
        except:
            self.startdate = QDate.currentDate()
            self.enddate = QDate.currentDate()

        self.setWindowTitle("WORDCLOUD OPTION")
        self.resize(300, 250)  # 창 크기를 조정

        layout = QVBoxLayout()

        # 레이아웃의 마진과 간격 조정
        # (left, top, right, bottom) 여백 설정
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)  # 위젯 간 간격 설정

        # 각 입력 필드를 위한 QLabel 및 QDateEdit 생성
        self.startdate_label = QLabel("분석 시작 일자를 선택하세요: ")
        self.startdate_input = QDateEdit(calendarPopup=True)
        self.startdate_input.setDisplayFormat("yyyyMMdd")
        self.startdate_input.setDate(self.startdate)
        layout.addWidget(self.startdate_label)
        layout.addWidget(self.startdate_input)

        self.enddate_label = QLabel("분석 종료 일자를 선택하세요: ")
        self.enddate_input = QDateEdit(calendarPopup=True)
        self.enddate_input.setDisplayFormat("yyyyMMdd")
        self.enddate_input.setDate(self.enddate)
        layout.addWidget(self.enddate_label)
        layout.addWidget(self.enddate_input)

        # 새로운 드롭다운 메뉴(QComboBox) 생성
        self.period_option_label = QLabel("분석 주기 선택: ")
        layout.addWidget(self.period_option_label)

        self.period_option_menu = QComboBox()
        self.period_option_menu.addItem("전 기간 통합 분석")
        self.period_option_menu.addItem("1년 (Yearly)")
        self.period_option_menu.addItem("6개월 (Half-Yearly)")
        self.period_option_menu.addItem("3개월 (Quarterly)")
        self.period_option_menu.addItem("1개월 (Monthly)")
        self.period_option_menu.addItem("1주 (Weekly)")
        self.period_option_menu.addItem("1일 (Daily)")
        layout.addWidget(self.period_option_menu)

        self.topword_label = QLabel("최대 단어 개수를 입력하세요: ")
        self.topword_input = QLineEdit()
        self.topword_input.setText("200")  # 기본값 설정
        layout.addWidget(self.topword_label)
        layout.addWidget(self.topword_input)

        # 체크박스 생성
        self.except_checkbox_label = QLabel("제외 단어 리스트를 추가하시겠습니까? ")
        layout.addWidget(self.except_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.except_yes_checkbox = QCheckBox("Yes")
        self.except_no_checkbox = QCheckBox("No")

        self.except_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
        self.except_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.except_yes_checkbox.toggled.connect(
            lambda: (
                self.except_no_checkbox.setChecked(False)
                if self.except_yes_checkbox.isChecked()
                else None
            )
        )
        self.except_no_checkbox.toggled.connect(
            lambda: (
                self.except_yes_checkbox.setChecked(False)
                if self.except_no_checkbox.isChecked()
                else None
            )
        )

        checkbox_layout.addWidget(self.except_yes_checkbox)
        checkbox_layout.addWidget(self.except_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 체크박스 생성
        self.eng_checkbox_label = QLabel("단어를 영문 변환하시겠습니까? ")
        layout.addWidget(self.eng_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.eng_yes_checkbox = QCheckBox("Yes")
        self.eng_no_checkbox = QCheckBox("No")

        self.eng_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
        self.eng_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.eng_yes_checkbox.toggled.connect(
            lambda: (
                self.eng_no_checkbox.setChecked(False)
                if self.eng_yes_checkbox.isChecked()
                else None
            )
        )
        self.eng_no_checkbox.toggled.connect(
            lambda: (
                self.eng_yes_checkbox.setChecked(False)
                if self.eng_no_checkbox.isChecked()
                else None
            )
        )

        checkbox_layout.addWidget(self.eng_yes_checkbox)
        checkbox_layout.addWidget(self.eng_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 확인 버튼 생성 및 클릭 시 동작 연결
        self.submit_button = QPushButton("분석 실행")
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def submit(self):
        period = self.period_option_menu.currentText()
        match period:
            case "전 기간 통합 분석":
                period = "total"
            case "1년 (Yearly)":
                period = "1y"
            case "6개월 (Half-Yearly)":
                period = "6m"
            case "3개월 (Quarterly)":
                period = "3m"
            case "1개월 (Monthly)":
                period = "1m"
            case "1주 (Weekly)":
                period = "1w"
            case "1일 (Daily)":
                period = "1d"
        startdate = self.startdate_input.text()
        enddate = self.enddate_input.text()
        maxword = self.topword_input.text()
        except_yes_selected = self.except_yes_checkbox.isChecked()
        eng_yes_selected = self.eng_yes_checkbox.isChecked()

        self.data = {
            "startdate": startdate,
            "enddate": enddate,
            "period": period,
            "maxword": maxword,
            "except_yes_selected": except_yes_selected,
            "eng_yes_selected": eng_yes_selected,
        }
        self.accept()


class SelectKemkimDialog(BaseDialog):
    def __init__(self, kemkim_file, rekemkim_file, interpret_kemkim):
        super().__init__()
        self.kemkim_file = kemkim_file
        self.rekemkim_file = rekemkim_file
        self.interpret_kemkim = interpret_kemkim
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        self.setWindowTitle("KEMKIM")
        self.resize(300, 100)  # 창 크기를 조정
        # 레이아웃 생성
        layout = QVBoxLayout()

        # 버튼 생성
        btn1 = QPushButton("새로운 KEMKIM 분석", self)
        btn2 = QPushButton("KEMKIM 그래프 조정", self)
        btn3 = QPushButton("KEMKIM 키워드 해석", self)

        # 버튼에 이벤트 연결
        btn1.clicked.connect(self.run_kemkim_file)
        btn2.clicked.connect(self.run_rekemkim_file)
        btn3.clicked.connect(self.run_interpretkemkim_file)

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

    def run_kemkim_file(self):
        self.accept()
        self.kemkim_file()

    def run_rekemkim_file(self):
        self.accept()
        self.rekemkim_file()

    def run_interpretkemkim_file(self):
        self.accept()
        self.interpret_kemkim()


class RunKemkimDialog(BaseDialog):
    def __init__(self, tokenfile_name):
        super().__init__()
        self.tokenfile_name = tokenfile_name
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        try:
            self.startdate = QDate.fromString(
                self.tokenfile_name.split("_")[3], "yyyyMMdd"
            )
            self.enddate = QDate.fromString(
                self.tokenfile_name.split("_")[4], "yyyyMMdd"
            )
        except:
            self.startdate = QDate.currentDate()
            self.enddate = QDate.currentDate()

        self.setWindowTitle("KEM KIM OPTION")
        self.resize(300, 250)  # 창 크기를 조정

        layout = QVBoxLayout()

        # 레이아웃의 마진과 간격 조정
        # (left, top, right, bottom) 여백 설정
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)  # 위젯 간 간격 설정

        # 각 입력 필드를 위한 QLabel 및 QDateEdit 생성
        self.startdate_label = QLabel("분석 시작 일자를 선택하세요: ")
        self.startdate_input = QDateEdit(calendarPopup=True)
        self.startdate_input.setDisplayFormat("yyyyMMdd")
        self.startdate_input.setDate(self.startdate)
        layout.addWidget(self.startdate_label)
        layout.addWidget(self.startdate_input)

        self.enddate_label = QLabel("분석 종료 일자를 선택하세요: ")
        self.enddate_input = QDateEdit(calendarPopup=True)
        self.enddate_input.setDisplayFormat("yyyyMMdd")
        self.enddate_input.setDate(self.enddate)
        layout.addWidget(self.enddate_label)
        layout.addWidget(self.enddate_input)

        # 새로운 드롭다운 메뉴(QComboBox) 생성
        self.period_option_label = QLabel("분석 주기 선택: ")
        layout.addWidget(self.period_option_label)

        self.period_option_menu = QComboBox()
        self.period_option_menu.addItem("1년 (Yearly)")
        self.period_option_menu.addItem("6개월 (Half-Yearly)")
        self.period_option_menu.addItem("3개월 (Quarterly)")
        self.period_option_menu.addItem("1개월 (Monthly)")
        self.period_option_menu.addItem("1주 (Weekly)")
        self.period_option_menu.addItem("1일 (Daily)")
        layout.addWidget(self.period_option_menu)

        self.topword_label = QLabel("상위 단어 개수를 입력하세요: ")
        self.topword_input = QLineEdit()
        self.topword_input.setText("500")  # 기본값 설정
        layout.addWidget(self.topword_label)
        layout.addWidget(self.topword_input)

        # Time Weight 입력 필드 생성 및 레이아웃에 추가
        self.weight_label = QLabel("시간 가중치(tw)를 입력하세요: ")
        self.weight_input = QLineEdit()
        self.weight_input.setText("0.1")  # 기본값 설정
        layout.addWidget(self.weight_label)
        layout.addWidget(self.weight_input)

        # Period Option Menu 선택 시 시간 가중치 변경 함수 연결
        self.period_option_menu.currentIndexChanged.connect(self.update_weight)

        self.wordcnt_label = QLabel(
            "그래프 애니메이션에 띄울 단어의 개수를 입력하세요: "
        )
        self.wordcnt_input = QLineEdit()
        self.wordcnt_input.setText("10")  # 기본값 설정
        layout.addWidget(self.wordcnt_label)
        layout.addWidget(self.wordcnt_input)

        # 비일관 필터링 체크박스 생성
        self.filter_checkbox_label = QLabel("비일관 데이터를 필터링하시겠습니까? ")
        layout.addWidget(self.filter_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.filter_yes_checkbox = QCheckBox("Yes")
        self.filter_no_checkbox = QCheckBox("No")

        self.filter_yes_checkbox.setChecked(True)  # Yes 체크박스 기본 체크
        self.filter_no_checkbox.setChecked(False)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.filter_yes_checkbox.toggled.connect(
            lambda: (
                self.filter_no_checkbox.setChecked(False)
                if self.filter_yes_checkbox.isChecked()
                else None
            )
        )
        self.filter_no_checkbox.toggled.connect(
            lambda: (
                self.filter_yes_checkbox.setChecked(False)
                if self.filter_no_checkbox.isChecked()
                else None
            )
        )

        checkbox_layout.addWidget(self.filter_yes_checkbox)
        checkbox_layout.addWidget(self.filter_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 추적 데이터 기준 연도 설정
        self.trace_standard_label = QLabel("추적 데이터 계산 기준 연도를 설정하십시오 ")
        layout.addWidget(self.trace_standard_label)

        checkbox_layout = QHBoxLayout()
        self.trace_prevyear_checkbox = QCheckBox("직전 기간")
        self.trace_startyear_checkbox = QCheckBox("시작 기간")

        self.trace_prevyear_checkbox.setChecked(True)  # Yes 체크박스 기본 체크
        self.trace_startyear_checkbox.setChecked(False)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.trace_prevyear_checkbox.toggled.connect(
            lambda: (
                self.trace_startyear_checkbox.setChecked(False)
                if self.trace_prevyear_checkbox.isChecked()
                else None
            )
        )
        self.trace_startyear_checkbox.toggled.connect(
            lambda: (
                self.trace_prevyear_checkbox.setChecked(False)
                if self.trace_startyear_checkbox.isChecked()
                else None
            )
        )

        checkbox_layout.addWidget(self.trace_prevyear_checkbox)
        checkbox_layout.addWidget(self.trace_startyear_checkbox)
        layout.addLayout(checkbox_layout)

        # 애니메이션 체크박스 생성
        self.ani_checkbox_label = QLabel("추적 데이터를 시각화하시겠습니까? ")
        layout.addWidget(self.ani_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.ani_yes_checkbox = QCheckBox("Yes")
        self.ani_no_checkbox = QCheckBox("No")

        self.ani_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
        self.ani_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.ani_yes_checkbox.toggled.connect(
            lambda: (
                self.ani_no_checkbox.setChecked(False)
                if self.ani_yes_checkbox.isChecked()
                else None
            )
        )
        self.ani_no_checkbox.toggled.connect(
            lambda: (
                self.ani_yes_checkbox.setChecked(False)
                if self.ani_no_checkbox.isChecked()
                else None
            )
        )

        checkbox_layout.addWidget(self.ani_yes_checkbox)
        checkbox_layout.addWidget(self.ani_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 체크박스 생성
        self.except_checkbox_label = QLabel("제외 단어 리스트를 추가하시겠습니까? ")
        layout.addWidget(self.except_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.except_yes_checkbox = QCheckBox("Yes")
        self.except_no_checkbox = QCheckBox("No")

        self.except_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
        self.except_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

        # 서로 배타적으로 선택되도록 설정
        self.except_yes_checkbox.toggled.connect(
            lambda: (
                self.except_no_checkbox.setChecked(False)
                if self.except_yes_checkbox.isChecked()
                else None
            )
        )
        self.except_no_checkbox.toggled.connect(
            lambda: (
                self.except_yes_checkbox.setChecked(False)
                if self.except_no_checkbox.isChecked()
                else None
            )
        )

        checkbox_layout.addWidget(self.except_yes_checkbox)
        checkbox_layout.addWidget(self.except_no_checkbox)
        layout.addLayout(checkbox_layout)

        # 드롭다운 메뉴(QComboBox) 생성
        self.dropdown_label = QLabel("분할 기준: ")
        layout.addWidget(self.dropdown_label)

        self.dropdown_menu = QComboBox()
        self.dropdown_menu.addItem("평균(Mean)")
        self.dropdown_menu.addItem("중앙값(Median)")
        self.dropdown_menu.addItem("직접 입력: 상위( )%")
        layout.addWidget(self.dropdown_menu)

        # 추가 입력창 (QLineEdit), 초기에는 숨김
        self.additional_input_label = QLabel("숫자를 입력하세요")
        self.additional_input = QLineEdit()
        self.additional_input.setPlaceholderText("입력")
        self.additional_input_label.hide()
        self.additional_input.hide()
        layout.addWidget(self.additional_input_label)
        layout.addWidget(self.additional_input)

        # 드롭다운 메뉴의 항목 변경 시 추가 입력창을 표시/숨김
        self.dropdown_menu.currentIndexChanged.connect(self.handle_dropdown_change)

        # 확인 버튼 생성 및 클릭 시 동작 연결
        self.submit_button = QPushButton("분석 실행")
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def handle_dropdown_change(self, index):
        # 특정 옵션이 선택되면 추가 입력창을 표시, 그렇지 않으면 숨김
        if self.dropdown_menu.currentText() == "직접 입력: 상위( )%":
            self.additional_input_label.show()
            self.additional_input.show()
        else:
            self.additional_input_label.hide()
            self.additional_input.hide()

    def update_weight(self):
        period = self.period_option_menu.currentText()
        if period == "1 (Yearly)":
            self.weight_input.setText("0.1")
        elif period == "6개월 (Half-Yearly)":
            self.weight_input.setText("0.05")
        elif period == "3개월 (Quarterly)":
            self.weight_input.setText("0.025")
        elif period == "1개월 (Monthly)":
            self.weight_input.setText("0.008")
        elif period == "1주 (Weekly)":
            self.weight_input.setText("0.002")
        elif period == "1일 (Daily)":
            self.weight_input.setText("0.0003")

    def submit(self):
        # 입력된 데이터를 확인하고 처리
        startdate = self.startdate_input.text()
        enddate = self.enddate_input.text()
        period = self.period_option_menu.currentText()
        match period:
            case "1년 (Yearly)":
                period = "1y"
            case "6개월 (Half-Yearly)":
                period = "6m"
            case "3개월 (Quarterly)":
                period = "3m"
            case "1개월 (Monthly)":
                period = "1m"
            case "1주 (Weekly)":
                period = "1w"
            case "1일 (Daily)":
                period = "1d"

        topword = self.topword_input.text()
        weight = self.weight_input.text()
        graph_wordcnt = self.wordcnt_input.text()
        trace_standard_selected = (
            "startyear" if self.trace_startyear_checkbox.isChecked() else "prevyear"
        )
        filter_yes_selected = self.filter_yes_checkbox.isChecked()
        ani_yes_selected = self.ani_yes_checkbox.isChecked()
        except_yes_selected = self.except_yes_checkbox.isChecked()
        split_option = self.dropdown_menu.currentText()
        split_custom = (
            self.additional_input.text() if self.additional_input.isVisible() else None
        )

        self.data = {
            "startDate": startdate,
            "endDate": enddate,
            "period": period,
            "topword": topword,
            "weight": weight,
            "graph_wordcnt": graph_wordcnt,
            "filter_yes_selected": filter_yes_selected,
            "trace_standard_selected": trace_standard_selected,
            "ani_yes_selected": ani_yes_selected,
            "except_yes_selected": except_yes_selected,
            "split_option": split_option,
            "split_custom": split_custom,
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
        groups = ["Strong Signal", "Weak Signal", "Latent Signal", "Well-known Signal"]

        self.checkboxes = []
        self.select_all_checkboxes = {}
        for group_name, words in zip(groups, self.words):
            group_box = QGroupBox(group_name)
            group_layout = QVBoxLayout()

            # '모두 선택' 체크박스 추가
            select_all_checkbox = QCheckBox("모두 선택", group_box)
            select_all_checkbox.stateChanged.connect(
                self.create_select_all_handler(group_name)
            )
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
                    self.create_individual_handler(group_name)
                )
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
        btn = QPushButton("포함 단어 결정", self)
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
        self.setWindowTitle("크롤링 데이터 CSV 필터링 기준 단어를 선택하세요")
        self.resize(800, 600)
        self.show()

        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def create_select_all_handler(self, group_name):
        def select_all_handler(state):

            try:
                checked = state == Qt.CheckState.Checked.value
            except AttributeError:
                checked = state == Qt.Checked

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
            all_checked = all(cb.isChecked() for cb in group_checkboxes)
            if not all_checked:
                self.select_all_checkboxes[group_name].blockSignals(True)
                self.select_all_checkboxes[group_name].setChecked(False)
                self.select_all_checkboxes[group_name].blockSignals(False)

        return individual_handler

    def show_selected_words(self):
        # 선택된 단어들을 그룹별로 분류하여 2차원 리스트로 저장
        selected_words_by_group = []

        groups = ["Strong Signal", "Weak Signal", "Latent Signal", "Well-known Signal"]

        for group_name in groups:
            group_checkboxes = [
                cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
            ]
            selected_words = [cb.text() for cb in group_checkboxes if cb.isChecked()]
            selected_words_by_group.append(selected_words)

        self.selected_words = selected_words_by_group
        self.selected_option = self.radio_button_group.checkedButton().text()

        # 선택된 단어를 메시지 박스로 출력
        selected_words_str = "\n".join(
            f"{group}: {', '.join(words)}"
            for group, words in zip(groups, self.selected_words)
        )
        QMessageBox.information(self, "선택한 단어", selected_words_str)
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

        self.info_label = QLabel("제외할 키워드를 선택하세요\n")
        main_layout.addWidget(self.info_label)

        # 체크박스를 배치할 각 그룹 박스 생성
        groups = ["Strong Signal", "Weak Signal", "Latent Signal", "Well-known Signal"]

        self.checkboxes = []
        self.select_all_checkboxes = {}
        for group_name, words in zip(groups, self.words):
            group_box = QGroupBox(group_name)
            group_layout = QVBoxLayout()

            # '모두 선택' 체크박스 추가
            select_all_checkbox = QCheckBox("모두 선택", self)
            select_all_checkbox.stateChanged.connect(
                self.create_select_all_handler(group_name)
            )
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
                    self.create_individual_handler(group_name)
                )
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
        self.x_size_label = QLabel("그래프 가로 스케일: ")
        self.x_size_input = QLineEdit()
        self.x_size_input.setText("100")  # 기본값 설정
        grid_layout.addWidget(self.x_size_label, 0, 0)
        grid_layout.addWidget(self.x_size_input, 0, 1)

        self.y_size_label = QLabel("그래프 세로 스케일: ")
        self.y_size_input = QLineEdit()
        self.y_size_input.setText("100")  # 기본값 설정
        grid_layout.addWidget(self.y_size_label, 0, 2)
        grid_layout.addWidget(self.y_size_input, 0, 3)

        self.font_size_label = QLabel("그래프 폰트 크기: ")
        self.font_size_input = QLineEdit()
        self.font_size_input.setText("50")  # 기본값 설정
        grid_layout.addWidget(self.font_size_label, 1, 0)
        grid_layout.addWidget(self.font_size_input, 1, 1)

        # 두 번째 열 (오른쪽)
        self.dot_size_label = QLabel("그래프 점 크기: ")
        self.dot_size_input = QLineEdit()
        self.dot_size_input.setText("20")  # 기본값 설정
        grid_layout.addWidget(self.dot_size_label, 1, 2)
        grid_layout.addWidget(self.dot_size_input, 1, 3)

        self.label_size_label = QLabel("그래프 레이블 글자 크기: ")
        self.label_size_input = QLineEdit()
        self.label_size_input.setText("12")  # 기본값 설정
        grid_layout.addWidget(self.label_size_label, 2, 0)
        grid_layout.addWidget(self.label_size_input, 2, 1)

        self.grade_size_label = QLabel("그래프 눈금 글자 크기: ")
        self.grade_size_input = QLineEdit()
        self.grade_size_input.setText("10")  # 기본값 설정
        grid_layout.addWidget(self.grade_size_label, 2, 2)
        grid_layout.addWidget(self.grade_size_input, 2, 3)

        main_layout.addLayout(grid_layout)

        # 애니메이션 체크박스 생성
        self.eng_checkbox_label = QLabel("\n키워드를 영어로 변환하시겠습니까? ")
        main_layout.addWidget(self.eng_checkbox_label)

        checkbox_layout = QHBoxLayout()
        self.eng_no_checkbox = QCheckBox("변환 안함")
        self.eng_auto_checkbox = QCheckBox("자동 변환")
        self.eng_manual_checkbox = QCheckBox("수동 변환")

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
        btn = QPushButton("그래프 설정 완료", self)
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
        self.setWindowTitle("KEMKIM 그래프 조정")
        self.resize(800, 600)
        self.show()

        for te in self.findChildren(QTextEdit):
            te.setTabChangesFocus(True)

    def create_select_all_handler(self, group_name):
        def select_all_handler(state):

            try:
                checked = state == Qt.CheckState.Checked.value
            except AttributeError:
                checked = state == Qt.Checked

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
            all_checked = all(cb.isChecked() for cb in group_checkboxes)
            if not all_checked:
                self.select_all_checkboxes[group_name].blockSignals(True)
                self.select_all_checkboxes[group_name].setChecked(False)
                self.select_all_checkboxes[group_name].blockSignals(False)

        return individual_handler

    def show_selected_words(self):
        # 선택된 단어를 리스트에 추가
        self.selected_words = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        self.size_input = (
            self.x_size_input.text(),
            self.y_size_input.text(),
            self.font_size_input.text(),
            self.dot_size_input.text(),
            self.label_size_input.text(),
            self.grade_size_input.text(),
        )
        self.eng_auto_checked = self.eng_auto_checkbox.isChecked()
        self.eng_manual_checked = self.eng_manual_checkbox.isChecked()
        self.eng_no_checked = self.eng_no_checkbox.isChecked()

        # 선택된 단어를 메시지 박스로 출력
        if self.selected_words == []:
            QMessageBox.information(self, "선택한 단어", "선택된 단어가 없습니다")
        else:
            QMessageBox.information(self, "선택한 단어", ", ".join(self.selected_words))
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
        self.setWindowTitle("Tokenization")
        self.resize(300, 100)  # 창 크기를 조정
        # 레이아웃 생성
        layout = QVBoxLayout()

        # 버튼 생성
        btn1 = QPushButton("파일 토큰화", self)
        btn2 = QPushButton("토큰 파일 조정", self)
        btn3 = QPushButton("교집합 토큰 추출", self)

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


class TokenizeDialog(BaseDialog):
    def __init__(self, column_names, default_save_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CSV 토큰화 설정")
        self.resize(500, 600)
        self.data = None
        self.column_names = column_names
        self.save_dir = default_save_path
        self.include_word_path = ""

        layout = QVBoxLayout(self)

        # 1. 열 선택 섹션 (Scroll Area)
        layout.addWidget(QLabel("<b>1. 토큰화할 열 선택:</b>"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_widget)
        self.checkboxes = []
        for col in self.column_names:
            cb = QCheckBox(col)
            if "text" in col.lower():
                cb.setChecked(True)
            self.scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # 2. 언어 선택 섹션
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("<b>2. 텍스트 언어:</b>"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["한국어 (ko)", "영어 (en)"])
        lang_layout.addWidget(self.lang_combo)
        layout.addLayout(lang_layout)

        path_section = QVBoxLayout()
        path_header = QHBoxLayout()
        path_header.addWidget(QLabel("<b>저장 위치 설정:</b>"))
        path_header.addStretch()

        btn, lbl = self.make_path_widgets(
            self.save_dir, lambda p: setattr(self, "save_dir", p)
        )
        path_header.addWidget(btn)

        path_section.addLayout(path_header)
        path_section.addWidget(lbl)
        layout.addLayout(path_section)

        # 4. 필수 포함 단어 섹션
        word_group = QGroupBox("4. 기타 옵션")
        word_layout = QVBoxLayout(word_group)
        self.include_check = QCheckBox("필수 포함 단어 사전(CSV) 사용")
        self.include_label = QLabel("선택된 파일 없음")
        self.include_label.setStyleSheet("color: gray;")
        self.word_btn = QPushButton("사전 파일 선택")
        self.word_btn.setEnabled(False)
        self.word_btn.clicked.connect(self.select_word_file)

        self.include_check.toggled.connect(self.word_btn.setEnabled)

        word_layout.addWidget(self.include_check)
        word_layout.addWidget(self.include_label)
        word_layout.addWidget(self.word_btn)
        layout.addWidget(word_group)

        # 하단 버튼
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def select_save_path(self):
        path = QFileDialog.getExistingDirectory(self, "저장 위치 선택", self.save_dir)
        if path:
            self.save_dir = path
            self.path_label.setText(path)

    def select_word_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "필수 포함 단어 리스트(CSV) 선택", self.save_dir, "CSV Files (*.csv)"
        )
        if path:
            self.include_word_path = path
            self.include_label.setText(os.path.basename(path))
            self.include_label.setStyleSheet("color: black;")

    def validate_and_accept(self):
        selected_cols = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        if not selected_cols:
            QMessageBox.warning(self, "알림", "최소 하나 이상의 열을 선택해야 합니다.")
            return

        lang = "ko" if "한국어" in self.lang_combo.currentText() else "en"

        self.data = {
            "selected_columns": selected_cols,
            "language": lang,
            "save_path": self.save_dir,
            "include_word_path": self.include_word_path
            if self.include_check.isChecked()
            else "",
        }
        self.accept()


class SelectEtcAnalysisDialog(BaseDialog):
    def __init__(self, whisper, youtube_download, yolo):
        super().__init__()
        self.whisper = whisper
        self.youtube_download = youtube_download
        self.yolo = yolo
        self.initUI()
        self.data = None  # 데이터를 저장할 속성 추가

    def initUI(self):
        layout = QVBoxLayout()

        whisper_btn = QPushButton("음성 인식")
        whisper_btn.clicked.connect(self.run_whisper)
        layout.addWidget(whisper_btn)

        youtube_btn = QPushButton("YouTube 다운로드")
        youtube_btn.clicked.connect(self.run_youtube_download)
        layout.addWidget(youtube_btn)

        yolo_btn = QPushButton("영상/이미지 객체 탐지")
        yolo_btn.clicked.connect(self.run_detection)
        layout.addWidget(yolo_btn)

        self.setLayout(layout)

    def run_whisper(self):
        self.accept()
        self.whisper()

    def run_youtube_download(self):
        self.accept()
        self.youtube_download()

    def run_detection(self):
        self.accept()
        self.yolo()


class WhisperOptionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("음성 인식 옵션")
        self.resize(360, 180)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        # 언어 선택
        self.lang_map = {
            "한국어": "ko",
            "영어": "en",
            "일본어": "ja",
            "중국어": "zh",
            "프랑스어": "fr",
            "독일어": "de",
            "스페인어": "es",
            "이탈리아어": "it",
            "포르투갈어": "pt",
            "러시아어": "ru",
            "아랍어": "ar",
            "힌디어": "hi",
            "태국어": "th",
            "베트남어": "vi",
            "인도네시아어": "id",
        }

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(self.lang_map.keys())
        self.lang_combo.setCurrentText("한국어")

        form.addRow("언어", self.lang_combo)

        # 모델 선택
        self.model_map = {
            "빠름 (small)": 1,
            "중간 (medium, 권장)": 2,
            "정확 (large)": 3,
        }

        self.model_combo = QComboBox()
        self.model_combo.addItems(self.model_map.keys())
        self.model_combo.setCurrentText("중간 (medium, 권장)")

        form.addRow("모델", self.model_combo)

        layout.addLayout(form)

        # 버튼
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout.addWidget(btns)

    def get_option(self) -> dict:
        return {
            "language": self.lang_map[self.lang_combo.currentText()],
            "model_level": self.model_map[self.model_combo.currentText()],
        }


class YouTubeDownloadDialog(BaseDialog):
    def __init__(self, parent=None, base_dir=""):
        super().__init__(parent)
        self.setWindowTitle("YouTube 다운로드 설정")
        self.resize(520, 420)
        self.data = None

        layout = QVBoxLayout(self)

        # URL 입력
        layout.addWidget(QLabel("YouTube URL (한 줄에 하나씩 입력):"))
        self.url_edit = QTextEdit()
        layout.addWidget(self.url_edit)

        # 포맷 선택
        layout.addWidget(QLabel("다운로드 포맷:"))
        self.format_box = QComboBox()
        self.format_box.addItems(["mp4", "mp3"])
        layout.addWidget(self.format_box)

        # Whisper 옵션
        self.whisper_checkbox = QCheckBox("음성 텍스트 변환 생성")
        layout.addWidget(self.whisper_checkbox)

        # 저장 경로
        path_section = QVBoxLayout()
        path_header = QHBoxLayout()
        path_header.addWidget(QLabel("<b>저장 위치 설정:</b>"))
        path_header.addStretch()

        btn, lbl = self.make_path_widgets("", lambda p: setattr(self, "save_dir", p))
        path_header.addWidget(btn)

        path_section.addLayout(path_header)
        path_section.addWidget(lbl)
        layout.addLayout(path_section)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def select_path(self):
        path = QFileDialog.getExistingDirectory(self, "저장 경로 선택")
        if path:
            self.save_dir = path
            self.path_label.setText(path)

    def accept(self):
        urls = [
            u.strip() for u in self.url_edit.toPlainText().splitlines() if u.strip()
        ]
        if not urls:
            QMessageBox.warning(self, "입력 오류", "YouTube URL을 입력하세요.")
            return
        if not self.save_dir:
            QMessageBox.warning(self, "입력 오류", "저장 경로를 선택하세요.")
            return

        self.data = {
            "urls": urls,
            "format": self.format_box.currentText(),
            "save_whisper": self.whisper_checkbox.isChecked(),
            "save_dir": self.save_dir,
        }
        super().accept()


class DetectOptionDialog(BaseDialog):
    def __init__(self, parent=None, base_dir="", yolo_models=None):
        super().__init__(parent)
        self.setWindowTitle("영상/이미지 객체 검출 설정")
        self.resize(560, 420)  # 높이 늘림
        self.data = None

        layout = QVBoxLayout(self)

        self.save_dir = parent.localDirectory

        # ---------- media 선택 ----------
        media_layout = QHBoxLayout()
        media_layout.addWidget(QLabel("미디어 타입"))

        self.media_combo = QComboBox()
        self.media_combo.addItems(["video", "image"])
        media_layout.addWidget(self.media_combo)
        media_layout.addStretch()
        layout.addLayout(media_layout)

        # ---------- 파일 선택 ----------
        file_layout = QHBoxLayout()
        self.file_label = QLabel("선택된 파일: 0개")
        self.file_btn = QPushButton("파일 선택")
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_btn)
        layout.addLayout(file_layout)

        self.file_paths = []
        self.file_btn.clicked.connect(self.select_files)

        # ---------- 저장 경로 ----------
        path_section = QVBoxLayout()
        path_header = QHBoxLayout()
        path_header.addWidget(QLabel("<b>저장 위치 설정:</b>"))
        path_header.addStretch()

        btn, lbl = self.make_path_widgets(
            self.save_dir, lambda p: setattr(self, "save_dir", p)
        )
        path_header.addWidget(btn)

        path_section.addLayout(path_header)
        path_section.addWidget(lbl)
        layout.addLayout(path_section)

        # ---------- YOLO conf_thres ----------
        form = QFormLayout()

        self.model_combo = QComboBox()
        self.model_combo.addItems(yolo_models)
        form.addRow("Model", self.model_combo)

        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.0, 1.0)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setDecimals(2)
        self.conf_spin.setValue(0.5)

        form.addRow("conf_thres", self.conf_spin)

        # ---------- (추가) DINO 옵션 ----------
        self.dino_check = QCheckBox("프롬프트 포함")
        layout.addWidget(self.dino_check)

        self.dino_prompt = QTextEdit()
        self.dino_prompt.setPlaceholderText("Prompt (예: person. red car. dog.)")
        self.dino_prompt.setFixedHeight(70)

        form.addRow("prompt", self.dino_prompt)

        layout.addLayout(form)

        desc = QLabel(
            "conf_thres: 객체로 판단할 최소 신뢰도 기준(0~1)\n"
            "값이 높을수록 확실한 객체만 남고, 낮을수록 더 많은 후보가 표시됩니다.\n"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ---------- buttons ----------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.base_dir = base_dir or ""

        # media 바뀌면 dino 옵션 enable/disable
        self.media_combo.currentTextChanged.connect(self._sync_dino_ui)
        self.dino_check.toggled.connect(self._sync_dino_ui)
        self._sync_dino_ui()

    def _sync_dino_ui(self):
        media = self.media_combo.currentText()
        can_use_dino = media in ("image", "video")

        # 미디어 타입이 지원 안하면 체크박스 강제 해제
        if not can_use_dino and self.dino_check.isChecked():
            self.dino_check.setChecked(False)

        is_dino_active = can_use_dino and self.dino_check.isChecked()

        self.dino_check.setEnabled(can_use_dino)
        self.dino_prompt.setEnabled(is_dino_active)
        self.model_combo.setEnabled(not is_dino_active)

        self.conf_spin.setEnabled(True)

    def select_files(self):
        media = self.media_combo.currentText()

        if media == "image":
            filt = "Images (*.jpg *.jpeg *.png *.webp *.bmp)"
            title = "이미지 파일 선택"
        else:
            filt = "Videos (*.mp4 *.avi *.mov *.mkv *.webm)"
            title = "영상 파일 선택"

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            title,
            self.base_dir,
            filt,
        )

        if paths:
            self.file_paths = paths
            self.file_label.setText(f"선택된 파일: {len(paths)}개")

    def select_path(self):
        path = QFileDialog.getExistingDirectory(self, "저장 경로 선택")
        if path:
            self.save_dir = path
            self.path_label.setText(path)

    def accept(self):
        if not self.file_paths:
            QMessageBox.warning(self, "입력 오류", "파일을 선택하세요.")
            return
        if not self.save_dir:
            QMessageBox.warning(self, "입력 오류", "저장 경로를 선택하세요.")
            return

        run_dino = self.dino_check.isChecked()
        media = self.media_combo.currentText()

        if run_dino:
            prompt = (self.dino_prompt.toPlainText() or "").strip()
            if not prompt:
                QMessageBox.warning(self, "입력 오류", "DINO prompt를 입력하세요.")
                return

        self.data = {
            "media": media,
            "file_paths": self.file_paths,
            "conf_thres": float(self.conf_spin.value()),
            "save_dir": self.save_dir,
            "run_dino": run_dino,
            "dino_prompt": (self.dino_prompt.toPlainText() or "").strip(),
            "model": self.model_combo.currentText(),  # [추가] 선택된 모델명 저장
        }

        super().accept()


class NetworkAnalysisDialog(BaseDialog):
    def __init__(self, csv_path, column_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("단어 네트워크 분석 (NetMiner 스타일)")
        self.resize(560, 780)
        self.data = None
        self.csv_path = csv_path
        self.save_dir = os.path.dirname(csv_path) if csv_path else ""

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        form = QFormLayout()

        # 대상 열
        self.column_combo = QComboBox()
        self.column_combo.addItems(column_names)
        for i in range(self.column_combo.count()):
            if "text" in self.column_combo.itemText(i).lower():
                self.column_combo.setCurrentIndex(i)
                break
        form.addRow("대상 열", self.column_combo)

        # 공출현 단위
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["문서 단위 (document)", "슬라이딩 윈도우 (window)"])
        form.addRow("공출현 단위", self.scope_combo)

        self.window_spin = QSpinBox()
        self.window_spin.setRange(2, 20)
        self.window_spin.setValue(4)
        self.window_spin.setEnabled(False)
        form.addRow("윈도우 크기", self.window_spin)
        self.scope_combo.currentIndexChanged.connect(
            lambda i: self.window_spin.setEnabled(i == 1)
        )

        # 연관성 척도
        self.measure_combo = QComboBox()
        self.measure_combo.addItems(
            ["동시출현 빈도 (raw)", "Jaccard", "Cosine", "Dice", "PMI", "NPMI"]
        )
        form.addRow("연관성 척도", self.measure_combo)

        # 기간
        self.period_combo = QComboBox()
        self.period_combo.addItems(
            ["전체 통합", "1년", "6개월", "3개월", "1개월", "1주"]
        )
        form.addRow("기간 분할", self.period_combo)

        # 필터
        self.minfreq_spin = QSpinBox()
        self.minfreq_spin.setRange(1, 10000)
        self.minfreq_spin.setValue(5)
        form.addRow("최소 단어 빈도", self.minfreq_spin)

        self.minedge_spin = QSpinBox()
        self.minedge_spin.setRange(1, 10000)
        self.minedge_spin.setValue(2)
        form.addRow("최소 동시출현 횟수", self.minedge_spin)

        self.topn_spin = QSpinBox()
        self.topn_spin.setRange(0, 100000)
        self.topn_spin.setValue(300)
        self.topn_spin.setToolTip("0 = 제한 없음")
        form.addRow("최대 노드 수 (Top-N)", self.topn_spin)

        # 노드 크기 기준
        self.sizeby_combo = QComboBox()
        self.sizeby_combo.addItems(
            ["freq", "degree", "betweenness", "pagerank", "eigenvector"]
        )
        form.addRow("노드 크기 기준", self.sizeby_combo)

        self.label_spin = QSpinBox()
        self.label_spin.setRange(0, 500)
        self.label_spin.setValue(40)
        form.addRow("라벨 표시 개수", self.label_spin)

        # 커뮤니티
        self.community_combo = QComboBox()
        self.community_combo.addItems(["Louvain", "Leiden", "없음"])
        form.addRow("커뮤니티 탐지", self.community_combo)

        # 레이아웃
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(
            ["Fruchterman-Reingold", "Kamada-Kawai", "Circle", "Grid"]
        )
        form.addRow("레이아웃", self.layout_combo)

        layout.addLayout(form)

        # 중심성 체크박스
        cent_group = QGroupBox("계산할 중심성")
        cg = QGridLayout(cent_group)
        self.cent_checks = {}
        cents = [
            "degree",
            "strength",
            "betweenness",
            "closeness",
            "eigenvector",
            "pagerank",
        ]
        for i, name in enumerate(cents):
            cb = QCheckBox(name)
            if name in ("degree", "betweenness", "pagerank"):
                cb.setChecked(True)
            cg.addWidget(cb, i // 3, i % 3)
            self.cent_checks[name] = cb
        layout.addWidget(cent_group)

        # 백본
        backbone_group = QGroupBox("백본 추출 (disparity filter)")
        bg = QHBoxLayout(backbone_group)
        self.backbone_check = QCheckBox("사용")
        self.backbone_alpha = QDoubleSpinBox()
        self.backbone_alpha.setRange(0.001, 0.5)
        self.backbone_alpha.setDecimals(3)
        self.backbone_alpha.setValue(0.05)
        bg.addWidget(self.backbone_check)
        bg.addWidget(QLabel("alpha"))
        bg.addWidget(self.backbone_alpha)
        layout.addWidget(backbone_group)

        # 노드 색 기준
        self.colorby_combo = QComboBox()
        self.colorby_combo.addItems(["커뮤니티", "degree", "betweenness", "pagerank"])
        form.addRow("노드 색 기준", self.colorby_combo)

        # ego 개수
        self.ego_spin = QSpinBox()
        self.ego_spin.setRange(0, 50)
        self.ego_spin.setValue(5)
        form.addRow("ego 네트워크 수", self.ego_spin)

        # 저장 경로
        path_header = QHBoxLayout()
        path_header.addWidget(QLabel("<b>저장 위치:</b>"))
        path_header.addStretch()
        btn, lbl = self.make_path_widgets(
            self.save_dir, lambda p: setattr(self, "save_dir", p)
        )
        path_header.addWidget(btn)
        layout.addLayout(path_header)
        layout.addWidget(lbl)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def validate_and_accept(self):
        if not self.save_dir:
            QMessageBox.warning(self, "입력 오류", "저장 경로를 선택하세요.")
            return

        scope = "document" if self.scope_combo.currentIndex() == 0 else "window"
        measure_map = {
            0: "raw",
            1: "jaccard",
            2: "cosine",
            3: "dice",
            4: "pmi",
            5: "npmi",
        }
        period_map = {0: "total", 1: "1y", 2: "6m", 3: "3m", 4: "1m", 5: "1w"}
        community_map = {0: "louvain", 1: "leiden", 2: "none"}
        layout_map = {0: "fr", 1: "kk", 2: "circle", 3: "grid"}
        colorby_map = {0: "community", 1: "degree", 2: "betweenness", 3: "pagerank"}

        self.data = {
            "text_col": self.column_combo.currentText(),
            "scope": scope,
            "window": self.window_spin.value(),
            "measure": measure_map[self.measure_combo.currentIndex()],
            "period": period_map[self.period_combo.currentIndex()],
            "min_freq": self.minfreq_spin.value(),
            "min_edge_weight": self.minedge_spin.value(),
            "top_n": self.topn_spin.value(),
            "node_size_by": self.sizeby_combo.currentText(),
            "label_top": self.label_spin.value(),
            "centralities": [k for k, cb in self.cent_checks.items() if cb.isChecked()],
            "community": community_map[self.community_combo.currentIndex()],
            "layout": layout_map[self.layout_combo.currentIndex()],
            "backbone": self.backbone_check.isChecked(),
            "backbone_alpha": self.backbone_alpha.value(),
            "save_dir": self.save_dir,
            "node_color_by": "community",
            "draw_hull": True,
            "adjust_labels": False,
            "compute_kcore": True,
            "compute_structural_holes": True,
            "ego_top": 5,
            "node_color_by": colorby_map[self.colorby_combo.currentIndex()],
            "ego_top": self.ego_spin.value(),
        }
        self.accept()


class EditHomeMemberDialog(BaseDialog):
    def __init__(self, data: dict | None = None, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("멤버 편집" if data else "멤버 추가")
        self.resize(400, 600)
        self.data = data or {}
        vbox = QVBoxLayout(self)

        def add_row(label: str, widget):
            vbox.addWidget(QLabel(label))
            vbox.addWidget(widget)

        self.in_name = QLineEdit(self.data.get("name", ""))

        self.in_pos = QComboBox()
        self.in_section = QComboBox()

        self.load_options()

        if self.data.get("position"):
            self.in_pos.setCurrentText(self.data["position"])
        if self.data.get("section"):
            self.in_section.setCurrentText(self.data["section"])

        self.in_aff = QLineEdit(self.data.get("affiliation", ""))
        self.in_email = QLineEdit(self.data.get("email", ""))
        self.in_school = QTextEdit()
        self.in_school.setPlainText("\n".join(self.data.get("학력", [])))
        self.in_career = QTextEdit()
        self.in_career.setPlainText("\n".join(self.data.get("경력", [])))
        self.in_research = QTextEdit()
        self.in_research.setPlainText("\n".join(self.data.get("연구", [])))
        self.in_awards = QTextEdit()
        self.in_awards.setPlainText("\n".join(self.data.get("수상", [])))

        for lbl, wid in [
            ("이름", self.in_name),
            ("포지션", self.in_pos),
            ("소속", self.in_aff),
            ("구분(section)", self.in_section),
            ("이메일", self.in_email),
            ("학력(줄바꿈 구분)", self.in_school),
            ("경력(줄바꿈 구분)", self.in_career),
            ("연구(줄바꿈 구분)", self.in_research),
            ("수상(줄바꿈 구분)", self.in_awards),
        ]:
            add_row(lbl, wid)

        img_row = QHBoxLayout()
        self.img_btn = QPushButton("프로필 이미지 선택")
        self.img_btn.clicked.connect(self.pick_image)
        img_row.addWidget(self.img_btn)
        vbox.addLayout(img_row)

        ok = QPushButton("저장")
        cancel = QPushButton("취소")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        vbox.addWidget(ok)
        vbox.addWidget(cancel)

        self.new_image_url = None

    def load_options(self):
        try:
            response = Request("get", "members/options", HOMEPAGE_EDIT_API)
            if response.status_code == 200:
                options = response.json()
                self.in_pos.addItems(options.get("positions", []))
                self.in_section.addItems(options.get("sections", []))
        except Exception as e:
            QMessageBox.warning(self, "경고", "옵션 목록을 불러오지 못했습니다.")

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            folder_name = f"members"
            object_name = self.data.get("name", "")
            if not object_name:
                object_name, ok = QInputDialog.getText(
                    None, "파일명 입력", "성함을 입력하세요:", text="merged_file"
                )
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
            "position": self.in_pos.currentText(),
            "affiliation": self.in_aff.text().strip(),
            "section": self.in_section.currentText(),
            "email": self.in_email.text().strip(),
            "학력": self.in_school.toPlainText().strip().splitlines(),
            "경력": self.in_career.toPlainText().strip().splitlines(),
            "연구": self.in_research.toPlainText().strip().splitlines(),
            "수상": self.in_awards.toPlainText().strip().splitlines(),
        }

        if self.new_image_url:
            payload["image"] = self.new_image_url
        elif self.data.get("image"):
            payload["image"] = self.data["image"]
        else:
            payload["image"] = ""

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
        self.in_content = QTextEdit()
        self.in_content.setPlainText(self.data.get("content", ""))
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
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            try:
                self.new_image_url = upload_homepage_image(
                    path, "news", uuid.uuid4().hex
                )
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
        self.resize(400, 480)
        self.data = data or {}
        self.crawled_record: dict = dict(self.data)  # 전체 메타데이터 베이스

        vbox = QVBoxLayout(self)

        def add_row(label: str, widget):
            vbox.addWidget(QLabel(label))
            vbox.addWidget(widget)

        self.in_year = QLineEdit(str(self.data.get("year", "")))
        self.in_title = QLineEdit(self.data.get("title", ""))

        raw_authors = self.data.get("authors", [])
        if isinstance(raw_authors, list):
            authors_text = ", ".join(raw_authors)
        else:
            authors_text = str(raw_authors)
        self.in_authors = QLineEdit(authors_text)

        self.in_conf = QLineEdit(self.data.get("venue", ""))
        self.in_link = QLineEdit(self.data.get("url", ""))

        vbox.addWidget(QLabel("제목"))
        vbox.addWidget(self.in_title)

        # 크롤링: 등재 종류 선택 + 메타데이터 가져오기 버튼
        crawl_row = QHBoxLayout()
        self.in_journal_type = QComboBox()
        self.in_journal_type.addItems(["KCI", "SCI", "SCOPUS"])
        crawl_btn = QPushButton("메타데이터 가져오기")
        crawl_btn.clicked.connect(self.crawl_metadata)
        crawl_row.addWidget(self.in_journal_type)
        crawl_row.addWidget(crawl_btn)
        vbox.addLayout(crawl_row)

        for lbl, wid in [
            ("연도 (예: 2025)", self.in_year),
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

    def crawl_metadata(self):
        title = self.in_title.text().strip()
        if not title:
            QMessageBox.warning(self, "입력 오류", "제목을 먼저 입력해주세요.")
            return

        try:
            resp = Request(
                "get",
                "/papers/crawl",
                HOMEPAGE_EDIT_API,
                params={"title": title, "type": self.in_journal_type.currentText()},
            )
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                QMessageBox.information(
                    self,
                    "검색 결과 없음",
                    "해당 제목으로 메타데이터를 찾지 못했습니다.",
                )
            else:
                QMessageBox.warning(
                    self, "크롤링 실패", "메타데이터를 가져오는 중 오류가 발생했습니다."
                )
            return
        except Exception:
            QMessageBox.warning(
                self, "크롤링 실패", "메타데이터를 가져오는 중 오류가 발생했습니다."
            )
            return

        record = resp.json() if hasattr(resp, "json") else resp
        if not record:
            QMessageBox.information(
                self, "검색 결과 없음", "해당 제목으로 메타데이터를 찾지 못했습니다."
            )
            return

        self.crawled_record = record  # <- 전체 결과 보관

        self.in_year.setText(str(record.get("year") or ""))
        self.in_title.setText(record.get("title") or title)
        self.in_authors.setText(", ".join(record.get("authors") or []))
        self.in_conf.setText(record.get("venue") or "")
        self.in_link.setText(record.get("url") or "")

        QMessageBox.information(
            self,
            "크롤링 완료",
            f"'{record.get('title')}' 메타데이터를 불러왔습니다.\n확인 후 저장하세요.",
        )

    def get_payload(self) -> dict:
        try:
            year = int(self.in_year.text().strip())
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "연도는 숫자로 입력해주세요.")
            return {}

        authors_raw = self.in_authors.text().strip()
        authors_list = [a.strip() for a in authors_raw.split(",") if a.strip()]

        payload = dict(self.crawled_record)  # doi, published_date 등 나머지 필드 유지
        payload.update(
            {
                "uid": self.data.get("uid") or payload.get("uid") or str(uuid.uuid4()),
                "title": self.in_title.text().strip(),
                "authors": authors_list,
                "year": year,
                "venue": self.in_conf.text().strip(),
                "url": self.in_link.text().strip(),
            }
        )
        return payload


class ViewHomePaperDialog(BaseDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("논문 정보")
        self.resize(500, 400)
        layout = QVBoxLayout(self)

        self.add_label(layout, "제목", data.get("title", ""))
        self.add_label(layout, "저자", ", ".join(data.get("authors", [])))
        self.add_label(layout, "컨퍼런스/저널", data.get("venue", ""))
        self.add_label(layout, "링크", data.get("url", ""))
        self.add_label(layout, "연도", str(data.get("year", "")))


class ViewHomeMemberDialog(BaseDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("멤버 정보")
        self.resize(500, 400)
        layout = QVBoxLayout(self)

        self.add_label(layout, "성명", data.get("name", ""))
        self.add_label(layout, "구분", data.get("section", ""))
        self.add_label(layout, "직책", data.get("position", ""))
        self.add_label(layout, "소속", data.get("affiliation", ""))
        self.add_label(layout, "이메일", data.get("email", ""))
        self.add_label(
            layout,
            "학력",
            "\n".join(data.get("학력", []))
            if isinstance(data.get("학력", []), list)
            else str(data.get("학력", "")),
            multiline=True,
        )
        self.add_label(
            layout,
            "경력",
            "\n".join(data.get("경력", []))
            if isinstance(data.get("경력", []), list)
            else str(data.get("경력", "")),
            multiline=True,
        )
        self.add_label(
            layout,
            "연구",
            "\n".join(data.get("연구", []))
            if isinstance(data.get("연구", []), list)
            else str(data.get("연구", "")),
            multiline=True,
        )
        self.add_label(
            layout,
            "수상",
            "\n".join(data.get("수상", []))
            if isinstance(data.get("수상", []), list)
            else str(data.get("수상", "")),
            multiline=True,
        )


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


class ViewGalleryPostDialog(BaseDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.initUI()

    def initUI(self):
        self.setWindowTitle("갤러리 게시글 상세 보기")
        self.resize(520, 650)
        layout = QVBoxLayout(self)

        photos = self.data.get("photos", [])
        layout.addWidget(QLabel(f"<b>사진 ({len(photos)}장):</b>"))

        photo_scroll = QScrollArea()
        photo_scroll.setWidgetResizable(True)
        photo_scroll.setFixedHeight(220)
        photo_container = QWidget()
        photo_grid = QGridLayout(photo_container)
        photo_scroll.setWidget(photo_container)
        layout.addWidget(photo_scroll)

        _build_photo_grid(photo_grid, [(url, True) for url in photos], on_remove=None)

        self.add_label(layout, "제목:", self.data.get("title", ""), readonly=True)
        self.add_label(layout, "날짜:", self.data.get("date", ""), readonly=True)
        self.add_label(
            layout,
            "본문:",
            self.data.get("content", ""),
            multiline=True,
            readonly=True,
        )

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)


class EditHomePopupDialog(BaseDialog):
    def __init__(self, data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("팝업 편집" if data else "팝업 추가")
        self.resize(460, 520)
        self.data = data or {}
        self.new_image_url = None

        vbox = QVBoxLayout(self)

        def add_row(label: str, widget):
            vbox.addWidget(QLabel(label))
            vbox.addWidget(widget)

        from datetime import timedelta

        today = datetime.now().strftime("%Y-%m-%d")
        end_default = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        self.in_title = QLineEdit(self.data.get("title", ""))
        self.in_content = QTextEdit()
        self.in_content.setPlainText(self.data.get("content", ""))
        self.in_start = QLineEdit(self.data.get("start_date", today))
        self.in_end = QLineEdit(self.data.get("end_date", end_default))
        self.in_link = QLineEdit(self.data.get("link_url", ""))
        self.chk_active = QCheckBox("활성화")
        self.chk_active.setChecked(self.data.get("is_active", True))

        for lbl, wid in [
            ("제목", self.in_title),
            ("내용", self.in_content),
            ("시작일 (YYYY-MM-DD)", self.in_start),
            ("종료일 (YYYY-MM-DD)", self.in_end),
            ("링크 URL (옵션)", self.in_link),
        ]:
            add_row(lbl, wid)

        vbox.addWidget(self.chk_active)

        self.img_btn = QPushButton("이미지 선택/변경")
        self.img_btn.clicked.connect(self.pick_image)
        vbox.addWidget(self.img_btn)

        self.img_status = QLabel(
            f"현재 이미지: {self.data.get('image', '없음')[:60]}"
            if self.data.get("image")
            else "이미지 없음"
        )
        self.img_status.setStyleSheet("color: gray; font-size: 11px;")
        self.img_status.setWordWrap(True)
        vbox.addWidget(self.img_status)

        ok = QPushButton("저장")
        cancel = QPushButton("취소")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        vbox.addWidget(ok)
        vbox.addWidget(cancel)

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg *.webp *.gif)"
        )
        if path:
            try:
                self.new_image_url = upload_homepage_image(
                    path, "popup", uuid.uuid4().hex
                )
                self.img_status.setText(f"업로드 완료: {self.new_image_url[:60]}")
                QMessageBox.information(self, "완료", "이미지 업로드 성공")
            except Exception as e:
                QMessageBox.warning(self, "실패", str(e))

    def get_payload(self):
        return {
            "title": self.in_title.text().strip(),
            "content": self.in_content.toPlainText().strip(),
            "start_date": self.in_start.text().strip(),
            "end_date": self.in_end.text().strip(),
            "link_url": self.in_link.text().strip(),
            "is_active": self.chk_active.isChecked(),
            "image": self.new_image_url or self.data.get("image", ""),
        }


class ViewHomePopupDialog(BaseDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("팝업 상세")
        self.resize(460, 480)
        self.data = data

        layout = QVBoxLayout(self)

        self.add_label(layout, "제목:", data.get("title", ""), readonly=True)
        self.add_label(layout, "내용:", data.get("content", ""), readonly=True)
        self.add_label(layout, "시작일:", data.get("start_date", ""), readonly=True)
        self.add_label(layout, "종료일:", data.get("end_date", ""), readonly=True)
        self.add_label(layout, "링크 URL:", data.get("link_url", ""), readonly=True)
        self.add_label(
            layout, "활성:", "예" if data.get("is_active") else "아니오", readonly=True
        )

        if data.get("image"):
            layout.addWidget(QLabel("<b>이미지 미리보기:</b>"))
            self.image_label = QLabel("로딩 중...")
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.image_label.setFixedSize(400, 240)
            self.image_label.setStyleSheet(
                "border: 1px solid #dcdcdc; background-color: #f9f9f9; border-radius: 5px;"
            )
            layout.addWidget(self.image_label)
            self.load_popup_image(data["image"])

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def load_popup_image(self, url):
        try:
            resp = httpx.get(url)
            if resp.status_code == 200:
                pixmap = load_pixmap_exif_safe(resp.content)
                self.image_label.setPixmap(
                    pixmap.scaled(
                        390,
                        230,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                self.image_label.setText("이미지를 불러올 수 없습니다.")
        except Exception:
            self.image_label.setText("이미지 로드 오류")
