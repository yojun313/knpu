import sys
import time
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QProgressBar, QPushButton, QVBoxLayout, QLabel


class Worker(QThread):
    # 작업의 진행 상황을 전달하기 위한 신호
    progress = pyqtSignal(int)

    def __init__(self, task_func, *args, **kwargs):
        super().__init__()
        self.task_func = task_func  # 작업 함수 저장
        self.args = args  # 작업 함수의 인자
        self.kwargs = kwargs  # 작업 함수의 키워드 인자

    def run(self):
        # 작업 함수를 실행하고, 진행 상황을 전달
        self.task_func(self, *self.args, **self.kwargs)


class LoadingBarExample(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.progress = QProgressBar(self)
        self.progress.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress)

        self.label = QLabel('Progress:', self)
        layout.addWidget(self.label)

        self.btn = QPushButton('Start', self)
        self.btn.clicked.connect(self.startTask)
        layout.addWidget(self.btn)

        self.setLayout(layout)

        self.setWindowTitle('Loading Bar with Background Task')
        self.setGeometry(300, 300, 280, 170)

    def startTask(self):
        # Worker 인스턴스에 실행할 작업 함수와 인자들을 전달
        arg1 = 10  # 첫 번째 추가 인자
        arg2 = 2   # 두 번째 추가 인자
        arg3 = 5   # 세 번째 추가 인자
        self.worker = Worker(self.someLongTask, arg1, arg2, arg3)
        self.worker.progress.connect(self.updateProgress)
        self.worker.start()
        self.btn.setEnabled(False)  # 작업 중에 버튼 비활성화

    def updateProgress(self, value):
        self.progress.setValue(value)
        self.label.setText(f'Progress: {value}%')
        if value == 100:
            self.btn.setEnabled(True)  # 작업 완료 후 버튼 활성화
            self.label.setText('Task Completed!')

    def someLongTask(self, worker, increment, multiplier, decrement):
        # 복잡한 작업을 시뮬레이션 (여기서는 세 개의 추가 인자를 사용)
        for i in range(1, 101):
            time.sleep(0.1)  # 작업의 일부를 처리 (시간 지연)
            progress_value = (i + increment) * multiplier - decrement
            worker.progress.emit(progress_value)  # 진행 상황을 전달 (세 개의 인자 사용)
            if progress_value >= 100:
                break


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = LoadingBarExample()
    ex.show()
    sys.exit(app.exec_())
