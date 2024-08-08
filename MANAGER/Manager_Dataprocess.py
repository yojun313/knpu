from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QMainWindow, QHeaderView, QMessageBox, QFileDialog, QSizePolicy, QPushButton
import copy
import pandas as pd
import os
import matplotlib.pyplot as plt
from functools import partial


class Manager_Dataprocess:
    def __init__(self, main_window):
        self.main = main_window
        self.dataprocess_obj = DataProcess()
        self.DB = copy.deepcopy(self.main.DB)
        self.DB_table_column = ['Type', 'Keyword', 'Period', 'Option', 'Crawl Start', 'Crawl End', 'Requester']
        self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)
        self.dataprocess_filefinder_maker()
        self.dataprocess_buttonMatch()

    def dataprocess_buttonMatch(self):
        self.main.dataprocess_tab1_refreshDB_button.clicked.connect(self.dataprocess_refresh_DB)
        self.main.dataprocess_tab1_searchDB_lineinput.returnPressed.connect(self.dataprocess_search_DB)
        self.main.dataprocess_tab1_searchDB_button.clicked.connect(self.dataprocess_search_DB)
        self.main.dataprocess_tab1_timesplit_button.clicked.connect(self.dataprocess_timesplit_DB)

        self.main.dataprocess_tab2_timesplit_button.clicked.connect(self.dataprocess_timesplit_file)

    def dataprocess_search_DB(self):
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

    def dataprocess_refresh_DB(self):
        self.main.printStatus("새로고침 중...")

        def refresh_database():
            self.DB = self.main.update_DB(self.DB)
            self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)

        QTimer.singleShot(1, refresh_database)
        QTimer.singleShot(1, self.main.printStatus)

    def dataprocess_timesplit_DB(self):
        def selectDB():
            selected_row = self.main.dataprocess_tab1_tablewidget.currentRow()
            if not selected_row >= 0:
                return 0 ,0, 0
            target_db = self.DB['DBlist'][selected_row]

            folder_path  = QFileDialog.getExistingDirectory(self.main, "분할 데이터를 저장할 폴더를 선택하세요")
            if folder_path:
                try:
                    splitdata_path = os.path.join(folder_path, target_db + '_split')

                    while True:
                        try:
                            os.mkdir(splitdata_path)
                            break
                        except:
                            splitdata_path += "_copy"

                    self.main.mySQL_obj.connectDB(target_db)
                    tableList = self.main.mySQL_obj.showAllTable(target_db)
                    tableList = [table for table in tableList if 'info' not in table]

                    return target_db, tableList, splitdata_path

                except Exception as e:
                    QMessageBox.critical(self.main, "Error", f"Failed to save splited database: {str(e)}")
            else:
                QMessageBox.warning(self.main, "Warning", "No directory selected.")
                return 0,0,0
        def splitTable(table, splitdata_path):
            table_path = os.path.join(splitdata_path, table + '_split')
            try:
                os.mkdir(table_path)
            except:
                table_path += "_copy"
                os.mkdir(table_path)

            table_df = self.main.mySQL_obj.TableToDataframe(table)
            table_df = self.dataprocess_obj.TimeSplitter(table_df)

            self.year_divided_group = table_df.groupby('year')
            self.month_divided_group = table_df.groupby('year_month')
            self.week_divided_group = table_df.groupby('week')

            return table_path
        def saveTable(tablename, table_path):
            self.dataprocess_obj.TimeSplitToCSV(1, self.year_divided_group, table_path, tablename)
            self.dataprocess_obj.TimeSplitToCSV(2, self.month_divided_group, table_path, tablename)
        def main(tableList, splitdata_path):
            for table in tableList:
                table_path = splitTable(table, splitdata_path)
                saveTable(table, table_path)

        self.main.printStatus("분할 데이터를 저장할 위치를 선택하세요...")
        targetDB, tableList, splitdata_path = selectDB()
        if targetDB == 0:
            self.main.printStatus()
            return
        QTimer.singleShot(1, lambda: self.main.printStatus(f"{targetDB} 변환 및 저장 중..."))
        self.main.openFileExplorer(splitdata_path)
        QTimer.singleShot(1000, lambda: main(tableList, splitdata_path))
        QTimer.singleShot(1000, self.main.printStatus)


    def dataprocess_filefinder_maker(self):
        self.file_dialog = self.main.filefinder_maker()
        self.main.tab2_fileexplorer_layout.addWidget(self.file_dialog)

    def dataprocess_getfiledirectory(self):
        selected_directory = self.file_dialog.selectedFiles()
        selected_directory = selected_directory[0].split(', ')

        for directory in selected_directory:
            if not directory.endswith('.csv'):
                return False

        for index, directory in enumerate(selected_directory):
            if index != 0:
                selected_directory[index] = os.path.join(os.path.dirname(selected_directory[0]), directory)

        return selected_directory

    def dataprocess_timesplit_file(self):
        try:
            selected_directory = self.dataprocess_getfiledirectory()
            if selected_directory == False:
                return
            def split_table(csv_path):
                table_path = os.path.join(os.path.dirname(csv_path), os.path.basename(csv_path).replace('.csv', '') + '_split')
                while True:
                    try:
                        os.mkdir(table_path)
                        break
                    except:
                        table_path += "_copy"

                table_df = self.main.csvReader(csv_path)
                table_df = self.dataprocess_obj.TimeSplitter(table_df)

                self.year_divided_group = table_df.groupby('year')
                self.month_divided_group = table_df.groupby('year_month')
                self.week_divided_group = table_df.groupby('week')

                return table_path
            def saveTable(tablename, table_path):
                self.dataprocess_obj.TimeSplitToCSV(1, self.year_divided_group, table_path, tablename)
                self.dataprocess_obj.TimeSplitToCSV(2, self.month_divided_group, table_path, tablename)
            def main(directory_list):
                for csv_path in directory_list:
                    table_path = split_table(csv_path)
                    saveTable(os.path.basename(csv_path).replace('.csv', ''), table_path)

            QTimer.singleShot(1, lambda: self.main.printStatus("변환 및 저장 중..."))
            self.main.openFileExplorer(os.path.dirname(selected_directory[0]))
            QTimer.singleShot(1000, lambda: main(selected_directory))
            QTimer.singleShot(1000, self.main.printStatus)
        except:
            pass

