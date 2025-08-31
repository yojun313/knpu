import warnings
import traceback
from PyQt5.QtWidgets import QMessageBox
import bcrypt
from ui.table import *
from core.shortcut import *
from config import *
from services.api import *
from services.logging import *
from services.auth import *

warnings.filterwarnings("ignore")


class Manager_User:
    def __init__(self, main_window):
        self.main = main_window
        self.refreshUserTable()
        self.matchButton()

    def refreshUserTable(self):
        # 데이터베이스 연결 및 데이터 가져오기

        self.user_list = Request('get', '/users').json()['data']
        user_data = [(user['name'], user['email'], user['pushoverKey'])
                     for user in self.user_list]
        self.userNameList = [user['name'] for user in self.user_list]
        # userNameList 및 userKeyList 업데이트
        self.userKeyList = [user['pushoverKey']
                            for user in self.user_list if user['pushoverKey'] != 'n']

        # 테이블 설정
        columns = ['Name', 'Email', 'PushOverKey']
        makeTable(
            self.main,
            widgetname=self.main.user_tablewidget,
            data=user_data,
            column=columns,
        )

    def addUser(self):
        try:
            name = self.main.userName_lineinput.text()
            email = self.main.user_email_lineinput.text()
            key = self.main.user_key_lineinput.text()

            if self.main.user != 'admin':
                ok, password = checkPassword(self.main, True)
                if not ok or bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')) == False:
                    return

            reply = QMessageBox.question(
                self.main, 'Confirm Add', f"{name}님을 추가하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                data = {
                    'name': name,
                    'email': email,
                    'pushoverKey': key
                }
                response = Request('post', '/users/add', json=data)
                self.refreshUserTable()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def deleteUser(self):
        try:
            if self.main.user != 'admin':
                ok, password = checkPassword(self.main, True)
                if not ok or bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')) == False:
                    return

            selectedRow = self.main.user_tablewidget.currentRow()
            if selectedRow >= 0:
                selectedUser = self.user_list[selectedRow]
                reply = QMessageBox.question(
                    self.main, 'Confirm Delete', f"{selectedUser['name']}님을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    response = Request(
                        'delete', f'/users/{selectedUser['uid']}')
                    if response.status_code == 200:
                        QMessageBox.information(
                            self.main, "Information", f"'{selectedUser['name']}'님이 삭제되었습니다")
                        self.refreshUserTable()
                    else:
                        QMessageBox.warning(
                            self.main, "Error", f"'{selectedUser['name']}'님을 삭제할 수 없습니다")

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def matchButton(self):
        self.main.user_adduser_button.clicked.connect(self.addUser)
        self.main.user_deleteuser_button.clicked.connect(self.deleteUser)

        self.main.user_adduser_button.setToolTip("Ctrl+A")
        self.main.user_deleteuser_button.setToolTip("Ctrl+D")

    def user_shortcut_setting(self):
        self.updateShortcut(0)
        self.main.tabWidget_user.currentChanged.connect(self.updateShortcut)

    def updateShortcut(self, index):
        resetShortcuts(self.main)

        # User List
        if index == 0:
            self.main.ctrld.activated.connect(self.deleteUser)
            self.main.cmdd.activated.connect(self.deleteUser)
