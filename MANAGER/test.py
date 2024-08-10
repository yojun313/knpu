import sys
import os
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Run KIMKEM')
        self.setGeometry(300, 300, 300, 200)

        layout = QVBoxLayout()

        self.btn = QPushButton('Run KIMKEM.py', self)
        self.btn.clicked.connect(self.run_kimkem)

        layout.addWidget(self.btn)
        self.setLayout(layout)

    def run_kimkem(self):
        # 현재 디렉토리의 경로를 가져옵니다.
        script_path = os.path.join(os.getcwd(), 'KIMKEM.py')

        if sys.platform == "win32":
            # Windows에서 새로운 cmd 창에서 실행
            subprocess.Popen(['start', 'cmd', '/k', f'python {script_path}'], shell=True)
        elif sys.platform == "darwin":
            # MacOS에서 새로운 터미널에서 실행
            subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "python3 {script_path}"'])
        else:
            print("지원되지 않는 운영체제입니다.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyApp()
    ex.show()
    sys.exit(app.exec_())
