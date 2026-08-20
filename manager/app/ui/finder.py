from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QAbstractItemView,
    QMessageBox,
    QTreeView,
    QHeaderView,
    QDialogButtonBox,
)
import subprocess
import os
from ui.status import printStatus
from libs.path import safe_path
import platform
import shutil
import webbrowser

# ────────────────────── GraphML 뷰어 연동 ──────────────────────
# 필요하면 나중에 Gephi, Cytoscape 등을 리스트에 더 추가할 수 있음
# ────────────────────── GraphML 뷰어 연동 ──────────────────────
# 리스트 순서 = 우선순위. 위에서부터 설치 여부를 확인해서 먼저 찾은 걸로 연다.
GRAPHML_VIEWERS = [
    {
        "name": "Gephi",
        "which": ["gephi"],  # PATH 등록된 경우 (Linux 등)
        "paths": {
            "Windows": [
                r"C:\Program Files\Gephi-0.10.1\bin\gephi64.exe",
                r"C:\Program Files\Gephi-0.10.1\bin\gephi.exe",
                r"C:\Program Files\Gephi-0.9.7\bin\gephi64.exe",
                r"C:\Program Files (x86)\Gephi\bin\gephi.exe",
            ],
            "Darwin": [
                "/Applications/Gephi.app",
            ],
            "Linux": [
                "/opt/gephi/bin/gephi",
                "/usr/share/gephi/bin/gephi",
                "/usr/local/gephi/bin/gephi",
            ],
        },
        "download_url": "https://gephi.org/users/download/",
    },
]


def _launch_app(system, exe_path, file_path):
    if system == "Darwin" and exe_path.endswith(".app"):
        subprocess.run(["open", "-a", exe_path])
        subprocess.run(["pbcopy"], input=file_path.encode())
    else:
        subprocess.Popen([exe_path, file_path])


