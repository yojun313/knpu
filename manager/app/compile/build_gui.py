import sys
import os
import re
import shutil
import socket
import subprocess
from datetime import datetime

from packaging.version import Version
import requests

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QPlainTextEdit, QRadioButton, QButtonGroup,
    QMessageBox, QFrame
)

# ----------------------------------------
# 기존 상수/함수들
# ----------------------------------------

OUTPUT_DIRECTORY = "D:/knpu/MANAGER/exe"

# 사용자 환경에 맞게 수정
VENV_PYTHON = r"C:/GitHub/knpu/venv/Scripts/python.exe"
INNO_SETUP_EXE = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

from upload import upload_file  # 기존 모듈 그대로 사용


def sendPushOver(msg, user_key='uvz7oczixno7daxvgxmq65g2gbnsd5', image_path=False):
    app_key_list = ["a22qabchdf25zzkd1vjn12exjytsjx"]

    for app_key in app_key_list:
        try:
            url = 'https://api.pushover.net/1/messages.json'
            message = {
                'token': app_key,
                'user': user_key,
                'message': msg
            }
            if not image_path:
                response = requests.post(url, data=message)
            else:
                response = requests.post(
                    url,
                    data=message,
                    files={
                        "attachment": (
                            "image.png",
                            open(image_path, "rb"),
                            "image/png"
                        )
                    }
                )
            break
        except Exception:
            continue


