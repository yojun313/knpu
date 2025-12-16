from PyQt6.QtWidgets import QInputDialog, QMessageBox
from PyQt6.QtWidgets import QLineEdit
import re
import socket
import traceback
import requests

from config import MANAGER_SERVER_API
from ui.status import printStatus
from services.api import get_api_headers
from core.setting import get_setting, set_setting

def checkPassword(parent, admin=False, string=""):
    while True:
        input_dialog = QInputDialog(parent)
        if admin == False:
            if string == "":
                input_dialog.setWindowTitle('Password')
            else:
                input_dialog.setWindowTitle(string)
        else:
            input_dialog.setWindowTitle('Admin Mode')

        input_dialog.setLabelText('Enter password:')
        input_dialog.setTextEchoMode(QLineEdit.EchoMode.Password)
        input_dialog.resize(300, 200)

        ok = input_dialog.exec()
        password = input_dialog.textValue()

        if re.match("^[a-zA-Z0-9!@#$%^&*()_+=-]*$", password):
            return ok, password
        else:
            QMessageBox.warning(parent, "Invalid Input", "영어로만 입력 가능합니다")

def loginProgram(parent):
    try:
        parent.userDevice = socket.gethostname()

        # 이전에 발급된 토큰이 있는지 확인
        saved_token = get_setting('auth_token')

        if saved_token:
            res = requests.get(
                f"{MANAGER_SERVER_API}/auth/login", headers=get_api_headers())
            if res.status_code == 200:
                userData = res.json()['user']
                parent.user = userData['name']
                parent.userUid = userData['uid']
                parent.usermail = userData['email']
                return True

        parent.closeBootscreen()
        parent.show()
        printStatus(parent, "로그인 중...")

        while True:
            inputDialogId = QInputDialog(parent)
            inputDialogId.setWindowTitle('Login')
            inputDialogId.setLabelText('User Name:')
            inputDialogId.resize(300, 200)
            ok = inputDialogId.exec()
            userName = inputDialogId.textValue()

            if not ok:
                QMessageBox.warning(parent, 'Program Shutdown', '프로그램을 종료합니다')
                return False

            parent.user = userName

            res = requests.get(f"{MANAGER_SERVER_API}/auth/request",
                                params={"name": parent.user})
            if res.status_code == 404:
                reply = QMessageBox.question(parent, "Error", f"사용자 {parent.user}을(를) 찾을 수 없습니다\n\n다시 시도하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    continue
                else:
                    return False
            else:
                break
        
        email = res.json().get("email", "")
        printStatus(parent)
        QMessageBox.information(parent, "Information",
                                f"{parent.user}님의 {email}로 인증번호가 전송되었습니다\n\n"
                                "인증번호를 확인 후 입력하십시오")

        while True:
            ok, password = checkPassword(parent, string="메일 인증번호")
            if not ok:
                QMessageBox.warning(parent, 'Error', '프로그램을 종료합니다')
                return False
            res = requests.post(f"{MANAGER_SERVER_API}/auth/verify", params={"name": parent.user, "code": password, "device": parent.userDevice})
            if res.status_code != 200:
                reply = QMessageBox.question(parent, 'Error', '인증번호가 올바르지 않습니다\n\n다시 인증번호를 받으시겠습니까?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    res = requests.get(f"{MANAGER_SERVER_API}/auth/request", params={"name": parent.user})
                    QMessageBox.information(parent, "Information",
                                            f"{parent.user}님의 메일로 다시 인증번호가 전송되었습니다\n\n"
                                            "인증번호를 확인 후 입력하십시오")
                    continue
                else:
                    return False
            else:
                res = res.json()
                break
            
        userData = res['user']
        access_token = res['access_token']

        parent.user = userData['name']
        parent.usermail = userData['email']
        parent.userUid = userData['uid']
        
        QMessageBox.information(parent, "기기 등록 완료", f"{parent.user}님 환영합니다!") 
        set_setting('auth_token', access_token)

    except Exception:
        parent.closeBootscreen()
        QMessageBox.critical(parent, "Error",
                                f"오류가 발생했습니다.\n\nError Log: {traceback.format_exc()}")
        return False

