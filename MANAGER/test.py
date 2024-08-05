import sys
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 메인 레이아웃
        self.setWindowTitle('Web Browser with Download Support')
        self.setGeometry(100, 100, 1200, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # QWebEngineView 설정
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl("http://www.example.com"))
        main_layout.addWidget(self.web_view)

        # 버튼 레이아웃 생성
        button_layout = QHBoxLayout()
        self.web_homepage_button = QPushButton("Home Page")
        self.web_downloadpage_button = QPushButton("Download Page")

        # 버튼을 버튼 레이아웃에 추가
        button_layout.addWidget(self.web_homepage_button)
        button_layout.addWidget(self.web_downloadpage_button)

        # 버튼 클릭 이벤트 연결
        self.web_homepage_button.clicked.connect(self.open_home_page)
        self.web_downloadpage_button.clicked.connect(self.open_download_page)

        # 메인 레이아웃에 버튼 레이아웃 추가
        main_layout.addLayout(button_layout)

        # 다운로드 처리기 설정
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self.on_download_requested)

    def open_home_page(self):
        self.web_view.setUrl(QUrl('http://www.example.com'))

    def open_download_page(self):
        self.web_view.setUrl(QUrl('http://bigmaclab-download.r-e.kr:90'))

    def on_download_requested(self, download):
        # 다운로드 요청을 처리하는 함수
        download_path = download.path()  # 파일 경로를 얻어옴
        download.accept()  # 다운로드 수락
        download.downloadProgress.connect(lambda received, total: print(f"Downloading: {received}/{total} bytes"))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
