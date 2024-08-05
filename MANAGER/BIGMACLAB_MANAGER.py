import os
import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QMainWindow, QHeaderView, QMessageBox, QFileDialog, QAction, QLabel, QStatusBar, QHBoxLayout
from PyQt5.QtCore import Qt
from mySQL import mySQL
from Manager_Database import Manager_Database
from Manager_Crawler import Manager_Crawler
from Manager_User import Manager_User
from Manager_Dataprocess import Manager_Dataprocess_TabDB
from datetime import datetime

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        ui_path = os.path.join(os.path.dirname(__file__), 'BIGMACLAB_MANAGER_GUI.ui')
        uic.loadUi(ui_path, self)
        self.setWindowTitle("BIGMACLAB MANAGER")  # 창의 제목 설정
        self.setGeometry(0, 0, 1400, 900)

        # 상태 표시줄 생성
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.left_label = QLabel("  Copyright 2024. BIGMACLAB all rights reserved.")
        self.right_label = QLabel("Version 1.0.0")
        self.left_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.right_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusbar.addPermanentWidget(self.left_label, 1)
        self.statusbar.addPermanentWidget(self.right_label, 1)

        # 스타일시트 적용
        self.setStyle()

        self.mySQL_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306,database='User_DB')

        # 사이드바 연결
        self.listWidget.currentRowChanged.connect(self.display)

        self.DB = self.update_DB({'DBlist':[], 'DBdata': []})
        self.Manager_Database_obj = Manager_Database(self)
        self.Manager_Crawler_obj  = Manager_Crawler(self)
        self.Manager_Dataprocess_obj = Manager_Dataprocess_TabDB(self)
        self.Manager_User_obj        = Manager_User(self)


    def update_DB(self, currentDB):
        def parse_date(date_str):
            for fmt in ('%m-%d %H:%M', '%m/%d %H:%M'):
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    pass
            raise ValueError(f"time data '{date_str}' does not match any known format")

        mySQL_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306,database='User_DB')
        currentDB_list = currentDB['DBlist']
        newDB_list = mySQL_obj.showAllDB()

        delete_target_list = list(set(currentDB_list)-set(newDB_list))
        add_target_list    = list(set(newDB_list)-set(currentDB_list))
        # Delete
        currentDB_list_copy = currentDB_list.copy()
        for i in range(len(currentDB_list_copy)):
            DB_name = currentDB_list_copy[i]
            if DB_name in delete_target_list:
                index_to_remove = currentDB_list.index(DB_name)
                currentDB['DBlist'].pop(index_to_remove)
                currentDB['DBdata'].pop(index_to_remove)

        for i in range(len(add_target_list)):
            DB_name = add_target_list[i]
            currentDB['DBlist'].append(DB_name)

            db_split = DB_name.split('_')
            crawltype = db_split[0]
            keyword = db_split[1]
            date = f"{db_split[2]}~{db_split[3]}"

            self.mySQL_obj.connectDB(DB_name)
            db_info_df = self.mySQL_obj.TableToDataframe(DB_name + '_info')
            db_info = db_info_df.iloc[-1].tolist()
            option = db_info[1]
            starttime = db_info[2]
            endtime = db_info[3]
            if endtime == '-':
                endtime = '크롤링 중'
            requester = db_info[4]

            currentDB['DBdata'].append((crawltype, keyword, date, option, starttime, endtime, requester))

        db_data = currentDB['DBdata']
        db_list = currentDB['DBlist']

        # 다섯 번째 요소를 datetime 객체로 변환하여 정렬
        sorted_indices = sorted(range(len(db_data)), key=lambda i: parse_date(db_data[i][4]), reverse=True)

        # 정렬된 순서대로 새로운 리스트 생성
        sorted_db_data = [db_data[i] for i in sorted_indices]
        sorted_db_list = [db_list[i] for i in sorted_indices]

        return {'DBdata': sorted_db_data, 'DBlist': sorted_db_list}

    def DB_table_maker(self, widgetname, DB):
        db_data = DB['DBdata']
        widgetname.setRowCount(len(db_data))
        widgetname.setColumnCount(7)
        widgetname.setHorizontalHeaderLabels(
            ['Type', 'Keyword', 'Period', 'Option', 'Crawl Start', 'Crawl End', 'Requester'])
        widgetname.setSelectionBehavior(QTableWidget.SelectRows)
        widgetname.setSelectionMode(QTableWidget.SingleSelection)
        widgetname.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for i, row_data in enumerate(db_data):
            for j, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                item.setTextAlignment(Qt.AlignCenter)  # 가운데 정렬 설정
                widgetname.setItem(i, j, item)

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
                            padding: 13px;
                            font-family: 'Tahoma';
                            font-size: 15px;
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
        if index == 0:
            self.Manager_Database_obj.database_refresh_DB()
        elif index == 1:
            self.Manager_Crawler_obj.crawler_open_webbrowser('http://bigmaclab-crawler.kro.kr')
        elif index == 2:
            self.Manager_Dataprocess_obj.Tab_DB_refresh_DB()
            pass
        elif index == 3:
            pass






app = QtWidgets.QApplication([])
application = MainWindow()
application.show()
sys.exit(app.exec_())