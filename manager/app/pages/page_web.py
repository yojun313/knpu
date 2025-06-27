from PyQt5.QtWidgets import QVBoxLayout, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import warnings
import traceback

from services.logging import programBugLog
from services.api import Request
from config import HOMEPAGE_EDIT_API

# 새롭게 만든 범용 Dialog
from ui.dialogs import (
    EditHomeMemberDialog,
    EditHomeNewsDialog,
    EditHomePaperDialog
)
from ui.table import *

warnings.filterwarnings("ignore")


class Manager_Web:

    def __init__(self, main_window):
        self.main = main_window
        self.browser = None

        self.crawler_web_layout = QVBoxLayout()
        self.main.crawler_webview.setLayout(self.crawler_web_layout)

        self.web_web_layout = QVBoxLayout()
        self.refreshPaperBoard()
        self.refreshMemberBoard()
        self.refreshNewsBoard()
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
        self.main.web_addpaper_button.clicked.connect(self.addHomePaper)
        self.main.web_addmember_button.clicked.connect(self.addHomeMember)
        self.main.web_addnews_button.clicked.connect(self.addHomeNews)
        self.main.web_deletepaper_button.clicked.connect(self.deleteHomePaper)
        self.main.web_deletemember_button.clicked.connect(self.deleteHomeMember)
        self.main.web_deletenews_button.clicked.connect(self.deleteHomeNews)
        self.main.web_editpaper_button.clicked.connect(self.editHomePaper)
        self.main.web_editmember_button.clicked.connect(self.editHomeMember)
        self.main.web_editnews_button.clicked.connect(self.editHomeNews)

    def refreshPaperBoard(self):
        self.origin_paper_data = Request(
            'get', 
            '/papers/',
            HOMEPAGE_EDIT_API
        ).json()

        parsed_items = []
        self.paper_uid_list = []
        for year_group in self.origin_paper_data:
            year = year_group.get("year", "")
            for paper in year_group.get("papers", []):
                paper["year"] = year  # 연도 추가
                self.paper_uid_list.append(paper.get("uid"))
                paper["authors"] = ', '.join(paper.get("authors", []))
                parsed_items.append(paper)

        self.paper_data = [[item['title'], item['authors'], item['conference'], item.get('link', ''), item['year']] for item in parsed_items]
        self.paper_table_column = ['Title', 'Authors', 'Conference', 'Url', 'Year']
        makeTable(self.main, self.main.web_papers_tableWidget, self.paper_data, self.paper_table_column)

    def refreshMemberBoard(self):
        self.origin_member_data = Request(
            'get', 
            '/members/',
            HOMEPAGE_EDIT_API
        ).json()

        parsed_items = []
        self.member_uid_list = []
        for member in self.origin_member_data:
            self.member_uid_list.append(member.get("uid"))
            member_info = {
                'name': str(member.get('name', '')),
                'position': str(member.get('position', '')),
                'email': str(member.get('email', '')),
                "학력": "\n".join(member.get("학력", [])) if isinstance(member.get("학력"), list) else str(member.get("학력", "")),
                "경력": "\n".join(member.get("경력", [])) if isinstance(member.get("경력"), list) else str(member.get("경력", "")),
                "연구": "\n".join(member.get("연구", [])) if isinstance(member.get("연구"), list) else str(member.get("연구", "")),
            }
            parsed_items.append(member_info)

        self.member_data = [[item['name'], item['position'], item['email'], item['학력'], item['경력'], item['연구']] for item in parsed_items]
        self.member_table_column = ['성명', '직책', '이메일', '학력', '경력', '연구']
        makeTable(self.main, self.main.web_members_tableWidget, self.member_data, self.member_table_column)

    def refreshNewsBoard(self):
        self.origin_news_data = Request(
            'get', 
            '/news/',
            HOMEPAGE_EDIT_API
        ).json()

        parsed_items = []
        self.news_uid_list = []
        for news in self.origin_news_data:
            self.news_uid_list.append(news.get("uid"))
            news_info = {
                'title': str(news.get('title', '')),
                'content': str(news.get('content', '')),
                'date': str(news.get('date', '')),
                'url': str(news.get('url', '')),
            }
            parsed_items.append(news_info)

        self.news_data = [[item['title'], item['content'], item['date'], item['url']] for item in parsed_items]
        self.news_table_column = ['제목', '내용', '날짜', 'URL']
        makeTable(self.main, self.main.web_news_tableWidget, self.news_data, self.news_table_column)

    def addHomePaper(self):
        try:
            dialog = EditHomePaperDialog(parent=self.main)
            if dialog.exec_():
                payload = dialog.get_payload()
                Request("post", "edit/paper", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload['paper'].get('title','논문')}가 추가되었습니다")
                self.refreshPaperBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def addHomeMember(self):
        try:
            dialog = EditHomeMemberDialog(parent=self.main)
            if dialog.exec_():
                payload = dialog.get_payload()
                Request("post", "edit/member", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload['name']} 멤버가 추가되었습니다")
                self.refreshMemberBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def addHomeNews(self):
        try:
            dialog = EditHomeNewsDialog(parent=self.main)
            if dialog.exec_():
                payload = dialog.get_payload()
                Request("post", "edit/news", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload.get('title','뉴스')}가 추가되었습니다")
                self.refreshNewsBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteHomePaper(self):
        try:
            selectedRow = self.main.web_papers_tableWidget.currentRow()
            selectedUid = self.paper_uid_list[selectedRow]
            reply = QMessageBox.question(self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                Request("delete", "edit/paper", HOMEPAGE_EDIT_API, params={"uid": selectedUid})
                self.refreshPaperBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteHomeMember(self):
        try:
            selectedRow = self.main.web_members_tableWidget.currentRow()
            selectedUid = self.member_uid_list[selectedRow]
            reply = QMessageBox.question(self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                Request("delete", "edit/member", HOMEPAGE_EDIT_API, params={"uid": selectedUid})
                self.refreshMemberBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteHomeNews(self):
        try:
            selectedRow = self.main.web_news_tableWidget.currentRow()
            selectedUid = self.news_uid_list[selectedRow]
            reply = QMessageBox.question(self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                Request("delete", "edit/news", HOMEPAGE_EDIT_API, params={"uid": selectedUid})
                self.refreshNewsBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def editHomePaper(self):
        try:
            selectedRow = self.main.web_papers_tableWidget.currentRow()
            if selectedRow == -1:
                QMessageBox.warning(self.main, "경고", "편집할 논문을 선택하세요.")
                return
            selectedUid = self.paper_uid_list[selectedRow]
            # 기존 데이터 가져오기
            origin = None
            for year_group in self.origin_paper_data:
                for p in year_group["papers"]:
                    if p.get("uid") == selectedUid:
                        origin = p
                        origin["year"] = year_group["year"]
                        break
            if not origin:
                QMessageBox.warning(self.main, "오류", "논문 정보를 찾을 수 없습니다.")
                return

            dialog = EditHomePaperDialog(data=origin, parent=self.main)
            if dialog.exec_():
                payload = dialog.get_payload()
                payload["paper"]["uid"] = selectedUid  # uid 유지
                Request("post", "edit/paper", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload['paper'].get('title')}가 수정되었습니다")
                self.refreshPaperBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())
    
    def editHomeMember(self):
        try:
            selectedRow = self.main.web_members_tableWidget.currentRow()
            if selectedRow == -1:
                QMessageBox.warning(self.main, "경고", "편집할 멤버를 선택하세요.")
                return
            selectedUid = self.member_uid_list[selectedRow]
            origin = None
            for m in self.origin_member_data:
                if m.get("uid") == selectedUid:
                    origin = m
                    break
            if not origin:
                QMessageBox.warning(self.main, "오류", "멤버 정보를 찾을 수 없습니다.")
                return

            dialog = EditHomeMemberDialog(data=origin, parent=self.main)
            if dialog.exec_():
                payload = dialog.get_payload()
                payload["uid"] = selectedUid
                Request("post", "edit/member", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload.get('name')} 멤버가 수정되었습니다")
                self.refreshMemberBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def editHomeNews(self):
        try:
            selectedRow = self.main.web_news_tableWidget.currentRow()
            if selectedRow == -1:
                QMessageBox.warning(self.main, "경고", "편집할 뉴스를 선택하세요.")
                return
            selectedUid = self.news_uid_list[selectedRow]
            origin = None
            for n in self.origin_news_data:
                if n.get("uid") == selectedUid:
                    origin = n
                    break
            if not origin:
                QMessageBox.warning(self.main, "오류", "뉴스 정보를 찾을 수 없습니다.")
                return

            dialog = EditHomeNewsDialog(data=origin, parent=self.main)
            if dialog.exec_():
                payload = dialog.get_payload()
                payload["uid"] = selectedUid
                Request("post", "edit/news", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(self.main, "완료", f"{payload.get('title')} 뉴스가 수정되었습니다")
                self.refreshNewsBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    