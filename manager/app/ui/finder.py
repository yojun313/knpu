from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import QFileDialog, QSizePolicy, QAbstractItemView, QMessageBox
import subprocess
import os
from ui.status import printStatus
import platform

def makeFileFinder(main_window, localDirectory=None):
    class EmbeddedFileDialog(QFileDialog):
        def __init__(self, parent=main_window, localDirectory=None):
            super().__init__(parent)
            self.setFileMode(QFileDialog.ExistingFiles)
            self.setOptions(QFileDialog.DontUseNativeDialog)
            self.setNameFilters(
                ["All Files (*.*)", "CSV Files (*.csv)", "Text Files (*.txt)", "Images (*.png *.jpg *.jpeg)"])
            self.currentChanged.connect(self.on_directory_change)
            self.accepted.connect(self.on_accepted)
            self.rejected.connect(self.on_rejected)
            self.setSizePolicy(QSizePolicy.Expanding,
                               QSizePolicy.Expanding)
            self.main = parent
            if localDirectory:
                self.setDirectory(localDirectory)
            self.setup_double_click_event()

            # QTreeView 찾아서 헤더뷰 리사이즈 모드 설정
            # QFileDialog가 Detail 모드일 때 내부적으로 QTreeView를 사용하므로 findChildren 사용
            from PyQt5.QtWidgets import QTreeView, QHeaderView
            for treeview in self.findChildren(QTreeView):
                # Size(1번 열)와 Kind(2번 열) 숨기기
                treeview.setColumnHidden(1, True)  # Size 숨기기
                treeview.setColumnHidden(2, True)  # Kind 숨기기
                header = treeview.header()
                # 파일명 컬럼(일반적으로 첫 번째 컬럼)만 크기 자동 조정
                header.setSectionResizeMode(
                    0, QHeaderView.ResizeToContents)
                # 나머지 컬럼들은 창 크기에 따라 비례적으로 늘어나도록 설정
                for col in range(1, header.count()):
                    header.setSectionResizeMode(col, QHeaderView.Stretch)

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
                printStatus(self.main,
                    f"{os.path.basename(file_path)} 여는 중...")
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                elif os.name == 'posix':  # macOS, Linux
                    subprocess.run(
                        ["open" if os.uname().sysname == "Darwin" else "xdg-open", file_path])
                printStatus(self.main)
            except Exception as e:
                printStatus(self.main, f"파일 열기 실패")

        def on_directory_change(self, path):
            printStatus(self.main)

        def on_accepted(self):
            selected_files = self.selectedFiles()
            if selected_files:
                self.selectFile(
                    ', '.join([os.path.basename(file) for file in selected_files]))
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
                    ', '.join([os.path.basename(file) for file in selected_files]))
            if len(selected_files) == 0:
                printStatus(self.main)
            else:
                printStatus(self.main, f"파일 {len(selected_files)}개 선택됨")
            self.show()

        def reject(self):
            self.show()

    return EmbeddedFileDialog(main_window, localDirectory)

def openFileExplorer(path):
    # 저장된 폴더를 파일 탐색기로 열기
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        os.system(f"open '{path}'")
    else:  # Linux and other OS
        os.system(f"xdg-open '{path}'")

def openFileResult(parent, msg, filepath):
    printStatus(parent)
    reply = QMessageBox.question(parent, 'Notification', msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
    if reply == QMessageBox.Yes:
        openFileExplorer(filepath)
    return