def open_graphml_with_viewer(main_window, file_path):
    system = platform.system()

    for viewer in GRAPHML_VIEWERS:
        # 1) PATH에 등록되어 있는지 확인
        for name in viewer["which"]:
            exe = shutil.which(name)
            if exe:
                try:
                    _launch_app(system, exe, file_path)
                    return True
                except Exception:
                    pass

        # 2) OS별 기본 설치 경로 확인
        for candidate in viewer["paths"].get(system, []):
            if os.path.exists(candidate):
                try:
                    _launch_app(system, candidate, file_path)
                    return True
                except Exception:
                    continue

    # 3) 혹시 사용자가 다른 GraphML 뷰어(Gephi 등)를 설치해
    #    OS 기본 연결 프로그램으로 등록해둔 경우를 대비한 폴백
    try:
        if system == "Windows":
            os.startfile(file_path)
            return True
        elif system == "Darwin":
            result = subprocess.run(["open", file_path])
            if result.returncode == 0:
                return True
        else:
            result = subprocess.run(["xdg-open", file_path])
            if result.returncode == 0:
                return True
    except Exception:
        pass

    # 4) 여기까지 실패 → 설치된 뷰어가 없다고 판단, 다운로드 페이지 안내
    from PySide6.QtWidgets import QMessageBox  # 지역 import (순환참조 방지)

    default_viewer = GRAPHML_VIEWERS[0]
    reply = QMessageBox.question(
        main_window,
        "GraphML 뷰어 없음",
        f"GraphML 파일을 열 수 있는 프로그램({default_viewer['name']})이 "
        f"설치되어 있지 않습니다.\n\n다운로드 페이지로 이동하시겠습니까?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if reply == QMessageBox.StandardButton.Yes:
        webbrowser.open(default_viewer["download_url"])
    return False


def makeFileFinder(main_window, localDirectory=None):
    class EmbeddedFileDialog(QFileDialog):
        def __init__(self, parent=main_window, localDirectory=None):
            super().__init__(parent)
            self.setFileMode(QFileDialog.FileMode.ExistingFiles)
            self.setOptions(QFileDialog.Option.DontUseNativeDialog)
            self.setNameFilters(
                [
                    "All Files (*.*)",
                    "CSV Files (*.csv)",
                    "Text Files (*.txt)",
                    "Images (*.png *.jpg *.jpeg)",
                    "Audio Files (*.mp3 *.wav *.m4a *.flac *.aac *.ogg)",
                ]
            )
            self.currentChanged.connect(self.on_directory_change)
            self.setup_cancel_as_open_folder()

            self.accepted.connect(self.on_accepted)
            self.rejected.connect(self.on_rejected)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self.main = parent
            if localDirectory:
                self.setDirectory(localDirectory)
            self.setup_double_click_event()

            # QTreeView 찾아서 헤더뷰 리사이즈 모드 설정
            # QFileDialog가 Detail 모드일 때 내부적으로 QTreeView를 사용하므로 findChildren 사용

            for treeview in self.findChildren(QTreeView):
                # Size(1번 열)와 Kind(2번 열) 숨기기
                treeview.setColumnHidden(1, True)  # Size 숨기기
                treeview.setColumnHidden(2, True)  # Kind 숨기기
                header = treeview.header()
                # 파일명 컬럼(일반적으로 첫 번째 컬럼)만 크기 자동 조정
                header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
                for col in range(1, header.count()):
                    header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

        def setup_double_click_event(self):
            def handle_double_click(index: QModelIndex):
                # 더블 클릭된 파일 경로 가져오기
                file_path = self.selectedFiles()[0]  # 현재 선택된 파일
                if file_path and os.path.isfile(file_path):  # 파일인지 확인
                    self.open_in_external_app(file_path)

            # QListView 또는 QTreeView 중 하나를 찾아서 더블 클릭 이벤트 연결
            for view in self.findChildren(QAbstractItemView):
                view.doubleClicked.connect(handle_double_click)

        def open_in_external_app(self, file_path):
            try:
                file_path = safe_path(file_path)
                printStatus(self.main, f"{os.path.basename(file_path)} 여는 중...")

                ext = os.path.splitext(file_path)[1].lower()
                GRAPH_EXTS = {".graphml", ".gexf", ".gml", ".net", ".gdf"}

                if ext in GRAPH_EXTS:
                    open_graphml_with_viewer(self.main, file_path)
                else:
                    if os.name == "nt":  # Windows
                        os.startfile(file_path)
                    elif os.name == "posix":  # macOS, Linux
                        subprocess.run(
                            [
                                "open"
                                if os.uname().sysname == "Darwin"
                                else "xdg-open",
                                file_path,
                            ]
                        )
                printStatus(self.main)
            except Exception:
                printStatus(self.main, f"파일 열기 실패")

        def on_directory_change(self, path):
            printStatus(self.main)

        def on_accepted(self):
            selected_files = self.selectedFiles()
            if selected_files:
                self.selectFile(
                    ", ".join([os.path.basename(file) for file in selected_files])
                )
            if len(selected_files) == 0:
                printStatus(self.main)
            else:
                printStatus(self.main, f"파일 {len(selected_files)}개 선택됨")
            self.show()

        def on_rejected(self):
            self.show()

        def accept(self):
            selected_files = self.selectedFiles()
            if selected_files:
                self.selectFile(
                    ", ".join([os.path.basename(file) for file in selected_files])
                )
            if len(selected_files) == 0:
                printStatus(self.main)
            else:
                printStatus(self.main, f"파일 {len(selected_files)}개 선택됨")
            self.show()

        def reject(self):
            self.show()

        def setup_cancel_as_open_folder(self):
            button_box = self.findChild(QDialogButtonBox)
            if not button_box:
                return

            cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
            if not cancel_btn:
                return

            # 버튼 이름 변경
            cancel_btn.setText("파일 탐색기")

            # 기본 reject 연결 제거
            try:
                cancel_btn.clicked.disconnect()
            except TypeError:
                pass

            # 새 동작 연결
            cancel_btn.clicked.connect(self.open_folder_from_cancel)

        def open_folder_from_cancel(self):
            try:
                openFileExplorer(self.directory().absolutePath())
            except Exception:
                pass

            # 다이얼로그 닫지 않음
            self.show()

    return EmbeddedFileDialog(main_window, localDirectory)


def openFileExplorer(path):
    if not path:
        return
    path = safe_path(path)
    # 저장된 폴더를 파일 탐색기로 열기
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        os.system(f"open '{path}'")
    else:  # Linux and other OS
        os.system(f"xdg-open '{path}'")


def openFileResult(parent, msg, filepath):
    if not msg:
        return
    printStatus(parent)
    reply = QMessageBox.question(
        parent,
        "Notification",
        msg,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if reply == QMessageBox.StandardButton.Yes:
        openFileExplorer(filepath)
    return
