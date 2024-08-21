from PyQt5.QtWidgets import QInputDialog, QMessageBox, QFileDialog, QDialog, QHBoxLayout, QCheckBox, QComboBox, \
    QLineEdit, QLabel, QDialogButtonBox, QWidget, QProgressBar, QToolBox, QGridLayout, \
    QListView, QMainWindow, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QSpacerItem, QSizePolicy
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QStringListModel
import copy
import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
import platform
from collections import Counter
from datetime import datetime
import gc
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 크기 제한 해제
import numpy as np
import io
import warnings
warnings.filterwarnings("ignore")

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
        self.DB_table_column = ['Name', 'Type', 'Keyword', 'Period', 'Option', 'Crawl Start', 'Crawl End', 'Requester']
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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def dataprocess_refresh_DB(self):
        try:
            self.main.printStatus("새로고침 중...")

            def refresh_database():
                self.DB = self.main.update_DB(self.DB)
                self.main.table_maker(self.main.dataprocess_tab1_tablewidget, self.DB['DBdata'], self.DB_table_column)

            QTimer.singleShot(1, refresh_database)
            QTimer.singleShot(1, self.main.printStatus)
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

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
                        QMessageBox.critical(self.main, "Error", f"Failed to save splited database: {str(e)}")
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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

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
                        QMessageBox.critical(self.main, "Error", f"Failed to save splited database: {str(e)}")
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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

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
                    QMessageBox.warning(self.main, "Warning", "CSV 파일 클릭 -> Open버튼 클릭 -> 옵션을 선택하세요")
                    return
                case _:
                    QMessageBox.warning(self.main, "Warning", f"{selected_options[1]} {selected_options[0]} 분석은 지원되지 않는 기능입니다")
                    return

            self.main.openFileExplorer(os.path.dirname(csv_path))
            del csv_data
            gc.collect()
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def kimkem_kimkem(self):
        class KimKemOptionDialog(QDialog):
            def __init__(self, kimkem_file, rekimkem_file):
                super().__init__()
                self.kimkem_file = kimkem_file
                self.rekimkem_file = rekimkem_file
                self.initUI()
                self.data = None  # 데이터를 저장할 속성 추가

            def initUI(self):
                self.setWindowTitle('KEMKIM Start')
                self.resize(300, 100)  # 창 크기를 조정
                # 레이아웃 생성
                layout = QVBoxLayout()

                # 버튼 생성
                btn1 = QPushButton('새로운 KEMKIM 분석', self)
                btn2 = QPushButton('KEMKIM 재분석', self)
                
                # 버튼에 이벤트 연결
                btn1.clicked.connect(self.run_kimkem_file)
                btn2.clicked.connect(self.run_rekimkem_file)
                
                # 버튼 배치를 위한 가로 레이아웃
                button_layout = QHBoxLayout()
                button_layout.addWidget(btn1)
                button_layout.addWidget(btn2)

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
                

        dialog = KimKemOptionDialog(self.kimkem_kimkem_file, self.kimkem_rekimkem_file)
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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
    
    def kimkem_rekimkem_file(self):
        import ast
        class WordSelector(QDialog):
            def __init__(self, words):
                super().__init__()
                self.words = words
                self.selected_words = []
                self.initUI()

            def initUI(self):
                # 레이아웃 설정
                layout = QVBoxLayout()

                grid_layout = QGridLayout()

                # 체크박스 추가
                self.checkboxes = []
                num_columns = min(20, len(self.words))  # 한 행에 최대 20개의 체크박스가 오도록 설정
                for i, word in enumerate(self.words):
                    checkbox = QCheckBox(word, self)
                    self.checkboxes.append(checkbox)
                    # 그리드 레이아웃에 체크박스 배치
                    row = i // num_columns
                    col = i % num_columns
                    grid_layout.addWidget(checkbox, row, col)

                # 그리드 레이아웃을 QVBoxLayout에 추가
                layout.addLayout(grid_layout)

                # 선택된 단어 출력 버튼 추가
                btn = QPushButton('제외 단어 결정', self)
                btn.clicked.connect(self.show_selected_words)
                layout.addWidget(btn)

                # 창 설정
                self.setLayout(layout)
                self.setWindowTitle('제외할 키워드를 선택하세요')
                self.setGeometry(300, 300, 300, 200)
                self.show()

            def show_selected_words(self):
                # 선택된 단어를 리스트에 추가
                self.selected_words = [cb.text() for cb in self.checkboxes if cb.isChecked()]
                # 선택된 단어를 메시지 박스로 출력
                QMessageBox.information(self, '선택한 단어', ', '.join(self.selected_words))
                self.accept()
        
        #try:
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
        deletedword_df = pd.read_csv(os.path.join(result_directory, "Graph", "DOV_coordinates.csv"))
        words = deletedword_df['key'].dropna().unique().tolist()
        words.pop(0)
        
        self.word_selector = WordSelector(words)
        if self.word_selector.exec_() == QDialog.Accepted:  # show() 대신 exec_() 사용
            selected_words = self.word_selector.selected_words
        else:
            self.main.printStatus()
            return
        
        if len(selected_words) == 0:
            QMessageBox.information(self.main, 'Information', '선택된 제외 단어가 없습니다')
            return
        
        DoV_coordinates_df = pd.read_csv(os.path.join(result_directory, "Graph", "DOV_coordinates.csv"))
        DoV_coordinates_dict = {}
        for index, row in DoV_coordinates_df.iterrows():
            key = row['key']
            value = ast.literal_eval(row['value'])  # 문자열을 튜플로 변환
            DoV_coordinates_dict[key] = value
            
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
        
        DoV_signal, DoV_coordinates = kimkem_obj.DoV_draw_graph(graph_folder=new_graph_folder, redraw_option=True, coordinates=DoV_coordinates_dict)
        DoD_signal, DoD_coordinates = kimkem_obj.DoD_draw_graph(graph_folder=new_graph_folder, redraw_option=True, coordinates=DoD_coordinates_dict)
        kimkem_obj._save_final_signals(DoV_signal, DoD_signal, new_signal_folder)
        
        delete_word_list.extend(selected_words)
        pd.DataFrame(delete_word_list, columns=['word']).to_csv(os.path.join(new_result_folder, 'filtered_words.csv'), index = False)
        
        del kimkem_obj
        gc.collect()
        
        self.main.printStatus()
        QMessageBox.information(self.main, 'Information', 'KEMKIM 재분석이 완료되었습니다')
        
        #except Exception as e:
        #    QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")
        
    def kimkem_kimkemStart(self, token_data, tokenfile_name):
        class KimKemInputDialog(QDialog):
            def __init__(self):
                super().__init__()
                self.initUI()
                self.data = None  # 데이터를 저장할 속성 추가

            def initUI(self):
                self.setWindowTitle('KEM KIM OPTION')
                self.setGeometry(100, 100, 300, 250)  # 창 크기를 조정

                layout = QVBoxLayout()

                # 레이아웃의 마진과 간격 조정
                layout.setContentsMargins(10, 10, 10, 10)  # (left, top, right, bottom) 여백 설정
                layout.setSpacing(10)  # 위젯 간 간격 설정

                # 각 입력 필드를 위한 QLabel 및 QTextEdit 생성
                self.startyear_label = QLabel('분석 시작 연도를 입력하세요: ')
                self.startyear_input = QLineEdit()
                self.startyear_input.setText('2010')  # 기본값 설정
                layout.addWidget(self.startyear_label)
                layout.addWidget(self.startyear_input)

                self.topword_label = QLabel('상위 단어 개수를 입력하세요: ')
                self.topword_input = QLineEdit()
                self.topword_input.setText('500')  # 기본값 설정
                layout.addWidget(self.topword_label)
                layout.addWidget(self.topword_input)

                self.weight_label = QLabel('계산 가중치를 입력하세요: ')
                self.weight_input = QLineEdit()
                self.weight_input.setText('0.05')  # 기본값 설정
                layout.addWidget(self.weight_label)
                layout.addWidget(self.weight_input)

                self.wordcnt_label = QLabel('그래프 애니메이션에 띄울 단어의 개수를 입력하세요: ')
                self.wordcnt_input = QLineEdit()
                self.wordcnt_input.setText('10')  # 기본값 설정
                layout.addWidget(self.wordcnt_label)
                layout.addWidget(self.wordcnt_input)

                # 체크박스 생성
                self.checkbox_label = QLabel('제외 단어 리스트를 추가하시겠습니까? ')
                layout.addWidget(self.checkbox_label)

                checkbox_layout = QHBoxLayout()
                self.yes_checkbox = QCheckBox('Yes')
                self.no_checkbox = QCheckBox('No')

                self.yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
                self.no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

                # 서로 배타적으로 선택되도록 설정
                self.yes_checkbox.toggled.connect(
                    lambda: self.no_checkbox.setChecked(False) if self.yes_checkbox.isChecked() else None)
                self.no_checkbox.toggled.connect(
                    lambda: self.yes_checkbox.setChecked(False) if self.no_checkbox.isChecked() else None)

                checkbox_layout.addWidget(self.yes_checkbox)
                checkbox_layout.addWidget(self.no_checkbox)
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
                self.submit_button = QPushButton('Submit')
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

            def submit(self):
                # 입력된 데이터를 확인하고 처리
                startyear = self.startyear_input.text()
                topword = self.topword_input.text()
                weight = self.weight_input.text()
                graph_wordcnt = self.wordcnt_input.text()
                yes_selected = self.yes_checkbox.isChecked()
                no_selected = self.no_checkbox.isChecked()
                split_option = self.dropdown_menu.currentText()
                split_custom = self.additional_input.text() if self.additional_input.isVisible() else None

                self.data = {
                    'startyear': startyear,
                    'topword': topword,
                    'weight': weight,
                    'graph_wordcnt': graph_wordcnt,
                    'yes_selected': yes_selected,
                    'no_selected': no_selected,
                    'split_option': split_option,
                    'split_custom': split_custom
                }
                self.accept()
        #try:
        self.main.printStatus("KEM KIM 데이터를 저장할 위치를 선택하세요")
        save_path = QFileDialog.getExistingDirectory(self.main, "KEM KIM 데이터를 저장할 위치를 선택하세요", self.main.default_directory)
        if save_path == '':
            self.main.printStatus()
            return

        while True:
            dialog = KimKemInputDialog()
            dialog.exec_()
            try:
                if dialog.data == None:
                    return
                startyear = int(dialog.data['startyear'])
                topword = int(dialog.data['topword'])
                weight = float(dialog.data['weight'])
                graph_wordcnt = int(dialog.data['graph_wordcnt'])
                yes_selected = dialog.data['yes_selected']
                no_selected = dialog.data['no_selected']
                split_option = dialog.data['split_option']
                split_custom = dialog.data['split_custom']
                if split_option in ['평균(Mean)', '중앙값(Median)'] and split_custom is None:
                    pass
                else:
                    split_custom = float(split_custom)
                break
            except:
                QMessageBox.information(self.main, "Warning", "입력 형식이 올바르지 않습니다")

        if yes_selected == True:
            QMessageBox.information(self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
            exception_word_list_path   = QFileDialog.getOpenFileName(self.main, "예외어 사전(CSV)를 선택하세요", self.main.default_directory, "CSV Files (*.csv);;All Files (*)")
            exception_word_list_path = exception_word_list_path[0]
            if exception_word_list_path == "":
                return
            df = pd.read_csv(exception_word_list_path, low_memory=False, encoding='utf-8-sig')
            if 'word' not in list(df.keys()):
                QMessageBox.information(self.main, "Warning", "예외어 사전 형식과 일치하지 않습니다")
                return
            exception_word_list = df['word'].tolist()
        else:
            exception_word_list = []

        self.main.printStatus(f"{tokenfile_name} KEMKIM 분석 중...")
        self.main.openFileExplorer(save_path)
        kimkem_obj = KimKem(token_data, tokenfile_name, save_path, startyear, topword, weight, graph_wordcnt, split_option, split_custom, exception_word_list)
        result = kimkem_obj.make_kimkem()

        if result == 1:
            QMessageBox.information(self.main, "Information", f"KEM KIM 분석 데이터가 성공적으로 저장되었습니다")
        else:
            QMessageBox.information(self.main, "Information", f"Keyword가 존재하지 않아 KEM KIM 분석이 진행되지 않았습니다")

        self.main.printStatus()
        del kimkem_obj
        gc.collect()
        #except Exception as e:
        #    QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

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
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def toolbox_DBlistItem_save(self):
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


class DataProcess:
    
    def __init__(self, main_window):
        self.main = main_window

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

        # 데이터의 수에 따라 그래프 크기 자동 조정
        num_data_points = len(keys)
        width_per_data_point = 0.5  # 데이터 포인트 하나당 가로 크기 (조정 가능)
        base_width = 10  # 최소 가로 크기
        height = 6  # 고정된 세로 크기

        fig_width = max(base_width, num_data_points * width_per_data_point)

        plt.figure(figsize=(fig_width, height))

        # 그래프 그리기
        sns.lineplot(x=keys, y=values, marker='o')

        # 그래프 설정
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        plt.title(f'{info_label} Data Visualization')
        plt.xlabel(info_label)
        plt.ylabel('Values')

        # 그래프 저장
        plt.savefig(f"{data_path}/{folder_name}/{folder_name} Graph.png", bbox_inches='tight')

    def calculate_figsize(self, data_length, base_width=12, height=6, max_width=50):
        # Increase width proportionally to the number of data points, but limit the maximum width
        width = min(base_width + (data_length / 20), max_width)
        return (width, height)

    def NaverNewsArticleAnalysis(self, data, file_path):
        if 'Article Press' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Article CSV 형태와 일치하지 않습니다")
            return

        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(data['Article Date'])
        data['Article ReplyCnt'] = pd.to_numeric(data['Article ReplyCnt'], errors='coerce')

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 시간에 따른 기사 및 댓글 수 분석
        time_analysis = data.groupby(data['Article Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 기사 유형별 분석
        article_type_analysis = data.groupby('Article Type').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 언론사별 분석 (상위 10개 언론사만)
        top_10_press = data['Article Press'].value_counts().head(10).index
        press_analysis = data[data['Article Press'].isin(top_10_press)].groupby('Article Press').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 상관관계 분석
        correlation_matrix = data[['Article ReplyCnt']].corr()

        # 시각화 및 분석 결과 저장 디렉토리 설정
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        article_type_analysis.to_csv(os.path.join(csv_output_dir, "article_type_analysis.csv"))
        press_analysis.to_csv(os.path.join(csv_output_dir, "press_analysis.csv"))
        #correlation_matrix.to_csv(os.path.join(output_dir, "correlation_matrix.csv"))

        # For time_analysis graph
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article Count', label='Article Count')
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article ReplyCnt',
                     label='Reply Count')
        plt.title('Monthly Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.yticks([])
        plt.ylabel('')
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_article_reply_count.png"))
        plt.close()

        # For article_type_analysis graph
        data_length = len(article_type_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        article_type_analysis = article_type_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x=article_type_analysis.index, y=article_type_analysis['Article Count'], palette="viridis")
        plt.title('Article Count by Type')
        plt.xlabel('Article Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_type_count.png"))
        plt.close()

        # For press_analysis graph
        data_length = len(press_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        press_analysis = press_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x=press_analysis.index, y=press_analysis['Article Count'], palette="plasma")
        plt.title('Top 10 Press by Article Count')
        plt.xlabel('Press')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "press_article_count.png"))
        plt.close()

        '''
        # 4. 상관관계 행렬 히트맵 (현재는 댓글 수에 대한 상관관계만 존재)
        plt.figure(figsize=(8, 6))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "correlation_matrix.png"))
        plt.close()
        '''

        # 그래프 설명 작성 (한국어)
        description_text = """
        그래프 설명:

        1. 월별 기사 및 댓글 수 분석 (monthly_article_reply_count.png):
           - 이 선 그래프는 시간에 따른 월별 기사 수와 댓글 수를 보여줍니다.
           - x축은 날짜를, y축은 수량을 나타냅니다.
           - 이 그래프는 특정 기간 동안 기사와 댓글이 어떻게 변동했는지를 파악하는 데 도움이 됩니다.

        2. 기사 유형별 분석 (article_type_count.png):
           - 이 막대 그래프는 기사 유형별 기사 수를 보여줍니다.
           - x축은 기사 유형을, y축은 해당 유형의 기사 수를 나타냅니다.
           - 이 그래프는 어떤 유형의 기사가 가장 많이 발행되었는지 확인하는 데 유용합니다.

        3. 상위 10개 언론사별 기사 수 (press_article_count.png):
           - 이 막대 그래프는 기사 수를 기준으로 상위 10개 언론사를 보여줍니다.
           - x축은 언론사명을, y축은 각 언론사에서 발행한 기사 수를 나타냅니다.
           - 이 그래프는 가장 활발하게 기사를 발행하는 언론사를 파악하는 데 도움을 줍니다.
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(description_file_path, 'w') as file:
            file.write(description_text)

    def NaverNewsStatisticsAnalysis(self, data, file_path):
        if 'Male' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Statistics CSV 형태와 일치하지 않습니다")
            return

        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(data['Article Date'])
        data['Article ReplyCnt'] = pd.to_numeric(data['Article ReplyCnt'], errors='coerce')

        # 백분율 값을 실제 댓글 수로 변환하기 전에 숫자(float)로 변환
        for col in ['Male', 'Female', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y']:
            data[col] = pd.to_numeric(data[col], errors='coerce')  # 각 열을 숫자로 변환
            data[col] = (data[col] / 100.0) * data['Article ReplyCnt']

        # 분석 결과 저장 디렉토리 설정
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 시간에 따른 기사 및 댓글 수 분석
        time_analysis = data.groupby(data['Article Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 기사 유형별 분석
        article_type_analysis = data.groupby('Article Type').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 언론사별 분석 (상위 10개 언론사만)
        top_10_press = data['Article Press'].value_counts().head(10).index
        press_analysis = data[data['Article Press'].isin(top_10_press)].groupby(
            'Article Press').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 상관관계 분석
        correlation_matrix = data[
            ['Article ReplyCnt', 'Male', 'Female', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y']].corr()

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        article_type_analysis.to_csv(os.path.join(csv_output_dir, "article_type_analysis.csv"))
        press_analysis.to_csv(os.path.join(csv_output_dir, "press_analysis.csv"))
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 월별 기사 및 댓글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article Count', label='Article Count')
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article ReplyCnt',
                     label='Reply Count')
        plt.title('Monthly Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_article_reply_count.png"))
        plt.close()

        # 2. 기사 유형별 기사 및 댓글 수
        data_length = len(article_type_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        article_type_analysis = article_type_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x=article_type_analysis.index, y=article_type_analysis['Article Count'], palette="viridis")
        plt.title('Article Count by Type')
        plt.xlabel('Article Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_type_count.png"))
        plt.close()

        # 3. 상위 10개 언론사별 기사 및 댓글 수
        data_length = len(press_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        press_analysis = press_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x=press_analysis.index, y=press_analysis['Article Count'], palette="plasma")
        plt.title('Top 10 Press by Article Count')
        plt.xlabel('Press')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "press_article_count.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        data_length = len(correlation_matrix)
        plt.figure(figsize=self.calculate_figsize(data_length, height=8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 성별 댓글 수 분석 및 시각화
        gender_reply_count = {
            'Male': data['Male'].sum(),
            'Female': data['Female'].sum()
        }
        gender_reply_df = pd.DataFrame(list(gender_reply_count.items()), columns=['Gender', 'Reply Count'])
        data_length = len(gender_reply_df)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=8))
        sns.barplot(x='Gender', y='Reply Count', data=gender_reply_df, palette="pastel")
        plt.title('Total Number of Replies by Gender')
        plt.xlabel('Gender')
        plt.ylabel('Reply Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "gender_reply_count.png"))
        plt.close()
        gender_reply_df.to_csv(os.path.join(csv_output_dir, "gender_reply_count.csv"), index=False)

        # 6. 연령대별 댓글 수 분석 및 시각화
        age_group_reply_count = {
            '10Y': data['10Y'].sum(),
            '20Y': data['20Y'].sum(),
            '30Y': data['30Y'].sum(),
            '40Y': data['40Y'].sum(),
            '50Y': data['50Y'].sum(),
            '60Y': data['60Y'].sum()
        }
        age_group_reply_df = pd.DataFrame(list(age_group_reply_count.items()), columns=['Age Group', 'Reply Count'])
        data_length = len(age_group_reply_df)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=10))
        sns.barplot(x='Age Group', y='Reply Count', data=age_group_reply_df, palette="coolwarm")
        plt.title('Total Number of Replies by Age Group')
        plt.xlabel('Age Group')
        plt.ylabel('Reply Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "age_group_reply_count.png"))
        plt.close()
        age_group_reply_df.to_csv(os.path.join(csv_output_dir, "age_group_reply_count.csv"), index=False)

        # 7. 연령대별 성별 댓글 비율 분석
        age_gender_df = data.groupby(['Article Date', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y'])[
            ['Male', 'Female']].sum().reset_index()
        age_gender_df = age_gender_df.melt(id_vars=['Article Date', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y'],
                                           value_vars=['Male', 'Female'],
                                           var_name='Gender',
                                           value_name='Reply Count')
        data_length = len(age_gender_df)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=12, height=8))
        sns.lineplot(data=age_gender_df, x='Article Date', y='Reply Count', hue='Gender')
        plt.title('Reply Count by Gender Over Time')
        plt.xlabel('Date')
        plt.ylabel('Reply Count')
        plt.legend(title='Gender')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "age_gender_reply_count.png"))
        plt.close()
        age_gender_df.to_csv(os.path.join(csv_output_dir, "age_gender_reply_count.csv"), index=False)

        # 그래프 설명 작성 (한국어)
        description_text = """
        그래프 설명:

        1. 월별 기사 및 댓글 수 추세 (monthly_article_reply_count.png):
           - 이 그래프는 월별 기사 수와 댓글 수의 변화를 보여줍니다.
           - x축은 날짜를, y축은 기사 수와 댓글 수를 나타냅니다.
           - 이를 통해 특정 시기에 기사와 댓글의 변동 추이를 확인할 수 있습니다.

        2. 기사 유형별 기사 및 댓글 수 (article_type_count.png):
           - 이 그래프는 기사 유형별로 기사의 수를 나타냅니다.
           - x축은 기사 유형을, y축은 기사 수를 나타냅니다.
           - 이를 통해 어떤 유형의 기사가 많이 작성되었는지 알 수 있습니다.

        3. 상위 10개 언론사별 기사 및 댓글 수 (press_article_count.png):
           - 이 그래프는 상위 10개 언론사에서 작성한 기사 수를 나타냅니다.
           - x축은 언론사명을, y축은 기사 수를 나타냅니다.
           - 이 그래프는 가장 많은 기사를 작성한 언론사를 보여줍니다.

        4. 상관관계 행렬 히트맵 (correlation_matrix.png):
           - 이 히트맵은 주요 지표들 간의 상관관계를 시각화한 것입니다.
           - 색상이 진할수록 상관관계가 높음을 나타내며, 음수는 음의 상관관계를 의미합니다.
           - 이를 통해 변수들 간의 관계를 파악할 수 있습니다.

        5. 성별 댓글 수 분석 (gender_reply_count.png):
           - 이 그래프는 남성과 여성의 총 댓글 수를 보여줍니다.
           - x축은 성별을, y축은 댓글 수를 나타냅니다.
           - 성별에 따른 댓글 수의 차이를 확인할 수 있습니다.

        6. 연령대별 댓글 수 분석 (age_group_reply_count.png):
           - 이 그래프는 각 연령대별 총 댓글 수를 나타냅니다.
           - x축은 연령대를, y축은 댓글 수를 나타냅니다.
           - 이를 통해 어떤 연령대가 댓글을 많이 남겼는지 알 수 있습니다.

        7. 연령대별 성별 댓글 비율 분석 (age_gender_reply_count.png):
           - 이 그래프는 시간에 따른 성별 댓글 비율을 연령대별로 보여줍니다.
           - x축은 날짜를, y축은 댓글 수를 나타내며, 성별에 따라 분리됩니다.
           - 이를 통해 특정 시기와 연령대에서 남성 또는 여성이 얼마나 댓글을 많이 달았는지 알 수 있습니다.
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(description_file_path, 'w') as file:
            file.write(description_text)

    def NaverNewsReplyAnalysis(self, data, file_path):
        if 'Reply Date' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Reply CSV 형태와 일치하지 않습니다")
            return
        # 'Reply Date'를 datetime 형식으로 변환
        data['Reply Date'] = pd.to_datetime(data['Reply Date'])
        for col in ['Rereply Count', 'Reply Like', 'Reply Bad', 'Reply LikeRatio', 'Reply Sentiment']:
            data[col] = pd.to_numeric(data[col], errors='coerce')  # 각 열을 숫자로 변환

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 댓글 길이 추가
        data['Reply Length'] = data['Reply Text'].apply(len)

        # 날짜별 댓글 수 분석
        time_analysis = data.groupby(data['Reply Date'].dt.date).agg({
            'id': 'count',
            'Reply Like': 'sum',
            'Reply Bad': 'sum'
        }).rename(columns={'id': 'Reply Count'})

        # 댓글 감성 분석 결과 빈도
        sentiment_counts = data['Reply Sentiment'].value_counts()

        # 상관관계 분석
        correlation_matrix = data[['Reply Like', 'Reply Bad', 'Rereply Count', 'Reply LikeRatio', 'Reply Sentiment',
                                   'Reply Length']].corr()

        # 작성자별 댓글 수 계산
        writer_reply_count = data['Reply Writer'].value_counts()

        # 결과를 저장할 디렉토리 생성
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        sentiment_counts.to_csv(os.path.join(csv_output_dir, "sentiment_counts.csv"))
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"))
        writer_reply_count.to_csv(os.path.join(csv_output_dir, "writer_reply_count.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 날짜별 댓글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index, y='Reply Count')
        plt.title('Daily Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "daily_reply_count.png"))
        plt.close()

        # 2. 댓글 감성 분석 결과 분포
        data_length = len(sentiment_counts)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=8))
        sns.countplot(x='Reply Sentiment', data=data)
        plt.title('Reply Sentiment Distribution')
        plt.xlabel('Sentiment')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "reply_sentiment_distribution.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        data_length = len(correlation_matrix)
        plt.figure(figsize=self.calculate_figsize(data_length, height=8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 작성자별 댓글 수 분포 (상위 10명)
        top_10_writers = writer_reply_count.head(10)  # 상위 10명 작성자 선택
        data_length = len(top_10_writers)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=top_10_writers.index, y=top_10_writers.values, palette="viridis")
        plt.title('Top 10 Writers by Number of Replies')
        plt.xlabel('Writer')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "writer_reply_count.png"))
        plt.close()

        # 그래프 설명 작성 (한국어)
        description_text = """
        그래프 설명:

        1. 날짜별 댓글 수 추세 (daily_reply_count.png):
           - 이 그래프는 날짜별 댓글 수의 변화를 보여줍니다.
           - x축은 날짜를, y축은 댓글 수를 나타냅니다.
           - 이를 통해 특정 기간 동안 댓글이 얼마나 많이 달렸는지 파악할 수 있습니다.

        2. 댓글 감성 분석 결과 분포 (reply_sentiment_distribution.png):
           - 이 그래프는 댓글의 감성 분석 결과를 시각화한 것입니다.
           - x축은 감성의 유형(긍정, 부정, 중립)을, y축은 해당 감성의 댓글 수를 나타냅니다.
           - 댓글의 전반적인 감성 분포를 확인할 수 있습니다.

        3. 상관관계 행렬 히트맵 (correlation_matrix.png):
           - 이 히트맵은 주요 지표들 간의 상관관계를 시각화한 것입니다.
           - 색상이 진할수록 상관관계가 높음을 나타내며, 음수는 음의 상관관계를 의미합니다.
           - 이를 통해 변수들 간의 관계를 파악할 수 있습니다.

        4. 작성자별 댓글 수 분포 (상위 10명) (writer_reply_count.png):
           - 이 그래프는 댓글을 가장 많이 작성한 상위 10명의 작성자를 보여줍니다.
           - x축은 작성자의 이름을, y축은 해당 작성자가 작성한 댓글 수를 나타냅니다.
           - 이를 통해 어떤 작성자가 댓글 활동이 활발한지 알 수 있습니다.
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(description_file_path, 'w') as file:
            file.write(description_text)

    def NaverNewsRereplyAnalysis(self, data, file_path):
        if 'Rereply Date' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Rereply CSV 형태와 일치하지 않습니다")
            return
        # 'Reply Date'를 datetime 형식으로 변환
        data['Rereply Date'] = pd.to_datetime(data['Rereply Date'])
        for col in ['Rereply Like', 'Rereply Bad', 'Rereply LikeRatio', 'Rereply Sentiment']:
            data[col] = pd.to_numeric(data[col], errors='coerce')  # 각 열을 숫자로 변환

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 댓글 길이 추가
        data['Rereply Length'] = data['Rereply Text'].apply(len)

        # 날짜별 댓글 수 분석
        time_analysis = data.groupby(data['Rereply Date'].dt.date).agg({
            'id': 'count',
            'Rereply Like': 'sum',
            'Rereply Bad': 'sum'
        }).rename(columns={'id': 'Rereply Count'})

        # 댓글 감성 분석 결과 빈도
        sentiment_counts = data['Rereply Sentiment'].value_counts()

        # 상관관계 분석
        correlation_matrix = data[['Rereply Like', 'Rereply Bad', 'Rereply Count', 'Rereply LikeRatio', 'Rereply Sentiment',
                                   'Rereply Length']].corr()

        # 작성자별 댓글 수 계산
        writer_reply_count = data['Rereply Writer'].value_counts()

        # 결과를 저장할 디렉토리 생성
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        sentiment_counts.to_csv(os.path.join(csv_output_dir, "sentiment_counts.csv"))
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"))
        writer_reply_count.to_csv(os.path.join(csv_output_dir, "writer_rereply_count.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 날짜별 댓글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index, y='Rereply Count')
        plt.title('Daily Rereply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Rereplies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "daily_rereply_count.png"))
        plt.close()

        # 2. 댓글 감성 분석 결과 분포
        data_length = len(sentiment_counts)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=8))
        sns.countplot(x='Rereply Sentiment', data=data)
        plt.title('Rereply Sentiment Distribution')
        plt.xlabel('Sentiment')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "rereply_sentiment_distribution.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        data_length = len(correlation_matrix)
        plt.figure(figsize=self.calculate_figsize(data_length, height=8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 작성자별 댓글 수 분포 (상위 10명)
        top_10_writers = writer_reply_count.head(10)  # 상위 10명 작성자 선택
        data_length = len(top_10_writers)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=top_10_writers.index, y=top_10_writers.values, palette="viridis")
        plt.title('Top 10 Writers by Number of Rereplies')
        plt.xlabel('Writer')
        plt.ylabel('Number of Rereplies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "writer_rereply_count.png"))
        plt.close()

        # 그래프 설명 작성 (한국어)
        description_text = """
            그래프 설명:

            1. 날짜별 댓글 수 추세 (daily_rereply_count.png):
               - 이 그래프는 날짜별 댓글 수의 변화를 보여줍니다.
               - x축은 날짜를, y축은 댓글 수를 나타냅니다.
               - 이를 통해 특정 기간 동안 댓글이 얼마나 많이 달렸는지 파악할 수 있습니다.

            2. 댓글 감성 분석 결과 분포 (rereply_sentiment_distribution.png):
               - 이 그래프는 댓글의 감성 분석 결과를 시각화한 것입니다.
               - x축은 감성의 유형(긍정, 부정, 중립)을, y축은 해당 감성의 댓글 수를 나타냅니다.
               - 댓글의 전반적인 감성 분포를 확인할 수 있습니다.

            3. 상관관계 행렬 히트맵 (correlation_matrix.png):
               - 이 히트맵은 주요 지표들 간의 상관관계를 시각화한 것입니다.
               - 색상이 진할수록 상관관계가 높음을 나타내며, 음수는 음의 상관관계를 의미합니다.
               - 이를 통해 변수들 간의 관계를 파악할 수 있습니다.

            4. 작성자별 댓글 수 분포 (상위 10명) (writer_rereply_count.png):
               - 이 그래프는 댓글을 가장 많이 작성한 상위 10명의 작성자를 보여줍니다.
               - x축은 작성자의 이름을, y축은 해당 작성자가 작성한 댓글 수를 나타냅니다.
               - 이를 통해 어떤 작성자가 댓글 활동이 활발한지 알 수 있습니다.
        """
        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(description_file_path, 'w') as file:
            file.write(description_text)

    def NaverCafeArticleAnalysis(self, data, file_path):
        if 'NaverCafe Name' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverCafe Article CSV 형태와 일치하지 않습니다")
            return
        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(data['Article Date'])
        for col in ['NaverCafe MemberCount', 'Article ReadCount', 'Article ReplyCount']:
            data[col] = pd.to_numeric(data[col], errors='coerce')  # 각 열을 숫자로 변환

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 카페별 분석
        cafe_analysis = data.groupby('NaverCafe Name').agg({
            'id': 'count',
            'Article ReadCount': 'mean',
            'Article ReplyCount': 'mean',
            'NaverCafe MemberCount': 'mean'
        }).rename(columns={'id': 'Article Count', 'Article ReadCount': 'Avg ReadCount',
                           'Article ReplyCount': 'Avg ReplyCount'})

        # 작성자별 분석
        writer_analysis = data.groupby('Article Writer').agg({
            'id': 'count',
            'Article ReadCount': 'mean',
            'Article ReplyCount': 'mean'
        }).rename(columns={'id': 'Article Count', 'Article ReadCount': 'Avg ReadCount',
                           'Article ReplyCount': 'Avg ReplyCount'})

        # 시간별 분석 (연도, 월별)
        time_analysis = data.groupby(data['Article Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Article ReadCount': 'sum',
            'Article ReplyCount': 'sum'
        }).rename(columns={'id': 'Article Count'})

        # 상관관계 분석
        numerical_cols = ['NaverCafe MemberCount', 'Article ReadCount', 'Article ReplyCount']
        correlation_matrix = data[numerical_cols].corr()

        # 결과를 저장할 디렉토리 생성
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"))
        cafe_analysis.to_csv(os.path.join(csv_output_dir, "cafe_analysis.csv"))
        writer_analysis.to_csv(os.path.join(csv_output_dir, "writer_analysis.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 카페별 게시글 수 분포
        data_length = len(cafe_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=cafe_analysis.index, y=cafe_analysis['Article Count'])
        plt.title('Number of Articles by NaverCafe')
        plt.xlabel('NaverCafe')
        plt.ylabel('Number of Articles')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "cafe_article_count.png"))
        plt.close()

        # 2. 시간별 게시글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Article Count')
        plt.title('Monthly Article Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Articles')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_article_count.png"))
        plt.close()


        # 4. 작성자별 게시글 수 분포 (상위 10명)
        top_10_writers = writer_analysis.sort_values('Article Count', ascending=False).head(10)
        data_length = len(top_10_writers)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=top_10_writers.index, y=top_10_writers['Article Count'])
        plt.title('Top 10 Writers by Number of Articles')
        plt.xlabel('Writer')
        plt.ylabel('Number of Articles')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "top_10_writers.png"))
        plt.close()

        # 그래프 설명 작성 (한국어)
        description_text = """
        그래프 설명:

        1. 카페별 게시글 수 분포 (cafe_article_count.png):
           - 이 그래프는 각 네이버 카페별로 작성된 게시글 수를 보여줍니다.
           - x축은 네이버 카페명을, y축은 해당 카페에서 작성된 게시글 수를 나타냅니다.
           - 이를 통해 각 카페에서의 게시글 작성 활동을 파악할 수 있습니다.

        2. 시간별 게시글 수 추세 (monthly_article_count.png):
           - 이 그래프는 시간에 따른 월별 게시글 수의 변화를 보여줍니다.
           - x축은 날짜를, y축은 해당 월에 작성된 게시글 수를 나타냅니다.
           - 이를 통해 특정 기간 동안의 게시글 작성 추세를 알 수 있습니다.

        3. 작성자별 게시글 수 분포 (상위 10명) (top_10_writers.png):
           - 이 그래프는 게시글을 가장 많이 작성한 상위 10명의 작성자를 보여줍니다.
           - x축은 작성자명을, y축은 해당 작성자가 작성한 게시글 수를 나타냅니다.
           - 이를 통해 어떤 작성자가 게시글 활동이 활발한지 파악할 수 있습니다.
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(description_file_path, 'w') as file:
            file.write(description_text)

    def NaverCafeReplyAnalysis(self, data, file_path):
        # 'Article URL' 열이 있는지 확인
        if 'Article URL' not in list(data.columns):
            QMessageBox.warning(self.main, "Warning", "NaverCafe Reply CSV 형태와 일치하지 않습니다")
            return

        # 'Reply Date'를 datetime 형식으로 변환
        data['Reply Date'] = pd.to_datetime(data['Reply Date'])
        for col in ['Reply Like']:
            data[col] = pd.to_numeric(data[col], errors='coerce')  # 각 열을 숫자로 변환


        # 작성자별 분석 (상위 10명)
        writer_analysis = data.groupby('Reply Writer').agg({
            'id': 'count'
        }).rename(columns={'id': 'Reply Count'}).sort_values(by='Reply Count', ascending=False).head(100)

        # 시간별 분석 (연도, 월별)
        time_analysis = data.groupby(data['Reply Date'].dt.to_period("M")).agg({
            'id': 'count'
        }).rename(columns={'id': 'Reply Count'})

        # 결과를 저장할 디렉토리 생성
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        writer_analysis.to_csv(os.path.join(csv_output_dir, "writer_analysis.csv"))
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"))

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 작성자별 댓글 수 분포 (상위 10명)
        data_length = len(writer_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=writer_analysis.index, y=writer_analysis['Reply Count'])
        plt.title('Number of Replies by Top 100 Writers')
        plt.xlabel('Writer')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "writer_reply_count.png"))
        plt.close()

        # 2. 시간별 댓글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis, x=time_analysis.index.to_timestamp(), y='Reply Count')
        plt.title('Monthly Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_reply_count.png"))
        plt.close()

        # 그래프 설명 작성 (한국어)
        description_text = """
        그래프 설명:

        1. 작성자별 댓글 수 분포 (상위 100명) (writer_reply_count.png):
           - 이 그래프는 댓글을 가장 많이 작성한 상위 100명의 작성자를 보여줍니다.
           - x축은 작성자명을, y축은 해당 작성자가 작성한 댓글 수를 나타냅니다.
           - 이를 통해 어떤 작성자가 댓글 활동이 활발한지 파악할 수 있습니다.

        2. 시간별 댓글 수 추세 (monthly_reply_count.png):
           - 이 그래프는 시간에 따른 월별 댓글 수의 변화를 보여줍니다.
           - x축은 날짜를, y축은 해당 월에 작성된 댓글 수를 나타냅니다.
           - 이를 통해 특정 기간 동안의 댓글 작성 추세를 알 수 있습니다.
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(description_file_path, 'w') as file:
            file.write(description_text)

class KimKem:
    def __init__(self, token_data=None, csv_name=None, save_path=None, startyear=None, topword=None, weight=None, graph_wordcnt=None, split_option=None, split_custom=None, exception_word_list=[], rekemkim = False):
        self.exception_word_list = exception_word_list
        
        if rekemkim == False:
            self.token_data = token_data
            self.folder_name = csv_name.replace('.csv', '').replace('token_', '')
            self.startyear = startyear
            self.topword = topword
            self.weight = weight
            self.graph_wordcnt = graph_wordcnt
            self.except_option_display = 'Y' if exception_word_list else 'N'
            self.split_option = split_option
            self.split_custom = split_custom
            self.now = datetime.now()

            # Text Column Name 지정
            for column in token_data.columns.tolist():
                if 'Text' in column:
                    self.textColumn_name = column
                elif 'Date' in column:
                    self.dateColumn_name = column

            self.kimkem_folder_path = os.path.join(
                save_path,
                f"kemkim_{str(self.folder_name)}_{self.now.strftime('%m%d%H%M')}"
            )
            os.makedirs(self.kimkem_folder_path, exist_ok=True)

    def write_status(self, msg=''):
        info = (
            f"===================================================================================================================\n"
            f"{'분석 데이터:':<15} {self.folder_name}\n"
            f"{'분석 시각:':<15} {self.now.strftime('%Y.%m.%d %H:%M')}\n"
            f"{'분석 시작 연도:':<15} {self.startyear}\n"
            f"{'상위 단어 개수:':<15} {self.topword}\n"
            f"{'계산 가중치:':<15} {self.weight}\n"
            f"{'제외 단어 여부:':<15} {self.except_option_display}\n"
            f"{'분할 기준:':<15} {self.split_option}\n"
            f"{'분할 상위%:':<15} {self.split_custom}\n"
            f"===================================================================================================================\n"
        )
        info += f'\n진행 상황: {msg}'
        
        with open(os.path.join(self.kimkem_folder_path, 'kemkim_info.txt'),'w+') as info_txt:
            info_txt.write(info)
        
    def make_kimkem(self):
        # Step 1: 데이터 분할 및 초기화
        year_divided_group = self.divide_period(self.token_data)#
        year_list = list(year_divided_group.groups.keys())
        if self.startyear < int(year_list[0]):
            self.startyear = year_list[0]
        self.write_status("토큰 데이터 분할 중...")
            
        # Step 2: 연도별 단어 리스트 생성
        yyear_divided_dic = self._initialize_year_divided_dic(year_divided_group)#
        # DF 계산을 위해서 각 연도(key)마다 2차원 리스트 할당 -> 요소 리스트 하나 = 문서 하나
        year_divided_dic = self._generate_year_divided_dic(yyear_divided_dic)#

        # TF 계산을 위해서 각 연도마다 모든 token 할당
        year_divided_dic_merged = self._merge_year_divided_dic(year_divided_dic)#

        # Step 3: 상위 공통 단어 추출 및 키워드 리스트 생성
        top_common_words = self._extract_top_common_words(year_divided_dic_merged)#
        keyword_list = self._get_keyword_list(top_common_words)#

        if keyword_list == []:
            os.rmdir(self.kimkem_folder_path)
            return 0

        self.write_status("TF/DF 계산 중...")
        # Step 4: TF, DF, DoV, DoD 계산
        tf_counts, df_counts = self.cal_tf(keyword_list, year_divided_dic_merged), self.cal_df(keyword_list, year_divided_dic)
        
        self.write_status("DOV/DOD 계산 중...")
        DoV_dict, DoD_dict = self.cal_DoV(keyword_list, year_divided_dic, tf_counts), self.cal_DoD(keyword_list, year_divided_dic, df_counts)
        self.year_list = list(tf_counts.keys())
        self.year_list.pop(0)

        # Step 5: 결과 저장 디렉토리 설정
        self._create_output_directories()

        # Step 6: 결과 저장 (TF, DF, DoV, DoD)
        self.write_status("시계열 데이터 애니메이션 생성 중...")
        self._save_kimkem_results(tf_counts, df_counts, DoV_dict, DoD_dict)
        
        DoV_signal_record = {}
        DoD_signal_record = {}
        DoV_coordinates_record = {}
        DoD_coordinates_record = {}
        Final_signal_record = {}
        
        self.DoV_graphPath_list = []
        self.DoD_graphPath_list = []
        
        for year in self.year_list:
            # Step 7: 평균 증가율 및 빈도 계산

            result_folder = os.path.join(self.history_folder, year)

            self.write_status(f"{year}년 KEMKIM 증가율 계산 중...")
            avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency = self._calculate_averages(keyword_list, DoV_dict, DoD_dict, tf_counts, df_counts, str(int(year)-1), year)

            self.write_status(f"{year}년 KEMKIM 신호 분석 및 그래프 생성 중...")
            # Step 8: 신호 분석 및 그래프 생성
            DoV_signal_record[year], DoD_signal_record[year], DoV_coordinates_record[year], DoD_coordinates_record[year] = self._analyze_signals(avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency, os.path.join(result_folder, 'Graph'))
            Final_signal_record[year] = self._save_final_signals(DoV_signal_record[year], DoD_signal_record[year], os.path.join(result_folder, 'Signal'))
        
        self.write_status("키워드 추적 데이터 생성 중...")
        DoV_signal_track = self.track_keyword_positions(DoV_signal_record)
        DoD_signal_track = self.track_keyword_positions(DoD_signal_record)
        Final_signal_track = self.track_keyword_positions(Final_signal_record)
        
        DoV_signal_track.to_csv(os.path.join(self.track_folder, 'DoV_signal_track.csv'), encoding='utf-8-sig', index=True, header=True)
        DoD_signal_track.to_csv(os.path.join(self.track_folder, 'DoD_signal_track.csv'), encoding='utf-8-sig', index=True, header=True)
        Final_signal_track.to_csv(os.path.join(self.track_folder, 'Final_signal_track.csv'), encoding='utf-8-sig', index=True, header=True)
        
        self.write_status("키워드 필터링 중...")
        DoV_signal_track, DoV_signal_deletewords = self.filter_clockwise_movements(DoV_signal_track)
        DoV_signal_track, DoD_signal_deletewords = self.filter_clockwise_movements(DoV_signal_track)  
        add_list = list(set(DoV_signal_deletewords+DoD_signal_deletewords))
        self.exception_word_list.extend(['']+add_list)
            
        self.write_status("키워드 추적 그래프 생성 중...")
        self.visualize_keyword_movements(DoV_signal_track, os.path.join(self.track_folder, 'DoV_signal_track_graph.png'), 'TF', 'Increasing Rate')
        self.visualize_keyword_movements(DoD_signal_track, os.path.join(self.track_folder, 'DoD_signal_track_graph.png'), 'DF', 'Increasing Rate')
        
        self.write_status("키워드 추적 애니메이션 생성 중...")
        self.animate_keyword_movements(DoV_signal_track, os.path.join(self.track_folder, 'DoV_signal_track_animation.gif'), 'TF', 'Increasing Rate')
        self.animate_keyword_movements(DoD_signal_track, os.path.join(self.track_folder, 'DoD_signal_track_animation.gif'), 'DF', 'Increasing Rate')
        
        self.write_status("최종 KEM KIM 생성 중...")
        avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency = self._calculate_averages(keyword_list, DoV_dict, DoD_dict, tf_counts, df_counts, str(self.startyear), self.year_list[-1])
        DoV_signal_record[year], DoD_signal_record[year], DoV_coordinates_record[year], DoD_coordinates_record[year] = self._analyze_signals(avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency, os.path.join(self.result_folder, 'Graph'))
        Final_signal_record[year] = self._save_final_signals(DoV_signal_record[year], DoD_signal_record[year], os.path.join(self.result_folder, 'Signal'))
        pd.DataFrame(self.exception_word_list, columns=['word']).to_csv(os.path.join(self.result_folder, 'filtered_words.csv'), index = False)
        
        self.write_status("완료")
        return 1
    
    def track_keyword_positions(self, yearly_data):
        
        # 모든 단어를 수집하기 위한 집합
        all_keywords = set()

        # 연도를 정렬하여 순차적으로 처리
        years = sorted(yearly_data.keys())

        # 각 연도별로 단어의 위치를 추적할 딕셔너리
        keyword_positions = {}

        for year in years:
            year_positions = {}
            for key, words in yearly_data[year].items():
                for word in words:
                    all_keywords.add(word)
                    year_positions[word] = f"{key}"
            
            keyword_positions[year] = year_positions

        # set을 list로 변환하여 인덱스로 사용
        df = pd.DataFrame(index=list(all_keywords))
        df.index.name = 'Keyword'
        
        for year in years:
            df[year] = df.index.map(keyword_positions[year].get)

        return df

    def visualize_keyword_movements(self, df, graph_path, x_axis_name='X-Axis', y_axis_name='Y-Axis', base_size=2, size_increment=2):
        # 포지션 매핑: 각 사분면에 위치를 계산
        def get_position(quadrant, size):
            if quadrant == 'strong_signal':   # 1사분면
                return size, size
            elif quadrant == 'weak_signal':   # 2사분면
                return -size, size
            elif quadrant == 'latent_signal': # 3사분면
                return -size, -size
            elif quadrant == 'well_known_signal': # 4사분면
                return size, -size

        # 각 키워드의 연도별 위치를 저장할 딕셔너리
        keyword_trajectories = {keyword: [] for keyword in df.index}

        max_size = base_size + (len(df.index) - 1) * size_increment  # 최대 크기 계산

        # 연도별 키워드의 위치를 계산
        for idx, keyword in enumerate(df.index):
            size = base_size + (idx * size_increment)  # 크기 증가를 반영
            for year in df.columns:
                quadrant = df.loc[keyword, year]
                position = get_position(quadrant, size)  # 크기를 포지션에 반영
                keyword_trajectories[keyword].append(position)

        # 색상 팔레트 생성
        num_keywords = len(df.index)
        colors = sns.color_palette("husl", num_keywords)
        
        # 시각화 함수
        plt.figure(figsize=(18, 18))  # 그래프 크기를 더 크게 설정
        
        # 4분면의 선 그리기
        plt.axhline(0, color='black', linewidth=1)
        plt.axvline(0, color='black', linewidth=1)

        position_years = {}
        
        # 각 키워드의 포인트를 시각화
        for i, (keyword, trajectory) in enumerate(keyword_trajectories.items()):
            trajectory_df = pd.DataFrame(trajectory, columns=['x', 'y'])
            
            # 포인트만 표시
            plt.scatter(trajectory_df['x'], trajectory_df['y'], label=keyword, color=colors[i], alpha=0.75)

            # 각 위치에 연도 표시
            for j, (x, y) in enumerate(trajectory):
                # 해당 위치에 이미 연도가 기록되어 있는지 확인
                if (x, y) in position_years:
                    position_years[(x, y)].append(df.columns[j])
                else:
                    position_years[(x, y)] = [df.columns[j]]

        # 모든 연도를 한 번에 표시
        for (x, y), years in position_years.items():
            keyword_at_position = None
            for keyword, trajectory in keyword_trajectories.items():
                if (x, y) in trajectory:
                    keyword_at_position = keyword
                    break
            
            # 키워드와 연도를 함께 표시
            label = f"{keyword_at_position}: " + ', '.join(map(str, years))
            plt.text(x, y, label, fontsize=6, ha='center', va='center')

        # 각 사분면의 이름을 그래프 바깥쪽에 설정
        plt.text(max_size * 1.1, max_size * 1.1, 'Strong Signal', fontsize=14, ha='center', va='center', color='black')
        plt.text(-max_size * 1.1, max_size * 1.1, 'Weak Signal', fontsize=14, ha='center', va='center', color='black')
        plt.text(-max_size * 1.1, -max_size * 1.1, 'Latent Signal', fontsize=14, ha='center', va='center', color='black')
        plt.text(max_size * 1.1, -max_size * 1.1, 'Well-Known Signal', fontsize=14, ha='center', va='center', color='black')

        # 그래프 설정
        plt.title('KEMKIM Keyword Movements', fontsize=18)
        plt.xlabel(x_axis_name, fontsize=14)
        plt.ylabel(y_axis_name, fontsize=14)
        plt.xlim(-max_size * 1.2, max_size * 1.2)  # 최대 크기에 따라 축 설정
        plt.ylim(-max_size * 1.2, max_size * 1.2)
        plt.xticks([])
        plt.yticks([])
        plt.grid(True)

        # 범례를 그래프 바깥으로 배치하고 여러 줄로 표시
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize='small', ncol=2, frameon=False)
        
        plt.savefig(graph_path, dpi=600, bbox_inches='tight')
        plt.close()
    
    def animate_keyword_movements(self, df,  gif_filename='keyword_movements.gif', x_axis_name='X-Axis', y_axis_name='Y-Axis', base_size=2, size_increment=2, frames_between_years=3, duration = 1000):
        # 포지션 매핑: 각 사분면에 위치를 계산
        def get_position(quadrant, size):
            if quadrant == 'strong_signal':   # 1사분면
                return size, size
            elif quadrant == 'weak_signal':   # 2사분면
                return -size, size
            elif quadrant == 'latent_signal': # 3사분면
                return -size, -size
            elif quadrant == 'well_known_signal': # 4사분면
                return size, -size

        # 각 키워드의 연도별 위치를 저장할 딕셔너리
        keyword_positions = {keyword: [] for keyword in df.index}

        max_size = base_size + (len(df.index) - 1) * size_increment  # 최대 크기 계산

        # 연도별 키워드의 위치를 계산
        for idx, keyword in enumerate(df.index):
            size = base_size + (idx * size_increment)  # 크기 증가를 반영
            for year in df.columns:
                quadrant = df.loc[keyword, year]
                position = get_position(quadrant, size)  # 크기를 포지션에 반영
                keyword_positions[keyword].append(position)

        # 색상 팔레트 생성
        num_keywords = len(df.index)
        colors = sns.color_palette("husl", num_keywords)
        
        # GIF로 저장할 프레임 리스트
        frames = []
        
        # 중간 프레임 생성
        for t in range(len(df.columns) - 1):
            year = df.columns[t]
            next_year = df.columns[t + 1]
            
            for frame in range(frames_between_years):
                plt.figure(figsize=(18, 18))  # 그래프 크기를 더 크게 설정
                
                # 4분면의 선 그리기
                plt.axhline(0, color='black', linewidth=1)
                plt.axvline(0, color='black', linewidth=1)
                
                # 각 키워드의 현재 위치와 다음 위치 사이의 중간 위치 계산 및 시각화
                for i, keyword in enumerate(keyword_positions.keys()):
                    x_start, y_start = keyword_positions[keyword][t]
                    x_end, y_end = keyword_positions[keyword][t + 1]
                    
                    # 중간 위치 계산
                    x = x_start + (x_end - x_start) * (frame / frames_between_years)
                    y = y_start + (y_end - y_start) * (frame / frames_between_years)
                    
                    plt.scatter(x, y, label=keyword, color=colors[i], alpha=0.75)
                    label = f"{keyword} ({year})"
                    plt.text(x, y, label, fontsize=6, ha='center', va='center')

                # 각 사분면의 이름을 그래프 바깥쪽에 설정
                plt.text(max_size * 1.1, max_size * 1.1, 'Strong Signal', fontsize=14, ha='center', va='center', color='black')
                plt.text(-max_size * 1.1, max_size * 1.1, 'Weak Signal', fontsize=14, ha='center', va='center', color='black')
                plt.text(-max_size * 1.1, -max_size * 1.1, 'Latent Signal', fontsize=14, ha='center', va='center', color='black')
                plt.text(max_size * 1.1, -max_size * 1.1, 'Well-Known Signal', fontsize=14, ha='center', va='center', color='black')

                # 그래프 설정
                plt.title(f'KEMKIM Keyword Movements ({year})', fontsize=18)
                plt.xlabel(x_axis_name, fontsize=14)
                plt.ylabel(y_axis_name, fontsize=14)
                plt.xlim(-max_size * 1.2, max_size * 1.2)  # 최대 크기에 따라 축 설정
                plt.ylim(-max_size * 1.2, max_size * 1.2)
                plt.xticks([])
                plt.yticks([])
                plt.grid(True)

                # 범례를 그래프 바깥으로 배치하고 여러 줄로 표시
                plt.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize='small', ncol=2, frameon=False)
                
                # 프레임을 메모리에 저장
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                img = Image.open(buf).copy()  # 이미지 복사하여 사용
                frames.append(img)
                buf.close()
                plt.close()

        # 마지막 연도에 대한 프레임 추가
        plt.figure(figsize=(18, 18))  # 그래프 크기를 더 크게 설정
        plt.axhline(0, color='black', linewidth=1)
        plt.axvline(0, color='black', linewidth=1)
        
        for i, keyword in enumerate(keyword_positions.keys()):
            x, y = keyword_positions[keyword][-1]
            plt.scatter(x, y, label=keyword, color=colors[i], alpha=0.75)
            label = f"{keyword} ({df.columns[-1]})"
            plt.text(x, y, label, fontsize=6, ha='center', va='center')

        plt.text(max_size * 1.1, max_size * 1.1, 'Strong Signal', fontsize=14, ha='center', va='center', color='black')
        plt.text(-max_size * 1.1, max_size * 1.1, 'Weak Signal', fontsize=14, ha='center', va='center', color='black')
        plt.text(-max_size * 1.1, -max_size * 1.1, 'Latent Signal', fontsize=14, ha='center', va='center', color='black')
        plt.text(max_size * 1.1, -max_size * 1.1, 'Well-Known Signal', fontsize=14, ha='center', va='center', color='black')

        plt.title(f'KEMKIM Keyword Movements ({df.columns[-1]})', fontsize=18)
        plt.xlabel(x_axis_name, fontsize=14)
        plt.ylabel(y_axis_name, fontsize=14)
        plt.xlim(-max_size * 1.2, max_size * 1.2)  # 최대 크기에 따라 축 설정
        plt.ylim(-max_size * 1.2, max_size * 1.2)
        plt.xticks([])
        plt.yticks([])
        plt.grid(True)

        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize='small', ncol=2, frameon=False)

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        img = Image.open(buf).copy()  # 이미지 복사하여 사용
        frames.append(img)
        buf.close()
        plt.close()

        # GIF로 변환
        frames[0].save(gif_filename, save_all=True, append_images=frames[1:], duration=duration, loop=0)
        
        plt.close()

    def filter_clockwise_movements(self, df):
        # 사분면 순서 정의
        quadrant_order = {
            'weak_signal': 2,
            'strong_signal': 1,
            'latent_signal': 3,
            'well_known_signal': 4
        }

        # 시계방향 이동 여부 확인 함수 (주어진 정의에 따른)
        def is_clockwise_movement(trajectory):
            for i in range(len(trajectory) - 1):
                current_quadrant = quadrant_order[trajectory.iloc[i]]
                next_quadrant = quadrant_order[trajectory.iloc[i + 1]]
                
                if current_quadrant is None or next_quadrant is None:
                    return False
                
                # 시계방향 순서 확인, 같은 사분면에 있으면 통과
                if (current_quadrant == 1 and next_quadrant not in [1, 3, 4]) or \
                (current_quadrant == 2 and next_quadrant not in [1, 2, 4]) or \
                (current_quadrant == 3 and next_quadrant not in [1, 2, 3]) or \
                (current_quadrant == 4 and next_quadrant not in [2, 3, 4]):
                    return False
                
            return True

        # 각 키워드별로 시계방향으로 이동한 데이터만 필터링we
        filtered_df = df[df.apply(lambda row: is_clockwise_movement(row), axis=1)]
        non_matching_keywords = df[~df.apply(lambda row: is_clockwise_movement(row), axis=1)].index.tolist()
        
        return filtered_df, non_matching_keywords

    def _initialize_year_divided_dic(self, year_divided_group):
        yyear_divided_dic = {}
        for group_name, group_data in year_divided_group:
            yyear_divided_dic[str(int(group_name))] = group_data[self.textColumn_name].tolist()
        yyear_divided_dic = {key: value for key, value in yyear_divided_dic.items() if int(key) >= self.startyear}
        return yyear_divided_dic

    def _generate_year_divided_dic(self, yyear_divided_dic):
        year_divided_dic = {}
        for key, string_list in yyear_divided_dic.items():
            word_lists = []
            for string in string_list:
                try:
                    words = string.split(', ')
                    word_lists.append(words)
                except:
                    pass
            year_divided_dic[key] = word_lists
        return year_divided_dic

    def _merge_year_divided_dic(self, year_divided_dic):
        return {key: [item for sublist in value for item in sublist] for key, value in year_divided_dic.items()}

    # self.topword 개의 top common words 뽑아냄
    def _extract_top_common_words(self, year_divided_dic_merged):
        return {k: [item for item, count in Counter(v).most_common(self.topword)] for k, v in
                year_divided_dic_merged.items()}

    def _get_keyword_list(self, top_common_words):
        intersection = set.intersection(*[set(value) for value in top_common_words.values()])
        return [word for word in list(intersection) if len(word) >= 2]

    def _create_output_directories(self):
        article_kimkem_folder = self.kimkem_folder_path
        self.data_folder = os.path.join(article_kimkem_folder, "Data")
        self.tf_folder = os.path.join(self.data_folder, "TF")
        self.df_folder = os.path.join(self.data_folder, "DF")
        self.DoV_folder = os.path.join(self.data_folder, "DoV")
        self.DoD_folder = os.path.join(self.data_folder, "DoD")
        self.result_folder = os.path.join(article_kimkem_folder, "Result")
        self.track_folder = os.path.join(article_kimkem_folder, "Track")
        self.history_folder = os.path.join(self.track_folder, 'History')

        os.makedirs(self.tf_folder, exist_ok=True)
        os.makedirs(self.df_folder, exist_ok=True)
        os.makedirs(self.DoV_folder, exist_ok=True)
        os.makedirs(self.DoD_folder, exist_ok=True)
        os.makedirs(self.result_folder, exist_ok=True)
        os.makedirs(os.path.join(self.result_folder, 'Graph'))
        os.makedirs(os.path.join(self.result_folder, 'Signal'))

        for year in self.year_list:
            year_path = os.path.join(self.history_folder, year)
            os.makedirs(year_path, exist_ok=True)
            os.makedirs(os.path.join(year_path, 'Graph'), exist_ok=True)
            os.makedirs(os.path.join(year_path, 'Signal'), exist_ok=True)

    def _save_kimkem_results(self, tf_counts, df_counts, DoV_dict, DoD_dict):
        for year in tf_counts:
            self._save_yearly_data(self.tf_folder, year, tf_counts, 'TF')
            self._save_yearly_data(self.df_folder, year, df_counts, 'DF')
            self._save_yearly_data(self.DoV_folder, year, DoV_dict, 'DoV')
            self._save_yearly_data(self.DoD_folder, year, DoD_dict, 'DoD')

        self.create_top_words_animation(tf_counts, os.path.join(self.tf_folder, 'tf_counts_animation.gif'), self.graph_wordcnt)
        self.create_top_words_animation(df_counts, os.path.join(self.df_folder, 'df_counts_animation.gif'), self.graph_wordcnt)
        self.create_top_words_animation(DoV_dict, os.path.join(self.DoV_folder, 'DOV_animation.gif'), self.graph_wordcnt, 100)
        self.create_top_words_animation(DoD_dict, os.path.join(self.DoD_folder, 'DOD_animation.gif'), self.graph_wordcnt, 100)

    def _save_yearly_data(self, folder, year, data_dict, label):
        data_df = pd.DataFrame(list(data_dict[year].items()), columns=['keyword', label])
        data_df.to_csv(f"{folder}/{year}_{label}.csv", index=False, encoding='utf-8-sig')

    def _calculate_averages(self, keyword_list, DoV_dict, DoD_dict, tf_counts, df_counts, min_year, max_year):
        
        avg_DoV_increase_rate = {}
        avg_DoD_increase_rate = {}
        avg_term_frequency = {}
        avg_doc_frequency = {}

        for word in keyword_list:
            avg_DoV_increase_rate[word] = self._calculate_average_increase(DoV_dict, word, max_year, min_year)
            avg_DoD_increase_rate[word] = self._calculate_average_increase(DoD_dict, word, max_year, min_year)
            avg_term_frequency[word] = self._calculate_average_frequency(tf_counts, word, max_year, min_year)
            avg_doc_frequency[word] = self._calculate_average_frequency(df_counts, word, max_year, min_year)

        return avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency

    def _calculate_average_increase(self, data_dict, word, max_year, min_year):
        return (((data_dict[max_year][word] / data_dict[min_year][word]) ** (
                    1 / (int(max_year) - int(min_year)))) - 1) * 100

    def _calculate_average_frequency(self, counts_dict, word, max_year, min_year):
        relevant_years = [year for year in counts_dict.keys() if min_year <= year <= max_year]
        total_frequency = sum([counts_dict[year][word] for year in relevant_years])
        return total_frequency / len(relevant_years) if relevant_years else 0

    def _analyze_signals(self, avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency, folder_path):
        DoV_signal, DoV_coordinates = self.DoV_draw_graph(avg_DoV_increase_rate, avg_term_frequency, folder_path)
        DoD_signal, DoD_coordinates = self.DoD_draw_graph(avg_DoD_increase_rate, avg_doc_frequency, folder_path)
        return DoV_signal, DoD_signal, DoV_coordinates, DoD_coordinates
    
    def _save_final_signals(self, DoV_signal, DoD_signal, result_folder):
        DoV_signal_df = pd.DataFrame([(k, v) for k, v in DoV_signal.items()], columns=['signal', 'word'])
        DoV_signal_df.to_csv(os.path.join(result_folder, "DoV_signal.csv"), index=False, encoding='utf-8-sig')

        DoD_signal_df = pd.DataFrame([(k, v) for k, v in DoD_signal.items()], columns=['signal', 'word'])
        DoD_signal_df.to_csv(os.path.join(result_folder, "DoD_signal.csv"), index=False, encoding='utf-8-sig')

        final_signal = self._get_communal_signals(DoV_signal, DoD_signal)
        final_signal_df = pd.DataFrame([(k, v) for k, v in final_signal.items()], columns=['signal', 'word'])
        final_signal_df.to_csv(os.path.join(result_folder, "Final_signal.csv"), index=False, encoding='utf-8-sig')
        
        return final_signal

    def _get_communal_signals(self, DoV_signal, DoD_signal):
        communal_strong_signal = [word for word in DoV_signal['strong_signal'] if word in DoD_signal['strong_signal']]
        communal_weak_signal = [word for word in DoV_signal['weak_signal'] if word in DoD_signal['weak_signal']]
        communal_latent_signal = [word for word in DoV_signal['latent_signal'] if word in DoD_signal['latent_signal']]
        communal_well_known_signal = [word for word in DoV_signal['well_known_signal'] if word in DoD_signal['well_known_signal']]
        return {
            'strong_signal': communal_strong_signal,
            'weak_signal': communal_weak_signal,
            'latent_signal': communal_latent_signal,
            'well_known_signal': communal_well_known_signal
        }

    def divide_period(self, csv_data):
        csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]
        csv_data[self.dateColumn_name] = pd.to_datetime(csv_data[self.dateColumn_name].str.split().str[0], format='%Y-%m-%d',
                                                  errors='coerce')
        csv_data['year'] = csv_data[self.dateColumn_name].dt.year
        csv_data['month'] = csv_data[self.dateColumn_name].dt.month
        csv_data['year_month'] = csv_data[self.dateColumn_name].dt.to_period('M')

        year_divided_group = csv_data.groupby('year')

        return year_divided_group

    def create_top_words_animation(self, dataframe, output_filename='top_words_animation.gif', word_cnt=10, scale_factor=1, frames_per_transition=20):
        df = pd.DataFrame(dataframe).fillna(0)
    
        # 연도별로 상위 word_cnt개 단어를 추출
        top_words_per_year = {}
        for year in df.columns:
            top_words_per_year[year] = df[year].nlargest(word_cnt).sort_values(ascending=True)

        # 색상 팔레트 설정 (세련된 색상)
        colors = sns.color_palette("husl", word_cnt)

        # 애니메이션 초기 설정
        fig, ax = plt.subplots(figsize=(10, 6))

        # 보간 함수 생성
        def interpolate(start, end, num_steps):
            return np.linspace(start, end, num_steps)

        def animate(i):
            year_idx = i // frames_per_transition
            year = list(top_words_per_year.keys())[year_idx]
            next_year_idx = year_idx + 1 if year_idx + 1 < len(top_words_per_year) else year_idx
            next_year = list(top_words_per_year.keys())[next_year_idx]

            start_data = top_words_per_year[year]
            end_data = top_words_per_year[next_year]

            # 데이터를 정렬하여 순위를 유지하게끔 보간
            combined_data = pd.concat([start_data, end_data], axis=1).fillna(0)
            combined_data.columns = ['start', 'end']
            combined_data['start_rank'] = combined_data['start'].rank(ascending=False, method='first')
            combined_data['end_rank'] = combined_data['end'].rank(ascending=False, method='first')

            interpolated_values = interpolate(combined_data['start'].values, combined_data['end'].values, frames_per_transition)[
                                    i % frames_per_transition] * scale_factor
            interpolated_ranks = interpolate(combined_data['start_rank'].values, combined_data['end_rank'].values, frames_per_transition)[
                i % frames_per_transition]

            # 순위에 따라 재정렬 및 word_cnt로 제한
            sorted_indices = np.argsort(interpolated_ranks)[::-1][:word_cnt]  # 역순 정렬 후 상위 word_cnt개만 선택
            sorted_words = combined_data.index[sorted_indices]
            sorted_values = interpolated_values[sorted_indices]

            ax.clear()
            ax.barh(sorted_words, sorted_values, color=colors[:len(sorted_words)])  # 색상도 word_cnt에 맞게 제한
            ax.set_xlim(0, (df.max().max() * scale_factor) + 500)  # 최대 빈도수를 기준으로 x축 설정
            ax.set_title(f'Top {word_cnt} Keywords in {year}', fontsize=16)
            ax.set_xlabel('Frequency', fontsize=14)
            ax.set_ylabel('Keywords', fontsize=14)
            plt.box(False)

        # GIF로 저장 (메모리 내에서 처리하여 속도 향상)
        frames = []
        
        for i in range((len(top_words_per_year) - 1) * frames_per_transition):
            animate(i)
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            img = Image.open(buf).copy()  # 이미지 복사하여 사용
            frames.append(img)
            buf.close()

        # Pillow를 사용해 GIF로 저장
        frames[0].save(output_filename, save_all=True, append_images=frames[1:], duration=100, loop=0)

        plt.close()
    
    # 연도별 keyword tf 딕셔너리 반환
    def cal_tf(self, keyword_list, year_divided_dic_merged):
        tf_counts = {}
        for key, value in year_divided_dic_merged.items():
            keyword_counts = {}
            for keyword in keyword_list:
                keyword_counts[keyword] = value.count(keyword)

            keyword_counts = dict(sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True))

            tf_counts[key] = keyword_counts
        return tf_counts
    # 연도별 keyword df 딕셔너리 반환
    def cal_df(self, keyword_list, year_divided_dic):
        df_counts = {}
        for year in year_divided_dic:
            keyword_counts = {}
            for keyword in keyword_list:  # keyword는 keyword_list의 keyword
                count = 0
                for doc in year_divided_dic[year]:
                    if keyword in doc:
                        count += 1
                keyword_counts[keyword] = count

            keyword_counts = dict(sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True))

            df_counts[year] = keyword_counts
        return df_counts

    # 연도별 keyword DoV 딕셔너리 반환
    def cal_DoV(self, keyword_list, year_divided_dic, tf_counts):
        DoV_dict = {}
        for year in year_divided_dic:
            keyword_DoV_dic = {}
            for keyword in keyword_list:
                value = (tf_counts[year][keyword] / len(year_divided_dic[year])) * (1 - self.weight * (int(year) - self.startyear))
                keyword_DoV_dic[keyword] = value
            DoV_dict[year] = keyword_DoV_dic
        return DoV_dict

    # 연도별 keyword DoD 딕셔너리 반환
    def cal_DoD(self, keyword_list, year_divided_dic, df_counts):
        DoD_dict = {}
        for year in year_divided_dic:
            keyword_DoV_dic = {}
            for keyword in keyword_list:
                value = (df_counts[year][keyword] / len(year_divided_dic[year])) * (1 - self.weight * (int(year) - self.startyear))
                keyword_DoV_dic[keyword] = value
            DoD_dict[year] = keyword_DoV_dic
        return DoD_dict

    def find_median(self, lst):
        sorted_lst = sorted(lst)
        n = len(sorted_lst)

        # 리스트의 길이가 홀수일 경우
        if n % 2 == 1:
            return sorted_lst[n // 2]
        # 리스트의 길이가 짝수일 경우
        else:
            return (sorted_lst[n // 2 - 1] + sorted_lst[n // 2]) / 2

    def find_mean(self, lst):
        return sum(lst) / len(lst) if lst else 0

    def top_n_percent(self, lst, n):
        if not lst:
            return None  # 빈 리스트가 입력될 경우 None 반환

        if n <= 0:
            return None  # n이 0이거나 음수일 경우 None 반환

        sorted_lst = sorted(lst, reverse=True)  # 내림차순으로 정렬
        threshold_index = max(0, int(len(sorted_lst) * n / 100) - 1)  # n%에 해당하는 인덱스 계산

        return sorted_lst[threshold_index]  # 상위 n%에 가장 가까운 요소 반환

    def DoV_draw_graph(self, avg_DoV_increase_rate=None, avg_term_frequency=None, graph_folder=None, redraw_option = False, coordinates=False):
        if redraw_option == False:
            match self.split_option:
                case '평균(Mean)':
                    avg_term = self.find_mean(list(avg_term_frequency.values()))  # x축, 평균 단어 빈도
                    avg_DoV = self.find_mean(list(avg_DoV_increase_rate.values()))  # y축, 평균 증가율
                case '중앙값(Median)':
                    avg_term = self.find_median(list(avg_term_frequency.values()))  # x축, 평균 단어 빈도
                    avg_DoV = self.find_median(list(avg_DoV_increase_rate.values()))  # y축, 평균 증가율
                case '직접 입력: 상위( )%':
                    avg_term = self.top_n_percent(list(avg_term_frequency.values()), self.split_custom)  # x축, 평균 단어 빈도
                    avg_DoV = self.top_n_percent(list(avg_DoV_increase_rate.values()), self.split_custom)  # y축, 평균 증가율

            coordinates = {}
            coordinates['axis'] = (avg_term, avg_DoV)

            for key in avg_DoV_increase_rate:
                coordinates[key] = (avg_term_frequency[key], avg_DoV_increase_rate[key])
        else:
            avg_term = coordinates['axis'][0]
            avg_DoV = coordinates['axis'][1]
            
        coordinates = {k: v for k, v in coordinates.items() if k not in self.exception_word_list}
        
        plt.figure(figsize=(100, 100))
        plt.axvline(x=avg_term, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=avg_DoV, color='k', linestyle='--')  # y축 중앙값 수평선

        strong_signal = [word for word in coordinates if coordinates[word][0] >= avg_term and coordinates[word][1] >= avg_DoV]
        weak_signal = [word for word in coordinates if coordinates[word][0] <= avg_term and coordinates[word][1] >= avg_DoV]
        latent_signal = [word for word in coordinates if coordinates[word][0] <= avg_term and coordinates[word][1] <= avg_DoV]
        well_known_signal = [word for word in coordinates if coordinates[word][0] >= avg_term and coordinates[word][1] <= avg_DoV]

        # 각 좌표와 해당 키를 표시, 글자 크기 변경
        for key, value in coordinates.items():
            if key != 'axis':
                plt.scatter(value[0], value[1])
                plt.text(value[0], value[1], key, fontsize=15)

        # 그래프 제목 및 레이블 설정
        plt.title("Keyword Emergence Map", fontsize=50)
        plt.xlabel("Average Term Frequency(TF)", fontsize=50)
        plt.ylabel("Time-Weighted increasing rate", fontsize=50)

        # 그래프 표시
        plt.savefig(os.path.join(graph_folder, "TF_DOV_graph.png"), bbox_inches='tight')
        plt.close()
        
        coordinates_df = pd.DataFrame([(k, v) for k, v in coordinates.items()], columns=['key', 'value'])
        coordinates_df.to_csv(os.path.join(graph_folder, "DOV_coordinates.csv"), index=False, encoding='utf-8-sig')

        return {'strong_signal': strong_signal, "weak_signal": weak_signal, "latent_signal": latent_signal, "well_known_signal": well_known_signal}, coordinates

    def DoD_draw_graph(self, avg_DoD_increase_rate=None, avg_doc_frequency=None, graph_folder=None, redraw_option=False, coordinates=None):
        if redraw_option == False:
            match self.split_option:
                case '평균(Mean)':
                    avg_doc = self.find_mean(list(avg_doc_frequency.values()))  # x축, 평균 단어 빈도
                    avg_DoD = self.find_mean(list(avg_DoD_increase_rate.values()))  # y축, 평균 증가율
                case '중앙값(Median)':
                    avg_doc = self.find_median(list(avg_doc_frequency.values()))  # x축, 평균 단어 빈도
                    avg_DoD = self.find_median(list(avg_DoD_increase_rate.values()))  # y축, 평균 증가율
                case '직접 입력: 상위( )%':
                    avg_doc = self.top_n_percent(list(avg_doc_frequency.values()), self.split_custom)  # x축, 평균 단어 빈도
                    avg_DoD = self.top_n_percent(list(avg_DoD_increase_rate.values()), self.split_custom)  # y축, 평균 증가율

            coordinates = {}
            coordinates['axis'] = (avg_doc, avg_DoD)

            for key in avg_DoD_increase_rate:
                coordinates[key] = (avg_doc_frequency[key], avg_DoD_increase_rate[key])
        else:
            avg_doc = coordinates['axis'][0]
            avg_DoD = coordinates['axis'][1]
        
        coordinates = {k: v for k, v in coordinates.items() if k not in self.exception_word_list}
        
        plt.figure(figsize=(100, 100))
        plt.axvline(x=avg_doc, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=avg_DoD, color='k', linestyle='--')  # y축 중앙값 수평선

        strong_signal = [word for word in coordinates if coordinates[word][0] >= avg_doc and coordinates[word][1] >= avg_DoD]
        weak_signal = [word for word in coordinates if coordinates[word][0] <= avg_doc and coordinates[word][1] >= avg_DoD]
        latent_signal = [word for word in coordinates if coordinates[word][0] <= avg_doc and coordinates[word][1] <= avg_DoD]
        well_known_signal = [word for word in coordinates if coordinates[word][0] >= avg_doc and coordinates[word][1] <= avg_DoD]

        # 각 좌표와 해당 키를 표시
        for key, value in coordinates.items():
            if key != 'axis':
                plt.scatter(value[0], value[1])
                plt.text(value[0], value[1], key, fontsize=50)

        # 그래프 제목 및 레이블 설정
        plt.title("Keyword Issue Map", fontsize=50)
        plt.xlabel("Average Document Frequency(DF)", fontsize=50)
        plt.ylabel("Time-Weighted increasing rate", fontsize=50)

        # 그래프 표시
        plt.savefig(os.path.join(graph_folder, "DF_DOD_graph.png"), bbox_inches='tight')
        plt.close()
        
        coordinates_df = pd.DataFrame([(k, v) for k, v in coordinates.items()], columns=['key', 'value'])
        coordinates_df.to_csv(os.path.join(graph_folder, "DOD_coordinates.csv"), index=False, encoding='utf-8-sig')

        return {'strong_signal': strong_signal, "weak_signal": weak_signal, "latent_signal": latent_signal, "well_known_signal": well_known_signal}, coordinates