import os
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QMainWindow, QHeaderView, QMessageBox, QFileDialog
import platform

class TableWindow(QMainWindow):
    def __init__(self, parent=None, target_db=None):
        super(TableWindow, self).__init__(parent)
        self.setWindowTitle(target_db)
        self.setGeometry(100, 100, 1600, 1200)

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
            self.init_table_view(parent.mySQL_obj, target_db)

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

class Manager_Database:
    def __init__(self, main_window):
        self.main = main_window
        self.database_init_table()
        self.database_buttonMatch()

    def database_init_table(self):
        db_data = []
        for db in self.main.DB_list:
            db_split  = db.split('_')
            crawltype = db_split[0]
            keyword   = db_split[1]
            date      = f"{db_split[2]}~{db_split[3]}"
            time      = db_split[4] + db_split[5]
            time      = f"{time[:2]}/{time[2:4]} {time[4:6]}:{time[6:]}"
            db_data.append((crawltype, keyword, date, time))

        self.main.database_tablewidget.setRowCount(len(self.main.DB_list))
        self.main.database_tablewidget.setColumnCount(4)
        self.main.database_tablewidget.setHorizontalHeaderLabels(['Crawl Type', 'Crawl Keyword', 'Crawl Date', 'Crawl Time'])
        self.main.database_tablewidget.setSelectionBehavior(QTableWidget.SelectRows)
        self.main.database_tablewidget.setSelectionMode(QTableWidget.SingleSelection)
        self.main.database_tablewidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for i, (crawltype, keyword, date, time) in enumerate(db_data):
            self.main.database_tablewidget.setItem(i, 0, QTableWidgetItem(crawltype))
            self.main.database_tablewidget.setItem(i, 1, QTableWidgetItem(keyword))
            self.main.database_tablewidget.setItem(i, 2, QTableWidgetItem(date))
            self.main.database_tablewidget.setItem(i, 3, QTableWidgetItem(time))

    def database_delete_DB(self):
        selected_row = self.main.database_tablewidget.currentRow()
        if selected_row >= 0:
            target_db = self.main.DB_list[selected_row]
            reply = QMessageBox.question(self.main, 'Confirm Delete', f"'{target_db}'를 삭제하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.main.mySQL_obj.dropDB(target_db)
                self.main.database_tablewidget.removeRow(selected_row)
                self.main.DB_list.remove(target_db)

    def database_view_DB(self):
        selected_row = self.main.database_tablewidget.currentRow()
        if selected_row >= 0:
            target_DB = self.main.DB_list[selected_row]
            self.DBtable_window = TableWindow(self.main, target_DB)
            self.DBtable_window.show()

    def database_search_DB(self):
        search_text = self.main.database_searchDB_lineinput.text().lower()
        if not search_text:
            return

        # 현재 선택된 행의 다음 행부터 검색 시작
        start_row = self.main.database_tablewidget.currentRow() + 1 if self.main.database_tablewidget.currentRow() != -1 else 0

        for row in range(start_row, self.main.database_tablewidget.rowCount()):
            match = False
            for col in range(self.main.database_tablewidget.columnCount()):
                item = self.main.database_tablewidget.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.main.database_tablewidget.selectRow(row)
                return

        # 검색어가 처음부터 검색되도록 반복
        for row in range(0, start_row):
            match = False
            for col in range(self.main.database_tablewidget.columnCount()):
                item = self.main.database_tablewidget.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.main.database_tablewidget.selectRow(row)
                return

    def database_save_DB(self):
        selected_row = self.main.database_tablewidget.currentRow()
        if not selected_row >= 0:
            return
        target_db = self.main.DB_list[selected_row]

        folder_path = QFileDialog.getExistingDirectory(self.main, "Select Directory")
        # 선택된 경로가 있는지 확인
        if folder_path:
            try:
                dbpath = os.path.join(folder_path, target_db)

                try:
                    os.mkdir(dbpath)
                except:
                    dbpath += "_copy"
                    os.mkdir(dbpath)

                self.main.mySQL_obj.connectDB(target_db)
                tableList = self.main.mySQL_obj.showAllTable(target_db)
                for tableName in tableList:
                    self.main.mySQL_obj.TableToCSV(tableName, dbpath)

                # 저장된 폴더를 파일 탐색기로 열기
                if platform.system() == "Windows":
                    os.startfile(dbpath)
                elif platform.system() == "Darwin":  # macOS
                    os.system(f"open '{dbpath}'")
                else:  # Linux and other OS
                    os.system(f"xdg-open '{dbpath}'")

            except Exception as e:
                QMessageBox.critical(self.main, "Error", f"Failed to save database: {str(e)}")
        else:
            QMessageBox.warning(self.main, "Warning", "No directory selected.")

    def database_refresh_DB(self):
        self.database_init_table()

    def database_buttonMatch(self):
        self.main.database_refreshDB_button.clicked.connect(self.database_refresh_DB)
        self.main.database_searchDB_button.clicked.connect(self.database_search_DB)
        self.main.database_searchDB_lineinput.returnPressed.connect(self.database_search_DB)

        self.main.database_saveDB_button.clicked.connect(self.database_save_DB)
        self.main.database_deleteDB_button.clicked.connect(self.database_delete_DB)
        self.main.database_viewDB_button.clicked.connect(self.database_view_DB)
