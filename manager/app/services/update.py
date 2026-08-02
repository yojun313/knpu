import os
import sys
import requests
import traceback
import subprocess
import webbrowser
import shutil
from PySide6.QtWidgets import QDialog, QPushButton, QMessageBox, QApplication
from PySide6.QtCore import Signal, QThread
from services.logging import programBugLog
from ui.status import printStatus
from ui.dialogs import ViewVersionDialog
from config import VERSION
from core.setting import get_setting
from core.boot import checkNewVersion, getVersionInfo
from core.thread import DownloadDialog
from libs.path import safe_path
from services.api import Request
import time


class DownloadWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url, save_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.save_path = save_path

    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            response.raise_for_status()
            totalSize = int(response.headers.get("content-length", 0))
            chunkSize = 8192
            downloaded = 0
            start_time = time.time()

            last_emit_time = 0
            last_percent = -1

            with open(safe_path(self.save_path), "wb") as f:
                for chunk in response.iter_content(chunk_size=chunkSize):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if totalSize > 0:
                            percent = int((downloaded / totalSize) * 100)

                            elapsed = time.time() - start_time
                            if elapsed <= 0:
                                elapsed = 0.001

                            speed = downloaded / (1024 * 1024) / elapsed
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


def openAndExit(parent, path):
    subprocess.Popen(f'"{path}"', shell=True)
    parent.force_quit()


def downloadProgram(parent, newVersionName, is_update=True):
    if is_update and not getattr(sys, "frozen", False):
        QMessageBox.warning(
            parent,
            "Warning",
            "개발 환경에서는 파일 교체 업데이트를 진행할 수 없습니다.\n전체 설치 패키지로 다운로드합니다.",
        )
        is_update = False

    temp_dir = "C:/Temp"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir, exist_ok=True)

    if is_update:
        downloadFile_path = os.path.join(
            temp_dir, f"MANAGER_{newVersionName}_update.exe"
        )
        download_url = (
            f"https://knpu.re.kr/download/MANAGER_{newVersionName}_update.exe"
        )
        msg = "업데이트 다운로드"
    else:
        downloadFile_path = os.path.join(temp_dir, f"MANAGER_{newVersionName}.exe")
        download_url = f"https://knpu.re.kr/download/MANAGER_{newVersionName}.exe"
        msg = "전체 패키지 다운로드"

    dialog = DownloadDialog(f"{msg}: {newVersionName}", parent=parent)
    worker = DownloadWorker(download_url, downloadFile_path)

    def on_finished(path):
        dialog.complete_task(True)

        if is_update:
            current_exe = sys.executable
            old_exe = current_exe + f".old_{int(time.time())}"
            try:
                os.rename(current_exe, old_exe)
                shutil.copy2(path, current_exe)

                subprocess.Popen([current_exe])
                parent.force_quit()
            except Exception as e:
                QMessageBox.critical(
                    parent, "업데이트 실패", f"파일 교체 중 오류가 발생했습니다:\n{e}"
                )
        else:
            openAndExit(parent, path)

    worker.progress.connect(
        lambda percent, msg: (
            dialog.update_progress(percent),
            dialog.update_text_signal.emit(msg),
        )
    )
    worker.finished.connect(on_finished)
    worker.error.connect(
        lambda e: (
            dialog.complete_task(False),
            QMessageBox.critical(parent, "Error", f"다운로드 실패: {e}"),
        )
    )

    worker.start()
    dialog.exec()


def updateProgram(parent, sc=False):
    try:
        newVersionCheck = checkNewVersion()
        if not newVersionCheck:
            newVersionName = VERSION
        else:
            newVersionName = newVersionCheck[0]

        def update_process(is_full_update):
            Request(
                "post",
                "users/version",
                json={"oldVersionName": VERSION, "newVersionName": newVersionName},
            )
            printStatus(parent, "버전 업데이트 중...")
            downloadProgram(parent, newVersionName, is_update=not is_full_update)

        if newVersionCheck:
            newVersionInfo = getVersionInfo(newVersionName)
            is_full_update = newVersionInfo.get("fullUpdate", False)

            if get_setting("AutoUpdate") == "auto":
                parent.closeBootscreen()
                update_process(is_full_update)
                return

            dialog = ViewVersionDialog(parent, newVersionInfo)
            update_btn = QPushButton("Update")
            cancel_btn = QPushButton("Cancel")

            update_btn.clicked.connect(dialog.accept)
            cancel_btn.clicked.connect(dialog.reject)

            dialog.add_buttons(update_btn, cancel_btn)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                update_process(is_full_update)

        else:
            if sc is True:
                reply = QMessageBox.question(
                    parent,
                    "Reinstall",
                    "현재 버전이 최신 버전입니다\n\n현재 버전을 재설치하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    printStatus(parent, "버전 재설치 중...")
                    # 재설치는 항상 전체 설치 패키지로 진행
                    downloadProgram(parent, newVersionName, is_update=False)
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
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open("https://manager.knpu.re.kr/api/download")
        return
