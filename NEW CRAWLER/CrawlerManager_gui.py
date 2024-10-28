import os
import sys
import subprocess
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QScrollArea, QMessageBox, QDialog, QGridLayout, QFileDialog)
from PyQt5.QtCore import Qt, QTimer
from datetime import datetime
import danger_analyzer


class CrawlerManagerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crawler Manager")
        self.setGeometry(100, 100, 700, 600)  # 창 가로 크기 650 픽셀로 고정

        # 실행 중인 크롤러 관리
        self.processes = {}
        self.output_buffers = {}
        
        # 현재 EXE 실행 파일의 디렉토리 위치를 가져옴
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(__file__)

        # word_list_path 초기값 설정 (기본적으로 EXE 파일이 있는 위치)
        self.word_list_path = os.path.join(self.base_path, "RealTime_wordList.txt")

        # 중앙 위젯 설정
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # 전체 레이아웃
        self.main_layout = QVBoxLayout(central_widget)

        # 상단 시계 및 설정 버튼 레이아웃
        top_layout = QHBoxLayout()
        self.main_layout.addLayout(top_layout)

        # 시계 라벨 (중앙 고정)
        self.time_label = QLabel("", self)
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; font-family: '맑은 고딕';")
        top_layout.addWidget(self.time_label)

        # 설정 버튼 추가
        self.settings_button = QPushButton("설정", self)
        self.settings_button.setFixedSize(100, 40)
        self.settings_button.setStyleSheet("background-color: #FFD700; color: black; font-weight: bold; font-family: '맑은 고딕';")
        self.settings_button.clicked.connect(self.show_settings_popup)
        top_layout.addWidget(self.settings_button)

        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        self.main_layout.addLayout(button_layout)

        # 크롤러 시작 버튼
        self.start_button = QPushButton("크롤러 시작", self)
        self.start_button.setFixedSize(200, 50)
        self.start_button.setStyleSheet("background-color: #416BBF; color: white; font-weight: bold; font-family: '맑은 고딕';")
        self.start_button.clicked.connect(self.show_start_popup)
        button_layout.addWidget(self.start_button)

        # 모델 생성 버튼 (기존 크롤러 중지 버튼 대체)
        self.train_button = QPushButton("모델 생성", self)
        self.train_button.setFixedSize(200, 50)
        self.train_button.setStyleSheet("background-color: #05AFF2; color: white; font-weight: bold; font-family: '맑은 고딕';")
        self.train_button.clicked.connect(self.train_model_popup)
        button_layout.addWidget(self.train_button)

        # 모든 크롤러 종료 버튼
        self.stop_all_button = QPushButton("모든 크롤러 종료", self)
        self.stop_all_button.setFixedSize(200, 50)
        self.stop_all_button.setStyleSheet("background-color: #2D4473; color: white; font-weight: bold; font-family: '맑은 고딕';")
        self.stop_all_button.clicked.connect(self.stop_all_crawlers)
        button_layout.addWidget(self.stop_all_button)

        # 스크롤 가능한 크롤러 목록 출력 영역
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area)

        # 주기적으로 크롤러 목록 및 시계 업데이트
        self.update_crawler_list()
        self.update_time()

        # 스타일시트 적용
        self.setStyleSheet(""" 
            QMainWindow {
                background-color: #0B1226;
                font-family: '맑은 고딕';
            }
            QPushButton {
                border: none;
                border-radius: 5px;
                padding: 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QScrollArea {
                background-color: #0B1226;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
            }
        """)

    def show_settings_popup(self):
        # 새로 추가된 설정 창에서 word_list_path를 설정할 수 있도록 함
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "RealTime_wordList.txt 파일 선택", "", "Text Files (*.txt);;All Files (*)", options=options)

        if file_path:
            self.word_list_path = file_path
            QMessageBox.information(self, "알림", f"파일 경로가 설정되었습니다: {file_path}")
        else:
            QMessageBox.critical(self, "오류", "파일을 선택하지 않았습니다.")

    def set_word_list_path(self, popup):
        # 사용자가 입력한 경로를 설정
        new_path = self.word_list_input.text()
        if os.path.exists(new_path):
            self.word_list_path = new_path
            QMessageBox.information(self, "알림", "파일 경로가 성공적으로 설정되었습니다.")
        else:
            QMessageBox.critical(self, "오류", "유효한 파일 경로를 입력하세요.")

        popup.close()

    def show_start_popup(self):
        popup = QDialog(self)  # 팝업을 QDialog로 구현하여 별도 창으로 열리게 함
        popup.setWindowTitle("크롤러 시작")
        popup.setFixedSize(400, 300)

        layout = QVBoxLayout(popup)

        # 크롤러 유형 선택
        layout.addWidget(QLabel("크롤러 유형:"))
        self.crawler_type_combobox = QComboBox(popup)
        self.crawler_type_combobox.addItems(["NaverCafe", "NaverBlog", "NaverNews", "DCinside"])
        layout.addWidget(self.crawler_type_combobox)

        # 키워드 입력
        layout.addWidget(QLabel("키워드:"))
        self.keyword_input = QLineEdit(popup)
        layout.addWidget(self.keyword_input)

        # 속도 입력
        layout.addWidget(QLabel("속도:"))
        self.speed_input = QLineEdit(popup)
        layout.addWidget(self.speed_input)

        # 페이지 수 입력
        layout.addWidget(QLabel("페이지 수:"))
        self.page_input = QLineEdit(popup)
        layout.addWidget(self.page_input)

        # 크롤러 시작 버튼
        start_btn = QPushButton("크롤러 시작", popup)
        start_btn.setStyleSheet("background-color: #05AFF2; color: white; font-weight: bold; font-family: '맑은 고딕';")
        start_btn.clicked.connect(lambda: self.start_crawler(popup))
        layout.addWidget(start_btn)

        popup.exec_()

    def train_model_popup(self):
        # danger_analyzer 모듈의 train_model 함수 실행
        danger_analyzer.train_model()

    def start_crawler(self, popup):
        crawler_type = self.crawler_type_combobox.currentText()
        keyword = self.keyword_input.text()
        speed = self.speed_input.text()
        page = self.page_input.text()

        if not keyword or not speed.isdigit() or not page.isdigit():
            QMessageBox.critical(self, "오류", "유효한 값을 입력하세요.")
            return

        speed = int(speed)
        page = int(page)

        # EXE 환경에서는 EXE 파일이 아닌 Python 인터프리터를 명시적으로 사용하여 중복 실행 문제를 방지
        if getattr(sys, 'frozen', False):
            # EXE로 패키징된 경우, Python 스크립트를 직접 실행할 수 없으므로 명령어 경로를 지정
            command = [sys.executable, os.path.join(self.base_path, 'RealTimeCRAWLER.py'), crawler_type, keyword, str(speed), str(page)]
        else:
            # Python으로 실행되는 경우
            command = [sys.executable, 'RealTimeCRAWLER.py', crawler_type, keyword, str(speed), str(page)]

        # 위험 단어 목록 파일이 설정되었는지 확인
        if self.word_list_path:
            command.append(self.word_list_path)  # 파일 경로를 인자로 추가

        try:
            # subprocess를 통해 새로운 프로세스를 시작 (stdout과 stderr를 파이프 처리)
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

            # 실행된 프로세스를 관리하는 딕셔너리에 추가
            self.processes[process.pid] = process
            self.output_buffers[process.pid] = []

            # 새로운 스레드를 시작하여 출력 결과를 비동기적으로 읽기
            thread = threading.Thread(target=self._read_process_output, args=(process, crawler_type, keyword), daemon=True)
            thread.start()

        except Exception as e:
            # 오류 발생 시 메시지 출력
            QMessageBox.critical(self, "오류", f"크롤러 실행 중 오류가 발생했습니다: {str(e)}")

        # 팝업 닫기
        popup.close()

    def _read_process_output(self, process, crawler_type, keyword):
        try:
            # 프로세스의 출력(stdout)을 실시간으로 읽기
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.output_buffers[process.pid].append(line.strip())
        finally:
            # 프로세스 종료 시 stdout과 stderr를 닫음
            process.stdout.close()
            process.stderr.close()
            process.wait()

    def show_stop_popup(self):
        stop_popup = QDialog(self)
        stop_popup.setWindowTitle("크롤러 중지")
        stop_popup.setFixedSize(300, 150)

        layout = QVBoxLayout(stop_popup)
        layout.addWidget(QLabel("중지할 크롤러의 PID를 입력하세요:"))

        self.pid_input = QLineEdit(stop_popup)
        layout.addWidget(self.pid_input)

        stop_btn = QPushButton("크롤러 중지", stop_popup)
        stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; font-family: '맑은 고딕';")
        stop_btn.clicked.connect(lambda: self.stop_crawler(stop_popup))
        layout.addWidget(stop_btn)

        stop_popup.exec_()

    def stop_crawler(self, popup):
        pid_input = self.pid_input.text()
        try:
            pid = int(pid_input)
        except ValueError:
            QMessageBox.critical(self, "오류", "유효한 PID를 입력하세요.")
            return

        if pid in self.processes:
            process = self.processes[pid]
            process.terminate()
            process.wait()
            del self.processes[pid]
            del self.output_buffers[pid]
            QMessageBox.information(self, "알림", f"PID {pid}의 크롤러가 중지되었습니다.")
        else:
            QMessageBox.critical(self, "오류", f"PID {pid}를 찾을 수 없습니다.")
        
        popup.close()

    def stop_all_crawlers(self):
        for pid, process in list(self.processes.items()):
            process.terminate()
            process.wait()
            del self.processes[pid]
            del self.output_buffers[pid]
        QMessageBox.information(self, "알림", "모든 크롤러가 중지되었습니다.")

    def update_crawler_list(self):
        # 스크롤 영역 초기화
        for i in reversed(range(self.scroll_layout.count())): 
            widget = self.scroll_layout.itemAt(i).widget()
            if widget is not None: 
                widget.deleteLater()

        # 크롤러 목록 표시
        if not self.processes:
            no_crawler_widget = QWidget()
            no_crawler_layout = QVBoxLayout(no_crawler_widget)
            no_crawler_widget.setFixedHeight(100)
            no_crawler_layout.setAlignment(Qt.AlignCenter)

            no_crawler_label = QLabel("현재 실행 중인 크롤러가 없습니다.")
            no_crawler_label.setStyleSheet("color: black; background-color: #E0E0E0; font-size: 16px; padding: 20px; border-radius: 10px;")
            no_crawler_layout.addWidget(no_crawler_label)
            self.scroll_layout.addWidget(no_crawler_widget)
        else:
            for pid, process in self.processes.items():
                recent_output = "\n".join(self.output_buffers[pid][-3:])

                # 크롤러 배너 생성
                banner = QWidget()
                banner_layout = QGridLayout(banner)
                banner.setFixedHeight(130)  # 크기 고정
                banner.setStyleSheet("background-color: #9AC7D9; padding: 10px; border-radius: 5px;")

                # PID, 크롤러 정보 칸 나누기
                labels = [
                    QLabel(f"PID: {pid}"),
                    QLabel(f"크롤러: {process.args[2]}"),
                    QLabel(f"키워드: {process.args[3]}"),
                    QLabel(f"속도: {process.args[4]}"),
                    QLabel(f"페이지: {process.args[5]}")
                ]

                for i, label in enumerate(labels):
                    label.setStyleSheet(f"color: white; font-size: 12px; background-color: #2D4473; padding: 5px; border-radius: 5px;")
                    label.setAlignment(Qt.AlignCenter)
                    banner_layout.addWidget(label, 0, i)

                output_label = QLabel(recent_output)
                output_label.setStyleSheet("color: black; font-size: 12px;")
                banner_layout.addWidget(output_label, 1, 0, 1, 5)

                # 종료 버튼 추가
                stop_button = QPushButton("종료", self)
                stop_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; font-family: '맑은 고딕';")
                stop_button.clicked.connect(lambda checked, pid=pid: self.stop_crawler_by_pid(pid))  # PID를 전달하도록 수정
                banner_layout.addWidget(stop_button, 0, 5)

                self.scroll_layout.addWidget(banner)

        QTimer.singleShot(1000, self.update_crawler_list)

    def stop_crawler_by_pid(self, pid):
        if pid in self.processes:
            process = self.processes[pid]
            process.terminate()
            process.wait()
            del self.processes[pid]
            del self.output_buffers[pid]
            QMessageBox.information(self, "알림", f"PID {pid}의 크롤러가 중지되었습니다.")
        else:
            QMessageBox.critical(self, "오류", f"PID {pid}를 찾을 수 없습니다.")

    def update_time(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(current_time)
        QTimer.singleShot(1000, self.update_time)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CrawlerManagerGUI()
    window.show()
    sys.exit(app.exec_())