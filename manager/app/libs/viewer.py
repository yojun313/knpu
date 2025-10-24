import os
import sys
import shutil
import subprocess
import requests
import tempfile
from config import MANAGER_PROGRESS_API

from PyQt5.QtWidgets import QDialog, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl
import os
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

class ViewerDialog(QDialog):
    def __init__(self, pid: str, width=800, height=400, parent=None):
        super().__init__(parent)
        self.pid = pid
        self.setWindowTitle(f"Progress Viewer - {pid}")
        self.resize(width, height)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.temp_dir = tempfile.mkdtemp(prefix="viewer-dialog-")  # 예전 profile_dir 역할

        layout = QVBoxLayout(self)
        self.webview = QWebEngineView(self)
        url = f"{VIEW_SERVER}/?pid={pid}"
        self.webview.setUrl(QUrl(url))
        layout.addWidget(self.webview)

    def closeEvent(self, event):
        # 기존 close_viewer에서 하던 것처럼 디렉토리 삭제
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        event.accept()
        
VIEW_SERVER = MANAGER_PROGRESS_API

'''
    사용법
    register_process(pid, f"Crawl DB Save")
    viewer = open_viewer(pid)
    close_viewer(viewer)
'''

def register_process(process_id: str, title: str):
    """
    뷰 서버에 프로세스 등록을 요청합니다.
    POST /process { title, process_id }
    """
    resp = requests.post(
        f"{VIEW_SERVER}/process",
        json={"title": title, "process_id": process_id}
    )
    resp.raise_for_status()

def _notify(process_id, payload):
    """
    /notify/{process_id} 로 메시지를 전송한다.
    payload 에는 최소 'type' 키가 포함되어야 함.
    실패 시 raise_for_status() 로 예외 발생.
    """
    url = f"{VIEW_SERVER}/notify/{process_id}"
    resp = requests.post(url, json=payload)
    resp.raise_for_status()

# ─────────────────────────────────────────────────────────────
# 1) 일반 텍스트 메시지
def send_message(process_id: str, text: str) -> None:
    """
    클라이언트 화면에 단순 텍스트를 표시한다.
    """
    _notify(process_id, {"type": "message", "text": text})

# 2) 진행률 업데이트
def send_progress(process_id: str, current: int, total: int) -> None:
    """
    current/total 로 진행률 바를 갱신한다.
    """
    _notify(process_id, {"type": "progress", "current": current, "total": total})

# 3) 단계(phase) 상태 업데이트
def send_status(process_id: str, phase: str) -> None:
    """
    단계명을 표시한다. (예: '다운로드', '변환 중' 등)
    """
    _notify(process_id, {"type": "status", "phase": phase})

def open_viewer(pid: str, width: int = 800, height: int = 400):
    viewer = ViewerDialog(pid, width, height)
    viewer.show()
    return viewer   # 기존처럼 객체 반환


from PyQt5.QtCore import QTimer

def close_viewer(viewer):
    if viewer:
        def _close():
            # 먼저 WebEngineView 정리
            viewer.webview.setUrl(QUrl("about:blank"))
            viewer.webview.deleteLater()

            # 창 닫기
            viewer.accept()  # ✅ reject() 또는 close() 대신 accept() 사용 시 안정적으로 종료됨

            # 안전하게 강제 종료 방어 로직 (혹시 안 닫히는 경우)
            QTimer.singleShot(500, lambda: viewer.close())

        # UI 스레드에서 실행
        QTimer.singleShot(0, _close)
