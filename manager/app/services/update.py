import os
import requests
import traceback
import subprocess
import webbrowser
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QMessageBox, QTextEdit
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import pyqtSignal, QThread

from libs.console import openConsole, closeConsole
from services.pushover import sendPushOver
from services.logging import userLogging, getUserLocation, programBugLog
from ui.status import printStatus
from config import VERSION
from core.setting import get_setting
from core.boot import checkNewVersion
from ui.dialogs import DownloadDialog
from libs.path import safe_path


def updateProgram(parent, sc=False):
    class DownloadWorker(QThread):
        progress = pyqtSignal(int)
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

                with open(self.save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunkSize):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            percent = int((downloaded / totalSize) * 100)
                            self.progress.emit(percent)

                self.finished.emit(self.save_path)

            except Exception as e:
                self.error.emit(str(e))

    try:
        newVersionInfo = checkNewVersion()
        if not newVersionInfo:
            newVersionName = VERSION
        else:
            newVersionName = newVersionInfo[0]

        def update_process():
            openConsole("Version Update Process")
            msg = f"{parent.user} updated {VERSION} -> {newVersionName}\n\n{getUserLocation(parent)}"
            sendPushOver(msg)
            userLogging(f'Program Update ({VERSION} -> {newVersionName})')
            printStatus(parent, "버전 업데이트 중...")

            downloadFile_path = os.path.join('C:/Temp', f"MANAGER_{newVersionName}.exe")
            download_url = f"https://knpu.re.kr/download/MANAGER_{newVersionName}.exe"

            # 다운로드 진행창 생성
            dialog = DownloadDialog(f"업데이트 다운로드: {newVersionName}", parent)
            worker = DownloadWorker(download_url, safe_path(downloadFile_path))

            worker.progress.connect(dialog.update_progress)
            worker.finished.connect(lambda path: (
                dialog.complete_task(True),
                subprocess.Popen([path], shell=True),
                os._exit(0)
            ))
            worker.error.connect(lambda e: (
                dialog.complete_task(False),
                QMessageBox.critical(parent, "Error", f"다운로드 실패: {e}")
            ))

            worker.start()
            dialog.exec_()

        # ────────────────────────────────────────────────────────────────
        # 새 버전 있음
        # ────────────────────────────────────────────────────────────────
        if newVersionInfo:
            # 자동 업데이트 모드일 경우 바로 실행
            if get_setting('AutoUpdate') == 'auto':
                parent.closeBootscreen()
                update_process()
                return

            # 수동 업데이트 안내 Dialog
            dialog = QDialog(parent)
            dialog.setWindowTitle("New Version Released")
            dialog.resize(480, 420)

            layout = QVBoxLayout(dialog)

            def add_field(title: str, content: str, *, monospace: bool = False, min_lines: int = 3) -> QTextEdit:
                layout.addWidget(QLabel(f"<b>{title}</b>"))
                edit = QTextEdit()
                edit.setReadOnly(True)
                edit.setAcceptRichText(False)
                edit.setPlainText("" if content is None else str(content))
                if monospace:
                    font = QFont("Consolas")
                    font.setStyleHint(QFont.Monospace)
                    edit.setFont(font)
                    edit.setLineWrapMode(QTextEdit.NoWrap)
                metrics = edit.fontMetrics()
                edit.setMinimumHeight(metrics.lineSpacing() * min_lines + 12)
                layout.addWidget(edit)
                return edit

            # newVersionInfo: [versionNum, changeLog, features, status, releaseDate]
            ver = str(newVersionInfo[0]) if len(newVersionInfo) > 0 else ""
            chg = str(newVersionInfo[1]) if len(newVersionInfo) > 1 else ""
            feat = str(newVersionInfo[2]) if len(newVersionInfo) > 2 else ""
            rel = str(newVersionInfo[-1]) if len(newVersionInfo) > 0 else ""

            add_field("Version Num", ver)
            add_field("Release Date", rel)
            add_field("ChangeLog", chg, monospace=True, min_lines=6)
            add_field("Version Features", feat, monospace=False, min_lines=4)

            button_layout = QHBoxLayout()
            confirm_button = QPushButton("Update")
            cancel_button = QPushButton("Cancel")
            confirm_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(confirm_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)

            dialog.setLayout(layout)

            if dialog.exec_() == QDialog.Accepted:
                update_process()
            else:
                QMessageBox.information(
                    parent,
                    "Information",
                    'Ctrl+U 단축어로 프로그램 실행 중 업데이트 가능합니다'
                )
                return

        # ────────────────────────────────────────────────────────────────
        # 새 버전 없음 (재설치 여부 묻기)
        # ────────────────────────────────────────────────────────────────
        else:
            if sc is True:
                reply = QMessageBox.question(
                    parent,
                    "Reinstall",
                    "현재 버전이 최신 버전입니다\n\n현재 버전을 재설치하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    printStatus(parent, "버전 재설치 중...")
                    openConsole("Version Reinstall Process")
                    downloadFile_path = os.path.join(
                        'C:/Temp', f"MANAGER_{newVersionName}.exe"
                    )
                    download_url = f"https://knpu.re.kr/download/MANAGER_{newVersionName}.exe"

                    # 다운로드 진행창 생성
                    dialog = DownloadDialog(f"재설치 다운로드: {newVersionName}", parent)
                    worker = DownloadWorker(download_url, safe_path(downloadFile_path))

                    worker.progress.connect(dialog.update_progress)
                    worker.finished.connect(lambda path: (
                        dialog.complete_task(True),
                        subprocess.Popen([path], shell=True),
                        os._exit(0)
                    ))
                    worker.error.connect(lambda e: (
                        dialog.complete_task(False),
                        QMessageBox.critical(parent, "Error", f"다운로드 실패: {e}")
                    ))

                    worker.start()
                    dialog.exec_()
                else:
                    return
            return

    except Exception:
        programBugLog(parent, traceback.format_exc())
        reply = QMessageBox.question(
            parent,
            "Reinstall",
            "다운로드 웹페이지를 열어 수동 업데이트를 진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            webbrowser.open("https://knpu.re.kr/download_manager")
        return
