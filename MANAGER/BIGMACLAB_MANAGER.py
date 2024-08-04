import os
import sys

from MANAGER.Package.Manager_Crawler import Manager_Crawler
from MANAGER.Package.Manager_User import Manager_User

MANAGER_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH = os.path.join(MANAGER_PATH, 'Package')
BIGMACLAB_PATH = os.path.dirname(MANAGER_PATH)
MYSQL_PATH = os.path.join(BIGMACLAB_PATH, 'MYSQL')

sys.path.append(MYSQL_PATH)
sys.path.append(PACKAGE_PATH)

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QMainWindow, QHeaderView, QMessageBox, QFileDialog, QAction, QLabel
from PyQt5.QtCore import Qt
from mySQL import mySQL
from Manager_Database import Manager_Database
from Manager_Crawler import Manager_Crawler
from Manager_User import Manager_User
from Manager_Dataprocess import Manager_Dataprocess

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        ui_path = os.path.join(os.path.dirname(__file__), 'BIGMACLAB_MANAGER_GUI.ui')
        uic.loadUi(ui_path, self)
        self.setWindowTitle("BIGMACLAB MANAGER")  # 창의 제목 설정
        self.status_label = QLabel()
        self.statusBar().addPermanentWidget(self.status_label, 1)
        self.status_label.setAlignment(Qt.AlignRight)

        self.printStatus("Copyright 2024. BIGMACLAB all rights reserved.")

        # 스타일시트 적용
        self.setStyle()

        self.mySQL_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306,database='User_DB')
        self.DB_list = self.mySQL_obj.showAllDB()

        # 사이드바 연결
        self.listWidget.currentRowChanged.connect(self.display)

        self.Manager_Database_obj    = Manager_Database(self)
        self.Manager_Crawler_obj     = Manager_Crawler(self)
        self.Manager_User_obj        = Manager_User(self)
        self.Manager_Dataprocess_obj = Manager_Dataprocess(self)


    def setStyle(self):
        self.setStyleSheet("""
                        QMainWindow {
                            background-color: #f7f7f7;
                            font-family: 'Tahoma';
                            font-size: 14px;
                        }
                        QPushButton {
                            background-color: #2c3e50;
                            color: white;
                            border: none;
                            border-radius: 5px;
                            padding: 10px;
                            font-family: 'Tahoma';
                            font-size: 14px;
                        }
                        QPushButton:hover {
                            background-color: #34495e;
                        }
                        QLineEdit {
                            border: 1px solid #bdc3c7;
                            border-radius: 5px;
                            padding: 8px;
                            font-family: 'Tahoma';
                            font-size: 14px;
                        }
                        QTableWidget {
                            background-color: white;
                            border: 1px solid #bdc3c7;
                            font-family: 'Tahoma';
                            font-size: 14px;
                        }
                        QHeaderView::section {
                            background-color: #2c3e50;
                            color: white;
                            padding: 8px;
                            border: none;
                            font-family: 'Tahoma';
                            font-size: 14px;
                        }
                        QListWidget {
                            background-color: #2c3e50;
                            color: white;
                            font-family: 'Tahoma';
                            font-size: 14px;
                            border: none;
                        }
                        QListWidget::item {
                            height: 40px;  /* 각 아이템의 높이를 조정 */
                            padding: 10px;
                            font-family: 'Tahoma';
                            font-size: 14px;
                        }
                        QListWidget::item:selected {
                            background-color: #34495e;
                        }
                        QTabWidget::pane {
                            border-top: 2px solid #bdc3c7;
                            background-color: #f7f7f7;  /* Matches QMainWindow background */
                        }
                        QTabWidget::tab-bar {
                            left: 5px;
                        }
                        QTabBar::tab {
                            background: #2c3e50;  /* Matches QPushButton background */
                            color: white;  /* Matches QPushButton text color */
                            border: 1px solid #bdc3c7;
                            border-bottom-color: #f7f7f7;  /* Matches QMainWindow background */
                            border-radius: 4px;
                            border-top-right-radius: 4px;
                            padding: 10px;
                            font-family: 'Tahoma';
                            font-size: 14px;
                            min-width: 100px;  /* 최소 가로 길이 설정 */
                            max-width: 200px;  /* 최대 가로 길이 설정 */
                        }
                        QTabBar::tab:selected, QTabBar::tab:hover {
                            background: #34495e;  /* Matches QPushButton hover background */
                        }
                        QTabBar::tab:selected {
                            border-color: #9B9B9B;
                            border-bottom-color: #f7f7f7;
                        }
                        QPushButton#pushButton_divide_DB {
                            background-color: #2c3e50;
                            color: white;
                            border: none;
                            border-radius: 5px;
                            padding: 10px;
                            font-family: 'Tahoma';
                            font-size: 14px;
                            min-width: 70px;  /* 최소 가로 길이 설정 */
                            max-width: 100px;  /* 최대 가로 길이 설정 */
                        }
                        QPushButton#pushButton_divide_DB:hover {
                            background-color: #34495e;
                        }
                        QLabel#label_status_divide_DB {
                            background-color: #f7f7f7;
                            color: #2c3e50;
                            border: 1px solid #bdc3c7;
                            border-radius: 5px;
                            padding: 8px;
                            font-family: 'Tahoma';
                            font-size: 14px;
                        }
                    """)



    def display(self, index):
        self.stackedWidget.setCurrentIndex(index)
        if index == 1:
            self.Manager_Crawler_obj.crawler_open_webbrowser('http://bigmaclab-crawler.kro.kr')

    def printStatus(self, message):
        self.status_label.setText(message)

app = QtWidgets.QApplication([])
application = MainWindow()
application.show()
sys.exit(app.exec_())