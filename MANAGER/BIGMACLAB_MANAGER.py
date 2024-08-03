import os
import sys

MANAGER_PATH = os.path.dirname(os.path.abspath(__file__))
BIGMACLAB_PATH = os.path.dirname(MANAGER_PATH)
MYSQL_PATH = os.path.join(BIGMACLAB_PATH, 'MYSQL')

sys.path.append(MYSQL_PATH)

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QMainWindow, QHeaderView, QMessageBox, QFileDialog
from PyQt5.QtWebEngineWidgets import QWebEngineView
import PyQt5.QtCore as QtCore
from mySQL import mySQL
import platform
from functools import partial


class TableWindow(QMainWindow):
    def __init__(self, parent=None, target_db=None):
        super(TableWindow, self).__init__(parent)
        self.setWindowTitle(target_db)
        self.setGeometry(100, 100, 800, 600)

        self.parent = parent  # 부모 객체를 저장하여 나중에 사용
        self.target_db = target_db  # target_db를 저장하여 나중에 사용

        self.central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # 상단 버튼 레이아웃
        self.button_layout = QtWidgets.QHBoxLayout()

        # 새로고침 버튼 추가
        self.refresh_button = QtWidgets.QPushButton("새로고침", self)
        self.refresh_button.setFixedWidth(80)  # 가로 길이 조정
        self.refresh_button.clicked.connect(self.refresh_table)
        self.button_layout.addWidget(self.refresh_button)

        # 닫기 버튼 추가
        self.close_button = QtWidgets.QPushButton("닫기", self)
        self.close_button.setFixedWidth(80)  # 가로 길이 조정
        self.close_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.close_button)

        # 버튼 레이아웃을 메인 레이아웃에 추가
        self.layout.addLayout(self.button_layout)

        self.tabWidget_tables = QtWidgets.QTabWidget(self)
        self.layout.addWidget(self.tabWidget_tables)

        # target_db가 주어지면 테이블 뷰를 초기화
        if target_db is not None:
            self.init_table_view(self.parent.mySQL_obj, target_db)

    def init_table_view(self, mySQL_obj, target_db):
        # target_db에 연결
        mySQL_obj.connectDB(target_db)

        tableNameList = mySQL_obj.showAllTable(target_db)
        self.tabWidget_tables.clear()  # 기존 탭 내용 초기화

        for tableName in tableNameList:
            tableDF = mySQL_obj.TableToDataframe(tableName)

            # 데이터프레임 값을 튜플 형태의 리스트로 변환
            tuple_list = [tuple(row) for row in tableDF.itertuples(index=False, name=None)]

            # 새로운 탭 생성
            new_tab = QWidget()
            new_tab_layout = QVBoxLayout(new_tab)
            new_table = QTableWidget(new_tab)
            new_tab_layout.addWidget(new_table)

            # 테이블 데이터 설정
            new_table.setRowCount(len(tuple_list))
            new_table.setColumnCount(len(tableDF.columns))
            new_table.setHorizontalHeaderLabels(tableDF.columns)

            # 열 너비 조정
            header = new_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Stretch)

            # 행 전체 선택 설정 및 단일 선택 모드
            new_table.setSelectionBehavior(QTableWidget.SelectRows)
            new_table.setSelectionMode(QTableWidget.SingleSelection)

            for row_idx, row_data in enumerate(tuple_list):
                for col_idx, col_data in enumerate(row_data):
                    new_table.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))

            self.tabWidget_tables.addTab(new_tab, tableName.split('_')[-1])

    def refresh_table(self):
        # 테이블 뷰를 다시 초기화하여 데이터를 새로 로드
        self.init_table_view(self.parent.mySQL_obj, self.target_db)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        ui_path = os.path.join(os.path.dirname(__file__), 'BIGMACLAB_MANAGER_GUI.ui')
        uic.loadUi(ui_path, self)
        self.setWindowTitle("BIGMACLAB MANAGER")  # 창의 제목 설정

        # 스타일시트 적용
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

        self.mySQL_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306,
                               database='User_DB')
        # 사이드바 연결
        self.listWidget.currentRowChanged.connect(self.display)

        # 테이블 초기화 및 예시 데이터 추가
        self.refresh_data()

        # DATABASE
        self.database_button()

        # CRAWLER
        self.crawler_button()

        # USER
        self.user_button()

        # DATA PROCESS
        self.dataprocess_button()

    def refresh_data(self):
        self.init_DB_table()
        self.init_user_table()
        self.init_dataprocessDB_table()

    def display(self, index):
        self.stackedWidget.setCurrentIndex(index)
        if index == 1:
            self.open_webbrowser('http://bigmaclab-crawler.kro.kr')



    #DATABASE ######################################################################################
    def init_DB_table(self):
        self.database_list = self.mySQL_obj.showAllDB()
        db_data = []
        for db in self.database_list:
            db_split = db.split('_')
            type = db_split[0]
            keyword = db_split[1]
            date = f"{db_split[2]}~{db_split[3]}"
            time = db_split[4] + db_split[5]
            time = f"{time[:2]}/{time[2:4]} {time[4:6]}:{time[6:]}"
            db_data.append((type, keyword, date, time))

        self.tableWidget_db.setRowCount(len(self.database_list))
        self.tableWidget_db.setColumnCount(4)
        self.tableWidget_db.setHorizontalHeaderLabels(['Crawl Type', 'Crawl Keyword', 'Crawl Date', 'Crawl Time'])
        self.tableWidget_db.setSelectionBehavior(QTableWidget.SelectRows)
        self.tableWidget_db.setSelectionMode(QTableWidget.SingleSelection)

        header = self.tableWidget_db.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        for i, (type, keyword, date, time) in enumerate(db_data):
            self.tableWidget_db.setItem(i, 0, QTableWidgetItem(type))
            self.tableWidget_db.setItem(i, 1, QTableWidgetItem(keyword))
            self.tableWidget_db.setItem(i, 2, QTableWidgetItem(date))
            self.tableWidget_db.setItem(i, 3, QTableWidgetItem(time))

    def delete_db(self):
        selected_row = self.tableWidget_db.currentRow()
        if selected_row >= 0:
            target_db = self.database_list[selected_row]
            reply = QMessageBox.question(self, 'Confirm Delete', f"'{target_db}'를 삭제하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.mySQL_obj.dropDB(target_db)
                self.tableWidget_db.removeRow(selected_row)
                self.database_list.remove(target_db)

    # DB 선택한다음 Table 창 열 때 작동
    def view_db(self):
        selected_row = self.tableWidget_db.currentRow()
        if selected_row >= 0:
            target_db = self.database_list[selected_row]
            self.table_window = TableWindow(self, target_db)
            self.table_window.show()

    def search_db(self):
        search_text = self.lineEdit_search.text().lower()
        if not search_text:
            return

        # 현재 선택된 행의 다음 행부터 검색 시작
        start_row = self.tableWidget_db.currentRow() + 1 if self.tableWidget_db.currentRow() != -1 else 0

        for row in range(start_row, self.tableWidget_db.rowCount()):
            match = False
            for col in range(self.tableWidget_db.columnCount()):
                item = self.tableWidget_db.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.tableWidget_db.selectRow(row)
                return

        # 검색어가 처음부터 검색되도록 반복
        for row in range(0, start_row):
            match = False
            for col in range(self.tableWidget_db.columnCount()):
                item = self.tableWidget_db.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.tableWidget_db.selectRow(row)
                return

    def save_db(self):
        # 파일 탐색기 열기
        selected_row = self.tableWidget_db.currentRow()
        if not selected_row >= 0:
            return
        target_db = self.database_list[selected_row]

        folder_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        # 선택된 경로가 있는지 확인
        if folder_path:
            try:
                dbpath = os.path.join(folder_path, target_db)

                try:
                    os.mkdir(dbpath)
                except:
                    dbpath += "_copy"
                    os.mkdir(dbpath)

                self.mySQL_obj.connectDB(target_db)
                tableList = self.mySQL_obj.showAllTable(target_db)
                for tableName in tableList:
                    self.mySQL_obj.TableToCSV(tableName, dbpath)

                # 저장된 폴더를 파일 탐색기로 열기
                if platform.system() == "Windows":
                    os.startfile(dbpath)
                elif platform.system() == "Darwin":  # macOS
                    os.system(f"open '{dbpath}'")
                else:  # Linux and other OS
                    os.system(f"xdg-open '{dbpath}'")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save database: {str(e)}")
        else:
            QMessageBox.warning(self, "Warning", "No directory selected.")

    def database_button(self):
        self.pushButton_delete_db.clicked.connect(self.delete_db)
        self.pushButton_view_db.clicked.connect(self.view_db)
        self.pushButton_save_db.clicked.connect(self.save_db)
        self.pushButton_search_db.clicked.connect(self.search_db)
        self.pushButton_refresh_db.clicked.connect(self.refresh_data)
        self.lineEdit_search.returnPressed.connect(self.search_db)
    ################################################################################################


    # USER #########################################################################################
    def init_user_table(self):
        self.mySQL_obj.connectDB('user_db')

        self.userNameList = []
        userDF = self.mySQL_obj.TableToDataframe('user_info')
        user_data = [tuple(row) for row in userDF.itertuples(index=False, name=None)]

        self.tableWidget_user.setRowCount(len(user_data))
        self.tableWidget_user.setColumnCount(3)
        self.tableWidget_user.setHorizontalHeaderLabels(['Name', 'Email', 'PushOverKey'])
        self.tableWidget_user.setSelectionBehavior(QTableWidget.SelectRows)
        self.tableWidget_user.setSelectionMode(QTableWidget.SingleSelection)

        header = self.tableWidget_user.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        for i, (id, name, email, key) in enumerate(user_data):
            self.tableWidget_user.setItem(i, 0, QTableWidgetItem(name))
            self.tableWidget_user.setItem(i, 1, QTableWidgetItem(email))
            self.tableWidget_user.setItem(i, 2, QTableWidgetItem(key))
            self.userNameList.append(name)

    def delete_user(self):
        selected_row = self.tableWidget_user.currentRow()
        if selected_row >= 0:
            reply = QMessageBox.question(self, 'Confirm Delete', f"{self.userNameList[selected_row]}님을 삭제하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.mySQL_obj.connectDB('user_db')
                self.mySQL_obj.deleteTableRowByColumn('user_info', self.userNameList[selected_row], 'Name')
                self.userNameList.pop(selected_row)
                self.tableWidget_user.removeRow(selected_row)

    def add_user(self):
        name = self.lineEdit_name.text()
        email = self.lineEdit_email.text()
        key = self.lineEdit_key.text()

        self.mySQL_obj.connectDB('user_db')

        reply = QMessageBox.question(self, 'Confirm Add', f"{name}님을 추가하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.mySQL_obj.insertToTable(tableName='user_info', data_list=[name, email, key])
            self.mySQL_obj.commit()
            self.userNameList.append(name)

            row_position = self.tableWidget_user.rowCount()
            self.tableWidget_user.insertRow(row_position)
            self.tableWidget_user.setItem(row_position, 0, QTableWidgetItem(name))
            self.tableWidget_user.setItem(row_position, 1, QTableWidgetItem(email))
            self.tableWidget_user.setItem(row_position, 2, QTableWidgetItem(key))
            self.lineEdit_name.clear()
            self.lineEdit_email.clear()
            self.lineEdit_key.clear()

    def user_button(self):
        self.pushButton_delete_user.clicked.connect(self.delete_user)
        self.pushButton_add_user.clicked.connect(self.add_user)
    ################################################################################################


    # CRAWLER ######################################################################################
    def open_webbrowser(self, url):
        # 이전 브라우저가 있으면 제거
        if self.browser is not None:
            self.webViewContainer.layout().removeWidget(self.browser)
            self.browser.deleteLater()

        # 새로운 브라우저 생성 및 추가
        self.browser = QWebEngineView(self.webViewContainer)
        self.browser.setUrl(QtCore.QUrl(url))
        self.webViewContainer.layout().addWidget(self.browser)
        self.browser.show()

    def crawler_button(self):
        self.browser = None
        self.crawler_history_button.clicked.connect(partial(self.open_webbrowser, "http://bigmaclab-crawler.kro.kr/history"))
        self.crawler_dashboard_button.clicked.connect(partial(self.open_webbrowser, "http://bigmaclab-crawler.kro.kr"))
        self.crawler_add_button.clicked.connect(partial(self.open_webbrowser, "http://bigmaclab-crawler.kro.kr/add_crawler"))
    ################################################################################################

    # Tab: 날짜 분할
    def init_dataprocessDB_table(self):
        self.database_list = self.mySQL_obj.showAllDB()
        db_data = []
        for db in self.database_list:
            db_split = db.split('_')
            type = db_split[0]
            keyword = db_split[1]
            date = f"{db_split[2]}~{db_split[3]}"
            time = db_split[4] + db_split[5]
            time = f"{time[:2]}/{time[2:4]} {time[4:6]}:{time[6:]}"
            db_data.append((type, keyword, date, time))

        self.tableWidget_data_process.setRowCount(len(self.database_list))
        self.tableWidget_data_process.setColumnCount(4)
        self.tableWidget_data_process.setHorizontalHeaderLabels(
            ['Crawl Type', 'Crawl Keyword', 'Crawl Date', 'Crawl Time'])
        self.tableWidget_data_process.setSelectionBehavior(QTableWidget.SelectRows)
        self.tableWidget_data_process.setSelectionMode(QTableWidget.SingleSelection)

        header = self.tableWidget_data_process.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        for i, (type, keyword, date, time) in enumerate(db_data):
            self.tableWidget_data_process.setItem(i, 0, QTableWidgetItem(type))
            self.tableWidget_data_process.setItem(i, 1, QTableWidgetItem(keyword))
            self.tableWidget_data_process.setItem(i, 2, QTableWidgetItem(date))
            self.tableWidget_data_process.setItem(i, 3, QTableWidgetItem(time))

    # Tab: 날짜 분할
    def search_dataprocessDB(self):
        search_text = self.lineEdit_search_dataprocessDB.text().lower()
        if not search_text:
            return

        # 현재 선택된 행의 다음 행부터 검색 시작
        start_row = self.tableWidget_data_process.currentRow() + 1 if self.tableWidget_data_process.currentRow() != -1 else 0

        for row in range(start_row, self.tableWidget_data_process.rowCount()):
            match = False
            for col in range(self.tableWidget_data_process.columnCount()):
                item = self.tableWidget_data_process.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.tableWidget_data_process.selectRow(row)
                return

        # 검색어가 처음부터 검색되도록 반복
        for row in range(0, start_row):
            match = False
            for col in range(self.tableWidget_data_process.columnCount()):
                item = self.tableWidget_data_process.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.tableWidget_data_process.selectRow(row)
                return

    def dataprocess_button(self):
        self.pushButton_search_dataprocessDB.clicked.connect(self.search_dataprocessDB)
        self.pushButton_refresh_dataprocessDB.clicked.connect(self.refresh_data)
        self.lineEdit_search_dataprocessDB.returnPressed.connect(self.search_dataprocessDB)


app = QtWidgets.QApplication([])
application = MainWindow()
application.show()
sys.exit(app.exec_())