from PyQt5.QtWidgets import QInputDialog, QMessageBox
from PyQt5.QtWidgets import QLineEdit
import re

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
        input_dialog.setTextEchoMode(QLineEdit.Password)
        input_dialog.resize(300, 200)  # 원하는 크기로 설정

        # 비밀번호 입력 창 띄우기
        ok = input_dialog.exec_()
        password = input_dialog.textValue()

        # 영어 알파벳만 있는지 확인
        if re.match("^[a-zA-Z0-9!@#$%^&*()_+=-]*$", password):
            return ok, password
        else:
            # 오류 메시지 표시
            QMessageBox.warning(parent, "Invalid Input", "영어로만 입력 가능합니다")