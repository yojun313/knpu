from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
import PyQt5.QtCore as QtCore
from functools import partial
import webbrowser


class Manager_Web:

    def __init__(self, main_window):
        self.main = main_window
        self.browser = None

        # crawler
        # QVBoxLayout을 설정하고 webViewLayout에 적용
        self.crawler_web_layout = QVBoxLayout()
        self.main.crawler_webview.setLayout(self.crawler_web_layout)

        # web
        self.web_web_layout = QVBoxLayout()
        self.main.web_webview.setLayout(self.web_web_layout)

        self.web_buttonMatch()

    def web_open_webbrowser(self, url, widget):
        if self.browser is not None:
            widget.removeWidget(self.browser)
            self.browser.deleteLater()

        # 새로운 브라우저 생성 및 추가
        self.browser = QWebEngineView()
        self.browser.setUrl(QtCore.QUrl(url))
        widget.addWidget(self.browser)
        self.browser.show()

    def web_open_downloadbrowser(self, url):
        webbrowser.open('http://bigmaclab-download.r-e.kr:90')

    def web_buttonMatch(self):
        self.main.crawler_server_button.clicked.connect(
            partial(self.web_open_webbrowser, "http://bigmaclab-crawler.kro.kr:80", self.crawler_web_layout))
        self.main.crawler_z_button.clicked.connect(
            partial(self.web_open_webbrowser, "http://bigmaclab-crawler.kro.kr:81", self.crawler_web_layout))
        self.main.crawler_omen_button.clicked.connect(
            partial(self.web_open_webbrowser, "http://bigmaclab-crawler.kro.kr:82", self.crawler_web_layout))
        self.main.web_downloadpage_button.clicked.connect(self.web_open_downloadbrowser)
        self.main.web_homepage_button.clicked.connect(
            partial(self.web_open_webbrowser, "https://knpu.re.kr", self.web_web_layout))
        self.main.web_github_button.clicked.connect(
            partial(self.web_open_webbrowser, "https://github.com/yojun313", self.web_web_layout))



