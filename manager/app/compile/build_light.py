import sys
import os
import re
import shutil
import subprocess
from datetime import datetime
from packaging.version import Version
import requests
from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QPlainTextEdit, QRadioButton, QButtonGroup,
    QMessageBox, QFrame
)
from upload import upload_file

OUTPUT_DIRECTORY = "D:/knpu/MANAGER/exe"
VENV_PYTHON = r"C:/GitHub/knpu/venv/Scripts/python.exe"

def sendPushOver(msg):
    requests.post('https://manager.knpu.re.kr/api/users/admin/pushover', json={"message": msg})

def create_spec_file(original_spec_file, new_spec_file, exe_name):
    with open(original_spec_file, 'r', encoding='utf-8') as file:
        spec_content = file.read()
    spec_content = spec_content.replace(
        "name='MANAGER'", f"name='{exe_name}'"
    )
    with open(new_spec_file, 'w', encoding='utf-8') as file:
        file.write(spec_content)

def build_exe_from_spec(spec_file, output_directory, version, log_func=None):
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    exe_name = f"MANAGER_{version}"
    new_spec_file = os.path.join(output_directory, f"{exe_name}.spec")
    create_spec_file(spec_file, new_spec_file, exe_name)

    try:
        cmd = [
            VENV_PYTHON,
            "-m", "PyInstaller",
            "--distpath", output_directory,
            "--workpath", os.path.join(output_directory, "build"),
            new_spec_file
        ]
        subprocess.run(cmd, check=True)
    finally:
        try:
            if os.path.exists(new_spec_file):
                os.remove(new_spec_file)
            build_path = os.path.join(os.path.dirname(new_spec_file), "build")
            if os.path.exists(build_path):
                shutil.rmtree(build_path)
        except Exception:
            pass

def read_latest_built_version() -> str | None:
    if not os.path.exists(OUTPUT_DIRECTORY):
        return None
    versions = []
    for name in os.listdir(OUTPUT_DIRECTORY):
        match = re.match(r"MANAGER_([\w.\-]+)$", name)
        if match:
            try:
                versions.append(Version(match.group(1)))
            except:
                continue
    if not versions:
        return None
    return str(max(versions))

