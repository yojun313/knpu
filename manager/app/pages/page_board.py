import traceback
import warnings
from PyQt6.QtWidgets import  QMessageBox
import bcrypt
from config import *
from ui.table import *
from ui.status import *
from services.auth import *
from services.api import *
from services.logging import *
from core.shortcut import *

warnings.filterwarnings("ignore")

class Manager_Board:
    def __init__(self, main_window):
        self.main = main_window
        self.refreshVersionBoard()
        self.refreshBugBoard()
        self.refreshPostBoard()
        self.matchButton()
        self.main.tabWidget_board.currentChanged.connect(self.updateShortcut)

    def refreshVersionBoard(self):
        try:
            def sort_by_version(two_dim_list):
                # 버전 번호를 파싱하여 비교하는 함수
                def version_key(version_str):
                    return [int(part) for part in version_str.split('.')]

                sorted_list = sorted(
                    two_dim_list, key=lambda x: version_key(x[0]), reverse=True)
                return sorted_list

            self.origin_version_data = Request(
                'get', '/board/version').json()['data']

            self.version_data = [[item['versionName'], item['releaseDate'], item['changeLog'], item['features'], item['details']] for item in self.origin_version_data]
            self.version_data = sort_by_version(self.version_data)
            self.version_data_for_table = [sub_list[:-1] for sub_list in self.version_data]
            self.version_table_column = ['Version Num', 'Release Date', 'ChangeLog', 'Version Features']
            makeTable(self.main, self.main.board_version_tableWidget, self.version_data_for_table, self.version_table_column)
            self.version_name_list = [version_data[0] for version_data in self.version_data_for_table]

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def addVersion(self):
        try:
            if self.main.user != 'admin':
                ok, password = checkPassword(self.main, True)
                if not ok or bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')) == False:
                    return

            # QDialog를 상속받은 클래스 생성
            from ui.dialogs import AddVersionDialog
            dialog = AddVersionDialog(VERSION)
            dialog.exec()

            # 데이터를 addVersion 함수에서 사용
            if dialog.data:
                version_data = dialog.data
                data = {
                    "versionName": version_data[0],
                    "changeLog": version_data[1],
                    "features": version_data[2],
                    "details": version_data[3],
                    'sendPushOver': False,
                }

                reply = QMessageBox.question(
                    self.main, 'Confirm Notification', "업데이트 알림을 전송하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    data['sendPushOver'] = True

                Request('post', '/board/version/add', json=data)
            self.refreshVersionBoard()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def editVersion(self):
        try:
            if self.main.user != 'admin':
                ok, password = checkPassword(self.main, True)
                if not ok or bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')) == False:
                    return

            selectedRow = self.main.board_version_tableWidget.currentRow()
            if selectedRow < 0:
                return

            # 기존 데이터
            origin = self.version_data[selectedRow]
        
            # Edit Dialog 열기
            from ui.dialogs import EditVersionDialog
            dialog = EditVersionDialog(origin)
            dialog.exec()

            if dialog.data:
                version_data = dialog.data
                version_data['sendPushOver'] = False
                Request('put', f'/board/version/{version_data["versionName"]}', json=version_data)
                QMessageBox.information(self.main, "완료", f"{version_data['versionName']} 수정 완료했습니다")
                self.refreshVersionBoard()

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteVersion(self):
        try:
            if self.main.user != 'admin':
                ok, password = checkPassword(self.main, True)
                if not ok or bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')) == False:
                    return

            selectedRow = self.main.board_version_tableWidget.currentRow()
            if selectedRow >= 0:
                reply = QMessageBox.question(
                    self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    version = self.version_name_list[selectedRow]
                    Request('delete', f'/board/version/{version}')

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
            self.origin_bug_data = Request(
                'get', '/board/bug').json()['data']
            self.bug_data_for_table = [
                [sub_list['writerName'], sub_list['versionName'],
                    sub_list['bugTitle'], sub_list['datetime']]
                for sub_list in self.origin_bug_data]
            self.bug_table_column = [
                'User', 'Version Num', 'Title', 'DateTime']
            makeTable(self.main, self.main.board_bug_tableWidget,
                      self.bug_data_for_table, self.bug_table_column)
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def addBug(self):
        try:
            # QDialog를 상속받은 클래스 생성
            from ui.dialogs import AddBugDialog
            dialog = AddBugDialog(self.main, VERSION)
            dialog.exec()

            # 데이터를 addVersion 함수에서 사용
            if dialog.data:
                bug_data = dialog.data
                bug_data = list(bug_data.values())

                json_data = {
                    "writerUid": self.main.userUid,
                    "versionName": bug_data[1],
                    "bugTitle": bug_data[2],
                    "bugText": bug_data[3],
                    "programLog": "",
                }

                Request('post', '/board/bug/add', json=json_data)
                self.refreshBugBoard()
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def deleteBug(self):
        try:
            selectedRow = self.main.board_bug_tableWidget.currentRow()
            if selectedRow >= 0:
                bug = self.origin_bug_data[selectedRow]

                if bug['writerUid'] == self.main.userUid or self.main.user == 'admin':
                    reply = QMessageBox.question(
                        self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                    if reply == QMessageBox.StandardButton.Yes:
                        printStatus(self.main, "삭제 중...")
                        Request('delete', f'/board/bug/{bug["uid"]}')
                        self.refreshBugBoard()
                        printStatus(self.main)
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"작성자만 삭제할 수 있습니다")
                    return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def viewBug(self):
        try:
            selectedRow = self.main.board_bug_tableWidget.currentRow()
            if selectedRow >= 0:
                printStatus(self.main, "불러오는 중...")
                bug_data = self.origin_bug_data[selectedRow]
                printStatus(self.main)
                from ui.dialogs import ViewBugDialog
                dialog = ViewBugDialog(self.main, bug_data)
                dialog.exec()

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def refreshPostBoard(self):
        try:
            self.origin_post_data = Request(
                'get', '/board/post').json()['data']
            self.post_data_for_table = [
                [sub_list['writerName'], sub_list['title'],
                    sub_list['datetime'], str(sub_list['viewCnt'])]
                for sub_list in self.origin_post_data
            ]
            self.post_table_column = [
                'User', 'Title', 'DateTime', 'View Count']
            makeTable(self.main, self.main.board_post_tableWidget,
                      self.post_data_for_table, self.post_table_column)
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def addPost(self):
        try:
            from ui.dialogs import AddPostDialog
            dialog = AddPostDialog(self.main)
            dialog.exec()

            if dialog.data:
                post_data = dialog.data
                post_data = list(post_data.values())

                json_data = {
                    "writerUid": self.main.userUid,
                    "title": post_data[0],
                    "text": post_data[1],
                    "sendPushOver": False,
                }

                reply = QMessageBox.question(
                    self.main, 'Confirm Notification', "현재 게시글에 대한 전체 알림을 전송하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    json_data['sendPushOver'] = True

                Request('post', '/board/post/add', json=json_data)
                self.refreshPostBoard()
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def viewPost(self, selectedRow = 1):
        try:
            if selectedRow != 0:
                selectedRow = self.main.board_post_tableWidget.currentRow()
            
            if selectedRow >= 0:
                printStatus(self.main, "불러오는 중...")
                post_data = self.origin_post_data[selectedRow]

                Request('get', f'/board/post/{post_data["uid"]}')
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
                post = self.origin_post_data[selectedRow]

                if post['writerUid'] == self.main.userUid or self.main.user == 'admin':
                    reply = QMessageBox.question(
                        self.main, 'Confirm Delete', "정말 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                    if reply == QMessageBox.StandardButton.Yes:
                        printStatus(self.main, "삭제 중...")
                        Request(
                            'delete', f'/board/post/{post["uid"]}')
                        self.refreshPostBoard()
                        printStatus(self.main)
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"작성자만 삭제할 수 있습니다")
                    return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def editPost(self):
        try:
            selectedRow = self.main.board_post_tableWidget.currentRow()
            if selectedRow >= 0:
                post = self.origin_post_data[selectedRow]
                postUid = post['uid']
                if post['writerUid'] == self.main.userUid or self.main.user == 'admin':
                    prev_post_data = self.origin_post_data[selectedRow]

                    from ui.dialogs import EditPostDialog
                    dialog = EditPostDialog(prev_post_data)
                    dialog.exec()

                    if dialog.data:
                        post_data = dialog.data
                        post_data = list(post_data.values())

                        json_data = {
                            "writerUid": self.main.userUid,
                            "title": post_data[0],
                            "text": post_data[1],
                            "sendPushOver": False,
                        }
                        Request(
                            'put', f'/board/post/{postUid}', json=json_data)
                        self.refreshPostBoard()
                        QMessageBox.information(
                            self.main, "Information", f"게시물이 수정되었습니다")
                else:
                    QMessageBox.warning(
                        self.main, "Wrong Password", f"비밀번호가 일치하지 않습니다")
                    printStatus(self.main)
                    return
        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def matchButton(self):
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
        self.updateShortcut(0)
        self.main.tabWidget_board.currentChanged.connect(self.updateShortcut)

    def updateShortcut(self, index):
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
