from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QFileDialog, QDialog, QHBoxLayout, QCheckBox, QComboBox, QLineEdit, QLabel, QDialogButtonBox, QVBoxLayout, QWidget, QProgressBar, QPushButton, QApplication
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import copy
import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
import platform
from kiwipiepy import Kiwi
from collections import Counter
import re


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

        self.main.kimkem_tab2_tokenization_button.clicked.connect(self.kimkem_tokenization_file)
        self.main.kimkem_tab2_kimkem_button.clicked.connect(self.kimkem_kimkem_file)

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
            QMessageBox.information(self.main, "Information", f"{targetDB}가 성공적으로 분할 저장되었습니다")

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
                    QMessageBox.warning(self.main, "Warning", "No directory selected.")
                    return 0,0,0
            def main(tableList, analysisdata_path):

                for index, table in enumerate(tableList):
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
                                case 'reply' | 'rereply':
                                    self.dataprocess_obj.NaverNewsReplyAnalysis(tabledf,
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
        self.file_dialog = self.main.filefinder_maker()
        self.main.tab2_fileexplorer_layout.addWidget(self.file_dialog)

    def dataprocess_getfiledirectory(self):
        selected_directory = self.file_dialog.selectedFiles()
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
            selected_directory = self.dataprocess_getfiledirectory()
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
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

            QTimer.singleShot(1, lambda: self.main.printStatus("변환 및 저장 중..."))
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

            selected_directory = self.dataprocess_getfiledirectory()
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) < 2:
                QMessageBox.warning(self.main, f"Warning", "2개 이상의 CSV 파일 선택이 필요합니다.")
                return


            all_df = [self.main.csvReader(directory) for directory in selected_directory]
            all_columns = [df.columns.tolist() for df in all_df]
            same_check_result = find_different_element_index(all_columns)
            if same_check_result != None:
                QMessageBox.warning(self.main, f"Warning", f"{os.path.basename(selected_directory[same_check_result])}의 CSV 형태가 다른 파일의 형태와 다릅니다.")
                return

            mergedfilename, ok = QInputDialog.getText(None, '파일명 입력', '병합 파일명을 입력하세요:', text='merged_file')
            mergedfiledir      = os.path.dirname(selected_directory[0])
            if ok and mergedfilename:
                merged_df = pd.DataFrame()

                for df in all_df:
                    merged_df = pd.concat([merged_df, df], ignore_index=True)

                merged_df.to_csv(os.path.join(mergedfiledir, mergedfilename)+'.csv', index=False, encoding='utf-8-sig')
                self.main.openFileExplorer(mergedfiledir)
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

            selected_directory = self.dataprocess_getfiledirectory()
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
                case ['reply 분석', 'Naver News'] | ['rereply 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsReplyAnalysis(csv_data, csv_path)
                case ['article 분석', 'Naver Cafe']:
                    self.dataprocess_obj.NaverCafeArticleAnalysis(csv_data, csv_path)
                case ['reply 분석', 'Naver Cafe']:
                    self.dataprocess_obj.NaverCafeReplyAnalysis(csv_data, csv_path)
                case []:
                    QMessageBox.warning(self.main, "Warning", "CSV 파일 클릭 -> Open버튼 클릭 -> 옵션을 선택하세요")
                case _:
                    QMessageBox.warning(self.main, "Warning", f"{selected_options[1]} {selected_options[0]} 분석은 지원되지 않는 기능입니다")

            self.main.openFileExplorer(os.path.dirname(csv_path))
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def kimkem_tokenization_file(self):
        try:
            selected_directory = self.dataprocess_getfiledirectory()
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Warning", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(self.main, f"Warning", "한 개의 CSV 파일만 선택하여 주십시오")
                return

            if 'token' in selected_directory[0]:
                QMessageBox.information(self.main, "Information", f"이미 토큰 파일입니다")
                return

            def tokenization_finished(tokenized_data):
                QMessageBox.information(self.main, "Information", f"{self.csv_name} 토큰화가 완료되었습니다\n\n데이터를 저장할 위치를 선택하세요")
                save_path = QFileDialog.getExistingDirectory(self.main, "데이터를 저장할 위치를 선택하세요", self.csv_path)
                if save_path == '':
                    QMessageBox.warning(self.main, "Warning", "No directory selected.")
                    return

                self.main.openFileExplorer(save_path)
                tokenized_data.to_csv(os.path.join(save_path, 'token_' + self.csv_name), index=False, encoding='utf-8-sig')

                reply = QMessageBox.question(self.main, 'KEM KIM', "KEMKIM을 구동하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
                token_data = tokenized_data
                tokenfile_name = self.csv_name

                if reply == QMessageBox.Yes:
                    self.kimkem_kimkemStart(token_data, tokenfile_name)

                elif reply == QMessageBox.No:
                    return

            self.csv_path = selected_directory[0]
            self.csv_name = os.path.basename(self.csv_path)
            csv_data = pd.read_csv(self.csv_path, low_memory=False)

            # Column 열에 Text라는 글자가 하나도 없으면
            if any('Text' in element for element in csv_data.columns.tolist()) == False:
                QMessageBox.information(self.main, "Warning", f"토큰화할 수 없는 파일입니다")
                return

            # Article URL을 기준으로 댓글을 하나의 문자열로 다 합침
            if 'Reply Text' in csv_data.columns.tolist() or 'Rereply Text' in csv_data.columns.tolist():
                # Article URL을 기준으로 Reply Text를 합칩니다.
                csv_data = csv_data.groupby('Article URL').agg({
                    'Reply Text': ' '.join,
                    'Reply Date': 'first'
                }).reset_index()

            self.tokenization_window = Tokenization(csv_data, self.csv_path)  # 새로운 창의 인스턴스를 생성
            self.tokenization_window.finished.connect(tokenization_finished)
            self.tokenization_window.show()  # 새로운 창을 띄움

        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def kimkem_kimkem_file(self):
        try:
            selected_directory = self.dataprocess_getfiledirectory()
            if len(selected_directory) == 0:
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

            token_data = pd.read_csv(selected_directory[0], low_memory=False)
            self.kimkem_kimkemStart(token_data, os.path.basename(selected_directory[0]))
        except Exception as e:
            QMessageBox.information(self.main, "Information", f"오류가 발생했습니다\nError Log: {e}")

    def kimkem_kimkemStart(self, token_data, tokenfile_name):
        QMessageBox.information(self.main, "Information", f"KEM KIM 데이터를 저장할 위치를 선택하세요")
        save_path = QFileDialog.getExistingDirectory(self.main, "데이터를 저장할 위치를 선택하세요", self.main.default_directory)
        if save_path == '':
            QMessageBox.warning(self.main, "Warning", "No directory selected.")
            return

        while True:
            dialog = KimKemInputDialog()
            dialog.exec_()
            try:
                if dialog.data['startyear'] == '' or dialog.data['topword'] == '':
                    return
                startyear = int(dialog.data['startyear'])
                topword = int(dialog.data['topword'])
                yes_selected = dialog.data['yes_selected']
                no_selected = dialog.data['no_selected']
                break
            except:
                QMessageBox.information(self.main, "Warning", "분석 시작 연도, 상위 단어 개수는 숫자로만 입력하세요")

        if yes_selected == True:
            QMessageBox.information(self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
            exception_word_list_path = QFileDialog.getOpenFileName(self.main, "데이터를 저장할 위치를 선택하세요", self.main.default_directory, "CSV Files (*.csv);;All Files (*)")
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

        self.main.openFileExplorer(save_path)
        kimkem_obj = KimKem(token_data, tokenfile_name, save_path, startyear, topword, exception_word_list)
        result = kimkem_obj.make_kimkem()

        if result == 1:
            QMessageBox.information(self.main, "Information", f"KEM KIM 분석 데이터가 성공적으로 저장되었습니다")
        else:
            QMessageBox.information(self.main, "Information", f"Keyword가 존재하지 않아 KEM KIM 분석이 진행되지 않았습니다")


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
    def NaverNewsReplyAnalysis(self, data, file_path):
        if 'Reply Sentiment' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Reply CSV 형태와 일치하지 않습니다")
            return
        # 'Reply Date'를 datetime 형식으로 변환
        data['Reply Date'] = pd.to_datetime(data['Reply Date'])

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

    def NaverCafeArticleAnalysis(self, data, file_path):
        if 'NaverCafe Name' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverCafe Article CSV 형태와 일치하지 않습니다")
            return
        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(data['Article Date'])
        # 특정 열들에 대해 pd.to_numeric을 적용하여 숫자형으로 변환
        cols_to_convert = ['NaverCafe MemberCount', 'Article ReadCount', 'Article ReplyCount']
        data[cols_to_convert] = data[cols_to_convert].apply(pd.to_numeric, errors='coerce')

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
    def NaverCafeReplyAnalysis(self, data, file_path):
        # 'Article URL' 열이 있는지 확인
        if 'Article URL' not in list(data.columns):
            QMessageBox.warning(self.main, "Warning", "NaverCafe Reply CSV 형태와 일치하지 않습니다")
            return

        # 'Reply Date'를 datetime 형식으로 변환
        data['Reply Date'] = pd.to_datetime(data['Reply Date'])

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

class KimKem:
    def __init__(self, token_data, csv_name, save_path, startyear, word_num, exception_word_list = []):
        self.token_data = token_data
        self.folder_name = csv_name.replace('.csv', '').replace('token_', '')
        self.startyear = startyear
        self.word_num = word_num
        self.except_option_display = 'Y' if exception_word_list else 'N'
        self.exception_word_list = exception_word_list

        # Text Column Name 지정
        for column in token_data.columns.tolist():
            if 'Text' in column:
                self.textColumn_name = column
            elif 'Date' in column:
                self.dateColumn_name = column


        self.kimkem_folder_path = os.path.join(
            save_path,
            f"kimkem_{str(self.folder_name)} (start={str(self.startyear)},topword={str(self.word_num)},except={str(self.except_option_display)})"
        )
        os.makedirs(self.kimkem_folder_path, exist_ok=True)

    def make_kimkem(self):
        # Step 1: 데이터 분할 및 초기화
        year_divided_group = self.divide_period(self.token_data)#
        yyear_divided_dic = self._initialize_year_divided_dic(year_divided_group)#

        # Step 2: 연도별 단어 리스트 생성
        year_divided_dic = self._generate_year_divided_dic(yyear_divided_dic)#
        year_divided_dic_merged = self._merge_year_divided_dic(year_divided_dic)#

        # Step 3: 상위 공통 단어 추출 및 키워드 리스트 생성
        top_common_words = self._extract_top_common_words(year_divided_dic_merged)#
        keyword_list = self._get_keyword_list(top_common_words)#

        if keyword_list == []:
            os.rmdir(self.kimkem_folder_path)
            return 0

        # Step 4: TF, DF, DoV, DoD 계산
        tf_counts, df_counts = self.cal_tf(keyword_list, year_divided_dic_merged), self.cal_df(keyword_list, year_divided_dic)
        DoV_dict, DoD_dict = self.cal_DoV(keyword_list, year_divided_dic, tf_counts), self.cal_DoD(keyword_list, year_divided_dic, df_counts)

        # Step 5: 결과 저장 디렉토리 설정
        self._create_output_directories()

        # Step 6: 결과 저장 (TF, DF, DoV, DoD)
        self._save_kimkem_results(tf_counts, df_counts, DoV_dict, DoD_dict)

        # Step 7: 평균 증가율 및 빈도 계산
        avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency = self._calculate_averages(keyword_list, DoV_dict, DoD_dict, tf_counts, df_counts)

        # Step 8: 신호 분석 및 그래프 생성
        DoV_signal, DoD_signal = self._analyze_signals(avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency)

        # Step 9: 최종 신호 저장
        self._save_final_signals(DoV_signal, DoD_signal)

        return 1

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

    # self.word_num 개의 top common words 뽑아냄
    def _extract_top_common_words(self, year_divided_dic_merged):
        return {k: [item for item, count in Counter(v).most_common(self.word_num)] for k, v in
                year_divided_dic_merged.items()}

    def _get_keyword_list(self, top_common_words):
        intersection = set.intersection(*[set(value) for value in top_common_words.values()])
        return [word for word in list(intersection) if len(word) >= 2]

    def _create_output_directories(self):
        article_kimkem_folder = self.kimkem_folder_path
        self.tf_folder = os.path.join(article_kimkem_folder, "article_TF")
        self.df_folder = os.path.join(article_kimkem_folder, "article_DF")
        self.DoV_folder = os.path.join(article_kimkem_folder, "article_DoV")
        self.DoD_folder = os.path.join(article_kimkem_folder, "article_DoD")
        self.signal_folder = os.path.join(article_kimkem_folder, "signal")
        self.graph_folder = os.path.join(article_kimkem_folder, "graph")

        os.makedirs(self.tf_folder, exist_ok=True)
        os.makedirs(self.df_folder, exist_ok=True)
        os.makedirs(self.DoV_folder, exist_ok=True)
        os.makedirs(self.DoD_folder, exist_ok=True)
        os.makedirs(self.signal_folder, exist_ok=True)
        os.makedirs(self.graph_folder, exist_ok=True)

    def _save_kimkem_results(self, tf_counts, df_counts, DoV_dict, DoD_dict):
        for year in tf_counts:
            self._save_yearly_data(self.tf_folder, year, tf_counts, 'TF')
            self._save_yearly_data(self.df_folder, year, df_counts, 'DF')
            self._save_yearly_data(self.DoV_folder, year, DoV_dict, 'DoV')
            self._save_yearly_data(self.DoD_folder, year, DoD_dict, 'DoD')

    def _save_yearly_data(self, folder, year, data_dict, label):
        data_df = pd.DataFrame(list(data_dict[year].items()), columns=['keyword', label])
        data_df.to_csv(f"{folder}/{year}_{label}.csv", index=False, encoding='utf-8-sig')

    def _calculate_averages(self, keyword_list, DoV_dict, DoD_dict, tf_counts, df_counts):
        year_list = list(tf_counts.keys())
        max_year, min_year = max(year_list), min(year_list)

        avg_DoV_increase_rate = {}
        avg_DoD_increase_rate = {}
        avg_term_frequency = {}
        avg_doc_frequency = {}

        for word in keyword_list:
            avg_DoV_increase_rate[word] = self._calculate_average_increase(DoV_dict, word, max_year, min_year)
            avg_DoD_increase_rate[word] = self._calculate_average_increase(DoD_dict, word, max_year, min_year)
            avg_term_frequency[word] = self._calculate_average_frequency(tf_counts, word)
            avg_doc_frequency[word] = self._calculate_average_frequency(df_counts, word)

        return avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency

    def _calculate_average_increase(self, data_dict, word, max_year, min_year):
        return (((data_dict[max_year][word] / data_dict[min_year][word]) ** (
                    1 / (int(max_year) - int(min_year)))) - 1) * 100

    def _calculate_average_frequency(self, counts_dict, word):
        return sum([counts_dict[year][word] for year in counts_dict.keys()]) / len(counts_dict)

    def _analyze_signals(self, avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency):
        DoV_signal = self.DoV_draw_graph(avg_DoV_increase_rate, avg_term_frequency, self.graph_folder)
        DoD_signal = self.DoD_draw_graph(avg_DoD_increase_rate, avg_doc_frequency, self.graph_folder)
        return DoV_signal, DoD_signal

    def _save_final_signals(self, DoV_signal, DoD_signal):
        DoV_signal_df = pd.DataFrame([(k, v) for k, v in DoV_signal.items()], columns=['signal', 'word'])
        DoV_signal_df.to_csv(os.path.join(self.signal_folder, "DoV_signal.csv"), index=False, encoding='utf-8-sig')

        DoD_signal_df = pd.DataFrame([(k, v) for k, v in DoD_signal.items()], columns=['signal', 'word'])
        DoD_signal_df.to_csv(os.path.join(self.signal_folder, "DoD_signal.csv"), index=False, encoding='utf-8-sig')

        final_signal = self._get_communal_signals(DoV_signal, DoD_signal)
        final_signal_df = pd.DataFrame([(k, v) for k, v in final_signal.items()], columns=['signal', 'word'])
        final_signal_df.to_csv(os.path.join(self.signal_folder, "communal_signal.csv"), index=False,
                               encoding='utf-8-sig')

    def _get_communal_signals(self, DoV_signal, DoD_signal):
        communal_strong_signal = [word for word in DoV_signal['strong_signal'] if word in DoD_signal['strong_signal']]
        communal_weak_signal = [word for word in DoV_signal['weak_signal'] if word in DoD_signal['weak_signal']]
        communal_latent_signal = [word for word in DoV_signal['latent_signal'] if word in DoD_signal['latent_signal']]
        communal_well_known_signal = [word for word in DoV_signal['well_known_signal'] if
                                      word in DoD_signal['well_known_signal']]
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
                value = (tf_counts[year][keyword] / len(year_divided_dic[year])) * (
                            1 - 0.05 * (int(year) - self.startyear))
                keyword_DoV_dic[keyword] = value
            DoV_dict[year] = keyword_DoV_dic
        return DoV_dict

    # 연도별 keyword DoD 딕셔너리 반환
    def cal_DoD(self, keyword_list, year_divided_dic, df_counts):
        DoD_dict = {}
        for year in year_divided_dic:
            keyword_DoV_dic = {}
            for keyword in keyword_list:
                value = (df_counts[year][keyword] / len(year_divided_dic[year])) * (
                            1 - 0.05 * (int(year) - self.startyear))
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

    def DoV_draw_graph(self, avg_DoV_increase_rate, avg_term_frequency, graph_folder):
        median_avg_term = self.find_median(list(avg_term_frequency.values()))  # x축, 평균 단어 빈도
        median_avg_DoV = self.find_median(list(avg_DoV_increase_rate.values()))  # y축, 평균 증가율

        coordinates = {}
        coordinates['axis'] = [median_avg_term, median_avg_DoV]

        for key in avg_DoV_increase_rate:
            if key not in self.exception_word_list:
                coordinates[key] = (avg_term_frequency[key], avg_DoV_increase_rate[key])

        plt.figure(figsize=(100, 100))
        plt.axvline(x=median_avg_term, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=median_avg_DoV, color='k', linestyle='--')  # y축 중앙값 수평선

        strong_signal = [word for word in coordinates if
                         coordinates[word][0] > median_avg_term and coordinates[word][1] > median_avg_DoV]
        weak_signal = [word for word in coordinates if
                       coordinates[word][0] < median_avg_term and coordinates[word][1] > median_avg_DoV]
        latent_signal = [word for word in coordinates if
                         coordinates[word][0] < median_avg_term and coordinates[word][1] < median_avg_DoV]
        well_known_signal = [word for word in coordinates if
                             coordinates[word][0] > median_avg_term and coordinates[word][1] < median_avg_DoV]

        strong_signal = [word for word in strong_signal if word not in self.exception_word_list]
        weak_signal = [word for word in weak_signal if word not in self.exception_word_list]
        latent_signal = [word for word in latent_signal if word not in self.exception_word_list]
        well_known_signal = [word for word in well_known_signal if word not in self.exception_word_list]

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
        plt.savefig(graph_folder + "/" + "TF_DOV_graph (size=100 font=50).png")

        coordinates_df = pd.DataFrame([(k, v) for k, v in coordinates.items()], columns=['key', 'value'])
        coordinates_df.to_csv(graph_folder + "/" + "DOV_coordinates.csv", index=False, encoding='utf-8-sig')

        return {'strong_signal': strong_signal, "weak_signal": weak_signal, "latent_signal": latent_signal, "well_known_signal": well_known_signal}

    def DoD_draw_graph(self, avg_DoD_increase_rate, avg_doc_frequency, graph_folder):
        median_avg_doc = self.find_median(list(avg_doc_frequency.values()))  # x축, 평균 단어 빈도
        median_avg_DoD = self.find_median(list(avg_DoD_increase_rate.values()))  # y축, 평균 증가율

        coordinates = {}
        coordinates['axis'] = [median_avg_doc, median_avg_DoD]

        for key in avg_DoD_increase_rate:
            if key not in self.exception_word_list:
                coordinates[key] = (avg_doc_frequency[key], avg_DoD_increase_rate[key])

        plt.figure(figsize=(100, 100))
        plt.axvline(x=median_avg_doc, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=median_avg_DoD, color='k', linestyle='--')  # y축 중앙값 수평선

        strong_signal = [word for word in coordinates if
                         coordinates[word][0] > median_avg_doc and coordinates[word][1] > median_avg_DoD]
        weak_signal = [word for word in coordinates if
                       coordinates[word][0] < median_avg_doc and coordinates[word][1] > median_avg_DoD]
        latent_signal = [word for word in coordinates if
                         coordinates[word][0] < median_avg_doc and coordinates[word][1] < median_avg_DoD]
        well_known_signal = [word for word in coordinates if
                             coordinates[word][0] > median_avg_doc and coordinates[word][1] < median_avg_DoD]

        strong_signal = [word for word in strong_signal if word not in self.exception_word_list]
        weak_signal = [word for word in weak_signal if word not in self.exception_word_list]
        latent_signal = [word for word in latent_signal if word not in self.exception_word_list]
        well_known_signal = [word for word in well_known_signal if word not in self.exception_word_list]

        # 각 좌표와 해당 키를 표시
        for key, value in coordinates.items():
            if key != 'axis':
                plt.scatter(value[0], value[1])
                plt.text(value[0], value[1], key, fontsize=50)

        # 그래프 제목 및 레이블 설정

        plt.title("Keyword Issue Map", fontsize=50)
        plt.xlabel("Average Document Frequency(TF)", fontsize=50)
        plt.ylabel("Time-Weighted increasing rate", fontsize=50)

        # 그래프 표시
        plt.savefig(graph_folder + "/" + "TF_DOD_graph (size=100 font=50).png")

        coordinates_df = pd.DataFrame([(k, v) for k, v in coordinates.items()], columns=['key', 'value'])
        coordinates_df.to_csv(graph_folder + "/" + "DOD_coordinates.csv", index=False, encoding='utf-8-sig')

        return {'strong_signal': strong_signal, "weak_signal": weak_signal, "latent_signal": latent_signal, "well_known_signal": well_known_signal}

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

        # 확인 버튼 생성 및 클릭 시 동작 연결
        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.submit)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def submit(self):
        # 입력된 데이터를 확인하고 처리
        startyear = self.startyear_input.text()
        topword = self.topword_input.text()
        yes_selected = self.yes_checkbox.isChecked()
        no_selected = self.no_checkbox.isChecked()

        self.data = {
            'startyear': startyear,
            'topword': topword,
            'yes_selected': yes_selected,
            'no_selected': no_selected,
        }
        self.accept()

class Tokenization(QWidget):
    # 작업 완료 시 데이터를 반환하는 신호
    finished = pyqtSignal(pd.DataFrame)

    def __init__(self, csv_data, csv_path):
        super().__init__()
        self.kiwi = Kiwi(num_workers=8)
        self.csv_data = csv_data
        self.csv_path = csv_path
        self.csv_name = os.path.basename(csv_path)

        for column in csv_data.columns.tolist():
            if 'Text' in column:
                self.textColumn_name = column

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 1000)  # 범위를 0.0에서 100.0처럼 보이게 설정
        self.progress.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress)

        self.label = QLabel('Progress:', self)
        layout.addWidget(self.label)

        self.btn = QPushButton('토큰화 시작', self)
        self.btn.clicked.connect(self.startTask)
        layout.addWidget(self.btn)

        self.setLayout(layout)

        self.setWindowTitle(f'{self.csv_name} Tokenization')
        self.setGeometry(300, 300, 800, 170)

    def startTask(self):
        # Worker 인스턴스에 실행할 작업 함수와 인자들을 전달
        self.worker = Worker(self.tokenization_task)
        self.worker.progress.connect(self.updateProgress)
        self.worker.finished.connect(self.onFinished)
        self.worker.start()
        self.btn.setEnabled(False)  # 작업 중에 버튼 비활성화

    def updateProgress(self, value):
        self.progress.setValue(value)
        self.label.setText(f'Progress: {value/10}%')
        if int(value/10) == 100:
            self.label.setText('Task Completed!')

    def onFinished(self):
        self.btn.setEnabled(True)  # 작업 완료 후 버튼 활성화
        self.finished.emit(self.csv_data)  # 작업 완료 신호와 함께 데이터 반환
        self.close()

    def tokenization_task(self, worker):
        text_list = list(self.csv_data[self.textColumn_name])
        tokenized_data = []

        for index, text in enumerate(text_list):
            try:
                if not isinstance(text, str):
                    tokenized_data.append([])
                    continue  # 문자열이 아니면 넘어감

                text = re.sub(r'[^가-힣a-zA-Z\s]', '', text)
                tokens = self.kiwi.tokenize(text)
                tokenized_text = [token.form for token in tokens if token.tag in ('NNG', 'NNP')]

                # 리스트를 쉼표로 구분된 문자열로 변환
                tokenized_text_str = ", ".join(tokenized_text)
                tokenized_data.append(tokenized_text_str)

                progress_value = round((index + 1) / len(text_list) * 100, 1) * 10
                progress_value = int(progress_value)
                worker.progress.emit(progress_value)  # 진행 상황을 전달

            except:
                tokenized_data.append([])

        self.csv_data[self.textColumn_name] = tokenized_data

class Worker(QThread):
    # 작업의 진행 상황을 전달하기 위한 신호
    progress = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, task_func, *args, **kwargs):
        super().__init__()
        self.task_func = task_func  # 작업 함수 저장
        self.args = args  # 작업 함수의 인자
        self.kwargs = kwargs  # 작업 함수의 키워드 인자

    def run(self):
        # 작업 함수를 실행하고, 완료되면 finished 신호 발송
        self.task_func(self, *self.args, **self.kwargs)
        self.finished.emit()

if __name__ == '__main__':
    import pandas as pd

    # CSV 파일을 읽어옵니다.
    df = pd.read_csv('/Users/yojunsmacbookprp/Desktop/BIGMACLAB_MANAGER/navernews_무고죄_20100101_20200101_0808_1047/navernews_무고죄_20100101_20200101_0808_1047_reply.csv')

    # Article URL을 기준으로 Reply Text를 합칩니다.
    merged_df = df.groupby('Article URL').agg({
        'Reply Text': ' '.join,
        'Reply Date': 'first'
    }).reset_index()

    # 결과를 새로운 CSV 파일로 저장합니다.
    merged_df.to_csv('merged_reply.csv', index=False, encoding='utf-8-sig')