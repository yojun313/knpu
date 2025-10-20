import os
import requests
import traceback
from libs.console import openConsole, closeConsole
from services.pushover import sendPushOver
from services.logging import userLogging, getUserLocation, programBugLog
from ui.status import printStatus
from config import VERSION
from core.setting import get_setting
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QMessageBox
from PyQt5.QtCore import Qt
from core.boot import checkNewVersion
import webbrowser
from libs.path import safe_path

def updateProgram(parent, sc=False):
    try:
        newVersionInfo = checkNewVersion()
        if not newVersionInfo:
            newVersionName = VERSION
        else:
            newVersionName = newVersionInfo[0]

        def downloadFile(download_url, local_filename):
            response = requests.get(download_url, stream=True)
            totalSize = int(response.headers.get(
                'content-length', 0))  # 파일의 총 크기 가져오기
            chunkSize = 8192  # 8KB씩 다운로드
            downloadSize = 0  # 다운로드된 크기 초기화

            with open(safe_path(local_filename), 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunkSize):
                    if chunk:  # 빈 데이터 확인
                        f.write(chunk)
                        downloadSize += len(chunk)
                        percent_complete = (downloadSize / totalSize) * 100
                        # 퍼센트 출력
                        print(
                            f"\r{newVersionName} Download: {percent_complete:.0f}%", end='')

            print("\nDownload Complete")
            closeConsole()
                

        def update_process():
            openConsole("Version Update Process")
            msg = (
                f"{parent.user} updated {VERSION} -> {newVersionName}\n\n{getUserLocation(parent)}"
            )
            sendPushOver(msg)
            userLogging(
                f'Program Update ({VERSION} -> {newVersionName})')

            printStatus(parent, "버전 업데이트 중...")
            import subprocess
            downloadFile_path = os.path.join(
                'C:/Temp', f"MANAGER_{newVersionName}.exe")
            downloadFile(
                f"https://knpu.re.kr/download/MANAGER_{newVersionName}.exe", downloadFile_path)
            subprocess.Popen([downloadFile_path], shell=True)
            closeConsole()
            os._exit(0)

        if newVersionInfo:
            if get_setting('AutoUpdate') == 'auto':
                parent.closeBootscreen()
                update_process()

            dialog = QDialog(parent)
            dialog.setWindowTitle("New Version Released")
            dialog.resize(480, 420)

            layout = QVBoxLayout(dialog)

            # 유틸: 라벨 + 읽기전용 QTextEdit 추가
            from PyQt5.QtWidgets import QLabel, QTextEdit
            from PyQt5.QtGui import QFont

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
                # 보기 좋은 최소 높이
                metrics = edit.fontMetrics()
                edit.setMinimumHeight(metrics.lineSpacing() * min_lines + 12)
                layout.addWidget(edit)
                return edit

            # newVersionInfo: [versionNum, changeLog, features, status, releaseDate]
            ver  = str(newVersionInfo[0]) if len(newVersionInfo) > 0 else ""
            chg  = str(newVersionInfo[1]) if len(newVersionInfo) > 1 else ""
            feat = str(newVersionInfo[2]) if len(newVersionInfo) > 2 else ""
            rel  = str(newVersionInfo[-1]) if len(newVersionInfo) > 0 else ""

            add_field("Version Num", ver)
            add_field("Release Date", rel)
            add_field("ChangeLog", chg, monospace=True, min_lines=6)
            add_field("Version Features", feat, monospace=False, min_lines=4)

            # 버튼 영역 (기존 구조 유지)
            button_layout = QHBoxLayout()
            confirm_button = QPushButton("Update")
            cancel_button = QPushButton("Cancel")

            confirm_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)

            button_layout.addWidget(confirm_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)

            dialog.setLayout(layout)

            # 대화상자 실행
            if dialog.exec_() == QDialog.Accepted:
                update_process()
            else:
                QMessageBox.information(
                    parent, "Information", 'Ctrl+U 단축어로 프로그램 실행 중 업데이트 가능합니다'
                )
                return
        else:
            if sc == True:
                reply = QMessageBox.question(parent, "Reinstall", "현재 버전이 최신 버전입니다\n\n현재 버전을 재설치하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    printStatus(parent, "버전 재설치 중...")
                    openConsole("Version Reinstall Process")
                    import subprocess
                    downloadFile_path = os.path.join(
                        'C:/Temp', f"MANAGER_{newVersionName}.exe")
                    downloadFile(f"https://knpu.re.kr/download/MANAGER_{newVersionName}.exe",
                                 downloadFile_path)
                    subprocess.Popen([downloadFile_path], shell=True)
                    closeConsole()
                    os._exit(0)
                else:
                    return
            return
    except:
        programBugLog(parent, traceback.format_exc())
        reply = QMessageBox.question(parent, "Reinstall", "다운로드 웹페이지를 열어 수동 업데이트를 진행하시겠습니까?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            webbrowser.open("https://knpu.re.kr/download_manager")
        return
