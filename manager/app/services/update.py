import os
import sys
import requests
import traceback
import subprocess
import webbrowser
from PyQt6.QtWidgets import QDialog, QPushButton, QMessageBox, QApplication
from PyQt6.QtCore import pyqtSignal, QThread
from services.pushover import sendPushOver
from services.logging import userLogging, getUserLocation, programBugLog
from ui.status import printStatus
from ui.dialogs import ViewVersionDialog
from config import VERSION
from core.setting import get_setting
from core.boot import checkNewVersion
from core.thread import DownloadDialog
import time

class DownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url, save_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            totalSize = int(response.headers.get('content-length', 0))
            chunkSize = 8192
            downloaded = 0
            start_time = time.time()

            last_emit_time = 0
            last_percent = -1

            with open(self.save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunkSize):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if totalSize > 0:
                            percent = int((downloaded / totalSize) * 100)

                            elapsed = time.time() - start_time
                            if elapsed <= 0:
                                elapsed = 0.001  # 0 division 방지

                            speed = downloaded / (1024 * 1024) / elapsed  # MB/s
                            current_mb = downloaded / (1024 * 1024)
                            total_mb = totalSize / (1024 * 1024)

                            now = time.time()
                            if percent != last_percent or now - last_emit_time > 0.2:
                                msg = f"{current_mb:.1f}MB / {total_mb:.1f}MB ({speed:.1f}MB/s)"
                                self.progress.emit(percent, msg)
                                last_percent = percent
                                last_emit_time = now

            self.finished.emit(self.save_path)

        except Exception as e:
            self.error.emit(str(e))


def openAndExit(path):
    subprocess.Popen(f'"{path}"', shell=True)
    QApplication.quit()
    sys.exit(0)

def downloadProgram(parent, newVersionName, reinstall=False):
    temp_dir = 'C:/Temp'
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
        
    downloadFile_path = os.path.join(temp_dir, f"MANAGER_{newVersionName}.exe")
    download_url = f"https://knpu.re.kr/download/MANAGER_{newVersionName}.exe"

    # 다운로드 진행창 생성
    msg = "업데이트 다운로드" if not reinstall else "재설치 다운로드"
    dialog = DownloadDialog(f"{msg}: {newVersionName}", parent=parent)
    worker = DownloadWorker(download_url, downloadFile_path)

    worker.progress.connect(lambda percent, msg: (
        dialog.update_progress(percent),
        dialog.update_text_signal.emit(msg)
    ))
    worker.finished.connect(lambda path: (
        dialog.complete_task(True),
        openAndExit(path)
    ))
    worker.error.connect(lambda e: (
        dialog.complete_task(False),
        QMessageBox.critical(parent, "Error", f"다운로드 실패: {e}")
    ))

    worker.start()
    dialog.exec()

def updateProgram(parent, sc=False):
    
    try:
        newVersionInfo = checkNewVersion()
        if not newVersionInfo:
            newVersionName = VERSION
        else:
            newVersionName = newVersionInfo[0]

        def update_process():
            msg = f"{parent.user} updated {VERSION} -> {newVersionName}\n\n{getUserLocation(parent)}"
            sendPushOver(msg)
            userLogging(f'Program Update ({VERSION} -> {newVersionName})')
            printStatus(parent, "버전 업데이트 중...")
            downloadProgram(parent, newVersionName)

        # 새 버전 있음
        if newVersionInfo:
            # 자동 업데이트 모드일 경우 바로 실행
            if get_setting('AutoUpdate') == 'auto':
                parent.closeBootscreen()
                update_process()
                return
            # newVersionInfo: [versionNum, changeLog, features, status, releaseDate]
            ver  = str(newVersionInfo[0]) if len(newVersionInfo) > 0 else ""
            chg  = str(newVersionInfo[1]) if len(newVersionInfo) > 1 else ""
            feat = str(newVersionInfo[2]) if len(newVersionInfo) > 2 else ""
            rel  = str(newVersionInfo[-1]) if len(newVersionInfo) > 0 else ""
            # detail은 없다면 빈 값으로
            detail = "" if len(newVersionInfo) < 5 else str(newVersionInfo[3])

            version_data = [ver, rel, chg, feat, detail]

            # ViewVersionDialog를 이용해 UI 띄우기
            dialog = ViewVersionDialog(parent, version_data)
            update_btn = QPushButton("Update")
            cancel_btn = QPushButton("Cancel")

            update_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)

            dialog.add_buttons(update_btn, cancel_btn)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                update_process()

        # 새 버전 없음 (재설치 여부 묻기)
        else:
            if sc is True:
                reply = QMessageBox.question(
                    parent,
                    "Reinstall",
                    "현재 버전이 최신 버전입니다\n\n현재 버전을 재설치하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    printStatus(parent, "버전 재설치 중...")
                    downloadProgram(parent, newVersionName, reinstall=True)
                else:
                    return
            return

    except Exception:
        programBugLog(parent, traceback.format_exc())
        reply = QMessageBox.question(
            parent,
            "Reinstall",
            "다운로드 웹페이지를 열어 수동 업데이트를 진행하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open("https://knpu.re.kr/download_manager")
        return
