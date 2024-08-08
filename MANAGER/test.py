import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QFileDialog, QPushButton

class EmbeddedFileDialog(QFileDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFileMode(QFileDialog.Directory)
        self.setOptions(QFileDialog.DontUseNativeDialog)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Embedded File Dialog Example')
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        self.file_dialog = EmbeddedFileDialog(self)
        layout.addWidget(self.file_dialog)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.select_button = QPushButton("Get Selected Directory", self)
        self.select_button.clicked.connect(self.get_selected_directory)
        layout.addWidget(self.select_button)

    def get_selected_directory(self):
        selected_directory = self.file_dialog.selectedFiles()
        if selected_directory:
            print(f'Selected directory: {selected_directory[0]}')
        else:
            print("No directory selected")

app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec_())
