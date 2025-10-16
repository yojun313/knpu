import sys
import os
import pandas as pd
from PyQt5.QtWidgets import QApplication, QFileDialog
from PyQt5.QtCore import Qt, QCoreApplication, QEventLoop, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QDialog, QProgressBar

# pandasgui
from pandasgui.gui import show

# 경로는 필요에 따라 수정
ASSETS_PATH = os.path.join(os.path.dirname(__file__), 'pandasgui', 'resources', 'images')  


# ------------------ Splash Dialog ------------------
class SplashDialog(QDialog):
    MAX_STEP = 5

    def __init__(self, version="1.0.0", theme="light"):
        super().__init__()
        self.theme = theme
        self.version = version
        self._sub_color = "lightgray" if self.theme == "dark" else "#2c3e50"
        self._step = 0

        # 프레임리스 & 투명 배경 설정
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.initUI()

    def initUI(self):
        self.resize(450, 450)
        bg_color = QColor('#2b2b2b') if self.theme == "dark" else QColor(255, 255, 255)
        text_color = "white" if self.theme == "dark" else "#2c3e50"
        gray_color = "lightgray" if self.theme == "dark" else "gray"

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(15)

        title_label = QLabel("ANALYZER")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"font-size: 24px; font-family: 'Tahoma'; color: {text_color};")
        main_layout.addWidget(title_label)

        image_label = QLabel(self)
        pixmap = QPixmap(os.path.join(ASSETS_PATH, "icon.png"))
        pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(image_label)

        self.status_label = QLabel("Booting...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            f"font-size: 15px; font-family: 'Tahoma'; color: {gray_color}; margin-top: 8px;")
        main_layout.addWidget(self.status_label)

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

        copyright_label = QLabel("Copyright © 2025 KNPU PAILAB\nAll rights reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet(
            f"font-size: 15px; font-family: 'Tahoma'; color: {gray_color}; margin-top: 10px;")
        main_layout.addWidget(copyright_label)

        self.bg_color = bg_color

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        painter.setBrush(QBrush(self.bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 30, 30)

    def updateStatus(self, msg: str):
        self.status_label.setText(msg)
        if self._step < self.MAX_STEP:
            self._step += 1
        self.bar.setValue(int(self._step / self.MAX_STEP * 100))
        QCoreApplication.processEvents(QEventLoop.AllEvents, 0)


# ------------------ CSV Loader Functions ------------------
def open_csv_from_dialog(splash):
    splash.updateStatus("Opening file dialog...")
    file_path, _ = QFileDialog.getOpenFileName(
        None,
        "CSV 파일 열기",
        "",
        "CSV Files (*.csv);;All Files (*)"
    )
    if not file_path:
        print("파일이 선택되지 않았습니다.")
        sys.exit()
    splash.updateStatus("Loading CSV...")
    df = pd.read_csv(file_path)
    splash.updateStatus("CSV loaded")
    return df


def open_csv_from_arg(path, splash):
    splash.updateStatus("Checking file path...")
    if not os.path.isfile(path):
        print(f"❌ 파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    try:
        splash.updateStatus("Loading CSV...")
        df = pd.read_csv(path)
        splash.updateStatus("CSV loaded")
        return df
    except Exception as e:
        print(f"❌ CSV 파일 로드 중 오류 발생: {e}")
        sys.exit(1)


# ------------------ Main ------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Splash 먼저 띄우기
    splash = SplashDialog(version="1.0.0", theme="light")
    splash.show()
    QCoreApplication.processEvents()

    def launch_gui():
        splash.updateStatus("Launching GUI...")
        gui = show(df, settings={'block': False})  # block=False로 바꿈
        splash.close()

    # CSV 로드
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
        df = open_csv_from_arg(csv_path, splash)
    else:
        df = open_csv_from_dialog(splash)

    # GUI 띄우는 작업을 이벤트 루프 다음 단계로 넘김
    QTimer.singleShot(100, launch_gui)

    sys.exit(app.exec_())