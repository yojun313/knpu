from PyQt5.QtCore import QTimer
import copy
class Manager_Dataprocess_TabDB:
    def __init__(self, main_window):
        self.main = main_window
        self.DB = copy.deepcopy(self.main.DB)
        self.DB_table_column = ['Type', 'Keyword', 'Period', 'Option', 'Crawl Start', 'Crawl End', 'Requester']
        self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)
        self.Tab_DB_buttonMatch()

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
        self.main.printStatus("새로고침 중...")

        def refresh_database():
            self.DB = self.main.update_DB(self.DB)
            self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)

        QTimer.singleShot(1, refresh_database)
        QTimer.singleShot(1, self.main.printStatus)

    def Tab_DB_buttonMatch(self):
        self.main.dataprocess_tab1_refreshDB_button.clicked.connect(self.Tab_DB_refresh_DB)
        self.main.dataprocess_tab1_searchDB_lineinput.returnPressed.connect(self.Tab_DB_search_DB)
        self.main.dataprocess_tab1_searchDB_button.clicked.connect(self.Tab_DB_search_DB)

class DataProcess:
    def __init__(self, main_window):
        self.main = main_window

    def DataDivider(self):
        pass