class BuildWorker(QObject):
    log_signal = Signal(str)
    finished = Signal(str, float)
    error = Signal(str)

    def __init__(self, version_mode: str, custom_version: str, spec_file: str, parent=None):
        super().__init__(parent)
        self.version_mode = version_mode
        self.custom_version = custom_version.strip()
        self.spec_file = spec_file
        self.output_directory = OUTPUT_DIRECTORY
        self._is_running = True

    def stop(self):
        self._is_running = False

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_signal.emit(f"[{timestamp}] {msg}")
    
    def run(self):
        start_time = datetime.now()
        try:
            current_version = read_latest_built_version()
            if not current_version:
                raise RuntimeError("버전을 읽을 수 없습니다.")

            if self.version_mode == "reuse":
                target_version = current_version
            elif self.version_mode == "next":
                current = Version(current_version)
                next_version = Version(
                    f"{current.major}.{current.minor}.{current.micro + 1}"
                )
                target_version = str(next_version)
            elif self.version_mode == "custom":
                if not self.custom_version:
                    raise ValueError("버전이 비어 있습니다.")
                _ = Version(self.custom_version)
                target_version = self.custom_version
            else:
                raise ValueError(f"version_mode error: {self.version_mode}")

            same_version_path = os.path.join(
                self.output_directory, f"MANAGER_{target_version}"
            )
            if os.path.exists(same_version_path):
                shutil.rmtree(same_version_path)

            build_exe_from_spec(
                self.spec_file,
                self.output_directory,
                target_version,
                log_func=self._log
            )

            exe_path = os.path.join(self.output_directory, f"MANAGER_{target_version}", f"MANAGER_{target_version}.exe")
            if not os.path.exists(exe_path):
                exe_path = os.path.join(self.output_directory, f"MANAGER_{target_version}.exe")

            upload_file(exe_path)

            end_time = datetime.now()
            elapsed = end_time - start_time
            elapsed_min = int(elapsed.total_seconds() // 60)
            elapsed_sec = int(elapsed.total_seconds() % 60)

            sendPushOver(
                f"MANAGER {target_version} 빌드 완료\n\n"
                f"소요시간: {elapsed_min}분 {elapsed_sec}초"
            )

            self.finished.emit(target_version, elapsed.total_seconds())

        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self, spec_file: str):
        super().__init__()
        self.spec_file = spec_file
        self.thread = None
        self.worker = None
        self.init_ui()
        self.load_current_version()

    def init_ui(self):
        self.setWindowTitle("MANAGER 빌드 및 배포 시스템")
        self.setMinimumSize(800, 600)

        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        central.setLayout(main_layout)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("MANAGER 빌드 및 배포 시스템")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("QLabel { font-size: 22px; font-weight: 600; }")

        self.current_version_label = QLabel("현재 버전: -")
        self.current_version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_version_label.setStyleSheet("QLabel { font-size: 14px; color: #bbbbbb; }")

        main_layout.addWidget(title_label)
        main_layout.addWidget(self.current_version_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        mid_layout = QVBoxLayout()
        mid_layout.setSpacing(10)

        mode_label = QLabel("빌드 버전 선택")
        mode_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        mid_layout.addWidget(mode_label)

        btn_layout = QHBoxLayout()
        self.radio_reuse = QRadioButton("현재 버전 재사용")
        self.radio_next = QRadioButton("패치 버전 +1 (x.y.z → x.y.z+1)")
        self.radio_custom = QRadioButton("직접 입력")

        self.radio_next.setChecked(True)

        self.version_group = QButtonGroup(self)
        self.version_group.addButton(self.radio_reuse)
        self.version_group.addButton(self.radio_next)
        self.version_group.addButton(self.radio_custom)

        btn_layout.addWidget(self.radio_reuse)
        btn_layout.addWidget(self.radio_next)
        btn_layout.addWidget(self.radio_custom)
        mid_layout.addLayout(btn_layout)

        custom_layout = QHBoxLayout()
        custom_label = QLabel("직접 입력 버전:")
        self.custom_version_edit = QLineEdit()
        self.custom_version_edit.setPlaceholderText("예: 1.2.3")
        custom_layout.addWidget(custom_label)
        custom_layout.addWidget(self.custom_version_edit)

        mid_layout.addLayout(custom_layout)

        build_btn_layout = QHBoxLayout()
        build_btn_layout.addStretch(1)
        self.build_button = QPushButton("빌드 시작")
        self.build_button.setFixedWidth(140)
        self.build_button.clicked.connect(self.start_build)
        build_btn_layout.addWidget(self.build_button)
        mid_layout.addLayout(build_btn_layout)

        main_layout.addLayout(mid_layout)

        log_label = QLabel("빌드 로그")
        log_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        main_layout.addWidget(log_label)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet("QPlainTextEdit { background-color: #151515; color: #f0f0f0; border-radius: 8px; padding: 8px; font-family: Consolas, 'JetBrains Mono', 'Courier New', monospace; font-size: 12px; }")
        main_layout.addWidget(self.log_edit, stretch=1)

        self.setStyleSheet("QMainWindow { background-color: #202124; color: #f0f0f0; } QWidget { background-color: #202124; color: #f0f0f0; } QPushButton { background-color: #3c4043; border-radius: 6px; padding: 8px 14px; } QPushButton:hover { background-color: #5f6368; } QPushButton:disabled { background-color: #3c4043; color: #777777; } QRadioButton, QLabel { color: #e8eaed; } QLineEdit { background-color: #2b2b2b; border-radius: 4px; padding: 4px 8px; border: 1px solid #5f6368; color: #f0f0f0; }")

    def append_log(self, text: str):
        self.log_edit.appendPlainText(text)
        self.log_edit.verticalScrollBar().setValue(
            self.log_edit.verticalScrollBar().maximum()
        )

    def load_current_version(self):
        version = read_latest_built_version()
        if version:
            self.current_version_label.setText(f"현재 버전: {version}")
        else:
            self.current_version_label.setText("현재 버전: (알 수 없음)")

    def start_build(self):
        if self.thread is not None:
            QMessageBox.warning(self, "빌드 실행 중", "이미 빌드가 진행 중입니다.")
            return

        if self.radio_reuse.isChecked():
            mode = "reuse"
        elif self.radio_next.isChecked():
            mode = "next"
        else:
            mode = "custom"

        custom_version = self.custom_version_edit.text()

        self.log_edit.clear()
        self.append_log("=== 빌드 작업 시작 ===")

        self.build_button.setEnabled(False)

        self.thread = QThread(self)
        self.worker = BuildWorker(
            version_mode=mode,
            custom_version=custom_version,
            spec_file=self.spec_file
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished.connect(self.on_build_finished)
        self.worker.error.connect(self.on_build_error)
        self.worker.finished.connect(lambda *_: self.cleanup_thread())
        self.worker.error.connect(lambda *_: self.cleanup_thread())

        self.thread.start()

    def cleanup_thread(self):
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.thread = None
        self.worker = None
        self.build_button.setEnabled(True)

    def on_build_finished(self, version: str, elapsed_seconds: float):
        self.append_log(
            f"=== 빌드 완료: MANAGER_{version} "
            f"({int(elapsed_seconds // 60)}분 {int(elapsed_seconds % 60)}초) ==="
        )
        QMessageBox.information(
            self,
            "빌드 완료",
            f"MANAGER {version} 빌드 및 배포가 완료되었습니다."
        )
        self.load_current_version()

    def on_build_error(self, message: str):
        self.append_log(f"[오류] {message}")
        QMessageBox.critical(
            self,
            "빌드 오류",
            f"빌드 중 오류가 발생했습니다:\n\n{message}"
        )

def main():
    app = QApplication(sys.argv)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(base_dir, "build.spec")
    window = MainWindow(spec_file)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()