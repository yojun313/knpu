import sys
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import Qt

def create_table():
    app = QApplication(sys.argv)

    table = QTableWidget()
    table.setRowCount(3)
    table.setColumnCount(3)

    for row in range(3):
        for column in range(3):
            item = QTableWidgetItem(f"Cell ({row}, {column})")
            item.setTextAlignment(Qt.AlignCenter)  # 가운데 정렬 설정
            table.setItem(row, column, item)

    table.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    create_table()
