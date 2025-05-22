import os
import requests
import traceback
from libs.console import openConsole, closeConsole
from services.pushover import sendPushOver
from services.logging import userLogging, getUserLocation
from ui.status import printStatus
from config import VERSION
from core.setting import get_setting
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QMessageBox
from PyQt5.QtCore import Qt
from core.boot import checkNewVersion


def updateProgram(parent, sc=False):
    try:
        newVersionInfo = checkNewVersion()
        if not newVersionInfo:
            newVersionName = VERSION

        def downloadFile(download_url, local_filename):
            try:
                response = requests.get(download_url, stream=True)
                totalSize = int(response.headers.get(
                    'content-length', 0))  # 파일의 총 크기 가져오기
                chunkSize = 8192  # 8KB씩 다운로드
                downloadSize = 0  # 다운로드된 크기 초기화

                with open(local_filename, 'wb') as f:
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
            except:
                closeConsole()
                parent.QMessageBox.critical(parent, "Error", "다운로드 중 오류가 발생했습니다\n\n관리자에게 문의하십시오")
                return False

        def update_process():
            openConsole("Version Update Process")
            msg = (
                "[ Admin Notification ]\n\n"
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

            version_info_html = parent.style_html + f"""
                <table>
                    <tr><th>Item</th><th>Details</th></tr>
                    <tr><td><b>Version Num:</b></td><td>{newVersionInfo[0]}</td></tr>
                    <tr><td><b>Release Date:</b></td><td>{newVersionInfo[-1]}</td></tr>
                    <tr><td><b>ChangeLog:</b></td><td>{newVersionInfo[1]}</td></tr>
                    <tr><td><b>Version Features:</b></td><td>{newVersionInfo[2]}</td></tr>
                    <tr><td><b>Version Status:</b></td><td>{newVersionInfo[3]}</td></tr>
                </table>
            """

            dialog = QDialog(parent)
            dialog.setWindowTitle(f"New Version Released")
            dialog.resize(350, 250)

            layout = QVBoxLayout()

            label = QLabel()
            label.setText(version_info_html)
            label.setWordWrap(True)
            label.setTextFormat(Qt.RichText)  # HTML 렌더링

            layout.addWidget(label, alignment=Qt.AlignHCenter)

            button_layout = QHBoxLayout()  # 수평 레이아웃

            # confirm_button과 cancel_button의 크기가 창의 너비에 맞게 비례하도록 설정
            confirm_button = QPushButton("Update")
            cancel_button = QPushButton("Cancel")

            # 버튼 클릭 이벤트 연결
            confirm_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)

            # 버튼 사이에 간격 추가
            button_layout.addWidget(confirm_button)
            button_layout.addWidget(cancel_button)

            layout.addLayout(button_layout)  # 버튼 레이아웃을 메인 레이아웃에 추가

            dialog.setLayout(layout)

            # 대화상자 실행
            if dialog.exec_() == QDialog.Accepted:
                update_process()
            else:
                QMessageBox.information(
                    parent, "Information", 'Ctrl+U 단축어로 프로그램 실행 중 업데이트 가능합니다')
                return
        else:
            if sc == True:
                reply = QMessageBox.question(parent, "Reinstall", "현재 버전이 최신 버전입니다\n\n현재 버전을 재설치하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
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
        print(traceback.format_exc())
        return
