from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
import PyQt5.QtCore as QtCore
from functools import partial


class Manager_Crawler:

    def __init__(self, main_window):
        self.main = main_window
        self.browser = None
        self.crawler_buttonMatch()

        # QVBoxLayout을 설정하고 webViewLayout에 적용
        self.web_layout = QVBoxLayout()
        self.main.webViewLayout.setLayout(self.web_layout)

    def crawler_open_webbrowser(self, url):
        if self.browser is not None:
            self.web_layout.removeWidget(self.browser)
            self.browser.deleteLater()

        # 새로운 브라우저 생성 및 추가
        self.browser = QWebEngineView()
        self.browser.setUrl(QtCore.QUrl(url))
        self.web_layout.addWidget(self.browser)
        self.browser.show()

    def crawler_buttonMatch(self):
        self.main.crawler_history_button.clicked.connect(
            partial(self.crawler_open_webbrowser, "http://bigmaclab-crawler.kro.kr/history"))
        self.main.crawler_dashboard_button.clicked.connect(
            partial(self.crawler_open_webbrowser, "http://bigmaclab-crawler.kro.kr"))
        self.main.crawler_add_button.clicked.connect(
            partial(self.crawler_open_webbrowser, "http://bigmaclab-crawler.kro.kr/add_crawler"))
