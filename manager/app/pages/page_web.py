import os
import warnings
import traceback
import httpx
from PySide6.QtWidgets import QMessageBox, QHeaderView, QLabel, QInputDialog
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QUrl, Qt
from core.shortcut import resetShortcuts
from services.logging import programBugLog
from services.api import Request
from config import HOMEPAGE_EDIT_API
from ui.dialogs import (
    EditHomePaperDialog,
    EditHomeMemberDialog,
    EditHomeNewsDialog,
    EditGroupPhotoDialog,
    EditHomePopupDialog,
    ViewHomePaperDialog,
    ViewHomeMemberDialog,
    ViewHomeNewsDialog,
    ViewHomePhotoDialog,
    ViewHomePopupDialog,
)
from ui.table import makeTable
from ui.status import changeStatusbarAction
from services.logging import printStatus, userLogging
from services.api import upload_homepage_image, delete_homepage_image
from core.setting import get_setting
from core.auth import accessCheck

warnings.filterwarnings("ignore")


class Manager_Web:
    def __init__(self, main_window):
        self.main = main_window
        self.refreshPaperBoard()
        self.refreshMemberBoard()
        self.refreshNewsBoard()
        self.refreshPopupBoard()
        self.web_buttonMatch()
        self.photoTableLoad = False

    def web_open_webbrowser(self, url, widget):
        try:
            if self.browser is not None:
                widget.removeWidget(self.browser)
                self.browser.deleteLater()

            self.main.browser.setUrl(QUrl(url))
            widget.addWidget(self.browser)
            self.browser.show()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def web_open_crawler(self):
        try:
            token = get_setting("auth_token")
            url = f"https://crawler.knpu.re.kr/auth/direct-login?token={token}"

            self.main.browser.setUrl(QUrl(url))
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def web_buttonMatch(self):
        self.main.web_addpaper_button.clicked.connect(self.addHomePaper)
        self.main.web_addmember_button.clicked.connect(self.addHomeMember)
        self.main.web_addnews_button.clicked.connect(self.addHomeNews)
        self.main.web_addgroupphoto_button.clicked.connect(self.addGroupPhoto)
        self.main.web_deletepaper_button.clicked.connect(self.deleteHomePaper)
        self.main.web_deletemember_button.clicked.connect(self.deleteHomeMember)
        self.main.web_deletenews_button.clicked.connect(self.deleteHomeNews)
        self.main.web_deletegroupphoto_button.clicked.connect(self.deleteGroupPhoto)
        self.main.web_editpaper_button.clicked.connect(self.editHomePaper)
        self.main.web_editmember_button.clicked.connect(self.editHomeMember)
        self.main.web_editnews_button.clicked.connect(self.editHomeNews)
        self.main.web_editgroupphoto_button.clicked.connect(self.editGroupPhoto)
        self.main.web_viewpaper_button.clicked.connect(self.viewPaper)
        self.main.web_viewmember_button.clicked.connect(self.viewMember)
        self.main.web_viewnews_button.clicked.connect(self.viewNews)
        self.main.web_viewgroupphoto_button.clicked.connect(self.viewGroupPhoto)
        self.main.web_addpopup_button.clicked.connect(self.addHomePopup)
        self.main.web_deletepopup_button.clicked.connect(self.deleteHomePopup)
        self.main.web_editpopup_button.clicked.connect(self.editHomePopup)
        self.main.web_viewpopup_button.clicked.connect(self.viewPopupDetail)

    def refreshPaperBoard(self):
        printStatus(self.main, "새로고침 중...")
        self.origin_paper_data = Request("get", "/papers/", HOMEPAGE_EDIT_API).json()

        self.paper_data = []
        for year_group in self.origin_paper_data:
            for paper in year_group.get("papers", []):
                self.paper_data.append(paper)

        self.paper_data_for_table = [
            [
                item.get("title", ""),
                ", ".join(item.get("authors", [])),
                item.get("venue", ""),
                item.get("url", ""),
                item.get("year", ""),
            ]
            for item in self.paper_data
        ]
        self.paper_table_column = ["Title", "Authors", "Conference", "Url", "Year"]
        makeTable(
            self.main,
            self.main.web_papers_tableWidget,
            self.paper_data_for_table,
            self.paper_table_column,
        )
        printStatus(self.main, "https://knpu.re.kr/publications")

    def refreshMemberBoard(self):
        printStatus(self.main, "새로고침 중...")
        self.origin_member_data = Request("get", "/members/", HOMEPAGE_EDIT_API).json()

        self.member_data = []
        for member in self.origin_member_data:
            member_info = {
                "uid": member.get("uid", ""),
                "name": str(member.get("name", "")),
                "position": str(member.get("position", "")),
                "email": str(member.get("email", "")),
                "section": str(member.get("section", "")),
                "학력": "\n".join(member.get("학력", []))
                if isinstance(member.get("학력"), list)
                else str(member.get("학력", "")),
                "경력": "\n".join(member.get("경력", []))
                if isinstance(member.get("경력"), list)
                else str(member.get("경력", "")),
                "연구": "\n".join(member.get("연구", []))
                if isinstance(member.get("연구"), list)
                else str(member.get("연구", "")),
                "수상": "\n".join(member.get("수상", []))
                if isinstance(member.get("수상"), list)
                else str(member.get("수상", "")),
            }
            self.member_data.append(member_info)

        self.member_data_for_table = [
            [
                item["name"],
                item["section"],
                item["position"],
                item["email"],
                item["학력"],
                item["경력"],
                item["연구"],
                item["수상"],
            ]
            for item in self.member_data
        ]
        self.member_table_column = [
            "성명",
            "구분",
            "직책",
            "이메일",
            "학력",
            "경력",
            "연구",
            "수상",
        ]
        makeTable(
            self.main,
            self.main.web_members_tableWidget,
            self.member_data_for_table,
            self.member_table_column,
        )
        printStatus(self.main, "https://knpu.re.kr/team")

    def refreshNewsBoard(self):
        printStatus(self.main, "새로고침 중...")
        self.news_data = Request("get", "/news/", HOMEPAGE_EDIT_API).json()
        self.news_data_for_table = [
            [item["title"], item["content"], item["date"], item["url"]]
            for item in self.news_data
        ]
        self.news_table_column = ["제목", "내용", "날짜", "URL"]
        makeTable(
            self.main,
            self.main.web_news_tableWidget,
            self.news_data_for_table,
            self.news_table_column,
        )
        printStatus(self.main, "https://knpu.re.kr#news")

    def refreshGroupPhotoBoard(self):
        printStatus(self.main, "갤러리 불러오는 중...")
        self.photo_data = Request("get", "/gallery/", HOMEPAGE_EDIT_API).json()

        self.photo_data_for_table = [
            [
                "",
                item.get("caption", ""),
                item.get("date", "").split("T")[0],
            ]
            for item in self.photo_data
        ]

        column_headers = ["Thumbnail", "Caption", "Date"]

        makeTable(
            self.main,
            self.main.web_groupphotos_tableWidget,
            self.photo_data_for_table,
            column_headers,
            popupsize=(600, 500),  # 상세조회 팝업 사이즈 조절
        )

        table = self.main.web_groupphotos_tableWidget

        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 120)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        for i in range(table.rowCount()):
            table.setRowHeight(i, 80)

            url = self.photo_data[i].get("url")
            if url:
                img_label = QLabel()
                img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                img_label.setStyleSheet(
                    "padding: 5px; border-radius: 5px;"
                )  # 디자인 요소

                try:
                    resp = httpx.get(url)
                    if resp.status_code == 200:
                        pixmap = QPixmap()
                        pixmap.loadFromData(resp.content)
                        img_label.setPixmap(
                            pixmap.scaled(
                                110,
                                70,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    else:
                        img_label.setText("No Image")
                except:
                    img_label.setText("Error")

                table.setCellWidget(i, 0, img_label)

    def addHomePaper(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            dialog = EditHomePaperDialog(parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                if not payload:
                    return
                Request("post", "/papers/", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(
                    self.main,
                    "완료",
                    f"{payload.get('title', '논문')}가 추가되었습니다",
                )
                userLogging(f"WEB -> addHomePaper({payload.get('title')})")
                self.refreshPaperBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def addHomeMember(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            dialog = EditHomeMemberDialog(parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                Request("post", "/members/", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(
                    self.main, "완료", f"{payload['name']} 멤버가 추가되었습니다"
                )
                userLogging(f"WEB -> addHomeMember({payload.get('name')})")
                self.refreshMemberBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def addHomeNews(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            dialog = EditHomeNewsDialog(parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                Request("post", "/news/", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(
                    self.main,
                    "완료",
                    f"{payload.get('title', '뉴스')}가 추가되었습니다",
                )
                userLogging(f"WEB -> addHomeNews({payload.get('title')})")
                self.refreshNewsBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def addGroupPhoto(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return

            dialog = EditGroupPhotoDialog(parent=self.main)
            if dialog.exec():
                if not dialog.image_path:
                    QMessageBox.warning(
                        self.main, "알림", "이미지 파일을 선택해야 합니다."
                    )
                    return

                printStatus(self.main, "이미지 업로드 중...")
                image_url = upload_homepage_image(
                    src_path=dialog.image_path,
                    folder="gallery",
                    file_name=os.path.basename(dialog.image_path),
                )

                if not image_url:
                    raise Exception("이미지 URL을 가져오지 못했습니다.")

                payload = dialog.get_payload()
                payload["url"] = image_url

                Request("post", "/gallery/", HOMEPAGE_EDIT_API, json=payload)

                QMessageBox.information(self.main, "완료", "갤러리에 추가되었습니다.")
                userLogging(f"WEB -> addGroupPhoto({payload.get('caption')})")
                self.refreshGroupPhotoBoard()

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteHomePaper(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            selectedRow = self.main.web_papers_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.paper_data[selectedRow]["uid"]
            reply = QMessageBox.question(
                self.main,
                "Confirm Delete",
                "정말 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                Request(
                    "delete",
                    "/papers/",
                    HOMEPAGE_EDIT_API,
                    params={"uid": selectedUid},
                )
                userLogging(
                    f"WEB -> deleteHomePaper({self.paper_data[selectedRow]['title']})"
                )
                self.refreshPaperBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteHomeMember(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return

            selectedRow = self.main.web_members_tableWidget.currentRow()
            if selectedRow < 0:
                return

            targetName = self.member_data[selectedRow]["name"]
            selectedUid = self.member_data[selectedRow]["uid"]

            # 1. 먼저 삭제 의사를 묻습니다.
            reply = QMessageBox.question(
                self.main,
                "Confirm Delete",
                f"[{targetName}] 멤버를 정말 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # 2. 이름을 직접 입력받아 확인합니다.
                confirmName, ok = QInputDialog.getText(
                    self.main,
                    "Security Check",
                    f"삭제 확인을 위해 멤버의 이름({targetName})을 정확히 입력해주세요.",
                )

                # 3. 입력값이 일치할 때만 삭제 진행
                if ok and confirmName == targetName:
                    Request(
                        "delete",
                        "/members/",
                        HOMEPAGE_EDIT_API,
                        params={"uid": selectedUid},
                    )
                    userLogging(f"WEB -> deleteHomeMember({targetName})")
                    self.refreshMemberBoard()
                    QMessageBox.information(
                        self.main, "Success", "성공적으로 삭제되었습니다."
                    )
                elif ok:
                    QMessageBox.warning(
                        self.main,
                        "Warning",
                        "이름이 일치하지 않습니다. 삭제를 취소합니다.",
                    )

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteHomeNews(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            selectedRow = self.main.web_news_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.news_data[selectedRow]["uid"]
            reply = QMessageBox.question(
                self.main,
                "Confirm Delete",
                "정말 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                Request(
                    "delete",
                    "news/",
                    HOMEPAGE_EDIT_API,
                    params={"uid": selectedUid},
                )
                userLogging(
                    f"WEB -> deleteHomeNews({self.news_data[selectedRow]['title']})"
                )
                self.refreshNewsBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteGroupPhoto(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            selectedRow = self.main.web_groupphotos_tableWidget.currentRow()
            if selectedRow < 0:
                return

            target_data = self.photo_data[selectedRow]
            uid = target_data["uid"]
            image_url = target_data["url"]

            if (
                QMessageBox.question(
                    self.main,
                    "삭제",
                    "정말 삭제하시겠습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                == QMessageBox.StandardButton.Yes
            ):
                delete_homepage_image(image_url)

                Request("delete", "gallery/", HOMEPAGE_EDIT_API, params={"uid": uid})

                self.refreshGroupPhotoBoard()
                QMessageBox.information(
                    self.main, "성공", "이미지와 데이터가 모두 삭제되었습니다."
                )
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def editHomePaper(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            selectedRow = self.main.web_papers_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.paper_data[selectedRow]["uid"]

            origin = None
            for year_group in self.origin_paper_data:
                for p in year_group["papers"]:
                    if p.get("uid") == selectedUid:
                        origin = p
                        origin["year"] = year_group["year"]
                        break
            if not origin:
                QMessageBox.warning(self.main, "오류", "논문 정보를 찾을 수 없습니다.")
                return

            dialog = EditHomePaperDialog(data=origin, parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                if not payload:
                    return  # 연도 검증 실패 등으로 get_payload가 {}를 반환한 경우

                payload["uid"] = selectedUid  # uid 유지
                Request("post", "papers/", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(
                    self.main,
                    "완료",
                    f"{payload.get('title')}가 수정되었습니다",
                )
                userLogging(f"WEB -> editHomePaper({payload.get('title')})")
                self.refreshPaperBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def editHomeMember(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            selectedRow = self.main.web_members_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.member_data[selectedRow]["uid"]
            origin = None
            for m in self.origin_member_data:
                if m.get("uid") == selectedUid:
                    origin = m
                    break
            if not origin:
                QMessageBox.warning(self.main, "오류", "멤버 정보를 찾을 수 없습니다.")
                return

            dialog = EditHomeMemberDialog(data=origin, parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                payload["uid"] = selectedUid
                Request("post", "members/", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(
                    self.main, "완료", f"{payload.get('name')} 멤버가 수정되었습니다"
                )
                userLogging(f"WEB -> editHomeMember({payload.get('name')})")
                self.refreshMemberBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def editHomeNews(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            selectedRow = self.main.web_news_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.news_data[selectedRow]["uid"]
            origin = None
            for n in self.news_data:
                if n.get("uid") == selectedUid:
                    origin = n
                    break
            if not origin:
                QMessageBox.warning(self.main, "오류", "뉴스 정보를 찾을 수 없습니다.")
                return

            dialog = EditHomeNewsDialog(data=origin, parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                payload["uid"] = selectedUid
                Request("post", "news/", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(
                    self.main, "완료", f"{payload.get('title')} 뉴스가 수정되었습니다"
                )
                userLogging(f"WEB -> editHomeNews({payload.get('title')})")
                self.refreshNewsBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def editGroupPhoto(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return

            selectedRow = self.main.web_groupphotos_tableWidget.currentRow()
            if selectedRow < 0:
                return

            selectedUid = self.photo_data[selectedRow]["uid"]
            origin = next(
                (p for p in self.photo_data if p.get("uid") == selectedUid), None
            )

            if not origin:
                QMessageBox.warning(self.main, "오류", "사진 정보를 찾을 수 없습니다.")
                return

            dialog = EditGroupPhotoDialog(data=origin, parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                payload["uid"] = selectedUid

                if dialog.image_path:
                    printStatus(self.main, "새 이미지 업로드 중...")

                    if origin.get("url"):
                        delete_homepage_image(origin["url"])

                    new_url = upload_homepage_image(
                        src_path=dialog.image_path,
                        folder="gallery",
                        file_name=os.path.basename(dialog.image_path),
                    )
                    payload["url"] = new_url
                else:
                    payload["url"] = origin.get("url")

                Request("post", "/gallery/", HOMEPAGE_EDIT_API, json=payload)

                QMessageBox.information(
                    self.main,
                    "완료",
                    f"'{payload.get('caption')}' 사진 정보가 수정되었습니다.",
                )
                userLogging(f"WEB -> editGroupPhoto({payload.get('caption')})")
                self.refreshGroupPhotoBoard()

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def viewPaper(self):
        try:
            selectedRow = self.main.web_papers_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.paper_data[selectedRow]["uid"]
            origin = None
            for year_group in self.origin_paper_data:
                for p in year_group["papers"]:
                    if p.get("uid") == selectedUid:
                        origin = p
                        origin["year"] = year_group["year"]
                        break
            if not origin:
                QMessageBox.warning(self.main, "오류", "논문 정보를 찾을 수 없습니다.")
                return
            dialog = ViewHomePaperDialog(data=origin, parent=self.main)
            dialog.exec()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def viewMember(self):
        try:
            selectedRow = self.main.web_members_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.member_data[selectedRow]["uid"]
            origin = None
            for m in self.origin_member_data:
                if m.get("uid") == selectedUid:
                    origin = m
                    break
            if not origin:
                QMessageBox.warning(self.main, "오류", "멤버 정보를 찾을 수 없습니다.")
                return
            dialog = ViewHomeMemberDialog(data=origin, parent=self.main)
            dialog.exec()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def viewNews(self):
        try:
            selectedRow = self.main.web_news_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.news_data[selectedRow]["uid"]
            origin = None
            for n in self.news_data:
                if n.get("uid") == selectedUid:
                    origin = n
                    break
            if not origin:
                QMessageBox.warning(self.main, "오류", "뉴스 정보를 찾을 수 없습니다.")
                return
            dialog = ViewHomeNewsDialog(data=origin, parent=self.main)
            dialog.exec()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def viewGroupPhoto(self):
        try:
            selectedRow = self.main.web_groupphotos_tableWidget.currentRow()
            if selectedRow < 0:
                return

            selectedUid = self.photo_data[selectedRow]["uid"]
            origin = None
            for p in self.photo_data:
                if p.get("uid") == selectedUid:
                    origin = p
                    break

            if not origin:
                QMessageBox.warning(self.main, "오류", "사진 정보를 찾을 수 없습니다.")
                return

            dialog = ViewHomePhotoDialog(data=origin, parent=self.main)
            dialog.exec()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def refreshPopupBoard(self):
        printStatus(self.main, "팝업 목록 불러오는 중...")
        self.popup_data = Request("get", "/popups/", HOMEPAGE_EDIT_API).json()
        self.popup_data_for_table = [
            [
                item.get("title", ""),
                item.get("content", "")[:50],
                item.get("start_date", ""),
                item.get("end_date", ""),
                "✔" if item.get("is_active") else "✘",
            ]
            for item in self.popup_data
        ]
        self.popup_table_column = ["제목", "내용", "시작일", "종료일", "활성"]
        makeTable(
            self.main,
            self.main.web_popup_tableWidget,
            self.popup_data_for_table,
            self.popup_table_column,
        )
        printStatus(self.main, "https://knpu.re.kr (팝업)")

    def addHomePopup(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            dialog = EditHomePopupDialog(parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                Request("post", "/popups/", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(
                    self.main,
                    "완료",
                    f"{payload.get('title', '팝업')}이 추가되었습니다",
                )
                userLogging(f"WEB -> addHomePopup({payload.get('title')})")
                self.refreshPopupBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def deleteHomePopup(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            selectedRow = self.main.web_popup_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.popup_data[selectedRow]["uid"]
            reply = QMessageBox.question(
                self.main,
                "Confirm Delete",
                "정말 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                Request(
                    "delete", "/popups/", HOMEPAGE_EDIT_API, params={"uid": selectedUid}
                )
                userLogging(
                    f"WEB -> deleteHomePopup({self.popup_data[selectedRow]['title']})"
                )
                self.refreshPopupBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def editHomePopup(self):
        try:
            if not accessCheck(self.main, exclude=["public"]):
                return
            selectedRow = self.main.web_popup_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.popup_data[selectedRow]["uid"]
            origin = next(
                (p for p in self.popup_data if p.get("uid") == selectedUid), None
            )
            if not origin:
                QMessageBox.warning(self.main, "오류", "팝업 정보를 찾을 수 없습니다.")
                return
            dialog = EditHomePopupDialog(data=origin, parent=self.main)
            if dialog.exec():
                payload = dialog.get_payload()
                payload["uid"] = selectedUid
                Request("post", "/popups/", HOMEPAGE_EDIT_API, json=payload)
                QMessageBox.information(
                    self.main, "완료", f"{payload.get('title')} 팝업이 수정되었습니다"
                )
                userLogging(f"WEB -> editHomePopup({payload.get('title')})")
                self.refreshPopupBoard()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def viewPopupDetail(self):
        try:
            selectedRow = self.main.web_popup_tableWidget.currentRow()
            if selectedRow < 0:
                return
            selectedUid = self.popup_data[selectedRow]["uid"]
            origin = next(
                (p for p in self.popup_data if p.get("uid") == selectedUid), None
            )
            if not origin:
                QMessageBox.warning(self.main, "오류", "팝업 정보를 찾을 수 없습니다.")
                return
            dialog = ViewHomePopupDialog(data=origin, parent=self.main)
            dialog.exec()
        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def setWebShortcut(self):
        self.updateShortcut(0)
        self.main.tabWidget_web.currentChanged.connect(self.updateShortcut)

    def updateShortcut(self, index):
        resetShortcuts(self.main)

        if index == 0:
            printStatus(self.main, "https://knpu.re.kr/publications")
            self.main.ctrld.activated.connect(self.deleteHomePaper)
            self.main.ctrle.activated.connect(self.editHomePaper)
            self.main.ctrla.activated.connect(self.addHomePaper)
            self.main.ctrlv.activated.connect(self.viewPaper)
            self.main.ctrlr.activated.connect(self.refreshPaperBoard)

            self.main.cmdd.activated.connect(self.deleteHomePaper)
            self.main.cmde.activated.connect(self.editHomePaper)
            self.main.cmda.activated.connect(self.addHomePaper)
            self.main.cmdv.activated.connect(self.viewPaper)
            self.main.cmdr.activated.connect(self.refreshPaperBoard)

        if index == 1:
            printStatus(self.main, "https://knpu.re.kr/gallery")

            if self.photoTableLoad == False:
                self.refreshGroupPhotoBoard()
                self.photoTableLoad = True

            self.main.ctrla.activated.connect(self.addGroupPhoto)
            self.main.ctrld.activated.connect(self.deleteGroupPhoto)
            self.main.ctrlv.activated.connect(self.viewGroupPhoto)
            self.main.ctrle.activated.connect(self.editGroupPhoto)
            self.main.ctrlr.activated.connect(self.refreshGroupPhotoBoard)

            self.main.cmda.activated.connect(self.addGroupPhoto)
            self.main.cmdd.activated.connect(self.deleteGroupPhoto)
            self.main.cmdv.activated.connect(self.viewGroupPhoto)
            self.main.cmde.activated.connect(self.editGroupPhoto)
            self.main.cmdr.activated.connect(self.refreshGroupPhotoBoard)

        if index == 2:
            printStatus(self.main, "https://knpu.re.kr/team")
            self.main.ctrld.activated.connect(self.deleteHomeMember)
            self.main.ctrle.activated.connect(self.editHomeMember)
            self.main.ctrla.activated.connect(self.addHomeMember)
            self.main.ctrlv.activated.connect(self.viewMember)
            self.main.ctrlr.activated.connect(self.refreshMemberBoard)

            self.main.cmdd.activated.connect(self.deleteHomeMember)
            self.main.cmde.activated.connect(self.editHomeMember)
            self.main.cmda.activated.connect(self.addHomeMember)
            self.main.cmdv.activated.connect(self.viewMember)
            self.main.cmdr.activated.connect(self.refreshMemberBoard)

        if index == 3:
            printStatus(self.main, "https://knpu.re.kr/#news")
            self.main.ctrla.activated.connect(self.addHomeNews)
            self.main.ctrld.activated.connect(self.deleteHomeNews)
            self.main.ctrle.activated.connect(self.editHomeNews)
            self.main.ctrlv.activated.connect(self.viewNews)
            self.main.ctrlr.activated.connect(self.refreshNewsBoard)

            self.main.cmda.activated.connect(self.addHomeNews)
            self.main.cmdd.activated.connect(self.deleteHomeNews)
            self.main.cmde.activated.connect(self.editHomeNews)
            self.main.cmdv.activated.connect(self.viewNews)
            self.main.cmdr.activated.connect(self.refreshNewsBoard)

        if index == 4:
            printStatus(self.main, "https://knpu.re.kr (팝업)")
            self.main.ctrla.activated.connect(self.addHomePopup)
            self.main.ctrld.activated.connect(self.deleteHomePopup)
            self.main.ctrle.activated.connect(self.editHomePopup)
            self.main.ctrlv.activated.connect(self.viewPopupDetail)
            self.main.ctrlr.activated.connect(self.refreshPopupBoard)

            self.main.cmda.activated.connect(self.addHomePopup)
            self.main.cmdd.activated.connect(self.deleteHomePopup)
            self.main.cmde.activated.connect(self.editHomePopup)
            self.main.cmdv.activated.connect(self.viewPopupDetail)
            self.main.cmdr.activated.connect(self.refreshPopupBoard)

        changeStatusbarAction(self.main, "WEB")
