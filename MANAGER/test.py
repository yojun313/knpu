import sys
import os
import subprocess
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

# KIMKEM.py의 내용
KIMKEM_CODE = """
# KIMKEM.py의 내용
print("KIMKEM.py is running")
"""

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
        # KIMKEM.py 파일을 임시 디렉토리에 생성합니다.
        temp_dir = os.path.dirname(os.path.abspath(sys.executable))
        script_path = os.path.join(temp_dir, 'KIMKEM.py')

        with open(script_path, 'w') as file:
            file.write(KIMKEM_CODE)

        if sys.platform == "win32":
            subprocess.Popen(['start', 'cmd', '/k', f'python {script_path}'], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "python3 {script_path}"'])
        else:
            print("지원되지 않는 운영체제입니다.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyApp()
    ex.show()
    sys.exit(app.exec_())
