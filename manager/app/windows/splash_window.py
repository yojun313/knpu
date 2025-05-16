from PyQt5.QtWidgets import QVBoxLayout, QLabel, QDialog, QProgressBar
from PyQt5.QtCore import Qt, QCoreApplication, QEventLoop
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor
import os
from config import ASSETS_PATH

class SplashDialog(QDialog):
    
    MAX_STEP      = 5
    
    def __init__(self, version, theme="light", booting=True):
        super().__init__()
        self.theme = theme
        self.version = version
        
        self._sub_color = "lightgray" if self.theme == "dark" else "#2c3e50"
        self._step = 0
        
        if booting:
            self.setWindowFlags(Qt.FramelessWindowHint |
                                Qt.WindowStaysOnTopHint)  # 최상위 창 설정
        self.setAttribute(Qt.WA_TranslucentBackground)  # 배경을 투명하게 설정
        self.initUI()
        

    def initUI(self):
        # 창 크기 설정
        self.resize(450, 450)

        # 테마 색상 설정
        if self.theme == "dark":
            bg_color = QColor('#2b2b2b')  # 다크 배경색
            text_color = "white"
            gray_color = "lightgray"
        else:
            bg_color = QColor(255, 255, 255)  # 디폴트 배경색 (흰색)
            text_color = "#2c3e50"
            gray_color = "gray"

        # 전체 레이아웃을 중앙 정렬로 설정
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(30, 30, 30, 30)  # 전체 여백 설정
        main_layout.setSpacing(15)  # 위젯 간격 확대

        # 프로그램 이름 라벨
        title_label = QLabel("MANAGER")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            f"font-size: 24px; font-family: 'Tahoma'; color: {text_color};")
        main_layout.addWidget(title_label)

        # 이미지 라벨
        image_label = QLabel(self)
        pixmap = QPixmap(os.path.join(ASSETS_PATH, "exe_icon.png"))
        pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)  # 이미지 크기 유지
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(image_label)

        # 버전 정보 라벨
        version_label = QLabel(f"Version {self.version}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet(
            f"font-size: 18px; font-family: 'Tahoma'; color: {text_color}; margin-top: 5px;")
        main_layout.addWidget(version_label)

        # 상태 메시지 라벨
        self.status_label = QLabel("Booting")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            f"font-size: 15px; font-family: 'Tahoma'; color: {gray_color}; margin-top: 8px;")
        main_layout.addWidget(self.status_label)

         # 진행-바
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.bar.setFixedWidth(200)  
        self.bar.setStyleSheet(f"""
            QProgressBar {{background: transparent; border-radius:4px;}}
            QProgressBar::chunk {{background:{self._sub_color}; border-radius:4px;}}
        """)
        main_layout.addWidget(self.bar, alignment=Qt.AlignCenter)
        
        # 저작권 정보 라벨
        copyrightLabel = QLabel(
            "Copyright © 2024 KNPU BIGMACLAB\nAll rights reserved.")
        copyrightLabel.setAlignment(Qt.AlignCenter)
        copyrightLabel.setStyleSheet(
            f"font-size: 15px; font-family: 'Tahoma'; color: {gray_color}; margin-top: 10px;")
        main_layout.addWidget(copyrightLabel)

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

    def updateStatus(self, msg: str):
        self.status_label.setText(msg)
        if self._step < self.MAX_STEP:
            self._step += 1
        self.bar.setValue(int(self._step / self.MAX_STEP * 100))

        for _ in range(2):
            QCoreApplication.processEvents(QEventLoop.AllEvents, 0)

