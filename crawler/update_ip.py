import sys
import os

import requests
from datetime import datetime

from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QMessageBox,
    QFrame,
    QFileDialog,
)
from dotenv import load_dotenv

load_dotenv()

CRAWLER_SERVER_URL = os.getenv("CRAWLER_SERVER_URL", "http://localhost:3001")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
PROXY_FILE_PATH = os.getenv("PROXY_FILE_PATH", "")


def read_proxy_file(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# ----------------------------------------
# 업로드 작업용 Worker (QThread에서 실행)
# ----------------------------------------


class UploadWorker(QObject):
    log_signal = Signal(str)
    finished = Signal(int)  # count
    error = Signal(str)

    def __init__(
        self,
        proxy_file_path: str,
        server_url: str,
        api_key: str,
        parent=None,
    ):
        super().__init__(parent)
        self.proxy_file_path = proxy_file_path.strip()
        self.server_url = self._normalize_server_url(server_url)
        self.api_key = api_key.strip()

    @staticmethod
    def _normalize_server_url(raw: str) -> str:
        url = raw.strip().rstrip("/")
        if url.lower().endswith("/api"):
            url = url[: -len("/api")]
        return url

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_signal.emit(f"[{timestamp}] {msg}")

    def run(self):
        try:
            # 1) 파일 읽기
            self._log(f"프록시 파일 읽는 중: {self.proxy_file_path}")
            if not os.path.exists(self.proxy_file_path):
                raise FileNotFoundError(
                    f"파일을 찾을 수 없습니다: {self.proxy_file_path}"
                )

            proxy_list = read_proxy_file(self.proxy_file_path)
            self._log(f"프록시 파일 로드 완료 ({len(proxy_list)}개)")

            # 2) 서버로 전송
            self._log("서버로 프록시 리스트 전송 중...")
            res = requests.post(
                f"{self.server_url}/api/proxy/update",
                headers={"X-Internal-Key": self.api_key},
                json={"proxies": proxy_list},
                timeout=15,
                allow_redirects=False,
            )
            if res.status_code in (301, 302, 303, 307, 308):
                raise RuntimeError(
                    f"{res.status_code} 리다이렉트: {res.request.url} → {res.headers.get('Location')}\n"
                    "인증 미들웨어가 이 요청을 API 요청으로 인식하지 못해 로그인 페이지로 돌려보냈습니다.\n"
                    "이 스크립트 파일이 최신 버전인지 확인해주세요 (저장소에서 crawler/update_ip.py를 다시 받아보세요)."
                )
            if res.status_code == 404:
                raise RuntimeError(
                    f"404 Not Found: {res.request.url}\n"
                    "서버 URL이 올바른지 확인해주세요 (예: http://localhost:3001, 끝에 /api를 붙이지 마세요)."
                )
            res.raise_for_status()
            try:
                data = res.json()
            except ValueError:
                preview = res.text[:200].replace("\n", " ")
                raise RuntimeError(
                    f"서버가 JSON이 아닌 응답을 반환했습니다 (status {res.status_code}, "
                    f"content-type: {res.headers.get('Content-Type')})\n미리보기: {preview}"
                )
            count = data.get("count", len(proxy_list))
            self._log(f"서버 업데이트 완료 ({count}개)")

            self.finished.emit(count)

        except Exception as e:
            self.error.emit(str(e))


# ----------------------------------------
# 메인 윈도우
# ----------------------------------------


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.thread: QThread | None = None
        self.worker: UploadWorker | None = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("프록시 업데이터")
        self.setMinimumSize(700, 560)

        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        central.setLayout(main_layout)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 제목
        title_label = QLabel("프록시 업데이터")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: 600;
            }
        """)
        main_layout.addWidget(title_label)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # 설정 영역
        config_label = QLabel("설정")
        config_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        main_layout.addWidget(config_label)

        # 서버 URL
        server_row = QHBoxLayout()
        server_label = QLabel("서버 URL:")
        server_label.setFixedWidth(110)
        self.server_url_edit = QLineEdit(CRAWLER_SERVER_URL)
        self.server_url_edit.setPlaceholderText("http://localhost:3001")
        server_row.addWidget(server_label)
        server_row.addWidget(self.server_url_edit)
        main_layout.addLayout(server_row)

        # API 키
        key_row = QHBoxLayout()
        key_label = QLabel("API 키:")
        key_label.setFixedWidth(110)
        self.api_key_edit = QLineEdit(INTERNAL_API_KEY)
        self.api_key_edit.setPlaceholderText("X-Internal-Key 값")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(key_label)
        key_row.addWidget(self.api_key_edit)
        main_layout.addLayout(key_row)

        # 프록시 파일 경로
        file_row = QHBoxLayout()
        file_label = QLabel("프록시 파일:")
        file_label.setFixedWidth(110)
        self.file_path_edit = QLineEdit(PROXY_FILE_PATH)
        self.file_path_edit.setPlaceholderText("프록시 목록 파일 경로 (.txt)")
        browse_btn = QPushButton("찾아보기")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self.browse_file)
        file_row.addWidget(file_label)
        file_row.addWidget(self.file_path_edit)
        file_row.addWidget(browse_btn)
        main_layout.addLayout(file_row)

        # 구분선
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line2)

        # 업로드 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.upload_button = QPushButton("업로드 시작")
        self.upload_button.setFixedWidth(140)
        self.upload_button.clicked.connect(self.start_upload)
        btn_layout.addWidget(self.upload_button)
        main_layout.addLayout(btn_layout)

        # 로그
        log_label = QLabel("로그")
        log_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        main_layout.addWidget(log_label)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #151515;
                color: #f0f0f0;
                border-radius: 8px;
                padding: 8px;
                font-family: Consolas, 'JetBrains Mono', 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.log_edit, stretch=1)

        # 전체 스타일 (다크 테마)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #202124;
                color: #f0f0f0;
            }
            QWidget {
                background-color: #202124;
                color: #f0f0f0;
            }
            QPushButton {
                background-color: #3c4043;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #5f6368;
            }
            QPushButton:disabled {
                background-color: #3c4043;
                color: #777777;
            }
            QRadioButton, QLabel {
                color: #e8eaed;
            }
            QLineEdit {
                background-color: #2b2b2b;
                border-radius: 4px;
                padding: 4px 8px;
                border: 1px solid #5f6368;
                color: #f0f0f0;
            }
            QFrame[frameShape="4"] {
                color: #3c4043;
            }
        """)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "프록시 파일 선택",
            "",
            "텍스트 파일 (*.txt);;모든 파일 (*)",
        )
        if path:
            self.file_path_edit.setText(path)

    def append_log(self, text: str):
        self.log_edit.appendPlainText(text)
        self.log_edit.verticalScrollBar().setValue(
            self.log_edit.verticalScrollBar().maximum()
        )

    def start_upload(self):
        if self.thread is not None:
            QMessageBox.warning(self, "진행 중", "이미 업로드가 진행 중입니다.")
            return

        proxy_file = self.file_path_edit.text().strip()
        server_url = self.server_url_edit.text().strip()
        api_key = self.api_key_edit.text().strip()

        if not proxy_file:
            QMessageBox.warning(self, "입력 오류", "프록시 파일 경로를 입력해주세요.")
            return
        if not server_url:
            QMessageBox.warning(self, "입력 오류", "서버 URL을 입력해주세요.")
            return

        self.log_edit.clear()
        self.append_log("=== 업로드 작업 시작 ===")
        self.upload_button.setEnabled(False)

        self.thread = QThread(self)
        self.worker = UploadWorker(
            proxy_file_path=proxy_file,
            server_url=server_url,
            api_key=api_key,
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(lambda *_: self.cleanup_thread())
        self.worker.error.connect(lambda *_: self.cleanup_thread())

        self.thread.start()

    def cleanup_thread(self):
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.thread = None
        self.worker = None
        self.upload_button.setEnabled(True)

    def on_finished(self, count: int):
        self.append_log(f"=== 업로드 완료: 총 {count}개 프록시 전송됨 ===")
        QMessageBox.information(
            self, "완료", f"프록시 업데이트가 완료되었습니다.\n총 {count}개 전송됨."
        )

    def on_error(self, message: str):
        self.append_log(f"[오류] {message}")
        QMessageBox.critical(
            self, "오류", f"업로드 중 오류가 발생했습니다:\n\n{message}"
        )


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