class DataProcess:
    def __init__(self):
        pass

    def TimeSplitter(self, data):
        # data 형태: DataFrame
        data_columns = data.columns.tolist()

        for i in data_columns:
            if 'Date' in i:
                word = i
                break

        data[word] = pd.to_datetime(data[word], format='%Y-%m-%d', errors='coerce')

        data['year'] = data[word].dt.year
        data['month'] = data[word].dt.month
        data['year_month'] = data[word].dt.to_period('M')
        data['week'] = data[word].dt.to_period('W')

        return data
    def TimeSplitToCSV(self, option, divided_group, data_path, tablename):
        # 폴더 이름과 데이터 그룹 설정
        data_group = divided_group
        if option == 1:
            folder_name = "Year Data"
            info_label = 'Year'
        elif option == 2:
            folder_name = "Month Data"
            info_label = 'Month'
        elif option == 3:
            folder_name = "Week Data"
            info_label = 'Week'

        info = {}

        # 디렉토리 생성
        os.mkdir(data_path + "/" + folder_name)

        # 데이터 그룹을 순회하며 파일 저장 및 정보 수집
        for group_name, group_data in data_group:
            info[str(group_name)] = len(group_data)
            group_data.to_csv(f"{data_path}/{folder_name}/{tablename+'_'+str(group_name)}.csv", index=False,
                              encoding='utf-8-sig', header=True)

        # 정보 파일 생성
        info_df = pd.DataFrame(list(info.items()), columns=[info_label, 'Count'])
        info_df.to_csv(f"{data_path}/{folder_name}/{folder_name} Count.csv", index=False,
                       encoding='utf-8-sig', header=True)

        info_df.set_index(info_label, inplace=True)
        keys = list(info_df.index)
        values = info_df['Count'].tolist()

        # 옵션에 따라 그래프 크기 조정
        if option == 1:
            plt.figure(figsize=(10, 6))
        else:
            plt.figure(figsize=(30, 18))

        # 그래프 그리기
        plt.plot(keys, values, marker='o')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        plt.title(f'{info_label} Data Visualization')
        plt.xlabel(info_label)
        plt.ylabel('Values')

        # 그래프 저장
        plt.savefig(f"{data_path}/{folder_name}/{folder_name} Graph.png", bbox_inches='tight')

    def DataDivider(self):
        pass