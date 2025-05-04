import os
import sys
import gc
import copy
import re
import ast
import csv
import platform
import warnings
import traceback
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm
from datetime import datetime
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QInputDialog, QMessageBox, QFileDialog, QDialog, QHBoxLayout, QCheckBox,
    QComboBox, QLineEdit, QLabel, QDialogButtonBox, QGridLayout,
    QGroupBox, QScrollArea, QVBoxLayout,
    QPushButton, QButtonGroup, QRadioButton, QDateEdit
)
from Manager_Console import openConsole, closeConsole
import chardet
from DataProcess import DataProcess
from Kemkim import KimKem
import asyncio
from googletrans import Translator

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
        self.DBTableColumn = ['Database', 'Type', 'Keyword', 'StartDate', 'EndDate', 'Option', 'Status', 'User', 'Size']
        self.main.makeTable(self.main.dataprocess_tab1_tablewidget, self.DB['DBtable'], self.DBTableColumn)
        self.analysis_makeFileFinder()
        self.anaylsis_buttonMatch()
        self.console_open = False

    def analysis_search_DB(self):
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
            self.main.programBugLog(traceback.format_exc())

    def analysis_refresh_DB(self):
        try:
            self.main.printStatus("새로고침 중...")

            self.DB = self.main.updateDB()
            self.main.makeTable(self.main.dataprocess_tab1_tablewidget, self.DB['DBtable'], self.DBTableColumn)

            self.main.printStatus()
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def analysis_timesplit_DB(self):
        try:
            def selectDB():
                selectedRow = self.main.dataprocess_tab1_tablewidget.currentRow()
                if not selectedRow >= 0:
                    return 0 ,0, 0
                targetDB = self.DB['DBnames'][selectedRow]
                self.main.userLogging(f'ANALYSIS -> timesplit_DB({targetDB})')

                folder_path  = QFileDialog.getExistingDirectory(self.main, "분할 데이터를 저장할 폴더를 선택하세요", self.main.localDirectory)
                if folder_path:
                    try:
                        splitdata_path = os.path.join(folder_path, targetDB + '_split')

                        while True:
                            try:
                                os.mkdir(splitdata_path)
                                break
                            except:
                                splitdata_path += "_copy"

                        self.main.mySQLObj.connectDB(targetDB)
                        tableList = self.main.mySQLObj.showAllTable(targetDB)
                        tableList = [table for table in tableList if 'info' not in table]

                        return targetDB, tableList, splitdata_path

                    except Exception as e:
                        self.main.programBugLog(traceback.format_exc())
                else:
                    return 0,0,0

            self.main.printStatus("분할 데이터를 저장할 위치를 선택하세요...")
            targetDB, tableList, splitdata_path = selectDB()

            if targetDB == 0:
                self.main.printStatus()
                return
            self.main.printStatus(f"{targetDB} 분할 및 저장 중...")
            if self.main.SETTING['ProcessConsole'] == 'default':
                openConsole("데이터 분할")

            if self.main.SETTING['ProcessConsole'] == 'default':
                iterator = tqdm(tableList, desc="Download(split) ", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' =')
            else:
                iterator = tableList

            for table in iterator:
                table_path = os.path.join(splitdata_path, table + '_split')
                try:
                    os.mkdir(table_path)
                except:
                    table_path += "_copy"
                    os.mkdir(table_path)

                table_df = self.main.mySQLObj.TableToDataframe(table)
                table_df = self.dataprocess_obj.TimeSplitter(table_df)

                year_divided_group = table_df.groupby('year')
                month_divided_group = table_df.groupby('year_month')
                week_divided_group = table_df.groupby('week')

                self.dataprocess_obj.TimeSplitToCSV(1, year_divided_group, table_path, table)
                self.dataprocess_obj.TimeSplitToCSV(2, month_divided_group, table_path, table)

                del year_divided_group
                del month_divided_group
                del week_divided_group
                gc.collect()
            self.main.printStatus()
            if self.main.SETTING['ProcessConsole'] == 'default':
                closeConsole()
            reply = QMessageBox.question(self.main, 'Notification', f"{targetDB} 분할 저장이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.openFileExplorer(splitdata_path)

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def analysis_analysis_DB(self):
        try:
            def selectDB():
                selectedRow = self.main.dataprocess_tab1_tablewidget.currentRow()
                if not selectedRow >= 0:
                    return 0 ,0, 0
                targetDB = self.DB['DBnames'][selectedRow]
                self.main.userLogging(f'ANALYSIS -> analysis_DB({targetDB})')

                folder_path  = QFileDialog.getExistingDirectory(self.main, "분석 데이터를 저장할 폴더를 선택하세요", self.main.localDirectory)
                if folder_path:
                    try:
                        analysisdata_path = os.path.join(folder_path, targetDB + '_analysis')

                        while True:
                            try:
                                os.mkdir(analysisdata_path)
                                break
                            except:
                                analysisdata_path += "_copy"

                        self.main.mySQLObj.connectDB(targetDB)
                        tableList = self.main.mySQLObj.showAllTable(targetDB)
                        tableList = [table for table in tableList if 'info' not in table]

                        return targetDB, tableList, analysisdata_path

                    except Exception as e:
                        self.main.programBugLog(traceback.format_exc())
                else:
                    return 0,0,0

            self.main.printStatus("분석 데이터를 저장할 위치를 선택하세요...")
            targetDB, tableList, analysisdata_path = selectDB()
            if targetDB == 0:
                self.main.printStatus()
                return

            self.main.printStatus(f"{targetDB} 분석 및 저장 중...")
            if self.main.SETTING['ProcessConsole'] == 'default':
                openConsole('데이터 분석')
            print(f"DB: {targetDB}\n")

            if self.main.SETTING['ProcessConsole'] == 'default':
                iterator = tqdm(enumerate(tableList), desc="Analysis ", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' =')
            else:
                iterator = enumerate(tableList)

            for index, table in iterator:
                if 'token' in table:
                    continue
                tablename = table.split('_')
                tabledf = self.main.mySQLObj.TableToDataframe(table)

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
                        QMessageBox.warning(self.main, "Not Supported",
                                            f"{tablename[0]} {tablename[6]} 분석은 지원되지 않는 기능입니다")
                        break

                del tabledf
                gc.collect()

            if self.main.SETTING['ProcessConsole'] == 'default':
                closeConsole()
            self.main.printStatus()

            reply = QMessageBox.question(self.main, 'Notification', f"{targetDB} 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.openFileExplorer(analysisdata_path)

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def analysis_makeFileFinder(self):
        self.file_dialog = self.main.makeFileFinder(self.main)
        self.main.analysis_filefinder_layout.addWidget(self.file_dialog)

    def analysis_getfiledirectory(self, file_dialog):
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

    def analysis_timesplit_file(self):
        try:
            selected_directory = self.analysis_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format", f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            reply = QMessageBox.question(self.main, 'Notification', f"선택하신 파일을 시간 분할하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply != QMessageBox.Yes:
                return
            if self.main.SETTING['ProcessConsole'] == 'default':
                openConsole("데이터 분할")

            def split_table(csv_path):
                table_path = os.path.join(os.path.dirname(csv_path), os.path.basename(csv_path).replace('.csv', '') + '_split')
                while True:
                    try:
                        os.mkdir(table_path)
                        break
                    except:
                        table_path += "_copy"

                table_df = self.main.readCSV(csv_path)

                if any('Date' in element for element in table_df.columns.tolist()) == False or table_df.columns.tolist() == []:
                    QMessageBox.information(self.main, "Wrong File", f"시간 분할할 수 없는 파일입니다")
                    if self.main.SETTING['ProcessConsole'] == 'default':
                        closeConsole()
                    return 0
                print("진행 중...")
                table_df = self.dataprocess_obj.TimeSplitter(table_df)

                self.year_divided_group = table_df.groupby('year')
                self.month_divided_group = table_df.groupby('year_month')
                self.week_divided_group = table_df.groupby('week')

                return table_path
            def saveTable(tablename, table_path):
                self.dataprocess_obj.TimeSplitToCSV(1, self.year_divided_group, table_path, tablename)
                self.dataprocess_obj.TimeSplitToCSV(2, self.month_divided_group, table_path, tablename)
            def main(directory_list):
                self.main.userLogging(f'ANALYSIS -> timesplit_file({directory_list[0]})')
                for csv_path in directory_list:
                    table_path = split_table(csv_path)
                    if table_path == 0:
                        return
                    saveTable(os.path.basename(csv_path).replace('.csv', ''), table_path)

                    del self.year_divided_group
                    del self.month_divided_group
                    del self.week_divided_group
                    gc.collect()
                if self.main.SETTING['ProcessConsole'] == 'default':
                    closeConsole()
                reply = QMessageBox.question(self.main, 'Notification', f"데이터 분할이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.main.openFileExplorer(os.path.dirname(selected_directory[0]))
                    
            self.main.printStatus("데이터 분할 및 저장 중...")
            main(selected_directory)
            self.main.printStatus()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def analysis_merge_file(self):
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

            selected_directory = self.analysis_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format", f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            elif len(selected_directory) < 2:
                QMessageBox.warning(self.main, f"Wrong Selection", "2개 이상의 CSV 파일 선택이 필요합니다")
                return

            mergedfilename, ok = QInputDialog.getText(None, '파일명 입력', '병합 파일명을 입력하세요:', text='merged_file')
            if not ok or not mergedfilename:
                return
            self.main.userLogging(f'ANALYSIS -> merge_file({mergedfilename})')
            all_df = [self.main.readCSV(directory) for directory in selected_directory]
            all_columns = [df.columns.tolist() for df in all_df]
            same_check_result = find_different_element_index(all_columns)
            if same_check_result != None:
                QMessageBox.warning(self.main, f"Wrong Format", f"{os.path.basename(selected_directory[same_check_result])}의 CSV 형식이 다른 파일과 일치하지 않습니다")
                return

            self.main.printStatus("데이터 병합 중...")
            if self.main.SETTING['ProcessConsole'] == 'default':
                openConsole("데이터 병합")
            print("Target Files *\n")
            for directory in selected_directory:
                print(directory)
            print("")

            mergedfiledir = os.path.dirname(selected_directory[0])
            if ok and mergedfilename:
                merged_df = pd.DataFrame()

                if self.main.SETTING['ProcessConsole'] == 'default':
                    iterator = tqdm(all_df, desc="Merge ", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' =')
                else:
                    iterator = all_df

                for df in iterator:
                    merged_df = pd.concat([merged_df, df], ignore_index=True)

                merged_df.to_csv(os.path.join(mergedfiledir, mergedfilename)+'.csv', index=False, encoding='utf-8-sig')
            self.main.printStatus()
            if self.main.SETTING['ProcessConsole'] == 'default':
                closeConsole()

            reply = QMessageBox.question(self.main, 'Notification', f"데이터 병합 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.openFileExplorer(mergedfiledir)

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def analysis_analysis_file(self):
        try:
            class OptionDialog(QDialog):
                def __init__(self):
                    super().__init__()
                    self.setWindowTitle('Select Options')

                    # 다이얼로그 레이아웃
                    layout = QVBoxLayout()

                    # 여러 옵션 추가 (예: 체크박스, 라디오 버튼, 콤보박스)
                    self.checkbox_group = []

                    self.combobox = QComboBox()
                    self.combobox.addItems(['Naver News', 'Naver Blog', 'Naver Cafe', 'Google YouTube'])
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
                    elif self.combobox.currentText() == 'Naver Cafe':
                        options = ['article 분석', 'reply 분석']
                    elif self.combobox.currentText() == 'Google YouTube':
                        options = ['article 분석', 'reply 분석', 'rereply 분석']

                    for option in options:
                        checkbox = QCheckBox(option)
                        checkbox.setAutoExclusive(True)  # 중복 체크 불가
                        self.checkbox_group.append(checkbox)
                        self.layout().insertWidget(self.layout().count() - 1, checkbox)  # 버튼 위에 체크박스 추가

            selected_directory = self.analysis_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(self.main, f"Wrong Selection", "한 개의 CSV 파일만 선택하여 주십시오")
                return

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
            else:
                self.main.printStatus()
                return
            if self.main.SETTING['ProcessConsole'] == 'default':
                openConsole('데이터 분석')

            print("CSV 파일 읽는 중...")
            csv_path = selected_directory[0]
            csv_filename = os.path.basename(csv_path)

            # 먼저, selected_options 리스트의 길이를 검사합니다.
            if len(selected_options) < 2:
                QMessageBox.warning(self.main, "Error", "선택 옵션이 부족합니다.")
                return

            # 첫 번째 요소의 split 결과 검사
            split0 = selected_options[0].split()
            if len(split0) < 1:
                QMessageBox.warning(self.main, "Error", "첫 번째 옵션 형식이 올바르지 않습니다.")
                return

            # 두 번째 요소의 split 결과 검사
            split1 = selected_options[1].split()
            if len(split1) < 2:
                QMessageBox.warning(self.main, "Error", "두 번째 옵션 형식이 올바르지 않습니다.")
                return

            # 검사 통과 시, words 집합 생성
            words = {split0[0].lower(), split1[0].lower(), split1[1].lower()}

            if selected_options[0].split()[0].lower() not in csv_filename and selected_options[1].split()[0].lower() not in csv_filename and selected_options[1].split()[1].lower() not in csv_filename:
                QMessageBox.warning(self.main, "Not Supported", f"선택하신 파일이 옵션과 일치하지 않습니다")
                return

            csv_data = pd.read_csv(csv_path, low_memory=False)

            self.main.userLogging(f'ANALYSIS -> analysis_file({csv_path})')

            print(f"\n{csv_filename.replace('.csv', '')} 데이터 분석 중...")
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
                case ['article 분석', 'Google YouTube']:
                    self.dataprocess_obj.YouTubeArticleAnalysis(csv_data, csv_path)
                case ['reply 분석', 'Google YouTube']:
                    self.dataprocess_obj.YouTubeReplyAnalysis(csv_data, csv_path)
                case ['rereply 분석', 'Google YouTube']:
                    self.dataprocess_obj.YouTubeRereplyAnalysis(csv_data, csv_path)
                case []:
                    if self.main.SETTING['ProcessConsole'] == 'default':
                        closeConsole()
                    return
                case _:
                    if self.main.SETTING['ProcessConsole'] == 'default':
                        closeConsole()
                    QMessageBox.warning(self.main, "Not Supported", f"{selected_options[1]} {selected_options[0]} 분석은 지원되지 않는 기능입니다")
                    return

            del csv_data
            gc.collect()
            if self.main.SETTING['ProcessConsole'] == 'default':
                closeConsole()

            reply = QMessageBox.question(self.main, 'Notification', f"{os.path.basename(csv_path)} 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.openFileExplorer(os.path.join(os.path.dirname(csv_path), os.path.basename(csv_path).replace('.csv', '') + '_analysis'))

        except Exception as e:
            if self.main.SETTING['ProcessConsole'] == 'default':
                closeConsole()
            self.main.programBugLog(traceback.format_exc())

    def analysis_wordcloud_file(self):
        try:
            selected_directory = self.analysis_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                QMessageBox.warning(self.main, f"Wrong Selection", f"선택된 CSV 토큰 파일이 없습니다")
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(self.main, f"Wrong Selection", "한 개의 CSV 파일만 선택하여 주십시오")
                return
            elif 'token' not in selected_directory[0]:
                QMessageBox.warning(self.main, f"Wrong File", "토큰 파일이 아닙니다")
                return

            self.main.printStatus("워드클라우드 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(self.main, "워드클라우드 데이터를 저장할 위치를 선택하세요", self.main.localDirectory)
            if save_path == '':
                self.main.printStatus()
                return

            class wordcloud_optionDialog(QDialog):
                def __init__(self, tokenfile_name):
                    super().__init__()
                    self.tokenfile_name = tokenfile_name
                    self.initUI()
                    self.data = None  # 데이터를 저장할 속성 추가

                def initUI(self):
                    try:
                        self.startdate = QDate.fromString(self.tokenfile_name.split('_')[3], "yyyyMMdd")
                        self.enddate = QDate.fromString(self.tokenfile_name.split('_')[4], "yyyyMMdd")
                    except:
                        self.startdate = QDate.currentDate()
                        self.enddate = QDate.currentDate()

                    self.setWindowTitle('WORDCLOUD OPTION')
                    self.resize(300, 250)  # 창 크기를 조정

                    layout = QVBoxLayout()

                    # 레이아웃의 마진과 간격 조정
                    layout.setContentsMargins(10, 10, 10, 10)  # (left, top, right, bottom) 여백 설정
                    layout.setSpacing(10)  # 위젯 간 간격 설정

                    # 각 입력 필드를 위한 QLabel 및 QDateEdit 생성
                    self.startdate_label = QLabel('분석 시작 일자를 선택하세요: ')
                    self.startdate_input = QDateEdit(calendarPopup=True)
                    self.startdate_input.setDisplayFormat('yyyyMMdd')
                    self.startdate_input.setDate(self.startdate)
                    layout.addWidget(self.startdate_label)
                    layout.addWidget(self.startdate_input)

                    self.enddate_label = QLabel('분석 종료 일자를 선택하세요: ')
                    self.enddate_input = QDateEdit(calendarPopup=True)
                    self.enddate_input.setDisplayFormat('yyyyMMdd')
                    self.enddate_input.setDate(self.enddate)
                    layout.addWidget(self.enddate_label)
                    layout.addWidget(self.enddate_input)

                    # 새로운 드롭다운 메뉴(QComboBox) 생성
                    self.period_option_label = QLabel('분석 주기 선택: ')
                    layout.addWidget(self.period_option_label)

                    self.period_option_menu = QComboBox()
                    self.period_option_menu.addItem('전 기간 통합 분석')
                    self.period_option_menu.addItem('1년 (Yearly)')
                    self.period_option_menu.addItem('6개월 (Half-Yearly)')
                    self.period_option_menu.addItem('3개월 (Quarterly)')
                    self.period_option_menu.addItem('1개월 (Monthly)')
                    self.period_option_menu.addItem('1주 (Weekly)')
                    self.period_option_menu.addItem('1일 (Daily)')
                    layout.addWidget(self.period_option_menu)

                    self.topword_label = QLabel('최대 단어 개수를 입력하세요: ')
                    self.topword_input = QLineEdit()
                    self.topword_input.setText('200')  # 기본값 설정
                    layout.addWidget(self.topword_label)
                    layout.addWidget(self.topword_input)

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
                        lambda: self.except_no_checkbox.setChecked(
                            False) if self.except_yes_checkbox.isChecked() else None)
                    self.except_no_checkbox.toggled.connect(
                        lambda: self.except_yes_checkbox.setChecked(
                            False) if self.except_no_checkbox.isChecked() else None)

                    checkbox_layout.addWidget(self.except_yes_checkbox)
                    checkbox_layout.addWidget(self.except_no_checkbox)
                    layout.addLayout(checkbox_layout)



                    # 체크박스 생성
                    self.eng_checkbox_label = QLabel('단어를 영문 변환하시겠습니까? ')
                    layout.addWidget(self.eng_checkbox_label)

                    checkbox_layout = QHBoxLayout()
                    self.eng_yes_checkbox = QCheckBox('Yes')
                    self.eng_no_checkbox = QCheckBox('No')

                    self.eng_yes_checkbox.setChecked(False)  # Yes 체크박스 기본 체크
                    self.eng_no_checkbox.setChecked(True)  # No 체크박스 기본 체크 해제

                    # 서로 배타적으로 선택되도록 설정
                    self.eng_yes_checkbox.toggled.connect(
                        lambda: self.eng_no_checkbox.setChecked(
                            False) if self.eng_yes_checkbox.isChecked() else None)
                    self.eng_no_checkbox.toggled.connect(
                        lambda: self.eng_yes_checkbox.setChecked(
                            False) if self.eng_no_checkbox.isChecked() else None)

                    checkbox_layout.addWidget(self.eng_yes_checkbox)
                    checkbox_layout.addWidget(self.eng_no_checkbox)
                    layout.addLayout(checkbox_layout)

                    # 확인 버튼 생성 및 클릭 시 동작 연결
                    self.submit_button = QPushButton('분석 실행')
                    self.submit_button.clicked.connect(self.submit)
                    layout.addWidget(self.submit_button)

                    self.setLayout(layout)

                def submit(self):
                    period = self.period_option_menu.currentText()
                    match period:
                        case '전 기간 통합 분석':
                            period = 'total'
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
                    startdate = self.startdate_input.text()
                    enddate = self.enddate_input.text()
                    maxword = self.topword_input.text()
                    except_yes_selected = self.except_yes_checkbox.isChecked()
                    eng_yes_selected = self.eng_yes_checkbox.isChecked()

                    self.data = {
                        'startdate': startdate,
                        'enddate': enddate,
                        'period': period,
                        'maxword': maxword,
                        'except_yes_selected': except_yes_selected,
                        'eng_yes_selected': eng_yes_selected
                    }
                    self.accept()

            self.main.printStatus("워드클라우드 옵션을 설정하세요")
            dialog = wordcloud_optionDialog(os.path.basename(selected_directory[0]))
            dialog.exec_()

            if dialog.data == None:
                self.main.printStatus()
                return

            startdate = dialog.data['startDate']
            enddate = dialog.data['endDate']
            date = (startdate, enddate)
            period = dialog.data['period']
            maxword = int(dialog.data['maxword'])
            except_yes_selected = dialog.data['except_yes_selected']
            eng_yes_selected = dialog.data['eng_yes_selected']

            filename = os.path.basename(selected_directory[0]).replace('token_', '').replace('.csv', '')
            filename = re.sub(r'(\d{8})_(\d{8})_(\d{4})_(\d{4})', f'{startdate}~{enddate}_{period}', filename)

            if except_yes_selected == True:
                QMessageBox.information(self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
                self.main.printStatus(f"예외어 사전(CSV)을 선택하세요")
                exception_word_list_path   = QFileDialog.getOpenFileName(self.main, "예외어 사전(CSV)를 선택하세요", self.main.localDirectory, "CSV Files (*.csv);;All Files (*)")
                exception_word_list_path = exception_word_list_path[0]
                if exception_word_list_path == "":
                    return
                with open(exception_word_list_path, 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']
                df = pd.read_csv(exception_word_list_path, low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    self.main.printStatus()
                    QMessageBox.warning(self.main, "Wrong Format", "예외어 사전 형식과 일치하지 않습니다")
                    return
                exception_word_list = df['word'].tolist()
            else:
                exception_word_list = []

            folder_path = os.path.join(
                save_path,
                f"wordcloud_{filename}_{datetime.now().strftime('%m%d%H%M')}"
            )

            if self.main.SETTING['ProcessConsole'] == 'default':
                openConsole("워드클라우드")

            self.main.userLogging(f'ANALYSIS -> WordCloud({os.path.basename(folder_path)})')

            self.main.printStatus("파일 불러오는 중...")
            print("\n파일 불러오는 중...\n")
            token_data = pd.read_csv(selected_directory[0], low_memory=False)

            self.dataprocess_obj.wordcloud(self.main, token_data, folder_path, date, maxword, period, exception_word_list, eng=eng_yes_selected)
            self.main.printStatus()

            if self.main.SETTING['ProcessConsole'] == 'default':
                closeConsole()

            reply = QMessageBox.question(self.main, 'Notification', f"{filename} 워드클라우드 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.main.openFileExplorer(folder_path)

            return

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

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
        class KimKemInputDialog(QDialog):
            def __init__(self, tokenfile_name):
                super().__init__()
                self.initUI()
                self.tokenfile_name = tokenfile_name
                self.data = None  # 데이터를 저장할 속성 추가

            def initUI(self):
                try:
                    self.startdate = QDate.fromString(tokenfile_name.split('_')[3], "yyyyMMdd")
                    self.enddate = QDate.fromString(tokenfile_name.split('_')[4], "yyyyMMdd")
                except:
                    self.startdate = QDate.currentDate()
                    self.enddate = QDate.currentDate()

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
                self.startdate_input.setDate(self.startdate)
                layout.addWidget(self.startdate_label)
                layout.addWidget(self.startdate_input)

                self.enddate_label = QLabel('분석 종료 일자를 선택하세요: ')
                self.enddate_input = QDateEdit(calendarPopup=True)
                self.enddate_input.setDisplayFormat('yyyyMMdd')
                self.enddate_input.setDate(self.enddate)
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

                # 비일관 필터링 체크박스 생성
                self.filter_checkbox_label = QLabel('비일관 데이터를 필터링하시겠습니까? ')
                layout.addWidget(self.filter_checkbox_label)

                checkbox_layout = QHBoxLayout()
                self.filter_yes_checkbox = QCheckBox('Yes')
                self.filter_no_checkbox = QCheckBox('No')

                self.filter_yes_checkbox.setChecked(True)  # Yes 체크박스 기본 체크
                self.filter_no_checkbox.setChecked(False)  # No 체크박스 기본 체크 해제

                checkbox_layout.addWidget(self.filter_yes_checkbox)
                checkbox_layout.addWidget(self.filter_no_checkbox)
                layout.addLayout(checkbox_layout)

                # 추적 데이터 기준 연도 설정
                self.trace_standard_label = QLabel('추적 데이터 계산 기준 연도를 설정하십시오 ')
                layout.addWidget(self.trace_standard_label)

                checkbox_layout = QHBoxLayout()
                self.trace_prevyear_checkbox = QCheckBox('직전 기간')
                self.trace_startyear_checkbox = QCheckBox('시작 기간')

                self.trace_prevyear_checkbox.setChecked(True)  # Yes 체크박스 기본 체크
                self.trace_startyear_checkbox.setChecked(False)  # No 체크박스 기본 체크 해제

                # 서로 배타적으로 선택되도록 설정
                self.trace_prevyear_checkbox.toggled.connect(
                    lambda: self.trace_startyear_checkbox.setChecked(
                        False) if self.trace_prevyear_checkbox.isChecked() else None)
                self.trace_startyear_checkbox.toggled.connect(
                    lambda: self.trace_prevyear_checkbox.setChecked(
                        False) if self.trace_startyear_checkbox.isChecked() else None)

                checkbox_layout.addWidget(self.trace_prevyear_checkbox)
                checkbox_layout.addWidget(self.trace_startyear_checkbox)
                layout.addLayout(checkbox_layout)

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
                    lambda: self.except_no_checkbox.setChecked(
                        False) if self.except_yes_checkbox.isChecked() else None)
                self.except_no_checkbox.toggled.connect(
                    lambda: self.except_yes_checkbox.setChecked(
                        False) if self.except_no_checkbox.isChecked() else None)

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
                trace_standard_selected = 'startyear' if self.trace_startyear_checkbox.isChecked() else 'prevyear'
                filter_yes_selected = self.filter_yes_checkbox.isChecked()
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
                    'filter_yes_selected': filter_yes_selected,
                    'trace_standard_selected': trace_standard_selected,
                    'ani_yes_selected': ani_yes_selected,
                    'except_yes_selected': except_yes_selected,
                    'split_option': split_option,
                    'split_custom': split_custom
                }
                self.accept()
        try:
            selected_directory = self.analysis_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                QMessageBox.warning(self.main, f"Wrong Selection", f"선택된 CSV 토큰 파일이 없습니다")
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format", f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(self.main, f"Wrong Selection", "한 개의 CSV 파일만 선택하여 주십시오")
                return
            elif 'token' not in selected_directory[0]:
                QMessageBox.warning(self.main, f"Wrong File", "토큰 파일이 아닙니다")
                return

            tokenfile_name = os.path.basename(selected_directory[0])

            self.main.printStatus("KEM KIM 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(self.main, "KEM KIM 데이터를 저장할 위치를 선택하세요", self.main.localDirectory)
            if save_path == '':
                self.main.printStatus()
                return

            self.main.printStatus("KEM KIM 옵션을 설정하세요")
            while True:
                dialog = KimKemInputDialog(tokenfile_name)
                dialog.exec_()
                try:
                    if dialog.data == None:
                        return
                    startdate = dialog.data['startDate']
                    enddate = dialog.data['endDate']
                    period = dialog.data['period']
                    topword = int(dialog.data['topword'])
                    weight = float(dialog.data['weight'])
                    graph_wordcnt = int(dialog.data['graph_wordcnt'])
                    filter_yes_selected = dialog.data['filter_yes_selected']
                    trace_standard_selected = dialog.data['trace_standard_selected']
                    ani_yes_selected = dialog.data['ani_yes_selected']
                    except_yes_selected = dialog.data['except_yes_selected']
                    split_option = dialog.data['split_option']
                    split_custom = dialog.data['split_custom']
                    # Calculate total periods based on the input period

                    if period == '1y':
                        total_periods = (1 / int(period[:-1])) * (int(enddate[:-4]) - int(startdate[:-4]) + 1)
                    elif period in ['6m', '3m', '1m']:
                        if startdate[:-4] == enddate[:-4]:  # 같은 연도일 경우
                            total_periods = ((int(enddate[4:6]) - int(startdate[4:6])) + 1) / int(period[:-1])
                        else:  # 다른 연도일 경우
                            total_periods = (12 / int(period[:-1])) * (int(enddate[:-4]) - int(startdate[:-4]) + 1)
                    elif period == '1w':
                        total_days = (datetime.strptime(str(enddate), '%Y%m%d') - datetime.strptime(str(startdate),
                                                                                                    '%Y%m%d')).days
                        total_periods = total_days // 7
                        if datetime.strptime(startdate, '%Y%m%d').strftime('%A') != 'Monday':
                            QMessageBox.warning(self.main, "Wrong Form",
                                                "분석 시작일이 월요일이 아닙니다\n\n1주 단위 분석에서는 분석 시작일을 월요일, 분석 종료일을 일요일로 설정하십시오")
                            continue
                        if datetime.strptime(enddate, '%Y%m%d').strftime('%A') != 'Sunday':
                            QMessageBox.warning(self.main, "Wrong Form",
                                                "분석 종료일이 일요일이 아닙니다\n\n1주 단위 분석에서는 분석 시작일을 월요일, 분석 종료일을 일요일로 설정하십시오")
                            continue
                    else:  # assuming '1d' or similar daily period
                        total_days = (datetime.strptime(str(enddate), '%Y%m%d') - datetime.strptime(str(startdate),
                                                                                                    '%Y%m%d')).days
                        total_periods = total_days

                    # Check if the total periods exceed the limit when multiplied by the weight
                    if total_periods * weight >= 1:
                        QMessageBox.warning(self.main, "Wrong Form",
                                            "분석 가능 기간 개수를 초과합니다\n시간가중치를 줄이거나, Period 값을 늘리거나 시작일~종료일 사이의 간격을 줄이십시오")
                        continue

                    if split_option in ['평균(Mean)', '중앙값(Median)'] and split_custom is None:
                        pass
                    else:
                        split_custom = float(split_custom)
                    break
                except:
                    QMessageBox.warning(self.main, "Wrong Form", "입력 형식이 올바르지 않습니다")

            if except_yes_selected == True:
                QMessageBox.information(self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
                self.main.printStatus(f"예외어 사전(CSV)을 선택하세요")
                exception_word_list_path = QFileDialog.getOpenFileName(self.main, "예외어 사전(CSV)를 선택하세요",
                                                                       self.main.localDirectory,
                                                                       "CSV Files (*.csv);;All Files (*)")
                exception_word_list_path = exception_word_list_path[0]
                if exception_word_list_path == "":
                    return
                with open(exception_word_list_path, 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']
                df = pd.read_csv(exception_word_list_path, low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    QMessageBox.warning(self.main, "Wrong Format", "예외어 사전 형식과 일치하지 않습니다")
                    self.main.printStatus()
                    return
                exception_word_list = df['word'].tolist()
            else:
                exception_word_list = []
                exception_word_list_path = 'N'

            if self.main.SETTING['ProcessConsole'] == 'default':
                openConsole('KEMKIM 분석')

            print("\n파일 읽는 중...\n")
            self.main.printStatus("파일 읽는 중...")
            token_data = pd.read_csv(selected_directory[0], low_memory=False)

            self.main.userLogging(
                f'ANALYSIS -> KEMKIM({tokenfile_name})-({startdate},{startdate},{topword},{weight},{filter_yes_selected})')
            kimkem_obj = KimKem(self.main, token_data, tokenfile_name, save_path, startdate, enddate, period,
                                topword, weight, graph_wordcnt, split_option, split_custom, filter_yes_selected, trace_standard_selected,
                                ani_yes_selected, exception_word_list, exception_word_list_path)
            result = kimkem_obj.make_kimkem()
            if self.main.SETTING['ProcessConsole'] == 'default':
                closeConsole()
            self.main.printStatus()

            if result == 1:
                reply = QMessageBox.question(self.main, 'Notification', "KEM KIM 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    self.main.openFileExplorer(kimkem_obj.kimkem_folder_path)
            elif result == 0:
                QMessageBox.information(self.main, "Notification", f"Keyword가 존재하지 않아 KEM KIM 분석이 진행되지 않았습니다")
            elif result == 2:
                QMessageBox.warning(self.main, "Wrong Range",
                                    "분석 가능 기간 개수를 초과합니다\n시간가중치를 줄이거나, Period 값을 늘리거나 시작일~종료일 사이의 간격을 줄이십시오")
            else:
                self.main.programBugLog(result)

            del kimkem_obj
            gc.collect()

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())
    
    def kimkem_rekimkem_file(self):

        class WordSelector(QDialog):
            def __init__(self, words):
                super().__init__()
                self.words = words
                self.selected_words = []
                self.initUI()

            def initUI(self):
                # 메인 레이아웃을 감쌀 위젯 생성
                container_widget = QDialog()
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
                self.eng_no_checkbox = QCheckBox('변환 안함')
                self.eng_auto_checkbox = QCheckBox('자동 변환')
                self.eng_manual_checkbox = QCheckBox('수동 변환')

                # ✅ QButtonGroup을 사용하여 배타적 선택 적용
                self.checkbox_group = QButtonGroup(self)
                self.checkbox_group.addButton(self.eng_no_checkbox)
                self.checkbox_group.addButton(self.eng_auto_checkbox)
                self.checkbox_group.addButton(self.eng_manual_checkbox)

                # ✅ 배타적 선택 활성화 (라디오 버튼처럼 동작)
                self.checkbox_group.setExclusive(True)

                # 기본 선택 설정
                self.eng_no_checkbox.setChecked(True)  # "변환 안함" 기본 선택

                # 레이아웃에 추가
                checkbox_layout.addWidget(self.eng_no_checkbox)
                checkbox_layout.addWidget(self.eng_auto_checkbox)
                checkbox_layout.addWidget(self.eng_manual_checkbox)
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
                self.eng_auto_checked = self.eng_auto_checkbox.isChecked()
                self.eng_manual_checked = self.eng_manual_checkbox.isChecked()
                self.eng_no_checked = self.eng_no_checkbox.isChecked()

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
                QMessageBox.warning(self.main, f"Wrong Selection", f"선택된 'Result' 디렉토리가 없습니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return
            elif len(result_directory) > 1:
                QMessageBox.warning(self.main, f"Wrong Selection", f"KemKim 폴더에 있는 하나의 'Result' 디렉토리만 선택하여 주십시오")
                return
            elif 'Result' not in os.path.basename(result_directory[0]):
                QMessageBox.warning(self.main, f"Wrong Directory", f"'Result' 디렉토리가 아닙니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return

            self.main.userLogging(f'ANALYSIS -> rekimkem_file({result_directory[0]})')
            self.main.printStatus("파일 불러오는 중...")
            
            result_directory = result_directory[0]
            final_signal_csv_path = os.path.join(result_directory, "Signal", "Final_signal.csv")
            if not os.path.exists(final_signal_csv_path):
                QMessageBox.information(self.main, 'Import Failed', 'Final_signal.csv 파일을 불러오는데 실패했습니다\n\nResult/Signal 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                self.main.printStatus()
                return
            final_signal_df = pd.read_csv(final_signal_csv_path, low_memory=False)
            words = final_signal_df['word'].tolist()
            all_keyword = []
            for word_list_str in words:
                word_list = ast.literal_eval(word_list_str)
                all_keyword.append(word_list)

            self.main.printStatus("옵션을 선택하세요")
            self.word_selector = WordSelector(all_keyword)
            if self.word_selector.exec_() == QDialog.Accepted:  # show() 대신 exec_() 사용
                selected_words = self.word_selector.selected_words
                size_input = self.word_selector.size_input
                eng_auto_option = self.word_selector.eng_auto_checked
                eng_manual_option = self.word_selector.eng_manual_checked
                eng_no_option = self.word_selector.eng_no_checked
                try:
                    size_input = tuple(map(int, size_input))
                except:
                    QMessageBox.warning(self.main, "Wrong Form", "그래프 사이즈를 숫자로 입력하여 주십시오")
                    self.main.printStatus()
                    return
            else:
                self.main.printStatus()
                return

            if eng_no_option == False:
                if eng_manual_option == True:
                    QMessageBox.information(self.main, "Information", f"키워드-영단어 사전(CSV)를 선택하세요")
                    self.main.printStatus("키워드-영단어 사전(CSV)를 선택하세요")
                    eng_keyword_list_path = QFileDialog.getOpenFileName(self.main, "키워드-영단어 사전(CSV)를 선택하세요", self.main.localDirectory, "CSV Files (*.csv);;All Files (*)")
                    eng_keyword_list_path = eng_keyword_list_path[0]
                    if eng_keyword_list_path == "":
                        return
                    with open(eng_keyword_list_path, 'rb') as f:
                        codec = chardet.detect(f.read())['encoding']
                    df = pd.read_csv(eng_keyword_list_path, low_memory=False, encoding=codec)
                    if 'english' not in list(df.keys()) or 'korean' not in list(df.keys()):
                        QMessageBox.warning(self.main, "Wrong Form", "키워드-영단어 사전 형식과 일치하지 않습니다")
                        return
                    eng_keyword_tupleList = list(zip(df['korean'], df['english']))
                elif eng_auto_option == True:
                    target_words = sum(all_keyword, [])
                    self.main.printStatus("키워드 영문 변환 중...")
                    async def wordcloud_translator(words_to_translate):
                        translator = Translator()
                        translate_history = {}

                        # 병렬 번역 수행 (이미 번역된 단어 제외)
                        if words_to_translate:
                            async def translate_word(word):
                                """ 개별 단어를 비동기적으로 번역하고 반환하는 함수 """
                                result = await translator.translate(word, dest='en', src='auto')  # ✅ await 추가
                                return word, result.text  # ✅ 원래 단어와 번역된 단어 튜플 반환

                            # 번역 실행 (병렬 처리)
                            translated_results = await asyncio.gather(
                                *(translate_word(word) for word in words_to_translate))

                            # 번역 결과를 캐시에 저장
                            for original, translated in translated_results:
                                translate_history[original] = translated

                        # ✅ (원래 단어, 번역된 단어) 튜플 리스트로 변환
                        translated_tuple_list = [(word, translate_history[word]) for word in words_to_translate if
                                                 word in translate_history]

                        return translated_tuple_list
                    eng_keyword_tupleList = asyncio.run(wordcloud_translator(target_words))
            else:
                eng_keyword_tupleList = []

            self.main.printStatus("KEMKIM 조정 중...")
            DoV_coordinates_path = os.path.join(result_directory, "Graph", "DOV_coordinates.csv")
            if not os.path.exists(DoV_coordinates_path):
                QMessageBox.warning(self.main, 'Import Failed', 'DOV_coordinates.csv 파일을 불러오는데 실패했습니다\n\nResult/Graph 디렉토리에 파일이 위치하는지 확인하여 주십시오')
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
                QMessageBox.warning(self.main, 'Import Failed', 'DOD_coordinates.csv 파일을 불러오는데 실패했습니다\n\nResult/Graph 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                self.main.printStatus()
                return
            DoD_coordinates_df = pd.read_csv(os.path.join(result_directory, "Graph", "DOD_coordinates.csv"))
            DoD_coordinates_dict = {}
            for index, row in DoD_coordinates_df.iterrows():
                key = row['key']
                value = ast.literal_eval(row['value'])  # 문자열을 튜플로 변환
                DoD_coordinates_dict[key] = value
                
            delete_word_list = pd.read_csv(os.path.join(result_directory, 'filtered_words.csv'))['word'].tolist()

            kimkem_obj = KimKem(self.main, exception_word_list=selected_words, rekemkim=True)
            
            new_result_folder = os.path.join(os.path.dirname(result_directory), f'Result_{datetime.now().strftime('%m%d%H%M')}')
            new_graph_folder = os.path.join(new_result_folder, 'Graph')
            new_signal_folder = os.path.join(new_result_folder, 'Signal')
            
            os.makedirs(new_result_folder, exist_ok=True)
            os.makedirs(new_graph_folder, exist_ok=True)
            os.makedirs(new_signal_folder, exist_ok=True)
            
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

            with open(os.path.join(new_graph_folder, 'graph_size.txt'),'w+', encoding="utf-8", errors="ignore") as graph_size:
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
            QMessageBox.information(self.main, 'Notification', 'KEMKIM 재분석이 완료되었습니다')
            self.main.openFileExplorer(new_result_folder)
        
        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def kimkem_interpretkimkem_file(self):
        class WordSelector(QDialog):
            def __init__(self, words):
                super().__init__()
                self.words = words
                self.selected_words = []
                self.initUI()

            def initUI(self):
                # 메인 레이아웃을 감쌀 위젯 생성
                container_widget = QDialog()
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
                QMessageBox.warning(self.main, f"Wrong Selection", f"선택된 'Result' 디렉토리가 없습니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return
            elif len(result_directory) > 1:
                QMessageBox.warning(self.main, f"Wrong Selection", f"KemKim 폴더에 있는 하나의 'Result' 디렉토리만 선택하여 주십시오")
                return
            elif 'Result' not in os.path.basename(result_directory[0]):
                QMessageBox.warning(self.main, f"Wrong Directory", f"'Result' 디렉토리가 아닙니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return

            result_directory = result_directory[0]
            self.main.userLogging(f'ANALYSIS -> interpret_kimkem_file({result_directory})')

            final_signal_csv_path = os.path.join(result_directory, "Signal", "Final_signal.csv")

            if not os.path.exists(final_signal_csv_path):
                QMessageBox.warning(self.main, 'Import Failed', 'Final_signal.csv 파일을 불러오는데 실패했습니다\n\nResult/Signal 디렉토리에 파일이 위치하는지 확인하여 주십시오')
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
                QMessageBox.warning(self.main, 'Import Failed', 'kemkim_info.txt 파일을 불러오는데 실패했습니다\n\nResult 디렉토리에 파일이 위치하는지 확인하여 주십시오')
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
                QMessageBox.warning(self.main, 'Import Failed', 'kemkim_info.txt 파일에서 정보를 불러오는데 실패했습니다\n\nResult 디렉토리 선택 유무와 수정되지 않은 info.txt 원본 파일이 올바른 위치에 있는지 확인하여 주십시오')
                self.main.printStatus()
                return

            QMessageBox.information(self.main, "Information", f'Keyword를 추출할 CSV 파일을 선택하세요\n\n"{recommend_csv_name}"를 선택하세요')
            object_csv_path = QFileDialog.getOpenFileName(self.main, "Keyword 추출 대상 CSV 파일을 선택하세요", self.main.localDirectory, "CSV Files (*.csv);;All Files (*)")
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
                QMessageBox.warning(self.main, 'Wrong Selection', '선택된 필터링 단어가 없습니다')
                return

            with open(object_csv_path, 'rb') as f:
                codec = chardet.detect(f.read())['encoding']
            object_csv_df = pd.read_csv(object_csv_path, low_memory=False, encoding=codec)
            if all('Text' not in word for word in list(object_csv_df.keys())):
                QMessageBox.warning(self.main, "Wrong Format", "크롤링 데이터 CSV 형식과 일치하지 않습니다")
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
                QMessageBox.warning(self.main, "No Data", "필터링 키워드를 포함하는 데이터가 존재하지 않습니다")
                return

            selected_words_dic = {
                'Filter Option': selected_option,
                'Strong Signal': ','.join(selected_words_2dim[0]),
                'Weak Signal': ','.join(selected_words_2dim[1]),
                'Latent Signal': ','.join(selected_words_2dim[2]),
                'Well-known Signal': ','.join(selected_words_2dim[3]),
            }
            # 존재 여부에 따라 파일명에 S, W, L, W를 추가
            signals = ["strong", "weak", "latent", "wellknown"]  # 각 신호의 약자
            included_signals = ','.join([signals[i] for i in range(len(selected_words_2dim)) if selected_words_2dim[i]])

            # 파일명 생성
            analysis_directory_name = f'Analysis_({included_signals})_{datetime.now().strftime("%m%d%H%M")}'
            analyze_directory = os.path.join(os.path.dirname(result_directory), analysis_directory_name)

            reply = QMessageBox.question(self.main, 'Notification', f'CSV 키워드 필터링이 완료되었습니다\n키워드를 포함하는 데이터는 {filtered_object_csv_df.shape[0]}개입니다\n\n데이터를 저장하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
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
                    with open(os.path.join(analyze_directory, 'keyword_context', f'{keyword}_context.txt'), 'w', encoding="utf-8", errors="ignore") as context:
                        context.write(add_text)

                context_df = pd.DataFrame(list(context_dict.items()), columns=['Keyword', 'Context Text'])
                # 데이터프레임을 CSV 파일로 저장
                context_df.to_csv(os.path.join(analyze_directory,  'keyword_context', 'keyword_context.csv'), index=False, encoding='utf-8-sig')
            else:
                self.main.printStatus()
                return

            if any('Title' in word for word in list(filtered_object_csv_df.keys())):
                reply = QMessageBox.question(self.main, 'Notification', f'키워드 필터링 데이터 저장이 완료되었습니다\n\nAI 분석을 진행하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    if self.main.gpt_api_key == 'default' or len(self.main.gpt_api_key) < 20:
                        QMessageBox.information(self.main, 'Notification', f'API Key가 설정되지 않았습니다\n\n환경설정에서 ChatGPT API Key를 입력해주십시오')
                        self.main.printStatus()
                        self.main.openFileExplorer(analyze_directory)
                        return

                    self.main.printStatus("AI 분석 중...")
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
                    gpt_response = self.main.generateLLM(gpt_query, self.main.SETTING['LLM_model'])
                    if type(gpt_response) != str:
                        QMessageBox.warning(self.main, "Error", f"{gpt_response[1]}")
                        self.main.printStatus()
                        self.main.openFileExplorer(analyze_directory)
                        return

                    with open(
                            os.path.join(analyze_directory, f"{object_csv_name}(키워드 {selected_option})_AI_analyze.txt"),
                            'w+', encoding="utf-8", errors="ignore") as gpt_txt:
                        gpt_txt.write(gpt_response)

                    QMessageBox.information(self.main, "AI 분석 결과", gpt_response)
                    self.main.printStatus()
                    self.main.openFileExplorer(analyze_directory)

                else:
                    self.main.printStatus()
                    self.main.openFileExplorer(analyze_directory)
            else:
                QMessageBox.information(self.main, "Notification", f"CSV 키워드 필터링이 완료되었습니다\n키워드를 포함하는 데이터는 {filtered_object_csv_df.shape[0]}개입니다")
                self.main.openFileExplorer(analyze_directory)

        except Exception as e:
            self.main.programBugLog(traceback.format_exc())

    def anaylsis_buttonMatch(self):
        self.main.analysis_refreshDB_btn.clicked.connect(self.analysis_refresh_DB)
        self.main.analysis_searchDB_lineinput.returnPressed.connect(self.analysis_search_DB)
        self.main.analysis_searchDB_btn.clicked.connect(self.analysis_search_DB)
        self.main.analysis_timesplitDB_btn.clicked.connect(self.analysis_timesplit_DB)
        self.main.analysis_dataanalysisDB_btn.clicked.connect(self.analysis_analysis_DB)

        self.main.analysis_timesplitfile_btn.clicked.connect(self.analysis_timesplit_file)
        self.main.analysis_dataanalysisfile_btn.clicked.connect(self.analysis_analysis_file)
        self.main.analysis_mergefile_btn.clicked.connect(self.analysis_merge_file)
        self.main.analysis_wordcloud_btn.clicked.connect(self.analysis_wordcloud_file)
        self.main.analysis_kemkim_btn.clicked.connect(self.kimkem_kimkem)

        self.main.analysis_refreshDB_btn.setToolTip("Ctrl+R")
        self.main.analysis_timesplitDB_btn.setToolTip("Ctrl+D")
        self.main.analysis_dataanalysisDB_btn.setToolTip("Ctrl+A")
        self.main.analysis_timesplitfile_btn.setToolTip("Ctrl+D")
        self.main.analysis_dataanalysisfile_btn.setToolTip("Ctrl+A")
        self.main.analysis_mergefile_btn.setToolTip("Ctrl+M")
        self.main.analysis_kemkim_btn.setToolTip("Ctrl+K")

    def analysis_shortcut_setting(self):
        self.updateShortcut(0)
        self.main.tabWidget_data_process.currentChanged.connect(self.updateShortcut)

    def updateShortcut(self, index):
        self.main.initShortcutialize()

        # 파일 불러오기
        if index == 0:
            self.main.ctrld.activated.connect(self.analysis_timesplit_file)
            self.main.ctrlm.activated.connect(self.analysis_merge_file)
            self.main.ctrla.activated.connect(self.analysis_analysis_file)
            self.main.ctrlk.activated.connect(self.kimkem_kimkem)

            self.main.cmdd.activated.connect(self.analysis_timesplit_file)
            self.main.cmdm.activated.connect(self.analysis_merge_file)
            self.main.cmda.activated.connect(self.analysis_analysis_file)
            self.main.cmdk.activated.connect(self.kimkem_kimkem)

        # DB 불러오기
        if index == 1:
            self.main.ctrld.activated.connect(self.analysis_timesplit_DB)
            self.main.ctrla.activated.connect(self.analysis_analysis_DB)
            self.main.ctrlr.activated.connect(self.analysis_refresh_DB)

            self.main.cmdd.activated.connect(self.analysis_timesplit_DB)
            self.main.cmda.activated.connect(self.analysis_analysis_DB)
            self.main.cmdr.activated.connect(self.analysis_refresh_DB)
