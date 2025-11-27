from PyQt6.QtWidgets import QVBoxLayout, QLabel, QDialog, QProgressBar, QPushButton, QGridLayout, QWidget, QHBoxLayout, QApplication
from PyQt6.QtCore import Qt, QCoreApplication, QEventLoop
from PyQt6.QtGui import QPixmap, QPainter, QBrush, QColor, QPen
from ui.dialogs import BaseDialog
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
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint
            )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
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
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(30, 30, 30, 30)  # 전체 여백 설정
        main_layout.setSpacing(15)  # 위젯 간격 확대

        # 프로그램 이름 라벨
        title_label = QLabel("MANAGER")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            f"font-size: 24px; font-family: 'Tahoma'; color: {text_color};")
        main_layout.addWidget(title_label)

        # 이미지 라벨
        image_label = QLabel(self)
        pixmap = QPixmap(os.path.join(ASSETS_PATH, "exe_icon.png"))
        pixmap = pixmap.scaled(
            180,
            180,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(image_label)

        # 버전 정보 라벨
        version_label = QLabel(f"Version {self.version}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet(
            f"font-size: 18px; font-family: 'Tahoma'; color: {text_color}; margin-top: 5px;")
        main_layout.addWidget(version_label)

        # 상태 메시지 라벨
        self.status_label = QLabel("Booting")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        main_layout.addWidget(self.bar, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 저작권 정보 라벨
        copyrightLabel = QLabel(
            "Copyright © 2024 KNPU PAILAB\nAll rights reserved.")
        copyrightLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyrightLabel.setStyleSheet(
            f"font-size: 15px; font-family: 'Tahoma'; color: {gray_color}; margin-top: 10px;")
        main_layout.addWidget(copyrightLabel)

        # 배경 색상 저장
        self.bg_color = bg_color

    def paintEvent(self, event):
        # 둥근 모서리를 위한 QPainter 설정
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))  # PyQt6: PenStyle 스코프 사용
        painter.drawRoundedRect(rect, 30, 30)  # 모서리를 둥글게 (30px radius)

    def updateStatus(self, msg: str):
        self.status_label.setText(msg)
        if self._step < self.MAX_STEP:
            self._step += 1
        self.bar.setValue(int(self._step / self.MAX_STEP * 100))

        for _ in range(2):
            QCoreApplication.processEvents(
                QEventLoop.ProcessEventsFlag.AllEvents, 0
            )

class AboutDialog(BaseDialog):
    def __init__(self, version, theme="light", parent=None):
        super().__init__(parent)
        self.parent = parent
        self.version = version
        self.theme = theme

        self.bg_color = QColor('#2b2b2b') if self.theme == "dark" else QColor(255, 255, 255)
        self.text_color = "white" if self.theme == "dark" else "#2c3e50"
        self.gray_color = "lightgray" if self.theme == "dark" else "gray"

        self.setWindowTitle("About MANAGER")
        self.resize(600, 300)  # 가로 길이를 넓혀줌
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(15)

        # ===== 상단: 이미지(왼쪽) + 텍스트(오른쪽) =====
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(0)
        grid.setColumnStretch(0, 1)   # 이미지 컬럼
        grid.setColumnStretch(1, 2)   # 텍스트 컬럼 (조금 더 넓게)

        # --- 이미지 ---
        image_label = QLabel(self)
        pixmap = QPixmap(os.path.join(ASSETS_PATH, "exe_icon.png"))
        pixmap = pixmap.scaled(
            150,
            150,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        image_label.setPixmap(pixmap)

        # 이미지가 컬럼 안에서 중앙에 오도록 컨테이너로 감싸기
        image_container = QWidget(self)
        ic_layout = QVBoxLayout(image_container)
        ic_layout.setContentsMargins(0, 0, 0, 0)
        ic_layout.addStretch(1)
        ic_layout.addWidget(
            image_label,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        ic_layout.addStretch(1)

        # 너무 왼쪽으로 붙지 않도록 컬럼 자체에 적당한 너비를 부여
        image_container.setFixedWidth(220)  # 필요하면 200~260 사이로 조절

        # --- 텍스트 ---
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)

        title_label = QLabel("MANAGER")
        title_label.setStyleSheet(f"font-size: 24px; font-family: 'Tahoma'; color: {self.text_color};")
        text_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignLeft)

        version_label = QLabel(f"Version {self.version}")
        version_label.setStyleSheet(f"font-size: 18px; font-family: 'Tahoma'; color: {self.text_color};")
        text_layout.addWidget(version_label, alignment=Qt.AlignmentFlag.AlignLeft)

        desc_label = QLabel("MANAGER는 KNPU PAILAB에서 개발한 빅데이터 분석 및 관리 프로그램입니다.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"font-size: 14px; font-family: 'Tahoma'; color: {self.gray_color};")
        text_layout.addWidget(desc_label, alignment=Qt.AlignmentFlag.AlignLeft)

        dev_label = QLabel('제작자: <a href="https://github.com/yojun313">github.com/yojun313</a>')
        dev_label.setOpenExternalLinks(True)
        dev_label.setStyleSheet(f"font-size: 14px; font-family: 'Tahoma'; color: {self.gray_color};")
        text_layout.addWidget(dev_label, alignment=Qt.AlignmentFlag.AlignLeft)

        # 그리드에 배치
        grid.addWidget(image_container, 0, 0, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        grid.addLayout(text_layout, 0, 1)

        main_layout.addLayout(grid)

        # ----- 하단 공통: 저작권 + 닫기 버튼 -----
        copyright_label = QLabel("Copyright © 2024 KNPU PAILAB\nAll rights reserved.")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet(
            f"font-size: 14px; font-family: 'Tahoma'; color: {self.gray_color}; margin-top: 10px;")
        main_layout.addWidget(copyright_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
        # 업데이트 확인 버튼
        update_btn = QPushButton("업데이트 확인")
        update_btn.setFixedWidth(120)
        update_btn.clicked.connect(lambda: self.parent.updateProgram(sc=True))
        update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._button_bg()};
                color: {self.text_color};
                border-radius: 8px;
                padding: 6px;
                font-size: 14px;
                font-family: 'Tahoma';
            }}
            QPushButton:hover {{ background-color: {self._button_hover_bg()}; }}
        """)
        button_layout.addWidget(update_btn)
    
        close_btn = QPushButton("닫기")
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._button_bg()};
                color: {self.text_color};
                border-radius: 8px;
                padding: 6px;
                font-size: 14px;
                font-family: 'Tahoma';
            }}
            QPushButton:hover {{ background-color: {self._button_hover_bg()}; }}
        """)
        button_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addLayout(button_layout)

    def showEvent(self, event):
        super().showEvent(event)
        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def _button_bg(self):
        return "#34495e" if self.theme == "dark" else "#ecf0f1"

    def _button_hover_bg(self):
        return "#2c3e50" if self.theme == "dark" else "#bdc3c7"
