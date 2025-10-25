import os
import re
import requests
import time
from services.api import get_api_headers
from libs.path import safe_path
from PyQt5.QtCore import QThread, pyqtSignal
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
import zipfile
from urllib.parse import unquote
from ui.dialogs import BaseDialog
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QTimer
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout, QProgressBar
from PyQt5.QtWebEngineWidgets import QWebEngineView
from services.api import *
from services.logging import *
from config import MANAGER_PROGRESS_API
VIEW_SERVER = MANAGER_PROGRESS_API

class BaseWorker(QThread):
    finished = pyqtSignal(bool, str, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def upload_file(self, file_path: str, url: str, extra_fields: dict = None, label: str = "업로드 중"):
        """
        파일 업로드를 공통으로 처리하는 메서드
        """
        try:
            file_size = os.path.getsize(file_path)
            uploaded = 0
            last_percent = -1
            last_emit_time = 0
            start_time = time.time()

            def upload_callback(monitor):
                nonlocal uploaded, last_percent, last_emit_time
                uploaded = monitor.bytes_read
                percent = int(uploaded / file_size * 100)
                now = time.time()
                if percent != last_percent or now - last_emit_time > 0.2:
                    mb_up = uploaded / (1024 * 1024)
                    mb_total = file_size / (1024 * 1024)
                    speed = mb_up / (now - start_time) if now > start_time else 0
                    msg = f"{label}... {mb_up:.1f}MB/{mb_total:.1f}MB ({speed:.1f}MB/s)"
                    self.progress.emit(percent, msg)
                    last_percent = percent
                    last_emit_time = now

            fields = extra_fields or {}
            fields["file"] = (os.path.basename(file_path), open(file_path, "rb"), "application/octet-stream")
            encoder = MultipartEncoder(fields=fields)
            monitor = MultipartEncoderMonitor(encoder, upload_callback)

            response = requests.post(
                url,
                data=monitor,
                headers={**get_api_headers(), "Content-Type": monitor.content_type},
                timeout=3600,
                stream=True
            )
            response.raise_for_status()
            return response

        except Exception as e:
            raise e

    def download_file(
        self,
        response,
        save_dir: str,
        filename: str = None,
        label: str = "다운로드 중",
        extract: bool = False
    ):
        """
        파일 다운로드 + (옵션) 압축 해제

        extract=True일 경우:
            - zip 파일이면 압축 해제 후 zip 파일 삭제
            - 압축 해제 경로 반환
        extract=False일 경우:
            - 다운로드한 파일 경로 반환
        """
        total_size = int(response.headers.get("Content-Length", 0))

        # 파일 이름 파싱
        if not filename:
            content_disp = response.headers.get("Content-Disposition", "")
            m = re.search(r'filename="(?P<fname>[^"]+)"', content_disp)
            if m:
                filename = m.group("fname")
            else:
                m2 = re.search(r"filename\*=utf-8''(?P<fname>[^;]+)", content_disp)
                filename = unquote(m2.group("fname")) if m2 else "download.bin"

        local_path = os.path.join(save_dir, filename)
        downloaded = 0
        start_time = time.time()
        last_percent = -1
        last_emit_time = 0

        # --- 파일 다운로드 ---
        with open(safe_path(local_path), "wb") as f:
            for chunk in response.iter_content(8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int(downloaded / total_size * 100)
                        elapsed = time.time() - start_time
                        speed = downloaded / (1024 * 1024) / elapsed
                        current_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        now = time.time()
                        if percent != last_percent or now - last_emit_time > 0.2:
                            msg = f"{label}... {current_mb:.1f}MB / {total_mb:.1f}MB ({speed:.1f}MB/s)"
                            self.progress.emit(percent, msg)
                            last_percent = percent
                            last_emit_time = now

        # --- 압축 해제 옵션 처리 ---
        if extract and local_path.lower().endswith(".zip"):
            self.progress.emit(100, "압축 해제 중...")
            base_folder = os.path.splitext(os.path.basename(local_path))[0]
            extract_path = os.path.join(save_dir, base_folder)
            os.makedirs(extract_path, exist_ok=True)
            with zipfile.ZipFile(local_path, "r") as zf:
                zf.extractall(extract_path)
            os.remove(local_path)
            return extract_path

        return local_path

class DownloadDialog(BaseDialog):
    update_text_signal = pyqtSignal(str)

    def __init__(self, display_name, pid=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{display_name}")
        self.setMinimumWidth(600)
        self.pid = pid 
        if self.pid:
            self.setMinimumHeight(400)
        else:
            self.setMinimumHeight(60)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.layout = QVBoxLayout(self)
        self.update_text_signal.connect(self.update_message)

        self.webview = None  # 기본값 None

        # -----------------------
        # 웹뷰 (pid가 있을 때만 생성)
        # -----------------------
        if self.pid:
            self.webview = QWebEngineView()
            self.layout.addWidget(self.webview, stretch=1)

            url = QUrl(f"{VIEW_SERVER}/?pid={pid}")
            self.webview.setUrl(url)

        # -----------------------
        # 상태 메시지 & 진행바 (웹뷰 아래)
        # -----------------------
        self.msg_label = QLabel("다운로드 대기 중...")
        self.msg_label.setWordWrap(True)
        self.msg_label.setStyleSheet("font-weight: bold; color: #333; font-size: 13px;")
        self.msg_label.setAlignment(Qt.AlignCenter)

        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        self.pbar.setTextVisible(True)
        self.pbar.setFormat("%p%")
        self.pbar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bcbcbc;
                border-radius: 8px;
                background-color: #f0f0f0;
                height: 22px;
                text-align: center;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 8px;
            }
        """)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.msg_label, 2)
        bottom_layout.addWidget(self.pbar, 4)
        self.layout.addLayout(bottom_layout)

    def update_progress(self, value: int):
        self.pbar.setValue(value)
        # 100%가 되면 자동으로 초기화 메시지 출력
        if value >= 100:
            QTimer.singleShot(200, self.reset_bar)

    def update_message(self, message: str):
        self.msg_label.setText(message)

    def complete_task(self, success=True):
        self.pbar.setValue(100 if success else 0)
        self.pbar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bcbcbc;
                border-radius: 8px;
                background-color: #f0f0f0;
                height: 22px;
                text-align: center;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: %s;
                border-radius: 8px;
            }
        """ % ("#4CAF50" if success else "#E74C3C"))
        self.msg_label.setText(
            "작업이 완료되었습니다." if success else "작업 중 오류가 발생했습니다."
        )
        self.close()

    def reset_bar(self):
        self.msg_label.setText("대기 중...")
        self.pbar.setValue(0)
    
    def closeEvent(self, event):
        if self.webview:
            self.webview.setUrl(QUrl("about:blank"))
            self.webview.deleteLater()
            self.webview = None
        super().closeEvent(event)
     
class TaskStatusDialog(BaseDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(400, 75)
        
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.label = QLabel("작업을 준비 중입니다...", self)
        self.label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

    def update_message(self, message: str):
        self.label.setText(message)
