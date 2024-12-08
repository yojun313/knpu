from PyQt5.QtWidgets import QVBoxLayout, QLabel, QDialog
from PyQt5.QtCore import Qt, QCoreApplication, QEventLoop
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor
from dotenv import load_dotenv
import platform
import os

class SplashDialog(QDialog):
    def __init__(self, version, theme="light", booting=True):
        super().__init__()

        if platform.system() == 'Windows':
            setting_path = os.path.join(os.path.join(os.environ['LOCALAPPDATA'], 'MANAGER'), 'settings.env')
            if os.path.exists(setting_path):
                load_dotenv(setting_path, encoding='utf-8')
                self.theme = os.getenv("OPTION_1")
            else:
                self.theme = 'default'
        else:
            setting_path = os.path.join(os.path.dirname(__file__), 'settings.env')
            load_dotenv(setting_path, encoding='utf-8')
            self.theme = os.getenv("OPTION_1")

        self.version = version
        if booting:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)  # 최상위 창 설정
        self.setAttribute(Qt.WA_TranslucentBackground)  # 배경을 투명하게 설정
        self.initUI()

    def initUI(self):
        # 창 크기 설정
        self.resize(450, 450)

        # 테마 색상 설정
        if self.theme == "dark":
            bg_color = QColor(45, 45, 45)  # 다크 배경색
            text_color = "white"
            gray_color = "lightgray"
        else:
            bg_color = QColor(255, 255, 255)  # 디폴트 배경색 (흰색)
            text_color = "black"
            gray_color = "gray"

        # 전체 레이아웃을 중앙 정렬로 설정
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(30, 30, 30, 30)  # 전체 여백 설정
        main_layout.setSpacing(15)  # 위젯 간격 확대

        # 프로그램 이름 라벨
        title_label = QLabel("MANAGER")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"font-size: 24px; font-family: 'Tahoma'; font-weight: bold; color: {text_color};")
        main_layout.addWidget(title_label)

        # 이미지 라벨
        image_label = QLabel(self)
        pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'source', 'exe_icon.png'))
        pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 이미지 크기 유지
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(image_label)

        # 버전 정보 라벨
        version_label = QLabel(f"Version {self.version}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet(f"font-size: 21px; font-family: 'Tahoma'; color: {text_color}; margin-top: 5px;")
        main_layout.addWidget(version_label)

        # 상태 메시지 라벨
        self.status_label = QLabel("Booting")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font-size: 15px; font-family: 'Tahoma'; color: {gray_color}; margin-top: 8px;")
        main_layout.addWidget(self.status_label)

        # 저작권 정보 라벨
        copyright_label = QLabel("Copyright © 2024 KNPU BIGMACLAB\nAll rights reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet(f"font-size: 15px; font-family: 'Tahoma'; color: {gray_color}; margin-top: 10px;")
        main_layout.addWidget(copyright_label)

        # 배경 색상 저장
        self.bg_color = bg_color

    def paintEvent(self, event):
        # 둥근 모서리를 위한 QPainter 설정
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 안티앨리어싱 적용
        rect = self.rect()
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(Qt.NoPen)  # 테두리를 없애기 위해 Pen 없음 설정
        painter.drawRoundedRect(rect, 30, 30)  # 모서리를 둥글게 (30px radius)

    def update_status(self, message):
        """
        SplashDialog의 상태 메시지를 업데이트하고 UI를 즉시 새로고침하는 메서드
        """
        self.status_label.setText(message)
        for i in range(2):
            QCoreApplication.processEvents(QEventLoop.AllEvents, 0)