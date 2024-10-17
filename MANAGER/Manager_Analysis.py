from PyQt5.QtWidgets import QInputDialog, QMessageBox, QFileDialog, QDialog, QHBoxLayout, QCheckBox, QComboBox, \
    QLineEdit, QLabel, QDialogButtonBox, QWidget, QToolBox, QGridLayout, QGroupBox, QScrollArea,\
    QListView, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QSpacerItem, QSizePolicy, QButtonGroup, QRadioButton, QDateEdit
from PyQt5.QtCore import QTimer, QStringListModel, Qt, QDate
import copy
import pandas as pd
import os
import matplotlib.pyplot as plt
import platform
from datetime import datetime
import gc
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 크기 제한 해제
import ast
import csv
import traceback
import warnings
import re
import chardet

warnings.filterwarnings("ignore")

from DataProcess import DataProcess
from Kemkim import KimKem

# 운영체제에 따라 한글 폰트를 설정
if platform.system() == 'Darwin':  # macOS
    plt.rcParams['font.family'] = 'AppleGothic'
elif platform.system() == 'Windows':  # Windows
    plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕 폰트 사용

# 폰트 설정 후 음수 기호가 깨지는 것을 방지
plt.rcParams['axes.unicode_minus'] = False

class Manager_Analysis:
    def __init__(self, main_window):
        self.main = main_window
        self.dataprocess_obj = DataProcess(self.main)
        self.DB = copy.deepcopy(self.main.DB)
        self.DB_table_column = ['Name', 'Type', 'Keyword', 'Period', 'Option', 'Crawl Start', 'Crawl End', 'Requester', 'Size']
        self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)
        self.userDB_layout_maker()
        self.dataprocess_filefinder_maker()

        self.anaylsis_buttonMatch()

    def anaylsis_buttonMatch(self):
        self.main.dataprocess_tab1_refreshDB_button.clicked.connect(self.dataprocess_refresh_DB)
        self.main.dataprocess_tab1_searchDB_lineinput.returnPressed.connect(self.dataprocess_search_DB)
        self.main.dataprocess_tab1_searchDB_button.clicked.connect(self.dataprocess_search_DB)
        self.main.dataprocess_tab1_timesplit_button.clicked.connect(self.dataprocess_timesplit_DB)
        self.main.dataprocess_tab1_analysis_button.clicked.connect(self.dataprocess_analysis_DB)

        self.main.dataprocess_tab2_timesplit_button.clicked.connect(self.dataprocess_timesplit_file)
        self.main.dataprocess_tab2_analysis_button.clicked.connect(self.dataprocess_analysis_file)
        self.main.dataprocess_tab2_merge_button.clicked.connect(self.dataprocess_merge_file)

        #self.main.kimkem_tab2_tokenization_button.clicked.connect(self.kimkem_tokenization_file)
        self.main.kimkem_tab2_kimkem_button.clicked.connect(self.kimkem_kimkem)
        

        self.selected_userDB = 'admin_db'
        self.selected_DBlistItem = None
        self.selected_DBlistItems = []
        self.main.userDB_list_delete_button.clicked.connect(self.toolbox_DBlistItem_delete)
        self.main.userDB_list_add_button.clicked.connect(self.toolbox_DBlistItem_add)
        self.main.userDB_list_view_button.clicked.connect(self.toolbox_DBlistItem_view)
        self.main.userDB_list_save_button.clicked.connect(self.toolbox_DBlistItem_save)

    def dataprocess_search_DB(self):
        try:
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
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def dataprocess_refresh_DB(self):
        try:
            self.main.printStatus("새로고침 중...")

            def refresh_database():
                self.DB = self.main.update_DB(self.DB)
                self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)

            QTimer.singleShot(1, refresh_database)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def dataprocess_timesplit_DB(self):
        try:
            def selectDB():
                selected_row = self.main.dataprocess_tab1_tablewidget.currentRow()
                if not selected_row >= 0:
                    return 0 ,0, 0
                target_db = self.DB['DBlist'][selected_row]

                folder_path  = QFileDialog.getExistingDirectory(self.main, "분할 데이터를 저장할 폴더를 선택하세요", self.main.default_directory)
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
                        QMessageBox.critical(self.main, "Error", f"오류가 발생했습니다: {traceback.format_exc()}")
                        self.main.program_bug_log(traceback.format_exc())
                else:
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

                    del self.year_divided_group
                    del self.month_divided_group
                    del self.week_divided_group
                    gc.collect()

                QMessageBox.information(self.main, "Information", f"{targetDB}가 성공적으로 분할 저장되었습니다")

            self.main.printStatus("분할 데이터를 저장할 위치를 선택하세요...")
            targetDB, tableList, splitdata_path = selectDB()
            if targetDB == 0:
                self.main.printStatus()
                return
            QTimer.singleShot(1, lambda: self.main.printStatus(f"{targetDB} 변환 및 저장 중..."))
            self.main.openFileExplorer(splitdata_path)
            QTimer.singleShot(1000, lambda: main(tableList, splitdata_path))
            QTimer.singleShot(1000, self.main.printStatus)


        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")

    def dataprocess_analysis_DB(self):
        try:
            def selectDB():
                selected_row = self.main.dataprocess_tab1_tablewidget.currentRow()
                if not selected_row >= 0:
                    return 0 ,0, 0
                target_db = self.DB['DBlist'][selected_row]

                folder_path  = QFileDialog.getExistingDirectory(self.main, "분석 데이터를 저장할 폴더를 선택하세요", self.main.default_directory)
                if folder_path:
                    try:
                        analysisdata_path = os.path.join(folder_path, target_db + '_analysis')

                        while True:
                            try:
                                os.mkdir(analysisdata_path)
                                break
                            except:
                                analysisdata_path += "_copy"

                        self.main.mySQL_obj.connectDB(target_db)
                        tableList = self.main.mySQL_obj.showAllTable(target_db)
                        tableList = [table for table in tableList if 'info' not in table]

                        return target_db, tableList, analysisdata_path

                    except Exception as e:
                        QMessageBox.critical(self.main, "Error", f"Failed to save splited database: {str(traceback.format_exc())}")
                        self.main.program_bug_log(traceback.format_exc())
                else:
                    return 0,0,0
            def main(tableList, analysisdata_path):

                for index, table in enumerate(tableList):
                    if 'token' in table:
                        continue
                    tablename = table.split('_')
                    tabledf = self.main.mySQL_obj.TableToDataframe(table)

                    match tablename[0]:
                        case 'navernews':
                            match tablename[6]:
                                case 'article':
                                    self.dataprocess_obj.NaverNewsArticleAnalysis(tabledf,
                                                                                  os.path.join(analysisdata_path, table))
                                case 'statistics':
                                    statisticsURL = tabledf['Article URL'].tolist()
                                    self.dataprocess_obj.NaverNewsStatisticsAnalysis(tabledf,
                                                                                     os.path.join(analysisdata_path, table))
                                case 'reply':
                                    self.dataprocess_obj.NaverNewsReplyAnalysis(tabledf,
                                                                                os.path.join(analysisdata_path, table))
                                case 'rereply':
                                    self.dataprocess_obj.NaverNewsRereplyAnalysis(tabledf,
                                                                                os.path.join(analysisdata_path, table))

                        case 'navercafe':
                            match tablename[6]:
                                case 'article':
                                    self.dataprocess_obj.NaverCafeArticleAnalysis(tabledf,
                                                                                  os.path.join(analysisdata_path, table))
                                case 'reply':
                                    self.dataprocess_obj.NaverCafeReplyAnalysis(tabledf,
                                                                                os.path.join(analysisdata_path, table))

                        case _:
                                QMessageBox.warning(self.main, "Warning", f"{tablename[0]} {tablename[6]} 분석은 지원되지 않는 기능입니다")
                                break
                    del tabledf
                    gc.collect()


            self.main.printStatus("분석 데이터를 저장할 위치를 선택하세요...")
            targetDB, tableList, analysisdata_path = selectDB()
            if targetDB == 0:
                self.main.printStatus()
                return
            QTimer.singleShot(1, lambda: self.main.printStatus(f"{targetDB} 분석 및 저장 중..."))
            self.main.openFileExplorer(analysisdata_path)
            QTimer.singleShot(1000, lambda: main(tableList, analysisdata_path))
            QTimer.singleShot(1000, self.main.printStatus)

        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def dataprocess_filefinder_maker(self):
        self.file_dialog = self.main.filefinder_maker(self.main)
        self.main.tab2_fileexplorer_layout.addWidget(self.file_dialog)

    def dataprocess_getfiledirectory(self, file_dialog):
        selected_directory = file_dialog.selectedFiles()
        if selected_directory == []:
            return selected_directory
        selected_directory = selected_directory[0].split(', ')

        for directory in selected_directory:
            if not directory.endswith('.csv'):
                return [False, directory]

        for index, directory in enumerate(selected_directory):
            if index != 0:
                selected_directory[index] = os.path.join(os.path.dirname(selected_directory[0]), directory)

        return selected_directory

    def dataprocess_timesplit_file(self):
        try:
            selected_directory = self.dataprocess_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다")
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

                if any('Date' in element for element in table_df.columns.tolist()) == False or table_df.columns.tolist() == []:
                    QMessageBox.information(self.main, "Warning", f"시간 분할할 수 없는 파일입니다")
                    return 0

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
                    if table_path == 0:
                        return
                    saveTable(os.path.basename(csv_path).replace('.csv', ''), table_path)

                    del self.year_divided_group
                    del self.month_divided_group
                    del self.week_divided_group
                    gc.collect()

            QTimer.singleShot(1, lambda: self.main.printStatus("데이터 분할 및 저장 중..."))
            self.main.openFileExplorer(os.path.dirname(selected_directory[0]))
            QTimer.singleShot(1000, lambda: main(selected_directory))
            QTimer.singleShot(1000, self.main.printStatus)

        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def dataprocess_merge_file(self):
        try:
            def find_different_element_index(lst):
                # 리스트가 비어있으면 None을 반환
                if not lst:
                    return None

                # 첫 번째 요소와 나머지 요소가 다르면 첫 번째 요소의 인덱스 반환
                if lst.count(lst[0]) == 1:
                    return 0

                # 그렇지 않으면 첫 번째 요소와 다른 첫 번째 요소의 인덱스 반환
                for i in range(1, len(lst)):
                    if lst[i] != lst[0]:
                        return i

                return None  # 모든 요소가 같다면 None을 반환

            selected_directory = self.dataprocess_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            elif len(selected_directory) < 2:
                QMessageBox.warning(self.main, f"Warning", "2개 이상의 CSV 파일 선택이 필요합니다")
                return

            mergedfilename, ok = QInputDialog.getText(None, '파일명 입력', '병합 파일명을 입력하세요:', text='merged_file')
            all_df = [self.main.csvReader(directory) for directory in selected_directory]
            all_columns = [df.columns.tolist() for df in all_df]
            same_check_result = find_different_element_index(all_columns)
            if same_check_result != None:
                QMessageBox.warning(self.main, f"Warning", f"{os.path.basename(selected_directory[same_check_result])}의 CSV 형식이 다른 파일과 일치하지 않습니다")
                return

            self.main.printStatus("데이터 병합 중...")

            mergedfiledir      = os.path.dirname(selected_directory[0])
            self.main.openFileExplorer(mergedfiledir)
            if ok and mergedfilename:
                merged_df = pd.DataFrame()

                for df in all_df:
                    merged_df = pd.concat([merged_df, df], ignore_index=True)

                merged_df.to_csv(os.path.join(mergedfiledir, mergedfilename)+'.csv', index=False, encoding='utf-8-sig')

            self.main.printStatus()

        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def dataprocess_analysis_file(self):
        try:
            class OptionDialog(QDialog):
                def __init__(self):
                    super().__init__()
                    self.setWindowTitle('Select Options')

                    # 다이얼로그 레이아웃
                    layout = QVBoxLayout()

                    # 여러 옵션 추가 (예: 체크박스, 라디오 버튼, 콤보박스)
                    # 여러 옵션 추가 (예: 체크박스, 라디오 버튼, 콤보박스)
                    self.checkbox_group = []

                    self.combobox = QComboBox()
                    self.combobox.addItems(['Naver News', 'Naver Blog', 'Naver Cafe', 'YouTube'])
                    self.combobox.currentIndexChanged.connect(self.update_checkboxes)

                    layout.addWidget(QLabel('Choose Data Type:'))
                    layout.addWidget(self.combobox)

                    # 다이얼로그의 OK/Cancel 버튼
                    self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    self.button_box.accepted.connect(self.accept)
                    self.button_box.rejected.connect(self.reject)

                    layout.addWidget(self.button_box)

                    self.setLayout(layout)
                    self.update_checkboxes()

                def update_checkboxes(self):
                    # 기존 체크박스 제거
                    for checkbox in self.checkbox_group:
                        checkbox.setParent(None)
                    self.checkbox_group.clear()

                    # 콤보박스 선택에 따라 다른 체크박스 표시
                    if self.combobox.currentText() == 'Naver News':
                        options = ['article 분석', 'statistics 분석', 'reply 분석', 'rereply 분석']
                    elif self.combobox.currentText() == 'Naver Blog':
                        options = ['article 분석', 'reply 분석']
                    elif self.combobox.currentText() == 'Naver Cafe':
                        options = ['article 분석', 'reply 분석']
                    elif self.combobox.currentText() == 'YouTube':
                        options = ['article 분석', 'reply 분석', 'rereply 분석']

                    for option in options:
                        checkbox = QCheckBox(option)
                        checkbox.setAutoExclusive(True)  # 중복 체크 불가
                        self.checkbox_group.append(checkbox)
                        self.layout().insertWidget(self.layout().count() - 1, checkbox)  # 버튼 위에 체크박스 추가

            selected_directory = self.dataprocess_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(self.main, f"Warning", "한 개의 CSV 파일만 선택하여 주십시오")
                return

            csv_path = selected_directory[0]
            csv_data = pd.read_csv(csv_path, low_memory=False)

            selected_options = []
            dialog = OptionDialog()
            if dialog.exec_() == QDialog.Accepted:
                selected_options = []

                # 선택된 체크박스 옵션 추가
                for checkbox in dialog.checkbox_group:
                    if checkbox.isChecked():
                        selected_options.append(checkbox.text())

                # 콤보박스에서 선택된 옵션 추가
                selected_options.append(dialog.combobox.currentText())

            match selected_options:
                case ['article 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsArticleAnalysis(csv_data, csv_path)
                case ['statistics 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsStatisticsAnalysis(csv_data, csv_path)
                case ['reply 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsReplyAnalysis(csv_data, csv_path)
                case ['rereply 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsRereplyAnalysis(csv_data, csv_path)
                case ['article 분석', 'Naver Cafe']:
                    self.dataprocess_obj.NaverCafeArticleAnalysis(csv_data, csv_path)
                case ['reply 분석', 'Naver Cafe']:
                    self.dataprocess_obj.NaverCafeReplyAnalysis(csv_data, csv_path)
                case []:
                    return
                case _:
                    QMessageBox.warning(self.main, "Warning", f"{selected_options[1]} {selected_options[0]} 분석은 지원되지 않는 기능입니다")
                    return

            self.main.openFileExplorer(os.path.dirname(csv_path))
            del csv_data
            gc.collect()
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def kimkem_kimkem(self):
        class KimKemOptionDialog(QDialog):
            def __init__(self, kimkem_file, rekimkem_file, interpret_kimkem):
                super().__init__()
                self.kimkem_file = kimkem_file
                self.rekimkem_file = rekimkem_file
                self.interpret_kimkem = interpret_kimkem
                self.initUI()
                self.data = None  # 데이터를 저장할 속성 추가

            def initUI(self):
                self.setWindowTitle('KEMKIM Start')
                self.resize(300, 100)  # 창 크기를 조정
                # 레이아웃 생성
                layout = QVBoxLayout()

                # 버튼 생성
                btn1 = QPushButton('새로운 KEMKIM 분석', self)
                btn2 = QPushButton('KEMKIM 그래프 조정', self)
                btn3 = QPushButton('KEMKIM 키워드 해석', self)
                
                # 버튼에 이벤트 연결
                btn1.clicked.connect(self.run_kimkem_file)
                btn2.clicked.connect(self.run_rekimkem_file)
                btn3.clicked.connect(self.run_interpretkimkem_file)
                
                # 버튼 배치를 위한 가로 레이아웃
                button_layout = QVBoxLayout()
                button_layout.addWidget(btn1)
                button_layout.addWidget(btn2)
                button_layout.addWidget(btn3)

                # 레이아웃에 버튼 레이아웃 추가
                layout.addLayout(button_layout)

                # 레이아웃을 다이얼로그에 설정
                self.setLayout(layout)
            
            def run_kimkem_file(self):
                self.accept()
                self.kimkem_file()
            
            def run_rekimkem_file(self):
                self.accept()
                self.rekimkem_file()

            def run_interpretkimkem_file(self):
                self.accept()
                self.interpret_kimkem()

        dialog = KimKemOptionDialog(self.kimkem_kimkem_file, self.kimkem_rekimkem_file, self.kimkem_interpretkimkem_file)
        dialog.exec_()
    
    def kimkem_kimkem_file(self):
        try:
            selected_directory = self.dataprocess_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                QMessageBox.warning(self.main, f"Warning", f"선택된 CSV 토큰 파일이 없습니다")
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(self.main, f"Warning", "한 개의 CSV 파일만 선택하여 주십시오")
                return
            elif 'token' not in selected_directory[0]:
                QMessageBox.warning(self.main, f"Warning", "토큰 파일이 아닙니다")
                return
            def start():
                token_data = pd.read_csv(selected_directory[0], low_memory=False)
                self.kimkem_kimkemStart(token_data, os.path.basename(selected_directory[0]))

            self.main.printStatus("파일 읽는 중...")
            QTimer.singleShot(1000, start)

        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())
    
    def kimkem_rekimkem_file(self):

        class WordSelector(QDialog):
            def __init__(self, words):
                super().__init__()
                self.words = words
                self.selected_words = []
                self.initUI()

            def initUI(self):
                # 메인 레이아웃을 감쌀 위젯 생성
                container_widget = QWidget()
                main_layout = QVBoxLayout(container_widget)

                self.info_label = QLabel('제외할 키워드를 선택하세요\n')
                main_layout.addWidget(self.info_label)

                # 체크박스를 배치할 각 그룹 박스 생성
                groups = ["Strong Signal", "Weak Signal", "Latent Signal", "Well-known Signal"]

                self.checkboxes = []
                self.select_all_checkboxes = {}
                for group_name, words in zip(groups, self.words):
                    group_box = QGroupBox(group_name)
                    group_layout = QVBoxLayout()

                    # '모두 선택' 체크박스 추가
                    select_all_checkbox = QCheckBox("모두 선택", self)
                    select_all_checkbox.stateChanged.connect(self.create_select_all_handler(group_name))
                    group_layout.addWidget(select_all_checkbox)
                    self.select_all_checkboxes[group_name] = select_all_checkbox

                    sorted_words = sorted(words)
                    num_columns = 10  # 한 행에 최대 10개의 체크박스

                    # 그리드 레이아웃 설정
                    grid_layout = QGridLayout()
                    grid_layout.setHorizontalSpacing(5)  # 수평 간격 설정
                    grid_layout.setVerticalSpacing(10)  # 수직 간격 설정
                    # 각 열이 동일한 비율로 확장되도록 설정
                    for col in range(num_columns):
                        grid_layout.setColumnStretch(col, 1)

                    for i, word in enumerate(sorted_words):
                        checkbox = QCheckBox(word, self)
                        checkbox.stateChanged.connect(self.create_individual_handler(group_name))
                        self.checkboxes.append(checkbox)
                        row = i // num_columns
                        col = i % num_columns
                        grid_layout.addWidget(checkbox, row, col)

                    group_layout.addLayout(grid_layout)
                    group_box.setLayout(group_layout)
                    main_layout.addWidget(group_box)

                # 그리드 레이아웃 사용
                grid_layout = QGridLayout()

                # 첫 번째 열 (왼쪽)
                self.x_size_label = QLabel('그래프 가로 스케일: ')
                self.x_size_input = QLineEdit()
                self.x_size_input.setText('100')  # 기본값 설정
                grid_layout.addWidget(self.x_size_label, 0, 0)
                grid_layout.addWidget(self.x_size_input, 0, 1)

                self.y_size_label = QLabel('그래프 세로 스케일: ')
                self.y_size_input = QLineEdit()
                self.y_size_input.setText('100')  # 기본값 설정
                grid_layout.addWidget(self.y_size_label, 0, 2)
                grid_layout.addWidget(self.y_size_input, 0, 3)

                self.font_size_label = QLabel('그래프 폰트 크기: ')
                self.font_size_input = QLineEdit()
                self.font_size_input.setText('50')  # 기본값 설정
                grid_layout.addWidget(self.font_size_label, 1, 0)
                grid_layout.addWidget(self.font_size_input, 1, 1)

                # 두 번째 열 (오른쪽)
                self.dot_size_label = QLabel('그래프 점 크기: ')
                self.dot_size_input = QLineEdit()
                self.dot_size_input.setText('20')  # 기본값 설정
                grid_layout.addWidget(self.dot_size_label, 1, 2)
                grid_layout.addWidget(self.dot_size_input, 1, 3)

                self.label_size_label = QLabel('그래프 레이블 글자 크기: ')
                self.label_size_input = QLineEdit()
                self.label_size_input.setText('12')  # 기본값 설정
                grid_layout.addWidget(self.label_size_label, 2, 0)
                grid_layout.addWidget(self.label_size_input, 2, 1)

                self.grade_size_label = QLabel('그래프 눈금 글자 크기: ')
                self.grade_size_input = QLineEdit()
                self.grade_size_input.setText('10')  # 기본값 설정
                grid_layout.addWidget(self.grade_size_label, 2, 2)
                grid_layout.addWidget(self.grade_size_input, 2, 3)

                main_layout.addLayout(grid_layout)

                # 애니메이션 체크박스 생성
                self.eng_checkbox_label = QLabel('\n키워드를 영어로 변환하시겠습니까? ')
                main_layout.addWidget(self.eng_checkbox_label)

                checkbox_layout = QHBoxLayout()
                self.eng_yes_checkbox = QCheckBox('Yes')
                self.eng_no_checkbox = QCheckBox('No')

                self.eng_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
                self.eng_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

                # 서로 배타적으로 선택되도록 설정
                self.eng_yes_checkbox.toggled.connect(
                    lambda: self.eng_no_checkbox.setChecked(False) if self.eng_yes_checkbox.isChecked() else None)
                self.eng_no_checkbox.toggled.connect(
                    lambda: self.eng_yes_checkbox.setChecked(False) if self.eng_no_checkbox.isChecked() else None)

                checkbox_layout.addWidget(self.eng_yes_checkbox)
                checkbox_layout.addWidget(self.eng_no_checkbox)
                main_layout.addLayout(checkbox_layout)

                # 선택된 단어 출력 버튼 추가
                btn = QPushButton('그래프 설정 완료', self)
                btn.clicked.connect(self.show_selected_words)
                main_layout.addWidget(btn)

                # QScrollArea 설정
                scroll_area = QScrollArea(self)
                scroll_area.setWidgetResizable(True)
                scroll_area.setWidget(container_widget)  # 위젯을 스크롤 영역에 추가

                # 기존의 main_layout을 scroll_area에 추가
                final_layout = QVBoxLayout()
                final_layout.addWidget(scroll_area)

                # 창 설정
                self.setLayout(final_layout)
                self.setWindowTitle('KEMKIM 그래프 조정')
                self.resize(800, 600)
                self.show()

            def create_select_all_handler(self, group_name):
                def select_all_handler(state):
                    group_checkboxes = [
                        cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
                    ]
                    for checkbox in group_checkboxes:
                        checkbox.blockSignals(True)  # 시그널을 일시적으로 비활성화
                        checkbox.setChecked(state == Qt.Checked)
                        checkbox.blockSignals(False)  # 시그널 다시 활성화
                    # 모두 선택/해제 시, 다른 개별 체크박스 핸들러의 영향 없이 동작하게 하기 위해 시그널을 임시로 막아둠

                return select_all_handler

            def create_individual_handler(self, group_name):
                def individual_handler():
                    group_checkboxes = [
                        cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
                    ]
                    all_checked = all(cb.isChecked() for cb in group_checkboxes)
                    if not all_checked:
                        self.select_all_checkboxes[group_name].blockSignals(True)
                        self.select_all_checkboxes[group_name].setChecked(False)
                        self.select_all_checkboxes[group_name].blockSignals(False)

                return individual_handler
            def show_selected_words(self):
                # 선택된 단어를 리스트에 추가
                self.selected_words = [cb.text() for cb in self.checkboxes if cb.isChecked()]
                self.size_input = (self.x_size_input.text(), self.y_size_input.text(), self.font_size_input.text(), self.dot_size_input.text(), self.label_size_input.text(), self.grade_size_input.text())
                self.eng_checked = self.eng_yes_checkbox.isChecked()
                # 선택된 단어를 메시지 박스로 출력
                if self.selected_words == []:
                    QMessageBox.information(self, '선택한 단어', '선택된 단어가 없습니다')
                else:
                    QMessageBox.information(self, '선택한 단어', ', '.join(self.selected_words))
                self.accept()

        def copy_csv(input_file_path, output_file_path):
                # CSV 파일 읽기
            with open(input_file_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                
                # 모든 데이터를 읽어옵니다 (헤더 포함)
                rows = list(reader)

            # 읽은 데이터를 그대로 새로운 CSV 파일로 저장하기
            with open(output_file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # 데이터를 행 단위로 다시 작성합니다
                for row in rows:
                    writer.writerow(row)
        
        try:
            result_directory = self.file_dialog.selectedFiles()
            if len(result_directory) == 0:
                QMessageBox.warning(self.main, f"Warning", f"선택된 'Result' 디렉토리가 없습니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return
            elif len(result_directory) > 1:
                QMessageBox.warning(self.main, f"Warning", f"KemKim 폴더에 있는 하나의 'Result' 디렉토리만 선택하여 주십시오")
                return
            elif 'Result' not in os.path.basename(result_directory[0]):
                QMessageBox.warning(self.main, f"Warning", f"'Result' 디렉토리가 아닙니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return
            
            self.main.printStatus("KEMKIM 재분석 중...")
            
            result_directory = result_directory[0]
            final_signal_csv_path = os.path.join(result_directory, "Signal", "Final_signal.csv")
            if not os.path.exists(final_signal_csv_path):
                QMessageBox.information(self.main, 'Information', 'Final_signal.csv 파일을 불러오는데 실패했습니다\n\nResult/Signal 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                self.main.printStatus()
                return
            final_signal_df = pd.read_csv(final_signal_csv_path, low_memory=False)
            words = final_signal_df['word'].tolist()
            all_keyword = []
            for word_list_str in words:
                word_list = ast.literal_eval(word_list_str)
                all_keyword.append(word_list)
            
            self.word_selector = WordSelector(all_keyword)
            if self.word_selector.exec_() == QDialog.Accepted:  # show() 대신 exec_() 사용
                selected_words = self.word_selector.selected_words
                size_input = self.word_selector.size_input
                eng_option = self.word_selector.eng_checked
                try:
                    size_input = tuple(map(int, size_input))
                except:
                    QMessageBox.information(self.main, "Information", "그래프 사이즈를 숫자로 입력하여 주십시오")
                    self.main.printStatus()
                    return
            else:
                self.main.printStatus()
                return

            if eng_option == True:
                QMessageBox.information(self.main, "Information", f"키워드-영단어 사전(CSV)를 선택하세요")
                eng_keyword_list_path = QFileDialog.getOpenFileName(self.main, "키워드-영단어 사전(CSV)를 선택하세요", self.main.default_directory, "CSV Files (*.csv);;All Files (*)")
                eng_keyword_list_path = eng_keyword_list_path[0]
                if eng_keyword_list_path == "":
                    return
                with open(eng_keyword_list_path, 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']
                df = pd.read_csv(eng_keyword_list_path, low_memory=False, encoding=codec)
                if 'english' not in list(df.keys()) or 'korean' not in list(df.keys()):
                    QMessageBox.information(self.main, "Warning", "키워드-영단어 사전 형식과 일치하지 않습니다")
                    return
                eng_keyword_tupleList = list(zip(df['korean'], df['english']))
            else:
                eng_keyword_tupleList = []

            DoV_coordinates_path = os.path.join(result_directory, "Graph", "DOV_coordinates.csv")
            if not os.path.exists(DoV_coordinates_path):
                QMessageBox.information(self.main, 'Information', 'DOV_coordinates.csv 파일을 불러오는데 실패했습니다\n\nResult/Graph 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                self.main.printStatus()
                return
            DoV_coordinates_df = pd.read_csv(DoV_coordinates_path)
            DoV_coordinates_dict = {}
            for index, row in DoV_coordinates_df.iterrows():
                key = row['key']
                value = ast.literal_eval(row['value'])  # 문자열을 튜플로 변환
                DoV_coordinates_dict[key] = value

            DoD_coordinates_path = os.path.join(result_directory, "Graph", "DOD_coordinates.csv")
            if not os.path.exists(DoD_coordinates_path):
                QMessageBox.information(self.main, 'Information', 'DOD_coordinates.csv 파일을 불러오는데 실패했습니다\n\nResult/Graph 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                self.main.printStatus()
                return
            DoD_coordinates_df = pd.read_csv(os.path.join(result_directory, "Graph", "DOD_coordinates.csv"))
            DoD_coordinates_dict = {}
            for index, row in DoD_coordinates_df.iterrows():
                key = row['key']
                value = ast.literal_eval(row['value'])  # 문자열을 튜플로 변환
                DoD_coordinates_dict[key] = value
                
            delete_word_list = pd.read_csv(os.path.join(result_directory, 'filtered_words.csv'))['word'].tolist()
            
            kimkem_obj = KimKem(exception_word_list=selected_words, rekemkim=True)
            
            new_result_folder = os.path.join(os.path.dirname(result_directory), f'Result_{datetime.now().strftime('%m%d%H%M')}')
            new_graph_folder = os.path.join(new_result_folder, 'Graph')
            new_signal_folder = os.path.join(new_result_folder, 'Signal')
            
            os.makedirs(new_result_folder, exist_ok=True)
            os.makedirs(new_graph_folder, exist_ok=True)
            os.makedirs(new_signal_folder, exist_ok=True)
            
            self.main.openFileExplorer(new_result_folder)
            
            # 그래프 Statistics csv 복사
            copy_csv(os.path.join(result_directory, "Graph", "DOD_statistics.csv"), os.path.join(new_graph_folder, "DOD_statistics.csv"))
            copy_csv(os.path.join(result_directory, "Graph", "DOD_statistics.csv"), os.path.join(new_graph_folder, "DOD_statistics.csv"))
            
            DoV_signal, DoV_coordinates = kimkem_obj.DoV_draw_graph(graph_folder=new_graph_folder, redraw_option=True, coordinates=DoV_coordinates_dict, graph_size=size_input, eng_keyword_list=eng_keyword_tupleList)
            DoD_signal, DoD_coordinates = kimkem_obj.DoD_draw_graph(graph_folder=new_graph_folder, redraw_option=True, coordinates=DoD_coordinates_dict, graph_size=size_input, eng_keyword_list=eng_keyword_tupleList)

            final_signal = kimkem_obj._get_communal_signals(DoV_signal, DoD_signal)
            final_signal_list = []
            for value in final_signal.values():
                final_signal_list.extend(value)

            kimkem_obj.DoV_draw_graph(graph_folder=new_graph_folder, redraw_option=True, coordinates=DoV_coordinates_dict, final_signal_list=final_signal_list, graph_name='KEM_graph.png', graph_size=size_input, eng_keyword_list=eng_keyword_tupleList)
            kimkem_obj.DoD_draw_graph(graph_folder=new_graph_folder, redraw_option=True, coordinates=DoD_coordinates_dict, final_signal_list=final_signal_list, graph_name='KIM_graph.png', graph_size=size_input, eng_keyword_list=eng_keyword_tupleList)
            kimkem_obj._save_final_signals(DoV_signal, DoD_signal, new_signal_folder)
            
            delete_word_list.extend(selected_words)
            pd.DataFrame(delete_word_list, columns=['word']).to_csv(os.path.join(new_result_folder, 'filtered_words.csv'), index = False, encoding='utf-8-sig')

            with open(os.path.join(new_graph_folder, 'graph_size.txt'),'w+') as graph_size:
                info = (
                    f'X Scale: {size_input[0]}\n'
                    f'Y Scale: {size_input[1]}\n'
                    f'Font Size: {size_input[2]}\n'
                    f'Dot Size: {size_input[3]}\n'
                    f'Label Size: {size_input[4]}\n'
                    f'Grade Size: {size_input[5]}'
                )
                graph_size.write(info)
            del kimkem_obj
            gc.collect()

            self.main.printStatus()
            QMessageBox.information(self.main, 'Information', 'KEMKIM 재분석이 완료되었습니다')
        
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def kimkem_interpretkimkem_file(self):
        class WordSelector(QDialog):
            def __init__(self, words):
                super().__init__()
                self.words = words
                self.selected_words = []
                self.initUI()

            def initUI(self):
                # 메인 레이아웃을 감쌀 위젯 생성
                container_widget = QWidget()
                main_layout = QVBoxLayout(container_widget)

                # 체크박스를 배치할 각 그룹 박스 생성
                groups = ["Strong Signal", "Weak Signal", "Latent Signal", "Well-known Signal"]

                self.checkboxes = []
                self.select_all_checkboxes = {}
                for group_name, words in zip(groups, self.words):
                    group_box = QGroupBox(group_name)
                    group_layout = QVBoxLayout()

                    # '모두 선택' 체크박스 추가
                    select_all_checkbox = QCheckBox("모두 선택", self)
                    select_all_checkbox.stateChanged.connect(self.create_select_all_handler(group_name))
                    group_layout.addWidget(select_all_checkbox)
                    self.select_all_checkboxes[group_name] = select_all_checkbox

                    sorted_words = sorted(words)
                    num_columns = 10  # 한 행에 최대 10개의 체크박스

                    # 그리드 레이아웃 설정
                    grid_layout = QGridLayout()
                    grid_layout.setHorizontalSpacing(5)  # 수평 간격 설정
                    grid_layout.setVerticalSpacing(10)  # 수직 간격 설정
                    # 각 열이 동일한 비율로 확장되도록 설정
                    for col in range(num_columns):
                        grid_layout.setColumnStretch(col, 1)

                    for i, word in enumerate(sorted_words):
                        checkbox = QCheckBox(word, self)
                        checkbox.stateChanged.connect(self.create_individual_handler(group_name))
                        self.checkboxes.append(checkbox)
                        row = i // num_columns
                        col = i % num_columns
                        grid_layout.addWidget(checkbox, row, col)

                    group_layout.addLayout(grid_layout)
                    group_box.setLayout(group_layout)
                    main_layout.addWidget(group_box)

                # 라디오 버튼 추가
                self.radio_button_group = QButtonGroup(self)

                radio_all = QRadioButton("모두 포함", self)
                radio_part = QRadioButton("개별 포함", self)

                self.radio_button_group.addButton(radio_all)
                self.radio_button_group.addButton(radio_part)

                main_layout.addWidget(radio_all)
                main_layout.addWidget(radio_part)

                # 기본값 설정 (첫 번째 옵션 선택)
                radio_all.setChecked(True)

                # 선택된 단어 출력 버튼 추가
                btn = QPushButton('포함 단어 결정', self)
                btn.clicked.connect(self.show_selected_words)
                main_layout.addWidget(btn)

                # QScrollArea 설정
                scroll_area = QScrollArea(self)
                scroll_area.setWidgetResizable(True)
                scroll_area.setWidget(container_widget)  # 위젯을 스크롤 영역에 추가

                # 기존의 main_layout을 scroll_area에 추가
                final_layout = QVBoxLayout()
                final_layout.addWidget(scroll_area)

                # 창 설정
                self.setLayout(final_layout)
                self.setWindowTitle('크롤링 데이터 CSV 필터링 기준 단어를 선택하세요')
                self.resize(800, 600)
                self.show()

            def create_select_all_handler(self, group_name):
                def select_all_handler(state):
                    group_checkboxes = [
                        cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
                    ]
                    for checkbox in group_checkboxes:
                        checkbox.blockSignals(True)  # 시그널을 일시적으로 비활성화
                        checkbox.setChecked(state == Qt.Checked)
                        checkbox.blockSignals(False)  # 시그널 다시 활성화
                    # 모두 선택/해제 시, 다른 개별 체크박스 핸들러의 영향 없이 동작하게 하기 위해 시그널을 임시로 막아둠

                return select_all_handler

            def create_individual_handler(self, group_name):
                def individual_handler():
                    group_checkboxes = [
                        cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
                    ]
                    all_checked = all(cb.isChecked() for cb in group_checkboxes)
                    if not all_checked:
                        self.select_all_checkboxes[group_name].blockSignals(True)
                        self.select_all_checkboxes[group_name].setChecked(False)
                        self.select_all_checkboxes[group_name].blockSignals(False)

                return individual_handler

            def show_selected_words(self):
                # 선택된 단어들을 그룹별로 분류하여 2차원 리스트로 저장
                selected_words_by_group = []

                groups = ["Strong Signal", "Weak Signal", "Latent Signal", "Well-known Signal"]

                for group_name in groups:
                    group_checkboxes = [
                        cb for cb in self.checkboxes if cb.parentWidget().title() == group_name
                    ]
                    selected_words = [cb.text() for cb in group_checkboxes if cb.isChecked()]
                    selected_words_by_group.append(selected_words)

                self.selected_words = selected_words_by_group
                self.selected_option = self.radio_button_group.checkedButton().text()

                # 선택된 단어를 메시지 박스로 출력
                selected_words_str = '\n'.join(
                    f"{group}: {', '.join(words)}" for group, words in zip(groups, self.selected_words))
                QMessageBox.information(self, '선택한 단어', selected_words_str)
                self.accept()

        try:
            result_directory = self.file_dialog.selectedFiles()
            if len(result_directory) == 0:
                QMessageBox.warning(self.main, f"Warning", f"선택된 'Result' 디렉토리가 없습니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return
            elif len(result_directory) > 1:
                QMessageBox.warning(self.main, f"Warning", f"KemKim 폴더에 있는 하나의 'Result' 디렉토리만 선택하여 주십시오")
                return
            elif 'Result' not in os.path.basename(result_directory[0]):
                QMessageBox.warning(self.main, f"Warning", f"'Result' 디렉토리가 아닙니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return

            result_directory = result_directory[0]
            final_signal_csv_path = os.path.join(result_directory, "Signal", "Final_signal.csv")

            if not os.path.exists(final_signal_csv_path):
                QMessageBox.information(self.main, 'Information', 'Final_signal.csv 파일을 불러오는데 실패했습니다\n\nResult/Signal 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                self.main.printStatus()
                return

            final_signal_df = pd.read_csv(final_signal_csv_path, low_memory=False)
            words = final_signal_df['word'].tolist()
            all_keyword = []
            for word_list_str in words:
                word_list = ast.literal_eval(word_list_str)
                all_keyword.append(word_list)

            startdate = 0
            enddate = 0
            topic = 0

            infotxt_path = os.path.join(os.path.dirname(result_directory), "kemkim_info.txt")
            if not os.path.exists(final_signal_csv_path):
                QMessageBox.information(self.main, 'Information', 'kemkim_info.txt 파일을 불러오는데 실패했습니다\n\nResult 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                self.main.printStatus()
                return

            with open(infotxt_path, 'r') as info_txt:
                lines = info_txt.readlines()

            for line in lines:
                if line.startswith('분석 데이터:'):
                    # '분석 데이터:' 뒤에 오는 값을 파싱
                    recommend_csv_name = line.split('분석 데이터:')[-1].strip().replace('token_', '')
                    topic = recommend_csv_name.split('_')[1]
                if line.startswith('분석 시작일:'):
                    # '분석 데이터:' 뒤에 오는 값을 파싱
                    startdate = line.split('분석 시작일:')[-1].strip().replace('token_', '')
                    startdate = int(startdate)
                if line.startswith('분석 종료일:'):
                    # '분석 데이터:' 뒤에 오는 값을 파싱
                    enddate = line.split('분석 종료일:')[-1].strip().replace('token_', '')
                    enddate = int(enddate)

            if startdate == 0 or enddate == 0 or topic == 0:
                QMessageBox.information(self.main, 'Information', 'kemkim_info.txt 파일에서 정보를 불러오는데 실패했습니다\n\nResult 디렉토리 선택 유무와 수정되지 않은 info.txt 원본 파일이 올바른 위치에 있는지 확인하여 주십시오')
                self.main.printStatus()
                return

            QMessageBox.information(self.main, "Information", f'Keyword를 추출할 CSV 파일을 선택하세요\n\n"{recommend_csv_name}"를 선택하세요')
            object_csv_path = QFileDialog.getOpenFileName(self.main, "Keyword 추출 대상 CSV 파일을 선택하세요", self.main.default_directory, "CSV Files (*.csv);;All Files (*)")
            object_csv_path = object_csv_path[0]
            object_csv_name = os.path.basename(object_csv_path).replace('.csv', '')
            if object_csv_path == "":
                return

            self.main.printStatus("CSV 데이터 키워드 필터링 중...")
            self.word_selector = WordSelector(all_keyword)
            if self.word_selector.exec_() == QDialog.Accepted:  # show() 대신 exec_() 사용
                selected_words_2dim = self.word_selector.selected_words
                selected_words = [word for group in selected_words_2dim for word in group]
                selected_option = self.word_selector.selected_option
            else:
                self.main.printStatus()
                return

            # 단어 선택 안했을 때
            if len(selected_words) == 0:
                QMessageBox.information(self.main, 'Information', '선택된 필터링 단어가 없습니다')
                return

            with open(object_csv_path, 'rb') as f:
                codec = chardet.detect(f.read())['encoding']
            object_csv_df = pd.read_csv(object_csv_path, low_memory=False, encoding=codec)
            if all('Text' not in word for word in list(object_csv_df.keys())):
                QMessageBox.information(self.main, "Warning", "크롤링 데이터 CSV 형식과 일치하지 않습니다")
                return
            for column in object_csv_df.columns.tolist():
                if 'Text' in column:
                    textColumn_name = column
                elif 'Date' in column:
                    dateColumn_name = column

            # 날짜 범위 설정
            object_csv_df[dateColumn_name] = pd.to_datetime(object_csv_df[dateColumn_name], format='%Y-%m-%d', errors='coerce')
            start_date = pd.to_datetime(str(startdate), format='%Y%m%d')
            end_date = pd.to_datetime(str(enddate), format='%Y%m%d')
            # 날짜 범위 필터링
            object_csv_df = object_csv_df[object_csv_df[dateColumn_name].between(start_date, end_date)]

            if selected_option == "모두 포함":
                filtered_object_csv_df = object_csv_df[object_csv_df[textColumn_name].apply(lambda x: all(word in str(x) for word in selected_words))]
            else:
                filtered_object_csv_df = object_csv_df[object_csv_df[textColumn_name].apply(lambda x: any(word in str(x) for word in selected_words))]

            if filtered_object_csv_df.shape[0] < 1:
                QMessageBox.information(self.main, "Information", "필터링 키워드를 포함하는 데이터가 존재하지 않습니다")
                return

            analyze_directory = os.path.join(os.path.dirname(result_directory), f'Analysis_{datetime.now().strftime('%m%d%H%M')}')
            selected_words_dic = {
                'Filter Option': selected_option,
                'Strong Signal': ','.join(selected_words_2dim[0]),
                'Weak Signal': ','.join(selected_words_2dim[1]),
                'Latent Signal': ','.join(selected_words_2dim[2]),
                'Well-known Signal': ','.join(selected_words_2dim[3]),
            }

            reply = QMessageBox.question(self.main, 'Confirm Delete', f'CSV 키워드 필터링이 완료되었습니다\n키워드를 포함하는 데이터는 {filtered_object_csv_df.shape[0]}개입니다\n\n데이터를 저장하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                os.makedirs(analyze_directory, exist_ok=True)
                os.makedirs(os.path.join(analyze_directory, 'keyword_context'), exist_ok=True)
                filtered_object_csv_df.to_csv(os.path.join(analyze_directory, f"{object_csv_name}(키워드 {selected_option}).csv"), index = False, encoding='utf-8-sig')
                pd.DataFrame([selected_words_dic]).to_csv(os.path.join(analyze_directory, f"filtered_words.csv"), index = False, encoding='utf-8-sig')

                def extract_surrounding_text(text, keyword, chars_before=200, chars_after=200):
                    # 키워드 위치 찾기
                    match = re.search(keyword, text)
                    if match:
                        start = max(match.start() - chars_before, 0)
                        end = min(match.end() + chars_after, len(text))

                        # 키워드를 강조 표시
                        highlighted_keyword = f'_____{keyword}_____'
                        extracted_text = text[start:end]

                        # 키워드를 강조 표시된 버전으로 대체
                        extracted_text = extracted_text.replace(keyword, highlighted_keyword)

                        return extracted_text
                    else:
                        return None  # 키워드가 없으면 None 반환

                context_dict = {}
                for keyword in selected_words:
                    extracted_texts = filtered_object_csv_df[textColumn_name].apply(lambda x: extract_surrounding_text(x, keyword))
                    keyword_texts = extracted_texts.dropna().tolist()
                    add_text = "\n\n".join(keyword_texts)
                    if keyword_texts:
                        context_dict[keyword] = add_text
                    with open(os.path.join(analyze_directory, 'keyword_context', f'{keyword}_context.txt'), 'w', encoding='utf-8-sig') as context:
                        context.write(add_text)

                context_df = pd.DataFrame(list(context_dict.items()), columns=['Keyword', 'Context Text'])
                # 데이터프레임을 CSV 파일로 저장
                context_df.to_csv(os.path.join(analyze_directory,  'keyword_context', 'keyword_context.csv'), index=False, encoding='utf-8-sig')
            else:
                self.main.printStatus()
                return

            if any('Title' in word for word in list(filtered_object_csv_df.keys())):
                reply = QMessageBox.question(self.main, 'Confirm Delete', f'키워드 필터링 데이터 저장이 완료되었습니다\n\nAI 분석을 진행하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    def gpt_start():
                        for column in filtered_object_csv_df.columns.tolist():
                            if 'Title' in column:
                                titleColumn_name = column
                                
                        if filtered_object_csv_df[titleColumn_name].count() > 50:
                            random_titles = filtered_object_csv_df[titleColumn_name].sample(n=50, random_state=42)
                        else:
                            random_titles = filtered_object_csv_df[titleColumn_name]
                        
                        merged_title = ' '.join(random_titles.tolist())
                        gpt_query = (
                            "한국어로 대답해. 지금 밑에 있는 텍스트는 신문기사의 제목들을 모아놓은거야\n\n"
                            f"{merged_title}\n\n"
                            f"이 신문기사 제목들은 검색창에 {topic}이라고 검색했을 때 나온 신문기사 제목이야"
                            "제시된 여러 개의 뉴스기사 제목을 바탕으로 관련된 토픽(주제)를 추출 및 요약해줘. 토픽은 최소 1개에서 최대 5개를 제시해줘. 토픽 추출 및 요약 방식, 너의 응답 형식은 다음과 같아\n"
                            "토픽 1. ~~: (여기에 내용 기입)\n"
                            "토픽 2. ~~: (여기에 내용 기입)\n"
                            "...\n"
                            "토픽 5. ~~: (여기에 내용 기입)"
                        )
                        gpt_response = self.main.chatgpt_generate(gpt_query)
                        if type(gpt_response) != str:
                            QMessageBox.information(self.main, "Information", f"{gpt_response[1]}")
                            self.main.printStatus()
                            self.main.openFileExplorer(analyze_directory)
                            return

                        with open(os.path.join(analyze_directory, f"{object_csv_name}(키워드 {selected_option})_AI_analyze.txt"), 'w+') as gpt_txt:
                            gpt_txt.write(gpt_response)

                        QMessageBox.information(self.main, "AI 분석 결과", gpt_response)
                        self.main.printStatus()
                        self.main.openFileExplorer(analyze_directory)

                    self.main.printStatus("AI 분석 중...")
                    QTimer.singleShot(1000, gpt_start)
                else:
                    self.main.printStatus()
                    self.main.openFileExplorer(analyze_directory)
            else:
                QMessageBox.information(self.main, "Information", f"CSV 키워드 필터링이 완료되었습니다\n키워드를 포함하는 데이터는 {filtered_object_csv_df.shape[0]}개입니다")
                self.main.openFileExplorer(analyze_directory)

        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def kimkem_kimkemStart(self, token_data, tokenfile_name):
        class KimKemInputDialog(QDialog):
            def __init__(self, tokenfile_name):
                super().__init__()
                self.initUI()
                self.data = None  # 데이터를 저장할 속성 추가

            def initUI(self):
                
                self.setWindowTitle('KEM KIM OPTION')
                self.resize(300, 250)  # 창 크기를 조정

                layout = QVBoxLayout()

                # 레이아웃의 마진과 간격 조정
                layout.setContentsMargins(10, 10, 10, 10)  # (left, top, right, bottom) 여백 설정
                layout.setSpacing(10)  # 위젯 간 간격 설정

                # 각 입력 필드를 위한 QLabel 및 QDateEdit 생성
                self.startdate_label = QLabel('분석 시작 일자를 선택하세요: ')
                self.startdate_input = QDateEdit(calendarPopup=True)
                self.startdate_input.setDisplayFormat('yyyyMMdd')
                self.startdate_input.setDate(QDate.currentDate())
                layout.addWidget(self.startdate_label)
                layout.addWidget(self.startdate_input)

                self.enddate_label = QLabel('분석 종료 일자를 선택하세요: ')
                self.enddate_input = QDateEdit(calendarPopup=True)
                self.enddate_input.setDisplayFormat('yyyyMMdd')
                self.enddate_input.setDate(QDate.currentDate())
                layout.addWidget(self.enddate_label)
                layout.addWidget(self.enddate_input)
                
                # 새로운 드롭다운 메뉴(QComboBox) 생성
                self.period_option_label = QLabel('분석 주기 선택: ')
                layout.addWidget(self.period_option_label)
                
                self.period_option_menu = QComboBox()
                self.period_option_menu.addItem('1년 (Yearly)')
                self.period_option_menu.addItem('6개월 (Half-Yearly)')
                self.period_option_menu.addItem('3개월 (Quarterly)')
                self.period_option_menu.addItem('1개월 (Monthly)')
                self.period_option_menu.addItem('1주 (Weekly)')
                self.period_option_menu.addItem('1일 (Daily)')
                layout.addWidget(self.period_option_menu)

                self.topword_label = QLabel('상위 단어 개수를 입력하세요: ')
                self.topword_input = QLineEdit()
                self.topword_input.setText('500')  # 기본값 설정
                layout.addWidget(self.topword_label)
                layout.addWidget(self.topword_input)

                # Time Weight 입력 필드 생성 및 레이아웃에 추가
                self.weight_label = QLabel('시간 가중치(tw)를 입력하세요: ')
                self.weight_input = QLineEdit()
                self.weight_input.setText('0.1')  # 기본값 설정
                layout.addWidget(self.weight_label)
                layout.addWidget(self.weight_input)

                # Period Option Menu 선택 시 시간 가중치 변경 함수 연결
                self.period_option_menu.currentIndexChanged.connect(self.update_weight)

                self.wordcnt_label = QLabel('그래프 애니메이션에 띄울 단어의 개수를 입력하세요: ')
                self.wordcnt_input = QLineEdit()
                self.wordcnt_input.setText('10')  # 기본값 설정
                layout.addWidget(self.wordcnt_label)
                layout.addWidget(self.wordcnt_input)

                # 애니메이션 체크박스 생성
                self.ani_checkbox_label = QLabel('추적 데이터를 시각화하시겠습니까? ')
                layout.addWidget(self.ani_checkbox_label)

                checkbox_layout = QHBoxLayout()
                self.ani_yes_checkbox = QCheckBox('Yes')
                self.ani_no_checkbox = QCheckBox('No')

                self.ani_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
                self.ani_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

                # 서로 배타적으로 선택되도록 설정
                self.ani_yes_checkbox.toggled.connect(
                    lambda: self.ani_no_checkbox.setChecked(False) if self.ani_yes_checkbox.isChecked() else None)
                self.ani_no_checkbox.toggled.connect(
                    lambda: self.ani_yes_checkbox.setChecked(False) if self.ani_no_checkbox.isChecked() else None)

                checkbox_layout.addWidget(self.ani_yes_checkbox)
                checkbox_layout.addWidget(self.ani_no_checkbox)
                layout.addLayout(checkbox_layout)

                # 체크박스 생성
                self.except_checkbox_label = QLabel('제외 단어 리스트를 추가하시겠습니까? ')
                layout.addWidget(self.except_checkbox_label)

                checkbox_layout = QHBoxLayout()
                self.except_yes_checkbox = QCheckBox('Yes')
                self.except_no_checkbox = QCheckBox('No')

                self.except_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
                self.except_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

                # 서로 배타적으로 선택되도록 설정
                self.except_yes_checkbox.toggled.connect(
                    lambda: self.except_no_checkbox.setChecked(False) if self.except_yes_checkbox.isChecked() else None)
                self.except_no_checkbox.toggled.connect(
                    lambda: self.except_yes_checkbox.setChecked(False) if self.except_no_checkbox.isChecked() else None)

                checkbox_layout.addWidget(self.except_yes_checkbox)
                checkbox_layout.addWidget(self.except_no_checkbox)
                layout.addLayout(checkbox_layout)

                # 드롭다운 메뉴(QComboBox) 생성
                self.dropdown_label = QLabel('분할 기준: ')
                layout.addWidget(self.dropdown_label)

                self.dropdown_menu = QComboBox()
                self.dropdown_menu.addItem('평균(Mean)')
                self.dropdown_menu.addItem('중앙값(Median)')
                self.dropdown_menu.addItem('직접 입력: 상위( )%')
                layout.addWidget(self.dropdown_menu)

                # 추가 입력창 (QLineEdit), 초기에는 숨김
                self.additional_input_label = QLabel('숫자를 입력하세요')
                self.additional_input = QLineEdit()
                self.additional_input.setPlaceholderText('입력')
                self.additional_input_label.hide()
                self.additional_input.hide()
                layout.addWidget(self.additional_input_label)
                layout.addWidget(self.additional_input)

                # 드롭다운 메뉴의 항목 변경 시 추가 입력창을 표시/숨김
                self.dropdown_menu.currentIndexChanged.connect(self.handle_dropdown_change)

                # 확인 버튼 생성 및 클릭 시 동작 연결
                self.submit_button = QPushButton('분석 실행')
                self.submit_button.clicked.connect(self.submit)
                layout.addWidget(self.submit_button)

                self.setLayout(layout)

            def handle_dropdown_change(self, index):
                # 특정 옵션이 선택되면 추가 입력창을 표시, 그렇지 않으면 숨김
                if self.dropdown_menu.currentText() == '직접 입력: 상위( )%':
                    self.additional_input_label.show()
                    self.additional_input.show()
                else:
                    self.additional_input_label.hide()
                    self.additional_input.hide()

            def update_weight(self):
                period = self.period_option_menu.currentText()
                if period == '1 (Yearly)':
                    self.weight_input.setText('0.1')
                elif period == '6개월 (Half-Yearly)':
                    self.weight_input.setText('0.05')
                elif period == '3개월 (Quarterly)':
                    self.weight_input.setText('0.025')
                elif period == '1개월 (Monthly)':
                    self.weight_input.setText('0.008')
                elif period == '1주 (Weekly)':
                    self.weight_input.setText('0.002')
                elif period == '1일 (Daily)':
                    self.weight_input.setText('0.0003')

            def submit(self):
                # 입력된 데이터를 확인하고 처리
                startdate = self.startdate_input.text()
                enddate = self.enddate_input.text()
                period = self.period_option_menu.currentText()
                match period:
                    case '1년 (Yearly)':
                        period = '1y'
                    case '6개월 (Half-Yearly)':
                        period = '6m'
                    case '3개월 (Quarterly)':
                        period = '3m'
                    case '1개월 (Monthly)':
                        period = '1m'
                    case '1주 (Weekly)':
                        period = '1w'
                    case '1일 (Daily)':
                        period = '1d'

                topword = self.topword_input.text()
                weight = self.weight_input.text()
                graph_wordcnt = self.wordcnt_input.text()
                ani_yes_selected = self.ani_yes_checkbox.isChecked()
                except_yes_selected = self.except_yes_checkbox.isChecked()
                split_option = self.dropdown_menu.currentText()
                split_custom = self.additional_input.text() if self.additional_input.isVisible() else None

                self.data = {
                    'startdate': startdate,
                    'enddate': enddate,
                    'period': period,
                    'topword': topword,
                    'weight': weight,
                    'graph_wordcnt': graph_wordcnt,
                    'ani_yes_selected': ani_yes_selected,
                    'except_yes_selected': except_yes_selected,
                    'split_option': split_option,
                    'split_custom': split_custom
                }
                self.accept()
        try:
            self.main.printStatus("KEM KIM 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(self.main, "KEM KIM 데이터를 저장할 위치를 선택하세요", self.main.default_directory)
            if save_path == '':
                self.main.printStatus()
                return

            self.main.printStatus(f"{tokenfile_name} KEMKIM 분석 중...")
            while True:
                dialog = KimKemInputDialog(tokenfile_name)
                dialog.exec_()
                try:
                    if dialog.data == None:
                        return
                    startdate = dialog.data['startdate']
                    enddate = dialog.data['enddate']
                    period = dialog.data['period']
                    topword = int(dialog.data['topword'])
                    weight = float(dialog.data['weight'])
                    graph_wordcnt = int(dialog.data['graph_wordcnt'])
                    ani_yes_selected = dialog.data['ani_yes_selected']
                    except_yes_selected = dialog.data['except_yes_selected']
                    split_option = dialog.data['split_option']
                    split_custom = dialog.data['split_custom']
                    # Calculate total periods based on the input period

                    if period == '1y':
                        total_periods = (1 / int(period[:-1])) * (int(enddate[:-4]) - int(startdate[:-4]) + 1)
                    elif period in ['6m', '3m', '1m']:
                        total_periods = (12 / int(period[:-1])) * (int(enddate[:-4]) - int(startdate[:-4]) + 1)
                    elif period == '1w':
                        total_days = (datetime.strptime(str(enddate), '%Y%m%d') - datetime.strptime(str(startdate),'%Y%m%d')).days
                        total_periods = total_days // 7
                        if datetime.strptime(startdate, '%Y%m%d').strftime('%A') != 'Monday':
                            QMessageBox.information(self.main, "Warning", "분석 시작일이 월요일이 아닙니다\n\n1주 단위 분석에서는 분석 시작일을 월요일, 분석 종료일을 일요일로 설정하십시오")
                            continue
                        if datetime.strptime(enddate, '%Y%m%d').strftime('%A') != 'Sunday':
                            QMessageBox.information(self.main, "Warning", "분석 종료일이 일요일이 아닙니다\n\n1주 단위 분석에서는 분석 시작일을 월요일, 분석 종료일을 일요일로 설정하십시오")
                            continue
                    else:  # assuming '1d' or similar daily period
                        total_days = (datetime.strptime(str(enddate), '%Y%m%d') - datetime.strptime(str(startdate),'%Y%m%d')).days
                        total_periods = total_days

                    # Check if the total periods exceed the limit when multiplied by the weight
                    if total_periods * weight >= 1:
                        QMessageBox.information(self.main, "Warning", "분석 가능 기간 개수를 초과합니다\n시간가중치를 줄이거나, Period 값을 늘리거나 시작일~종료일 사이의 간격을 줄이십시오")
                        continue

                    if split_option in ['평균(Mean)', '중앙값(Median)'] and split_custom is None:
                        pass
                    else:
                        split_custom = float(split_custom)
                    break
                except:
                    QMessageBox.information(self.main, "Warning", "입력 형식이 올바르지 않습니다")


            if except_yes_selected == True:
                QMessageBox.information(self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
                exception_word_list_path   = QFileDialog.getOpenFileName(self.main, "예외어 사전(CSV)를 선택하세요", self.main.default_directory, "CSV Files (*.csv);;All Files (*)")
                exception_word_list_path = exception_word_list_path[0]
                if exception_word_list_path == "":
                    return
                with open(exception_word_list_path, 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']
                df = pd.read_csv(exception_word_list_path, low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    QMessageBox.information(self.main, "Warning", "예외어 사전 형식과 일치하지 않습니다")
                    return
                exception_word_list = df['word'].tolist()
            else:
                exception_word_list = []
                exception_word_list_path = 'N'

            kimkem_obj = KimKem(token_data, tokenfile_name, save_path, startdate, enddate, period, topword, weight, graph_wordcnt, split_option, split_custom, ani_yes_selected, exception_word_list, exception_word_list_path)
            self.main.openFileExplorer(kimkem_obj.kimkem_folder_path)
            result = kimkem_obj.make_kimkem()

            if result == 1:
                self.main.printStatus()
                QMessageBox.information(self.main, "Information", f"KEM KIM 분석 데이터가 성공적으로 저장되었습니다")
            elif result == 0:
                self.main.printStatus()
                QMessageBox.information(self.main, "Information", f"Keyword가 존재하지 않아 KEM KIM 분석이 진행되지 않았습니다")
            elif result == 2:
                self.main.printStatus()
                QMessageBox.information(self.main, "Information", "분석 가능 기간 개수를 초과합니다\n시간가중치를 줄이거나, Period 값을 늘리거나 시작일~종료일 사이의 간격을 줄이십시오")
            else:
                self.main.printStatus()
                QMessageBox.information(self.main, "Warning", f"치명적 오류가 발생하였습니다. 버그 리포트에 오류 작성 부탁드립니다\n\nlog:{result}")
                self.main.program_bug_log(result)
            del kimkem_obj
            gc.collect()
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def userDB_layout_maker(self):
        # File Explorer를 탭 레이아웃에 추가
        self.userDBfiledialog = self.main.filefinder_maker(self.main)
        self.main.tab3_userDB_fileexplorerlayout.addWidget(self.userDBfiledialog)

        # QToolBox 생성
        self.tool_box = QToolBox()
        self.main.tab3_userDB_buttonlayout.addWidget(self.tool_box)

        # QListView들을 저장할 딕셔너리 생성
        self.list_views = {}

        def create_list(DBname):
            # 데이터베이스에서 테이블 목록 가져오기
            data = self.main.mySQL_obj.showAllTable(database_name=DBname)

            # QListView 생성
            list_view = QListView()

            # 여러 항목을 선택할 수 있도록 MultiSelection 모드로 설정
            list_view.setSelectionMode(QListView.MultiSelection)

            # 데이터를 QListView와 연결하기 위한 모델 설정
            model = QStringListModel(data)
            list_view.setModel(model)

            # QListView 항목이 클릭될 때 발생하는 시그널 연결
            list_view.clicked.connect(self.toolbox_DBlistItem_selected)

            # QListView를 포함하는 QWidget 생성
            section = QWidget()
            layout = QVBoxLayout(section)
            layout.addWidget(list_view)

            # 생성된 QListView를 딕셔너리에 저장
            self.list_views[DBname] = list_view

            return section

        for userName in self.main.userNameList:
            DBname = userName + '_db'
            section = create_list(DBname)
            self.tool_box.addItem(section, DBname.replace('_db', ' DB'))

        self.tool_box.setCurrentIndex(-1)
        self.tool_box.currentChanged.connect(self.toolbox_DB_selected)

    def toolbox_DB_selected(self, index):
        self.selected_userDB = self.tool_box.itemText(index)
        self.selected_userDB = self.selected_userDB.replace(' DB', '_db')

    def toolbox_DBlistItem_selected(self, index):
        self.selected_DBlistItems = [item.data() for item in self.list_views[self.selected_userDB].selectedIndexes()]
        self.main.printStatus(f"Table {len(self.selected_DBlistItems)}개 선택됨")

    def toolbox_DBlistItem_delete(self):
        try:
            if not self.selected_DBlistItems or self.selected_DBlistItems == []:
                self.main.printStatus()
                return

            reply = QMessageBox.question(self.main, 'Confirm Delete', "테이블을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.main.printStatus(f"Table {len(self.selected_DBlistItems)}개 삭제 중...")
                self.main.mySQL_obj.connectDB(self.selected_userDB)

                for item in self.selected_DBlistItems:
                    self.main.mySQL_obj.dropTable(item)

                # QListView에서 해당 항목 삭제 및 업데이트
                list_view = self.list_views[self.selected_userDB]
                model = list_view.model()

                for item in self.selected_DBlistItems:
                    row = model.stringList().index(item)
                    model.removeRow(row)

                # 선택된 항목 초기화
                self.selected_DBlistItems = []

                # 리스트 갱신 (이 작업을 통해 UI에 즉각 반영됨)
                list_view.setModel(model)
                self.main.printStatus()
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def toolbox_DBlistItem_add(self):
        try:
            selected_directory = self.dataprocess_getfiledirectory(self.userDBfiledialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            self.main.printStatus()

            def update_list_view(DBname):
                # 데이터베이스에서 테이블 목록 다시 가져오기
                updated_data = self.main.mySQL_obj.showAllTable(database_name=DBname)

                # 해당 DB의 QListView 가져오기
                list_view = self.list_views[DBname]
                model = QStringListModel(updated_data)

                # 모델 업데이트 (QListView 갱신)
                list_view.setModel(model)

            self.main.mySQL_obj.connectDB(self.selected_userDB)

            self.main.printStatus(f'{self.selected_userDB}에 Table {len(selected_directory)}개 추가 중...')
            for csv_path in selected_directory:
                self.main.mySQL_obj.CSVToTable(csv_path, os.path.basename(csv_path).replace('.csv', ''))
            update_list_view(self.selected_userDB)
            self.main.printStatus()
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def toolbox_DBlistItem_view(self):
        class SingleTableWindow(QMainWindow):
            def __init__(self, parent=None, target_db=None, target_table=None):
                super(SingleTableWindow, self).__init__(parent)
                self.setWindowTitle(target_table)
                self.setGeometry(100, 100, 1600, 1200)

                self.parent = parent  # 부모 객체 저장
                self.target_db = target_db  # 대상 데이터베이스 이름 저장
                self.target_table = target_table  # 대상 테이블 이름 저장

                self.central_widget = QWidget(self)
                self.setCentralWidget(self.central_widget)

                self.layout = QVBoxLayout(self.central_widget)

                # 상단 버튼 레이아웃
                self.button_layout = QHBoxLayout()

                # spacer 아이템 추가 (버튼을 오른쪽 끝에 배치)
                spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
                self.button_layout.addItem(spacer)

                # 닫기 버튼 추가
                self.close_button = QPushButton("닫기", self)
                self.close_button.setFixedWidth(80)
                self.close_button.clicked.connect(self.closeWindow)
                self.button_layout.addWidget(self.close_button)

                # 버튼 레이아웃을 메인 레이아웃에 추가
                self.layout.addLayout(self.button_layout)

                # target_db와 target_table이 주어지면 테이블 뷰를 초기화
                if target_db is not None and target_table is not None:
                    self.init_table_view(parent.mySQL_obj, target_db, target_table)

            def closeWindow(self):
                self.close()  # 창 닫기
                self.deleteLater()  # 객체 삭제
                gc.collect()

            def closeEvent(self, event):
                # 윈도우 창이 닫힐 때 closeWindow 메서드 호출
                self.closeWindow()
                event.accept()  # 창 닫기 이벤트 허용

            def init_table_view(self, mySQL_obj, target_db, target_table):
                # target_db에 연결
                mySQL_obj.connectDB(target_db)

                tableDF_begin = mySQL_obj.TableToDataframe(target_table, ':50')
                tableDF_end = mySQL_obj.TableToDataframe(target_table, ':-50')
                tableDF = pd.concat([tableDF_begin, tableDF_end], axis=0)

                # 데이터프레임 값을 튜플 형태의 리스트로 변환
                self.tuple_list = [tuple(row) for row in tableDF.itertuples(index=False, name=None)]

                # 테이블 위젯 생성
                new_table = QTableWidget(self.central_widget)
                self.layout.addWidget(new_table)

                # 테이블 데이터 설정
                new_table.setRowCount(len(self.tuple_list))
                new_table.setColumnCount(len(tableDF.columns))
                new_table.setHorizontalHeaderLabels(tableDF.columns)

                # 열 너비 조정
                header = new_table.horizontalHeader()
                header.setSectionResizeMode(QHeaderView.Stretch)

                # 행 전체 선택 설정 및 단일 선택 모드
                new_table.setSelectionBehavior(QTableWidget.SelectRows)
                new_table.setSelectionMode(QTableWidget.SingleSelection)

                for row_idx, row_data in enumerate(self.tuple_list):
                    for col_idx, col_data in enumerate(row_data):
                        new_table.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))

        try:
            if not self.selected_DBlistItems or self.selected_DBlistItems == []:
                self.main.printStatus()
                return
            if len(self.selected_DBlistItems) > 1:
                QMessageBox.information(self.main, "Information", f"선택 가능한 테이블 수는 1개입니다")
                return

            def destory_table():
                del self.DBtable_window
                gc.collect()

            def load_database():
                self.DBtable_window = SingleTableWindow(self.main, self.selected_userDB, self.selected_DBlistItems[0])
                self.DBtable_window.destroyed.connect(destory_table)
                self.DBtable_window.show()

            self.main.printStatus(f"{self.selected_DBlistItems[0]} 조회 중...")
            QTimer.singleShot(1, load_database)
            QTimer.singleShot(1, self.main.printStatus)

        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())

    def toolbox_DBlistItem_save(self):
        try:
            if not self.selected_DBlistItems or self.selected_DBlistItems == []:
                self.main.printStatus()
                return

            self.main.printStatus("데이터를 저장할 위치를 선택하세요...")
            folder_path = QFileDialog.getExistingDirectory(self.main, "데이터를 저장할 위치를 선택하세요", self.main.default_directory)
            if folder_path == '':
                self.main.printStatus()
                return

            folder_path = os.path.join(folder_path, f'{self.selected_userDB}_download_{datetime.now().strftime('%m%d_%H%M')}')
            os.makedirs(folder_path, exist_ok=True)

            self.main.printStatus(f"Table {len(self.selected_DBlistItems)}개 저장 중...")
            self.main.mySQL_obj.connectDB(self.selected_userDB)

            self.main.openFileExplorer(folder_path)
            for item in self.selected_DBlistItems:
                self.main.mySQL_obj.TableToCSV(item, folder_path)

            self.main.printStatus()
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {traceback.format_exc()}")
            self.main.program_bug_log(traceback.format_exc())