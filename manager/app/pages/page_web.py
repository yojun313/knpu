from PyQt5.QtWidgets import QVBoxLayout, QInputDialog, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from functools import partial
import webbrowser
import warnings
import traceback

from services.logging import programBugLog
from services.api import Request
from config import HOMEPAGE_EDIT_API

# 새롭게 만든 범용 Dialog
from ui.dialogs import (
    EditHomeMemberDialog,
    EditHomeNewsDialog,
    EditHomePaperDialog,
    SelectAndEditDialog,  # ★ 범용 선택/수정 다이얼로그
)

warnings.filterwarnings("ignore")


class Manager_Web:

    def __init__(self, main_window):
        self.main = main_window
        self.browser = None

        self.crawler_web_layout = QVBoxLayout()
        self.main.crawler_webview.setLayout(self.crawler_web_layout)

        self.web_web_layout = QVBoxLayout()
        self.web_buttonMatch()

    def web_open_webbrowser(self, url, widget):
        try:
            if self.browser is not None:
                widget.removeWidget(self.browser)
                self.browser.deleteLater()

            self.browser = QWebEngineView()
            self.browser.setUrl(QUrl(url))
            widget.addWidget(self.browser)
            self.browser.show()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def web_buttonMatch(self):
        # 웹사이트 링크들
        self.main.crawler_server_button.clicked.connect(
            partial(self.web_open_webbrowser, "https://crawler.knpu.re.kr", self.crawler_web_layout))
        self.main.web_homepage_button.clicked.connect(
            partial(webbrowser.open, "https://knpu.re.kr"))
        self.main.web_sue_button.clicked.connect(
            partial(webbrowser.open, "https://complaint.knpu.re.kr"))
        self.main.web_carnumber_button.clicked.connect(
            partial(webbrowser.open, "https://carnumber.knpu.re.kr"))
        self.main.web_github_button.clicked.connect(
            partial(webbrowser.open, "https://github.com/yojun313"))

        self.main.homepage_member_edit_btn.clicked.connect(self.open_member_action_dialog)
        self.main.homepage_news_edit_btn.clicked.connect(self.open_news_action_dialog)
        self.main.homepage_paper_edit_btn.clicked.connect(self.open_paper_action_dialog)

    def open_member_action_dialog(self):
        options = ["멤버 추가", "멤버 수정(선택)", "멤버 삭제(선택)"]
        choice, ok = QInputDialog.getItem(self.main, "멤버 작업 선택",
                                          "원하는 작업을 선택하세요:", options, 0, False)
        if not ok or not choice:
            return
        if choice.startswith("멤버 추가"):
            self.open_add_member_dialog()
        elif choice.startswith("멤버 수정"):
            self.open_select_and_edit_dialog("member")
        elif choice.startswith("멤버 삭제"):
            self.open_select_and_delete_dialog("member")

    def open_news_action_dialog(self):
        options = ["뉴스 추가", "뉴스 수정(선택)", "뉴스 삭제(선택)"]
        choice, ok = QInputDialog.getItem(self.main, "뉴스 작업 선택",
                                          "원하는 작업을 선택하세요:", options, 0, False)
        if not ok or not choice:
            return
        if choice.startswith("뉴스 추가"):
            self.open_add_news_dialog()
        elif choice.startswith("뉴스 수정"):
            self.open_select_and_edit_dialog("news")
        elif choice.startswith("뉴스 삭제"):
            self.open_select_and_delete_dialog("news")

    def open_paper_action_dialog(self):
        options = ["논문 추가", "논문 수정(선택)", "논문 삭제(선택)"]
        choice, ok = QInputDialog.getItem(self.main, "논문 작업 선택",
                                          "원하는 작업을 선택하세요:", options, 0, False)
        if not ok or not choice:
            return
        if choice.startswith("논문 추가"):
            self.open_add_paper_dialog()
        elif choice.startswith("논문 수정"):
            self.open_select_and_edit_dialog("paper")
        elif choice.startswith("논문 삭제"):
            self.open_select_and_delete_dialog("paper")

    def open_add_member_dialog(self):
        try:
            dialog = EditHomeMemberDialog(parent=self.main)
            if dialog.exec_():  # OK
                payload = dialog.get_payload()
                Request("post", "edit/member", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload['name']} 멤버가 추가되었습니다!")
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())
            QMessageBox.critical(self.main, "실패", str(e))

    def open_add_news_dialog(self):
        try:
            dialog = EditHomeNewsDialog(parent=self.main)
            if dialog.exec_():
                payload = dialog.get_payload()
                Request("post", "edit/news", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload.get('title','뉴스')}가 추가되었습니다!")
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def open_add_paper_dialog(self):
        try:
            dialog = EditHomePaperDialog(parent=self.main)
            if dialog.exec_():
                payload = dialog.get_payload()
                Request("post", "edit/paper", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload.get('title','논문')}가 추가되었습니다!")
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def open_select_and_edit_dialog(self, item_type: str):
        try:
            dialog = SelectAndEditDialog(item_type=item_type, parent=self.main)
            dialog.exec_()  # 수정 선택 후 내부에서 서버 전송
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def open_select_and_delete_dialog(self, item_type: str):
        try:
            dialog = SelectAndEditDialog(item_type=item_type, parent=self.main)
            dialog.setWindowTitle(f"{item_type} 삭제")
            dialog.edit_btn.setText(f"선택 {item_type} 삭제")
            dialog.edit_btn.clicked.disconnect()  # 원래 수정 연결 끊기
            dialog.edit_btn.clicked.connect(partial(self.delete_selected_item, dialog, item_type))
            dialog.exec_()
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def delete_selected_item(self, dialog, item_type: str):
        current_row = dialog.list_widget.currentRow()
        if current_row < 0:
            QMessageBox.warning(self.main, "선택 안됨", f"삭제할 {item_type}를 선택하세요.")
            return
        item = dialog.items[current_row]
        try:
            endpoint = f"{item_type}"
            params = { "name": item.get("name") } if item_type == "member" else { "title": item.get("title") }
            Request("delete", endpoint, HOMEPAGE_EDIT_API, params=params)
            QMessageBox.information(self.main, "삭제됨", f"{item.get('name') or item.get('title')}가 삭제되었습니다!")
            dialog.load_items()  # 삭제 후 목록 새로고침
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())
