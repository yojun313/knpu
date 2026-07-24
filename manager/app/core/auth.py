from PySide6.QtWidgets import QInputDialog, QMessageBox, QDialog, QVBoxLayout, QLineEdit
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
import socket
import traceback
import requests
from config import HOMEPAGE_URL
from ui.status import printStatus
from services.api import get_api_headers
from core.setting import get_setting, set_setting


class WebLoginDialog(QDialog):
    """knpu.re.kr 로그인 페이지를 임베디드 브라우저로 띄우고, 로그인 성공 시
    발급되는 session 쿠키(JWT)를 가로채 MANAGER 앱의 인증 토큰으로 재사용한다.
    (기존 page_web.py의 web_open_crawler가 쓰던 embedded QWebEngineView와 같은 패턴)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KNPU 로그인")
        self.resize(480, 720)
        self.token = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        layout.addWidget(self.view)

        cookie_store = self.view.page().profile().cookieStore()
        cookie_store.cookieAdded.connect(self._on_cookie_added)

        self.view.setUrl(QUrl(f"{HOMEPAGE_URL}/login?client=manager"))

    def _on_cookie_added(self, cookie):
        name = bytes(cookie.name()).decode("utf-8", "ignore")
        if name != "session":
            return
        domain = cookie.domain()
        if not domain.endswith("knpu.re.kr"):
            return

        self.token = bytes(cookie.value()).decode("utf-8", "ignore")
        self.accept()


def _fetch_profile(parent) -> bool:
    """저장된(또는 방금 발급된) 토큰으로 knpu.re.kr 프로필을 조회해 parent에 채운다."""
    res = requests.get(f"{HOMEPAGE_URL}/api/auth/me", headers=get_api_headers())
    if res.status_code != 200:
        return False

    userData = res.json()
    parent.user = userData["name"]
    parent.userUid = userData["uid"]
    parent.usermail = userData["email"]
    parent.user_role = userData["role"]
    return True


def loginProgram(parent):
    try:
        parent.userDevice = socket.gethostname()

        # 이전에 발급된 토큰이 있으면 유효성만 확인
        if get_setting("auth_token") and _fetch_profile(parent):
            return True

        parent.closeBootscreen()
        parent.show()
        printStatus(parent, "로그인 중...")

        dialog = WebLoginDialog(parent)
        result = dialog.exec()

        if result != QDialog.DialogCode.Accepted or not dialog.token:
            printStatus(parent)
            QMessageBox.warning(parent, "Program Shutdown", "로그인이 취소되어 프로그램을 종료합니다")
            return False

        set_setting("auth_token", dialog.token)

        if not _fetch_profile(parent):
            printStatus(parent)
            QMessageBox.critical(parent, "Error", "로그인 정보를 확인할 수 없습니다")
            return False

        QMessageBox.information(parent, "로그인 완료", f"{parent.user}님 환영합니다!")
        printStatus(parent, "Loading...")
        return True

    except Exception:
        parent.closeBootscreen()
        QMessageBox.critical(
            parent,
            "Error",
            f"오류가 발생했습니다.\n\nError Log: {traceback.format_exc()}",
        )
        return False


def verifyAdmin(parent) -> bool:
    """관리자 전용 동작을 수행하기 전, 관리자 본인의 knpu.re.kr 아이디/비밀번호로
    권한을 확인한다 (예전의 공용 하드코딩 비밀번호 방식을 대체)."""
    id_dialog = QInputDialog(parent)
    id_dialog.setWindowTitle("Admin Mode")
    id_dialog.setLabelText("관리자 아이디:")
    id_dialog.resize(300, 200)
    if not id_dialog.exec():
        return False
    username = id_dialog.textValue().strip()
    if not username:
        return False

    pw_dialog = QInputDialog(parent)
    pw_dialog.setWindowTitle("Admin Mode")
    pw_dialog.setLabelText("관리자 비밀번호:")
    pw_dialog.setTextEchoMode(QLineEdit.EchoMode.Password)
    pw_dialog.resize(300, 200)
    if not pw_dialog.exec():
        return False
    password = pw_dialog.textValue()

    try:
        res = requests.post(
            f"{HOMEPAGE_URL}/api/auth/login",
            json={"username": username, "password": password},
        )
    except Exception:
        QMessageBox.warning(parent, "Error", "서버와 통신할 수 없습니다")
        return False

    if res.status_code != 200 or res.json().get("user", {}).get("role") != "admin":
        QMessageBox.warning(parent, "Access Denied", "관리자 인증에 실패했습니다")
        return False

    return True


def accessCheck(parent, exclude=[]):
    if parent.user in exclude:
        QMessageBox.critical(
            parent, "Access Denied", "이 기능에 대한 액세스 권한이 없습니다"
        )
        return False
    return True
