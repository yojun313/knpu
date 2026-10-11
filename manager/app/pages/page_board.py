import traceback
import warnings
from PySide6.QtWidgets import QMessageBox
from config import VERSION
from ui.table import makeTable
from services.api import Request
from services.logging import programBugLog, printStatus
from core.shortcut import resetShortcuts
from core.auth import verifyAdmin

warnings.filterwarnings("ignore")


class Manager_Board:
    def __init__(self, main_window):
        self.main = main_window
        self.refreshVersionBoard()
        self.refreshBugBoard()
        self.refreshPostBoard()
        self.refreshSuggestionBoard()
        self.matchButton()
        self.main.tabWidget_board.currentChanged.connect(self.updateShortcut)

    def refreshVersionBoard(self):
        try:
            self.version_data = Request("get", "/board/version").json()["data"]
            self.version_data_for_table = [
                [
                    data["versionName"],
                    data["releaseDate"],
                    data["changeLog"],
                    data["features"],
                    data["publisher"],
                ]
                for data in self.version_data
            ]
            self.version_table_column = [
                "Version Num",
                "Release Date",
                "ChangeLog",
                "Version Features",
                "Publisher",
            ]
            makeTable(
                self.main,
                self.main.board_version_tableWidget,
                self.version_data_for_table,
                self.version_table_column,
            )
            self.version_name_list = [data["versionName"] for data in self.version_data]

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def addVersion(self):
        try:
            if self.main.user_role != "admin":
                if not verifyAdmin(self.main):
                    return

            from ui.dialogs import AddVersionDialog

            dialog = AddVersionDialog(VERSION)
            dialog.exec()

            if dialog.data:
                json_data = dialog.data
                # 새 버전은 항상 디스코드로 공지되므로 별도 확인창 없음
                Request("post", "/board/version/add", json=json_data)
            self.refreshVersionBoard()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def editVersion(self):
        try:
            if self.main.user_role != "admin":
                if not verifyAdmin(self.main):
                    return

            selectedRow = self.main.board_version_tableWidget.currentRow()
            if selectedRow < 0:
                return

            origin = self.version_data[selectedRow]

            # Edit Dialog 열기
            from ui.dialogs import EditVersionDialog

            dialog = EditVersionDialog(origin)
            dialog.exec()

            if dialog.data:
                version_data = dialog.data

                Request(
                    "put", f"/board/version/{origin['versionName']}", json=version_data
                )
                QMessageBox.information(
                    self.main,
                    "완료",
                    f"{version_data['versionName']} 수정 완료했습니다",
                )
                self.refreshVersionBoard()

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteVersion(self):
        try:
            if self.main.user_role != "admin":
                if not verifyAdmin(self.main):
                    return

            selectedRow = self.main.board_version_tableWidget.currentRow()
            if selectedRow >= 0:
                reply = QMessageBox.question(
                    self.main,
                    "Confirm Delete",
                    "정말 삭제하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    version = self.version_name_list[selectedRow]
                    Request("delete", f"/board/version/{version}")

            self.refreshVersionBoard()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def viewVersion(self):
        try:
            selectedRow = self.main.board_version_tableWidget.currentRow()
            if selectedRow >= 0:
                printStatus(self.main, "불러오는 중...")
                version_data = self.version_data[selectedRow]
                printStatus(self.main)

                from ui.dialogs import ViewVersionDialog

                dialog = ViewVersionDialog(self.main, version_data)
                dialog.exec()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def refreshBugBoard(self):
        try:
            self.bug_data = Request("get", "/board/bug").json()["data"]
            self.bug_data_for_table = [
                [
                    sub_list["writerName"],
                    sub_list["versionName"],
                    sub_list["bugTitle"],
                    "답변 있음" if sub_list.get("replyCount", 0) else "답변 대기",
                    sub_list["datetime"],
                ]
                for sub_list in self.bug_data
            ]
            self.bug_table_column = ["User", "Version Num", "Title", "답변", "DateTime"]
            makeTable(
                self.main,
                self.main.board_bug_tableWidget,
                self.bug_data_for_table,
                self.bug_table_column,
            )

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def addBug(self):
        try:
            # QDialog를 상속받은 클래스 생성
            from ui.dialogs import AddBugDialog

            dialog = AddBugDialog(self.main, VERSION)
            dialog.exec()

            if dialog.data:
                json_data = dialog.data
                json_data["writerUid"] = self.main.userUid
                json_data["programLog"] = ""
                Request("post", "/board/bug/add", json=json_data)
                self.refreshBugBoard()
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def deleteBug(self):
        try:
            selectedRow = self.main.board_bug_tableWidget.currentRow()
            if selectedRow >= 0:
                bug = self.bug_data[selectedRow]

                if (
                    bug["writerUid"] == self.main.userUid
                    or self.main.user_role == "admin"
                ):
                    reply = QMessageBox.question(
                        self.main,
                        "Confirm Delete",
                        "정말 삭제하시겠습니까?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        printStatus(self.main, "삭제 중...")
                        Request("delete", f"/board/bug/{bug['uid']}")
                        self.refreshBugBoard()
                        printStatus(self.main)
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"작성자만 삭제할 수 있습니다"
                    )
                    return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def viewBug(self):
        try:
            selectedRow = self.main.board_bug_tableWidget.currentRow()
            if selectedRow >= 0:
                printStatus(self.main, "불러오는 중...")
                bug_data = Request(
                    "get", f"/board/bug/{self.bug_data[selectedRow]['uid']}"
                ).json()["data"]
                printStatus(self.main)
                from ui.dialogs import ViewBugDialog

                dialog = ViewBugDialog(self.main, bug_data)
                dialog.exec()
                self.refreshBugBoard()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def refreshVersionBoard(self):
        try:
            self.version_data = Request("get", "/board/version").json()["data"]
            self.version_data_for_table = [
                [
                    data["versionName"],
                    data["releaseDate"],
                    data["changeLog"],
                    data["features"],
                    data["publisher"],
                ]
                for data in self.version_data
            ]
            self.version_table_column = [
                "Version Num",
                "Release Date",
                "ChangeLog",
                "Version Features",
                "Publisher",
            ]
            makeTable(
                self.main,
                self.main.board_version_tableWidget,
                self.version_data_for_table,
                self.version_table_column,
            )
            self.version_name_list = [data["versionName"] for data in self.version_data]

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def refreshPostBoard(self):
        try:
            self.post_data = Request("get", "/board/post").json()["data"]
            self.post_data_for_table = [
                [
                    sub_list["writerName"],
                    sub_list["title"],
                    sub_list["datetime"],
                    str(sub_list["viewCnt"]),
                ]
                for sub_list in self.post_data
            ]
            self.post_table_column = ["User", "Title", "DateTime", "View Count"]
            makeTable(
                self.main,
                self.main.board_post_tableWidget,
                self.post_data_for_table,
                self.post_table_column,
            )
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def addPost(self):
        try:
            from ui.dialogs import AddPostDialog

            dialog = AddPostDialog(self.main)
            dialog.exec()

            if dialog.data:
                json_data = dialog.data
                json_data["writerUid"] = self.main.userUid
                json_data["broadcastNotify"] = False

                reply = QMessageBox.question(
                    self.main,
                    "Confirm Notification",
                    "현재 게시글에 대한 전체 알림을 전송하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    json_data["broadcastNotify"] = True

                Request("post", "/board/post/add", json=json_data)
                self.refreshPostBoard()
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def viewPost(self, new=False):
        try:
            selectedRow = self.main.board_post_tableWidget.currentRow()
            if new:
                selectedRow = 0

            if selectedRow >= 0:
                print(f"Selected Row: {selectedRow}")
                printStatus(self.main, "불러오는 중...")
                post_data = self.post_data[selectedRow]

                post_data = Request("get", f"/board/post/{post_data['uid']}").json()[
                    "data"
                ]
                printStatus(self.main)

                from ui.dialogs import ViewPostDialog

                dialog = ViewPostDialog(self.main, post_data)
                dialog.exec()
                self.refreshPostBoard()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def deletePost(self):
        try:
            selectedRow = self.main.board_post_tableWidget.currentRow()
            if selectedRow >= 0:
                post = self.post_data[selectedRow]

                if (
                    post["writerUid"] == self.main.userUid
                    or self.main.user_role == "admin"
                ):
                    reply = QMessageBox.question(
                        self.main,
                        "Confirm Delete",
                        "정말 삭제하시겠습니까?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        printStatus(self.main, "삭제 중...")
                        Request("delete", f"/board/post/{post['uid']}")
                        self.refreshPostBoard()
                        printStatus(self.main)
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"작성자만 삭제할 수 있습니다"
                    )
                    return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def editPost(self):
        try:
            selectedRow = self.main.board_post_tableWidget.currentRow()
            if selectedRow >= 0:
                post = self.post_data[selectedRow]
                postUid = post["uid"]
                if (
                    post["writerUid"] == self.main.userUid
                    or self.main.user_role == "admin"
                ):
                    prev_post_data = self.post_data[selectedRow]

                    from ui.dialogs import EditPostDialog

                    dialog = EditPostDialog(prev_post_data)
                    dialog.exec()

                    if dialog.data:
                        json_data = dialog.data
                        json_data["writerUid"] = self.main.userUid
                        json_data["broadcastNotify"] = False

                        Request("put", f"/board/post/{postUid}", json=json_data)
                        self.refreshPostBoard()
                        QMessageBox.information(
                            self.main, "Information", f"게시물이 수정되었습니다"
                        )
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"비밀번호가 일치하지 않습니다"
                    )
                    printStatus(self.main)
                    return
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def suggestionError(self, error):
        from services.api import handle_permission_error

        if handle_permission_error(self.main, error):
            return
        message = "요청을 처리하지 못했습니다. 연결 상태를 확인하고 다시 시도해주세요."
        response = getattr(error, "response", None)
        if response is not None:
            try:
                detail = response.json().get("detail")
                if isinstance(detail, str):
                    message = detail
            except (ValueError, AttributeError):
                pass
        QMessageBox.warning(self.main, "건의·제안사항", message)

    def refreshSuggestionBoard(self):
        try:
            self.suggestion_data = Request(
                "get", "/board/suggestion", timeout=30
            ).json()["data"]
            categories = {
                "feature": "기능 추가",
                "workflow": "사용 방법 개선",
                "other": "기타 제안",
            }
            statuses = {
                "new": "접수",
                "reviewing": "검토 중",
                "planned": "반영 예정",
                "done": "반영 완료",
                "declined": "보류",
            }
            rows = [
                [
                    d.get("writerName", ""),
                    categories.get(d.get("category"), "기타 제안"),
                    d.get("title", ""),
                    statuses.get(d.get("status"), "접수"),
                    d.get("datetime", ""),
                    str(d.get("commentCount", 0)),
                ]
                for d in self.suggestion_data
            ]
            makeTable(
                self.main,
                self.main.board_suggestion_tableWidget,
                rows,
                ["작성자", "제안 유형", "제목", "검토 상태", "작성일", "댓글"],
            )
            self.main.board_suggestion_tableWidget.itemDoubleClicked.disconnect()
            self.main.board_suggestion_tableWidget.itemDoubleClicked.connect(
                lambda _: self.viewSuggestion()
            )
        except Exception as error:
            self.suggestion_data = []
            self.suggestionError(error)

    def selectedSuggestion(self):
        row = self.main.board_suggestion_tableWidget.currentRow()
        return (
            self.suggestion_data[row] if 0 <= row < len(self.suggestion_data) else None
        )

    def addSuggestion(self):
        try:
            from ui.dialogs import SuggestionEditorDialog

            dialog = SuggestionEditorDialog(self.main)
            dialog.exec()
            if dialog.data:
                Request("post", "/board/suggestion/add", json=dialog.data, timeout=30)
                self.refreshSuggestionBoard()
        except Exception as error:
            self.suggestionError(error)

    def viewSuggestion(self):
        doc = self.selectedSuggestion()
        if not doc:
            return
        try:
            from ui.dialogs import ViewPostDialog

            detail = Request(
                "get", f"/board/suggestion/{doc['uid']}", timeout=30
            ).json()["data"]
            dialog = ViewPostDialog(self.main, detail, kind="suggestion")
            dialog.exec()
            self.refreshSuggestionBoard()
        except Exception as error:
            self.suggestionError(error)

    def editSuggestion(self):
        doc = self.selectedSuggestion()
        if not doc:
            return
        if doc.get("writerUid") != self.main.userUid and self.main.user_role != "admin":
            QMessageBox.warning(
                self.main, "권한 없음", "작성자 또는 관리자만 수정할 수 있습니다."
            )
            return
        try:
            from ui.dialogs import SuggestionEditorDialog

            detail = Request(
                "get", f"/board/suggestion/{doc['uid']}", timeout=30
            ).json()["data"]
            dialog = SuggestionEditorDialog(self.main, detail)
            dialog.exec()
            if dialog.data:
                Request(
                    "put",
                    f"/board/suggestion/{doc['uid']}",
                    json=dialog.data,
                    timeout=30,
                )
                self.refreshSuggestionBoard()
        except Exception as error:
            self.suggestionError(error)

    def deleteSuggestion(self):
        doc = self.selectedSuggestion()
        if not doc:
            return
        if doc.get("writerUid") != self.main.userUid and self.main.user_role != "admin":
            QMessageBox.warning(
                self.main, "권한 없음", "작성자 또는 관리자만 삭제할 수 있습니다."
            )
            return
        if (
            QMessageBox.question(
                self.main,
                "제안 삭제",
                "이 제안을 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            Request("delete", f"/board/suggestion/{doc['uid']}", timeout=30)
            self.refreshSuggestionBoard()
        except Exception as error:
            self.suggestionError(error)

    def matchButton(self):
        for name, method, shortcut in (
            ("add", self.addSuggestion, "A"),
            ("edit", self.editSuggestion, "E"),
            ("delete", self.deleteSuggestion, "D"),
            ("detail", self.viewSuggestion, "V"),
        ):
            button = getattr(self.main, f"board_{name}suggestion_button")
            button.clicked.connect(method)
            button.setToolTip(f"Ctrl+{shortcut} / Cmd+{shortcut}")
        self.main.board_addversion_button.clicked.connect(self.addVersion)
        self.main.board_deleteversion_button.clicked.connect(self.deleteVersion)
        self.main.board_editversion_button.clicked.connect(self.editVersion)
        self.main.board_detailversion_button.clicked.connect(self.viewVersion)

        self.main.board_addbug_button.clicked.connect(self.addBug)
        self.main.board_deletebug_button.clicked.connect(self.deleteBug)
        self.main.board_detailbug_button.clicked.connect(self.viewBug)

        self.main.board_addpost_button.clicked.connect(self.addPost)
        self.main.board_detailpost_button.clicked.connect(self.viewPost)
        self.main.board_deletepost_button.clicked.connect(self.deletePost)
        self.main.board_editpost_button.clicked.connect(self.editPost)

        self.main.board_deleteversion_button.setToolTip("Ctrl+D")
        self.main.board_addversion_button.setToolTip("Ctrl+A")
        self.main.board_detailversion_button.setToolTip("Ctrl+V")
        self.main.board_editversion_button.setToolTip("Ctrl+E")
        self.main.board_addbug_button.setToolTip("Ctrl+A")
        self.main.board_deletebug_button.setToolTip("Ctrl+D")
        self.main.board_detailbug_button.setToolTip("Ctrl+V")
        self.main.board_addpost_button.setToolTip("Ctrl+A")
        self.main.board_detailpost_button.setToolTip("Ctrl+V")
        self.main.board_deletepost_button.setToolTip("Ctrl+D")
        self.main.board_editpost_button.setToolTip("Ctrl+E")

    def setBoardShortcut(self):
        self.updateShortcut(self.main.tabWidget_board.currentIndex())

    def updateShortcut(self, index):
        if (
            not getattr(self.main, "_pages_ready", False)
            or self.main.stackedWidget.currentIndex() != 3
        ):
            return
        resetShortcuts(self.main)

        # 패치 노트 탭
        if index == 0:
            self.main.ctrld.activated.connect(self.deleteVersion)
            self.main.ctrlv.activated.connect(self.viewVersion)
            self.main.ctrla.activated.connect(self.addVersion)
            self.main.ctrle.activated.connect(self.editVersion)

            self.main.cmdd.activated.connect(self.deleteVersion)
            self.main.cmdv.activated.connect(self.viewVersion)
            self.main.cmda.activated.connect(self.addVersion)
            self.main.cmde.activated.connect(self.editVersion)

        # 버그 리포트 탭
        if index == 1:
            self.main.ctrld.activated.connect(self.deleteBug)
            self.main.ctrlv.activated.connect(self.viewBug)
            self.main.ctrla.activated.connect(self.addBug)

            self.main.cmdd.activated.connect(self.deleteBug)
            self.main.cmdv.activated.connect(self.viewBug)
            self.main.cmda.activated.connect(self.addBug)

        # 자유 게시판 탭
        if index == 2:
            self.main.ctrld.activated.connect(self.deletePost)
            self.main.ctrlv.activated.connect(self.viewPost)
            self.main.ctrla.activated.connect(self.addPost)
            self.main.ctrle.activated.connect(self.editPost)

            self.main.cmdd.activated.connect(self.deletePost)
            self.main.cmdv.activated.connect(self.viewPost)
            self.main.cmda.activated.connect(self.addPost)
            self.main.cmde.activated.connect(self.editPost)

        # 건의·제안사항 탭
        if index == 3:
            for suffix, method in (
                ("d", self.deleteSuggestion),
                ("v", self.viewSuggestion),
                ("a", self.addSuggestion),
                ("e", self.editSuggestion),
            ):
                for prefix in ("ctrl", "cmd"):
                    getattr(self.main, prefix + suffix).activated.connect(method)
