from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QMainWindow, QHeaderView, QMessageBox, QFileDialog

class Manager_Dataprocess:
    def __init__(self, main_window):
        self.main = main_window
        Tab_DB_obj = Tab_DB(main_window)

class Tab_DB:
    def __init__(self, main_window):
        self.main = main_window
        self.Tab_DB_init_table()
        self.Tab_DB_buttonMatch()

    def Tab_DB_init_table(self):
        db_data = []
        for db in self.main.DB_list:
            db_split = db.split('_')
            crawltype = db_split[0]
            keyword = db_split[1]
            date = f"{db_split[2]}~{db_split[3]}"
            time = db_split[4] + db_split[5]
            time = f"{time[:2]}/{time[2:4]} {time[4:6]}:{time[6:]}"
            db_data.append((crawltype, keyword, date, time))

        self.main.dataprocess_tab1_tablewidget.setRowCount(len(self.main.DB_list))
        self.main.dataprocess_tab1_tablewidget.setColumnCount(4)
        self.main.dataprocess_tab1_tablewidget.setHorizontalHeaderLabels(
            ['Crawl Type', 'Crawl Keyword', 'Crawl Date', 'Crawl Time'])
        self.main.dataprocess_tab1_tablewidget.setSelectionBehavior(QTableWidget.SelectRows)
        self.main.dataprocess_tab1_tablewidget.setSelectionMode(QTableWidget.SingleSelection)
        self.main.dataprocess_tab1_tablewidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for i, (crawltype, keyword, date, time) in enumerate(db_data):
            self.main.dataprocess_tab1_tablewidget.setItem(i, 0, QTableWidgetItem(crawltype))
            self.main.dataprocess_tab1_tablewidget.setItem(i, 1, QTableWidgetItem(keyword))
            self.main.dataprocess_tab1_tablewidget.setItem(i, 2, QTableWidgetItem(date))
            self.main.dataprocess_tab1_tablewidget.setItem(i, 3, QTableWidgetItem(time))

    def Tab_DB_search_DB(self):
        search_text = self.main.dataprocess_tab1_searchDB_lineinput.text().lower()
        if not search_text:
            return

        # 현재 선택된 행의 다음 행부터 검색 시작
        start_row = self.main.dataprocess_tab1_tablewidget.currentRow() + 1 if self.main.dataprocess_tab1_tablewidget.currentRow() != -1 else 0

        for row in range(start_row, self.main.dataprocess_tab1_tablewidget.rowCount()):
            match = False
            for col in range(self.main.dataprocess_tab1_tablewidget.columnCount()):
                item = self.main.dataprocess_tab1_tablewidget.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.main.dataprocess_tab1_tablewidget.selectRow(row)
                return

        # 검색어가 처음부터 검색되도록 반복
        for row in range(0, start_row):
            match = False
            for col in range(self.main.dataprocess_tab1_tablewidget.columnCount()):
                item = self.main.dataprocess_tab1_tablewidget.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break

            if match:
                self.main.dataprocess_tab1_tablewidget.selectRow(row)
                return

    def Tab_DB_refresh_DB(self):
        self.Tab_DB_init_table()

    def Tab_DB_buttonMatch(self):
        self.main.dataprocess_tab1_refreshDB_button.clicked.connect(self.Tab_DB_refresh_DB)
        self.main.dataprocess_tab1_searchDB_lineinput.returnPressed.connect(self.Tab_DB_search_DB)
        self.main.dataprocess_tab1_searchDB_button.clicked.connect(self.Tab_DB_search_DB)