import os
import re
import gc
import traceback
import platform
import socket
import sys
from pathlib import Path
from datetime import datetime
from packaging import version

from PyQt6 import uic
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox, QMainWindow, QPushButton, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QTimer, QUrl

from config import VERSION, ASSETS_PATH
from libs.console import openConsole, closeConsole
from pages.page_analysis import Manager_Analysis
from pages.page_user import Manager_User
from pages.page_board import Manager_Board
from pages.page_web import Manager_Web
from pages.page_database import Manager_Database
from pages.page_settings import Manager_Setting
from core.boot import (
    initListIcon, initStatusbar,
    checkNetwork, checkNewPost, checkNewVersion, getVersionInfo
)
from core.shortcut import initShortcut, resetShortcuts
from core.setting import get_setting, set_setting
from services.crawldb import updateDB
from services.pushover import sendPushOver
from services.update import updateProgram
from services.logging import userLogging, getUserLocation
from services.auth import loginProgram
from ui.style import theme_option
from ui.status import printStatus, changeStatusbarAction
from ui.dialogs import ViewVersionDialog

class MainWindow(QMainWindow):

    def __init__(self, splashDialog):
        try:
            self.splashDialog = splashDialog

            super(MainWindow, self).__init__()
            uiPath = os.path.join(ASSETS_PATH,  'gui.ui')
            iconPath = os.path.join(ASSETS_PATH, 'exe_icon.png')
            
            uic.loadUi(uiPath, self)
            initListIcon(self)
            initStatusbar(self)

            self.setWindowTitle("MANAGER")  # 창의 제목 설정
            self.setWindowIcon(QIcon(iconPath))
            self.resize(1400, 1000)
            self.set_web_layout()
            
            try:
                self.listWidget.setCurrentRow(0)
                if get_setting('BootTerminal') == 'on': openConsole("Boot Process")
                self.startTime = datetime.now()
                checkNetwork(self.splashDialog)
                self.listWidget.currentRowChanged.connect(self.display)
                self._resolve_app_paths()

                self.networkText = (
                    "\n\n[ DB 접속 반복 실패 시... ]\n"
                    "\n1. Wi-Fi 또는 유선 네트워크가 정상적으로 동작하는지 확인하십시오"
                    "\n2. 네트워크 호환성에 따라 DB 접속이 불가능한 경우가 있습니다. 다른 네트워크 연결을 시도해보십시오\n"
                )
                
                # User Checking & Login Process
                print("\nI. Checking User... ", end='')
                self.splashDialog.updateStatus("Checking User")
                if loginProgram(self) == False:
                    QApplication.quit()
                    sys.exit(0)
                print("Done")

                self.splashDialog.updateStatus("Loading Data")
                print("\nII. Loading Data... ", end='')

                self.DB = updateDB(self)
                self.managerWebObj = Manager_Web(self)
                self.managerBoardObj = Manager_Board(self)
                self.managerUserObj = Manager_User(self)
                self.managerDatabaseObj = Manager_Database(self)
                self.managerAnalysisObj = Manager_Analysis(self)
                print("Done")
                
                self.splashDialog.updateStatus("Checking New Version")
                print("\nIII. Checking New Version... ", end='')
                if checkNewVersion():
                    self.closeBootscreen()
                    updateProgram(self)
                print("Done")

                self.splashDialog.updateStatus(f"안녕하세요, {self.user}님!")
                print(f"\n{self.user}님 환영합니다!")

                initShortcut(self)
                self.managerDatabaseObj.setDatabaseShortcut()
                userLogging(f'Booting ({getUserLocation(self)})')

                if get_setting('BootTerminal') == 'on': closeConsole()
                self.closeBootscreen()
                self.show()

                if get_setting('ScreenSize') == 'max':
                    self.showMaximized()
                printStatus(self, f"{self.fullStorage} GB / 2 TB")

                # After Booting
                self.showNewVersionInfo()
                self.showNewPostInfo()

            except Exception as e:
                print("Failed")
                print(traceback.format_exc())
                self.closeBootscreen()
                printStatus(self)
                msg = f'[ CRITICAL ]\n\nThere is Error in MANAGER Booting\n\nPC: {socket.gethostname()}\n\nError Log: {traceback.format_exc()}'
                sendPushOver(msg)
                QMessageBox.critical(self, "Error", f"부팅 과정에서 오류가 발생했습니다\n\nError Log: {traceback.format_exc()}")
                
                if checkNewVersion():
                    self.closeBootscreen()
                    updateProgram(self)
                
                QMessageBox.information(
                    self, "Information", f"관리자에게 에러 상황과 로그가 전달되었습니다\n\n프로그램을 종료합니다")
                QApplication.quit()
                sys.exit(0)

        except Exception as e:
            self.closeBootscreen()
            openConsole()
            print(traceback.format_exc())
    
    
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.centerWindow)

    def centerWindow(self):
        screen = self.screen() or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(geo.center())
        self.move(frame.topLeft())
        
    def _resolve_app_paths(self):
        # 유저 문서 폴더 안에 MANAGER 생성
        documents_dir = Path.home() / "Documents" / "MANAGER"
        documents_dir.mkdir(parents=True, exist_ok=True)
        self.localDirectory = str(documents_dir)

        # 프로그램 설치/동작 경로 구분
        if platform.system() == "Windows":
            # PyInstaller 실행 환경 고려
            if getattr(sys, 'frozen', False):
                base_dir = Path(os.getenv("LOCALAPPDATA")) / "MANAGER"
            else:
                base_dir = Path(os.getenv("APPDATA")) / "MANAGER"
        else:
            # macOS / Linux 공통
            if getattr(sys, 'frozen', False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).resolve().parent

        base_dir.mkdir(parents=True, exist_ok=True)
        self.programDirectory = str(base_dir)

    ################################## Booting ##################################
    def set_web_layout(self):
        self.browser = QWebEngineView()
        self.web_layout = QVBoxLayout()
        self.web_layout.addWidget(self.browser)
        self.tab_webview.setLayout(self.web_layout)
    
    def showNewVersionInfo(self):
        # Show New Version Info
        lastVersion = version.parse(get_setting('LastVersion'))
        
        # 최신 버전으로 업데이트 되었을 때
        if version.parse(VERSION) > lastVersion:
            newVersionInfo = getVersionInfo(VERSION)
            version_data = [
                str(newVersionInfo['versionName']),
                str(newVersionInfo['releaseDate']),
                str(newVersionInfo['changeLog']),
                str(newVersionInfo['features']),
                str(newVersionInfo['details'])
            ]
            set_setting('LastVersion', VERSION)
            dialog = ViewVersionDialog(self, version_data, title = f"새로운 버전으로 업데이트되었습니다")
            confirm_btn = QPushButton("확인")
            confirm_btn.clicked.connect(dialog.accept)
            dialog.add_buttons(confirm_btn)
            dialog.exec()
    
    def showNewPostInfo(self):
        newpost = checkNewPost(self)
        if newpost == True:
            reply = QMessageBox.question(
                self, "New Post", "새로운 게시물이 업로드되었습니다\n\n확인하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.managerBoardObj.viewPost(selectedRow=0)
    
    def closeBootscreen(self):
        try:
            self.splashDialog.accept()
        except:
            print(traceback.format_exc())

    def display(self, index):
        if index != 6:
            self.stackedWidget.setCurrentIndex(index)

        # DATABASE
        if index == 0:
            self.managerDatabaseObj.setDatabaseShortcut()
            if get_setting('DB_Refresh') == 'default':
                self.managerDatabaseObj.refreshDB()
            printStatus(self, f"{self.fullStorage} GB / 2 TB")
            changeStatusbarAction(self, "DATABASE")
        # CRAWLER
        elif index == 1:
            printStatus(self, f"활성 크롤러 수: {self.activeCrawl}")
            self.managerWebObj.web_open_crawler()
            changeStatusbarAction(self)
            resetShortcuts(self)
        # ANALYSIS
        elif index == 2:
            printStatus(self)
            changeStatusbarAction(self, "ANALYSIS")
            self.managerAnalysisObj.analysis_shortcut_setting()
        # BOARD
        elif index == 3:
            printStatus(self)
            changeStatusbarAction(self)
            self.managerBoardObj.setBoardShortcut()
        # WEB
        elif index == 4:
            printStatus(self, "https://knpu.re.kr/publications")
            changeStatusbarAction(self, "WEB")
            self.managerWebObj.setWebShortcut()
        # USER
        elif index == 5:
            printStatus(self)
            self.managerUserObj.user_shortcut_setting()
        
        # SETTING
        elif index == 6:
            userLogging(f'User Setting')
            dialog = Manager_Setting(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                QMessageBox.information(self, "Information", f"설정이 완료되었습니다")
                printStatus(self, "설정 반영 중...")
                QApplication.instance().setStyleSheet(theme_option[get_setting('Theme')])
                self.managerDatabaseObj.refreshDB()
                printStatus(self)
            previous_index = self.stackedWidget.currentIndex()  # 현재 활성 화면의 인덱스
            self.listWidget.setCurrentRow(previous_index)  # 선택 상태를 이전 인덱스로 변경

        gc.collect()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Shutdown', "프로그램을 종료하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                userLogging('Shutdown')
                self.cleanUpTemp()
            except Exception as e:
                print(traceback.format_exc())
                
            QApplication.quit()
            event.accept() 
        else:
            event.ignore()

    def cleanUpTemp(self):
        if platform.system() != "Windows":
            return
        try:
            # 이전 설치 exe 정리
            exe_dir = Path(os.getenv("LOCALAPPDATA")) / "MANAGER"
            exe_dir.mkdir(exist_ok=True)

            pattern = re.compile(r"MANAGER_(\d+\.\d+\.\d+)\.exe")
            current_ver = version.Version(VERSION)

            for file in exe_dir.iterdir():
                match = pattern.match(file.name)
                if match:
                    file_ver = version.Version(match.group(1))
                    if file_ver != current_ver:
                        try:
                            file.unlink()
                            print(f"[Cleanup] removed old installer: {file}")
                        except Exception as e:
                            print(f"[Cleanup] failed to remove: {file} -> {e}")

        except Exception as e:
            print(f"[Cleanup ERROR] {e}")

    def updateProgram(self, sc=False):  
        updateProgram(self, sc)