def update_inno_version(iss_path: str, new_version: str):
    temp_iss_path = os.path.join(os.path.dirname(iss_path), 'setup_temp.iss')

    with open(iss_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated_lines = []
    pattern = r'^\s*#define\s+MyAppVersion\s+"[\w.\-]+"'

    for line in lines:
        if re.match(pattern, line):
            new_line = f'#define MyAppVersion "{new_version}"\n'
            updated_lines.append(new_line)
        else:
            updated_lines.append(line)

    with open(temp_iss_path, 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)

    return temp_iss_path


def create_spec_file(original_spec_file, new_spec_file, exe_name):
    with open(original_spec_file, 'r', encoding='utf-8') as file:
        spec_content = file.read()

    spec_content = spec_content.replace(
        "name='MANAGER'", f"name='{exe_name}'"
    )

    with open(new_spec_file, 'w', encoding='utf-8') as file:
        file.write(spec_content)


def build_exe_from_spec(spec_file, output_directory, version, log_func=None):
    """
    log_func: 로그를 GUI에 출력하기 위한 콜백 (str -> None)
    """
    def log(msg):
        if log_func:
            log_func(msg)
        else:
            print(msg)

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    log(f"Building exe for spec: {spec_file}")

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
        log(f"Running PyInstaller: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.stdout:
            log(result.stdout)

        if result.stderr:
            log("[PyInstaller 오류]\n" + result.stderr)

        if result.returncode != 0:
            raise RuntimeError("PyInstaller 빌드 실패")
        log(f"Finished building {exe_name}.exe")
    finally:
        # cleanup
        try:
            if os.path.exists(new_spec_file):
                os.remove(new_spec_file)
            build_path = os.path.join(os.path.dirname(new_spec_file), "build")
            if os.path.exists(build_path):
                shutil.rmtree(build_path)
            log(f"Cleaned temporary files in {os.path.dirname(new_spec_file)}")
        except Exception as e:
            log(f"[경고] 임시 파일 정리 중 오류 발생: {e}")

def read_latest_built_version() -> str | None:
    """
    OUTPUT_DIRECTORY 내부에서 MANAGER_x.y.z 형식의 폴더명을 읽고,
    가장 최신 버전을 반환한다.
    """
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

# ----------------------------------------
# 빌드 작업용 Worker (QThread에서 실행)
# ----------------------------------------

class BuildWorker(QObject):
    log_signal = pyqtSignal(str)
    finished = pyqtSignal(str, float)  # version, elapsed_seconds
    error = pyqtSignal(str)

    def __init__(self, version_mode: str, custom_version: str,
                 spec_file: str, iss_path: str, parent=None):
        super().__init__(parent)
        self.version_mode = version_mode    # 'reuse', 'next', 'custom'
        self.custom_version = custom_version.strip()
        self.spec_file = spec_file
        self.iss_path = iss_path
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
            # 1) 현재 버전 읽기
            current_version = read_latest_built_version()
            if not current_version:
                raise RuntimeError("setup.iss 에서 현재 버전을 읽을 수 없습니다.")

            self._log(f"현재 버전: {current_version}")

            # 2) 목표 버전 결정
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
                    raise ValueError("직접 입력 버전이 비어 있습니다.")
                # 형식 검증 정도만 가볍게
                _ = Version(self.custom_version)
                target_version = self.custom_version
            else:
                raise ValueError(f"알 수 없는 version_mode: {self.version_mode}")

            self._log(f"빌드 대상 버전: {target_version}")

            # 3) 기존 동일 버전 디렉터리 삭제
            same_version_path = os.path.join(
                self.output_directory, f"MANAGER_{target_version}"
            )
            if os.path.exists(same_version_path):
                shutil.rmtree(same_version_path)
                self._log(f"이전 동일 버전 디렉토리 삭제: {same_version_path}")

            # 4) PyInstaller 빌드
            self._log("PyInstaller 빌드 시작")
            build_exe_from_spec(
                self.spec_file,
                self.output_directory,
                target_version,
                log_func=self._log
            )
            self._log("PyInstaller 빌드 완료")

            # 5) Inno Setup 버전 업데이트
            self._log("Inno Setup 버전 정보 업데이트")
            temp_iss_path = update_inno_version(self.iss_path, target_version)

            # 6) Inno Setup 실행
            self._log("Inno Setup 실행 중...")
            subprocess.run(
                [INNO_SETUP_EXE, temp_iss_path],
                check=True
            )
            self._log("Inno Setup 완료")

            # 임시 iss 삭제
            try:
                os.remove(temp_iss_path)
                self._log("임시 setup_temp.iss 삭제")
            except Exception as e:
                self._log(f"[경고] 임시 파일 삭제 실패: {e}")

            # 7) 업로드
            filename = f"MANAGER_{target_version}.exe"
            self._log(f"업로드 시작: {filename}")
            upload_file(filename)
            self._log("업로드 완료")

            # 8) Pushover 알림
            end_time = datetime.now()
            elapsed = end_time - start_time
            elapsed_min = int(elapsed.total_seconds() // 60)
            elapsed_sec = int(elapsed.total_seconds() % 60)

            sendPushOver(
                f"MANAGER {target_version} 빌드 완료\n\n"
                f"소요시간: {elapsed_min}분 {elapsed_sec}초"
            )
            self._log("Pushover 알림 전송 완료")

            self.finished.emit(target_version, elapsed.total_seconds())

        except Exception as e:
            self.error.emit(str(e))


# ----------------------------------------
# 메인 윈도우
# ----------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, spec_file: str, iss_path: str):
        super().__init__()
        self.spec_file = spec_file
        self.iss_path = iss_path

        self.thread: QThread | None = None
        self.worker: BuildWorker | None = None

        self.init_ui()
        self.load_current_version()

    def init_ui(self):
        self.setWindowTitle("MANAGER 빌드 및 배포 시스템")
        self.setMinimumSize(800, 600)

        # 전체 위젯 & 레이아웃
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        central.setLayout(main_layout)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 상단: 제목 & 현재 버전
        title_label = QLabel("MANAGER 빌드 및 배포 시스템")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: 600;
            }
        """)

        self.current_version_label = QLabel("현재 버전: -")
        self.current_version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_version_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #bbbbbb;
            }
        """)

        main_layout.addWidget(title_label)
        main_layout.addWidget(self.current_version_label)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # 가운데: 버전 선택 영역
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

        # 직접 입력
        custom_layout = QHBoxLayout()
        custom_label = QLabel("직접 입력 버전:")
        self.custom_version_edit = QLineEdit()
        self.custom_version_edit.setPlaceholderText("예: 1.2.3")
        custom_layout.addWidget(custom_label)
        custom_layout.addWidget(self.custom_version_edit)

        mid_layout.addLayout(custom_layout)

        # 빌드 버튼
        build_btn_layout = QHBoxLayout()
        build_btn_layout.addStretch(1)
        self.build_button = QPushButton("빌드 시작")
        self.build_button.setFixedWidth(140)
        self.build_button.clicked.connect(self.start_build)
        build_btn_layout.addWidget(self.build_button)
        mid_layout.addLayout(build_btn_layout)

        main_layout.addLayout(mid_layout)

        # 로그 출력 영역
        log_label = QLabel("빌드 로그")
        log_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        main_layout.addWidget(log_label)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #151515;
                color: #f0f0f0;
                border-radius: 8px;
                padding: 8px;
                font-family: Consolas, 'JetBrains Mono', 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.log_edit, stretch=1)

        # 전체 스타일 (다크 테마 느낌)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #202124;
                color: #f0f0f0;
            }
            QWidget {
                background-color: #202124;
                color: #f0f0f0;
            }
            QPushButton {
                background-color: #3c4043;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #5f6368;
            }
            QPushButton:disabled {
                background-color: #3c4043;
                color: #777777;
            }
            QRadioButton, QLabel {
                color: #e8eaed;
            }
            QLineEdit {
                background-color: #2b2b2b;
                border-radius: 4px;
                padding: 4px 8px;
                border: 1px solid #5f6368;
                color: #f0f0f0;
            }
        """)

    def append_log(self, text: str):
        self.log_edit.appendPlainText(text)
        # 자동 스크롤
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

        # 버전 모드 결정
        if self.radio_reuse.isChecked():
            mode = "reuse"
        elif self.radio_next.isChecked():
            mode = "next"
        else:
            mode = "custom"

        custom_version = self.custom_version_edit.text()

        # 로그 초기화
        self.log_edit.clear()
        self.append_log("=== 빌드 작업 시작 ===")

        # 버튼 비활성화
        self.build_button.setEnabled(False)

        # Thread + Worker 설정
        self.thread = QThread(self)
        self.worker = BuildWorker(
            version_mode=mode,
            custom_version=custom_version,
            spec_file=self.spec_file,
            iss_path=self.iss_path
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
        # 현재 버전 라벨 갱신
        self.load_current_version()

    def on_build_error(self, message: str):
        self.append_log(f"[오류] {message}")
        QMessageBox.critical(
            self,
            "빌드 오류",
            f"빌드 중 오류가 발생했습니다:\n\n{message}"
        )


# ----------------------------------------
# 진입점
# ----------------------------------------

def main():
    app = QApplication(sys.argv)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(base_dir, "build.spec")
    iss_path = os.path.join(base_dir, "setup.iss")

    window = MainWindow(spec_file, iss_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
