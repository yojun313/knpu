import os
import sys
import gc
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
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QFileDialog, QDialog

from libs.console import openConsole, closeConsole
from ui.finder import makeFileFinder, openFileExplorer
from ui.status import printStatus
import chardet
from libs.analysis import DataProcess
from libs.kemkim import KimKem
import uuid
import asyncio
from googletrans import Translator
import json
from urllib.parse import unquote
import zipfile
import requests
from libs.viewer import open_viewer, close_viewer, register_process
from core.shortcut import resetShortcuts
from core.setting import get_setting
from services.api import api_headers
from services.logging import userLogging, programBugLog
from services.llm import generateLLM
from services.csv import readCSV
from config import MANAGER_SERVER_API

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
        self.analysis_makeFileFinder()
        self.anaylsis_buttonMatch()
        self.console_open = False

    def analysis_makeFileFinder(self):
        self.file_dialog = makeFileFinder(self.main, self.main.localDirectory)
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
                selected_directory[index] = os.path.join(
                    os.path.dirname(selected_directory[0]), directory)

        return selected_directory

    def run_timesplit(self):
        try:
            selected_directory = self.analysis_getfiledirectory(
                self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format",
                                    f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            reply = QMessageBox.question(
                self.main, 'Notification', f"선택하신 파일을 시간 분할하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply != QMessageBox.Yes:
                return

            openConsole("데이터 분할")

            def split_table(csv_path):
                table_path = os.path.join(os.path.dirname(csv_path), os.path.basename(
                    csv_path).replace('.csv', '') + '_split')
                while True:
                    try:
                        os.mkdir(table_path)
                        break
                    except:
                        table_path += "_copy"

                table_df = readCSV(csv_path)

                if any('Date' in element for element in table_df.columns.tolist()) == False or table_df.columns.tolist() == []:
                    QMessageBox.information(
                        self.main, "Wrong File", f"시간 분할할 수 없는 파일입니다")
                    closeConsole()
                    return 0
                print("진행 중...")
                table_df = self.dataprocess_obj.TimeSplitter(table_df)

                self.year_divided_group = table_df.groupby('year')
                self.month_divided_group = table_df.groupby('year_month')
                self.week_divided_group = table_df.groupby('week')

                return table_path

            def saveTable(tablename, table_path):
                self.dataprocess_obj.TimeSplitToCSV(
                    1, self.year_divided_group, table_path, tablename)
                self.dataprocess_obj.TimeSplitToCSV(
                    2, self.month_divided_group, table_path, tablename)

            def main(directory_list):
                userLogging(
                    f'ANALYSIS -> timesplit_file({directory_list[0]})')
                for csv_path in directory_list:
                    table_path = split_table(csv_path)
                    if table_path == 0:
                        return
                    saveTable(os.path.basename(csv_path).replace(
                        '.csv', ''), table_path)

                    del self.year_divided_group
                    del self.month_divided_group
                    del self.week_divided_group
                    gc.collect()

                closeConsole()
                reply = QMessageBox.question(
                    self.main, 'Notification', f"데이터 분할이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    openFileExplorer(
                        os.path.dirname(selected_directory[0]))

            printStatus(self.main, "데이터 분할 및 저장 중...")
            main(selected_directory)
            printStatus(self.main)

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def run_merge(self):
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

            selected_directory = self.analysis_getfiledirectory(
                self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format",
                                    f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            elif len(selected_directory) < 2:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", "2개 이상의 CSV 파일 선택이 필요합니다")
                return

            mergedfilename, ok = QInputDialog.getText(
                None, '파일명 입력', '병합 파일명을 입력하세요:', text='merged_file')
            if not ok or not mergedfilename:
                return
            userLogging(f'ANALYSIS -> merge_file({mergedfilename})')
            all_df = [readCSV(directory)
                      for directory in selected_directory]
            all_columns = [df.columns.tolist() for df in all_df]
            same_check_result = find_different_element_index(all_columns)
            if same_check_result != None:
                QMessageBox.warning(
                    self.main, f"Wrong Format", f"{os.path.basename(selected_directory[same_check_result])}의 CSV 형식이 다른 파일과 일치하지 않습니다")
                return

            printStatus(self.main, "데이터 병합 중...")
            openConsole("데이터 병합")
            print("Target Files *\n")
            for directory in selected_directory:
                print(directory)
            print("")

            mergedfiledir = os.path.dirname(selected_directory[0])
            if ok and mergedfilename:
                merged_df = pd.DataFrame()

                iterator = tqdm(
                    all_df, desc="Merge ", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' =')

                for df in iterator:
                    merged_df = pd.concat([merged_df, df], ignore_index=True)

                merged_df.to_csv(os.path.join(
                    mergedfiledir, mergedfilename)+'.csv', index=False, encoding='utf-8-sig')
            printStatus(self.main)
            closeConsole()

            reply = QMessageBox.question(
                self.main, 'Notification', f"데이터 병합 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                openFileExplorer(mergedfiledir)

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def run_analysis(self):
        try:
            selected_directory = self.analysis_getfiledirectory(
                self.file_dialog)
            if len(selected_directory) == 0:
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format",
                                    f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", "한 개의 CSV 파일만 선택하여 주십시오")
                return

            selected_options = []
            from ui.dialogs import StatAnalysisDialog
            dialog = StatAnalysisDialog()
            if dialog.exec_() == QDialog.Accepted:
                selected_options = []

                # 선택된 체크박스 옵션 추가
                for checkbox in dialog.checkbox_group:
                    if checkbox.isChecked():
                        selected_options.append(checkbox.text())

                # 콤보박스에서 선택된 옵션 추가
                selected_options.append(dialog.combobox.currentText())
            else:
                printStatus(self.main)
                return

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
                QMessageBox.warning(self.main, "Error",
                                    "첫 번째 옵션 형식이 올바르지 않습니다.")
                return

            # 두 번째 요소의 split 결과 검사
            split1 = selected_options[1].split()
            if len(split1) < 2:
                QMessageBox.warning(self.main, "Error",
                                    "두 번째 옵션 형식이 올바르지 않습니다.")
                return

            # 검사 통과 시, words 집합 생성
            words = {split0[0].lower(), split1[0].lower(), split1[1].lower()}

            if selected_options[0].split()[0].lower() not in csv_filename and selected_options[1].split()[0].lower() not in csv_filename and selected_options[1].split()[1].lower() not in csv_filename:
                QMessageBox.warning(self.main, "Not Supported",
                                    f"선택하신 파일이 옵션과 일치하지 않습니다")
                return

            csv_data = pd.read_csv(csv_path, low_memory=False)

            userLogging(f'ANALYSIS -> analysis_file({csv_path})')

            print(f"\n{csv_filename.replace('.csv', '')} 데이터 분석 중...")
            match selected_options:

                case ['article 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsArticleAnalysis(
                        csv_data, csv_path)
                case ['statistics 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsStatisticsAnalysis(
                        csv_data, csv_path)
                case ['reply 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsReplyAnalysis(
                        csv_data, csv_path)
                case ['rereply 분석', 'Naver News']:
                    self.dataprocess_obj.NaverNewsRereplyAnalysis(
                        csv_data, csv_path)
                case ['article 분석', 'Naver Cafe']:
                    self.dataprocess_obj.NaverCafeArticleAnalysis(
                        csv_data, csv_path)
                case ['reply 분석', 'Naver Cafe']:
                    self.dataprocess_obj.NaverCafeReplyAnalysis(
                        csv_data, csv_path)
                case ['article 분석', 'Google YouTube']:
                    self.dataprocess_obj.YouTubeArticleAnalysis(
                        csv_data, csv_path)
                case ['reply 분석', 'Google YouTube']:
                    self.dataprocess_obj.YouTubeReplyAnalysis(
                        csv_data, csv_path)
                case ['rereply 분석', 'Google YouTube']:
                    self.dataprocess_obj.YouTubeRereplyAnalysis(
                        csv_data, csv_path)
                case []:
                    closeConsole()
                    return
                case _:
                    closeConsole()
                    QMessageBox.warning(
                        self.main, "Not Supported", f"{selected_options[1]} {selected_options[0]} 분석은 지원되지 않는 기능입니다")
                    return

            del csv_data
            gc.collect()
            closeConsole()

            reply = QMessageBox.question(
                self.main, 'Notification', f"{os.path.basename(csv_path)} 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                openFileExplorer(os.path.join(os.path.dirname(
                    csv_path), os.path.basename(csv_path).replace('.csv', '') + '_analysis'))

        except Exception as e:
            closeConsole()
            programBugLog(self.main, traceback.format_exc())

    def run_wordcloud(self):
        try:
            selected_directory = self.analysis_getfiledirectory(
                self.file_dialog)
            if len(selected_directory) == 0:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", f"선택된 CSV 토큰 파일이 없습니다")
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format",
                                    f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", "한 개의 CSV 파일만 선택하여 주십시오")
                return
            elif 'token' not in selected_directory[0]:
                QMessageBox.warning(self.main, f"Wrong File", "토큰 파일이 아닙니다")
                return

            printStatus(self.main, "워드클라우드 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "워드클라우드 데이터를 저장할 위치를 선택하세요", self.main.localDirectory)
            if save_path == '':
                printStatus(self.main)
                return

            printStatus(self.main, "워드클라우드 옵션을 설정하세요")
            from ui.dialogs import WordcloudDialog
            dialog = WordcloudDialog(
                os.path.basename(selected_directory[0]))
            dialog.exec_()

            if dialog.data == None:
                printStatus(self.main)
                return

            startdate = dialog.data['startdate']
            enddate = dialog.data['enddate']
            date = (startdate, enddate)
            period = dialog.data['period']
            maxword = int(dialog.data['maxword'])
            except_yes_selected = dialog.data['except_yes_selected']
            eng_yes_selected = dialog.data['eng_yes_selected']

            filename = os.path.basename(selected_directory[0]).replace(
                'token_', '').replace('.csv', '')
            filename = re.sub(r'(\d{8})_(\d{8})_(\d{4})_(\d{4})',
                              f'{startdate}~{enddate}_{period}', filename)

            if except_yes_selected == True:
                QMessageBox.information(
                    self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
                printStatus(self.main, f"예외어 사전(CSV)을 선택하세요")
                exception_word_list_path = QFileDialog.getOpenFileName(
                    self.main, "예외어 사전(CSV)를 선택하세요", self.main.localDirectory, "CSV Files (*.csv);;All Files (*)")
                exception_word_list_path = exception_word_list_path[0]
                if exception_word_list_path == "":
                    return
                with open(exception_word_list_path, 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']
                df = pd.read_csv(exception_word_list_path,
                                 low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    printStatus(self.main)
                    QMessageBox.warning(
                        self.main, "Wrong Format", "예외어 사전 형식과 일치하지 않습니다")
                    return
                exception_word_list = df['word'].tolist()
            else:
                exception_word_list = []

            folder_path = os.path.join(
                save_path,
                f"wordcloud_{filename}_{datetime.now().strftime('%m%d%H%M')}"
            )

            openConsole("워드클라우드")

            userLogging(
                f'ANALYSIS -> WordCloud({os.path.basename(folder_path)})')

            printStatus(self.main, "파일 불러오는 중...")
            print("\n파일 불러오는 중...\n")
            token_data = pd.read_csv(selected_directory[0], low_memory=False)

            self.dataprocess_obj.wordcloud(
                self.main, token_data, folder_path, date, maxword, period, exception_word_list, eng=eng_yes_selected)
            printStatus(self.main)

            closeConsole()

            reply = QMessageBox.question(
                self.main, 'Notification', f"{filename} 워드클라우드 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                openFileExplorer(folder_path)

            return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def select_kemkim(self):
        from ui.dialogs import SelectKemkimDialog
        dialog = SelectKemkimDialog(
            self.run_kemkim, self.modify_kemkim, self.interpret_kemkim)
        dialog.exec_()

    def run_kemkim(self):
        try:
            selected_directory = self.analysis_getfiledirectory(
                self.file_dialog)
            if len(selected_directory) == 0:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", f"선택된 CSV 토큰 파일이 없습니다")
                return
            elif selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format",
                                    f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
                return
            elif len(selected_directory) != 1:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", "한 개의 CSV 파일만 선택하여 주십시오")
                return
            elif 'token' not in selected_directory[0]:
                QMessageBox.warning(self.main, f"Wrong File", "토큰 파일이 아닙니다")
                return

            tokenfile_name = os.path.basename(selected_directory[0])

            printStatus(self.main, "KEM KIM 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "KEM KIM 데이터를 저장할 위치를 선택하세요", self.main.localDirectory)
            if save_path == '':
                printStatus(self.main)
                return

            printStatus(self.main, "KEM KIM 옵션을 설정하세요")
            while True:
                from ui.dialogs import RunKemkimDialog
                dialog = RunKemkimDialog(tokenfile_name)
                result = dialog.exec_()
                try:
                    if result != QDialog.Accepted or dialog.data is None:
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
                        total_periods = (
                            1 / int(period[:-1])) * (int(enddate[:-4]) - int(startdate[:-4]) + 1)
                    elif period in ['6m', '3m', '1m']:
                        if startdate[:-4] == enddate[:-4]:  # 같은 연도일 경우
                            total_periods = (
                                (int(enddate[4:6]) - int(startdate[4:6])) + 1) / int(period[:-1])
                        else:  # 다른 연도일 경우
                            total_periods = (
                                12 / int(period[:-1])) * (int(enddate[:-4]) - int(startdate[:-4]) + 1)
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
                except Exception as e:
                    QMessageBox.warning(
                        self.main, "Wrong Form", f"입력 형식이 올바르지 않습니다, {e}")

            if except_yes_selected == True:
                QMessageBox.information(
                    self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
                printStatus(self.main, f"예외어 사전(CSV)을 선택하세요")
                exception_word_list_path = QFileDialog.getOpenFileName(self.main, "예외어 사전(CSV)를 선택하세요",
                                                                       self.main.localDirectory,
                                                                       "CSV Files (*.csv);;All Files (*)")
                exception_word_list_path = exception_word_list_path[0]
                if exception_word_list_path == "":
                    return
                with open(exception_word_list_path, 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']
                df = pd.read_csv(exception_word_list_path,
                                 low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    QMessageBox.warning(
                        self.main, "Wrong Format", "예외어 사전 형식과 일치하지 않습니다")
                    printStatus(self.main)
                    return
                exception_word_list = df['word'].tolist()
            else:
                exception_word_list = []
                exception_word_list_path = 'N'

            pid = str(uuid.uuid4())
            register_process(pid, "KEMKIM")
            viewer = open_viewer(pid)

            option = {
                "pid": pid,
                "tokenfile_name": tokenfile_name,
                "startdate": startdate,
                "enddate": enddate,
                "period": period,
                "topword": topword,
                "weight": weight,
                "graph_wordcnt": graph_wordcnt,
                "split_option": split_option,
                "split_custom": split_custom,
                "filter_option": filter_yes_selected,
                "trace_standard": trace_standard_selected,
                "ani_option": ani_yes_selected,
                "exception_word_list": exception_word_list,
                "exception_filename": exception_word_list_path,
            }

            download_url = MANAGER_SERVER_API + "/analysis/kemkim"

            response = requests.post(
                download_url,
                files={"token_file": open(selected_directory[0], "rb")},
                data={"option": json.dumps(option)},
                headers=api_headers,
                timeout=3600
            )

            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "message") or error_data.get("error") or "분석 실패"
                except Exception:
                    error_msg = response.text or "분석 중 알 수 없는 오류가 발생했습니다."

                QMessageBox.critical(self.main, "분석 실패",
                                     f"KEMKIM 분석 실패\n\n{error_msg}")
                printStatus(self.main)
                return

            userLogging(
                f'ANALYSIS -> KEMKIM({tokenfile_name})-({startdate},{startdate},{topword},{weight},{filter_yes_selected})')

            # 1) Content-Disposition 헤더에서 파일명 파싱
            content_disp = response.headers.get("Content-Disposition", "")

            # 2) 우선 filename="…" 시도
            m = re.search(r'filename="(?P<fname>[^"]+)"', content_disp)
            if m:
                zip_name = m.group("fname")
            else:
                # 3) 없으면 filename*=utf-8''… 로 시도
                m2 = re.search(
                    r"filename\*=utf-8''(?P<fname>[^;]+)", content_disp)
                if m2:
                    zip_name = unquote(m2.group("fname"))
                else:
                    zip_name = f"example.zip"

            # 4) 이제 다운로드 & 압축 해제
            local_zip = os.path.join(save_path, zip_name)
            total_size = int(response.headers.get("Content-Length", 0))

            close_viewer(viewer)
            openConsole('KEMKIM 분석')

            with open(local_zip, "wb") as f, tqdm(
                total=total_size,
                file=sys.stdout,
                unit="B", unit_scale=True, unit_divisor=1024,
                desc="Downloading Kemkim Data",
                ascii=True, ncols=80,
                bar_format="{desc}: |{bar}| {percentage:3.0f}% [{n_fmt}/{total_fmt} {unit}] @ {rate_fmt}",
                dynamic_ncols=True
            ) as pbar:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

            printStatus(self.main, "다운로드 완료, 압축 해제 중…")
            print("\n다운로드 완료, 압축 해제 중...\n")

            # 압축 풀 폴더 이름은 zip 파일 이름(확장자 제외)
            base_folder = os.path.splitext(zip_name)[0]
            extract_path = os.path.join(save_path, base_folder)
            os.makedirs(extract_path, exist_ok=True)

            with zipfile.ZipFile(local_zip, "r") as zf:
                zf.extractall(extract_path)

            os.remove(local_zip)
            printStatus(self.main)
            closeConsole()

            reply = QMessageBox.question(self.main, 'Notification', f"KEMKIM 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                openFileExplorer(extract_path)

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def modify_kemkim(self):
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
                QMessageBox.warning(self.main, f"Wrong Selection",
                                    f"선택된 'Result' 디렉토리가 없습니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return
            elif len(result_directory) > 1:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", f"KemKim 폴더에 있는 하나의 'Result' 디렉토리만 선택하여 주십시오")
                return
            elif 'Result' not in os.path.basename(result_directory[0]):
                QMessageBox.warning(self.main, f"Wrong Directory",
                                    f"'Result' 디렉토리가 아닙니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return

            userLogging(
                f'ANALYSIS -> rekimkem_file({result_directory[0]})')
            printStatus(self.main, "파일 불러오는 중...")

            result_directory = result_directory[0]
            final_signal_csv_path = os.path.join(
                result_directory, "Signal", "Final_signal.csv")
            if not os.path.exists(final_signal_csv_path):
                QMessageBox.information(
                    self.main, 'Import Failed', 'Final_signal.csv 파일을 불러오는데 실패했습니다\n\nResult/Signal 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                printStatus(self.main)
                return
            final_signal_df = pd.read_csv(
                final_signal_csv_path, low_memory=False)
            words = final_signal_df['word'].tolist()
            all_keyword = []
            for word_list_str in words:
                word_list = ast.literal_eval(word_list_str)
                all_keyword.append(word_list)

            printStatus(self.main, "옵션을 선택하세요")

            from ui.dialogs import ModifyKemkimDialog
            self.word_selector = ModifyKemkimDialog(all_keyword)
            if self.word_selector.exec_() == QDialog.Accepted:  # show() 대신 exec_() 사용
                selected_words = self.word_selector.selected_words
                size_input = self.word_selector.size_input
                eng_auto_option = self.word_selector.eng_auto_checked
                eng_manual_option = self.word_selector.eng_manual_checked
                eng_no_option = self.word_selector.eng_no_checked
                try:
                    size_input = tuple(map(int, size_input))
                except:
                    QMessageBox.warning(
                        self.main, "Wrong Form", "그래프 사이즈를 숫자로 입력하여 주십시오")
                    printStatus(self.main)
                    return
            else:
                printStatus(self.main)
                return

            if eng_no_option == False:
                if eng_manual_option == True:
                    QMessageBox.information(
                        self.main, "Information", f"키워드-영단어 사전(CSV)를 선택하세요")
                    printStatus(self.main, "키워드-영단어 사전(CSV)를 선택하세요")
                    eng_keyword_list_path = QFileDialog.getOpenFileName(
                        self.main, "키워드-영단어 사전(CSV)를 선택하세요", self.main.localDirectory, "CSV Files (*.csv);;All Files (*)")
                    eng_keyword_list_path = eng_keyword_list_path[0]
                    if eng_keyword_list_path == "":
                        return
                    with open(eng_keyword_list_path, 'rb') as f:
                        codec = chardet.detect(f.read())['encoding']
                    df = pd.read_csv(eng_keyword_list_path,
                                     low_memory=False, encoding=codec)
                    if 'english' not in list(df.keys()) or 'korean' not in list(df.keys()):
                        QMessageBox.warning(
                            self.main, "Wrong Form", "키워드-영단어 사전 형식과 일치하지 않습니다")
                        return
                    eng_keyword_tupleList = list(
                        zip(df['korean'], df['english']))
                elif eng_auto_option == True:
                    target_words = sum(all_keyword, [])
                    printStatus(self.main, "키워드 영문 변환 중...")

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
                    eng_keyword_tupleList = asyncio.run(
                        wordcloud_translator(target_words))
            else:
                eng_keyword_tupleList = []

            printStatus(self.main, "KEMKIM 조정 중...")
            DoV_coordinates_path = os.path.join(
                result_directory, "Graph", "DOV_coordinates.csv")
            if not os.path.exists(DoV_coordinates_path):
                QMessageBox.warning(
                    self.main, 'Import Failed', 'DOV_coordinates.csv 파일을 불러오는데 실패했습니다\n\nResult/Graph 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                printStatus(self.main)
                return
            DoV_coordinates_df = pd.read_csv(DoV_coordinates_path)
            DoV_coordinates_dict = {}
            for index, row in DoV_coordinates_df.iterrows():
                key = row['key']
                value = ast.literal_eval(row['value'])  # 문자열을 튜플로 변환
                DoV_coordinates_dict[key] = value

            DoD_coordinates_path = os.path.join(
                result_directory, "Graph", "DOD_coordinates.csv")
            if not os.path.exists(DoD_coordinates_path):
                QMessageBox.warning(
                    self.main, 'Import Failed', 'DOD_coordinates.csv 파일을 불러오는데 실패했습니다\n\nResult/Graph 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                printStatus(self.main)
                return
            DoD_coordinates_df = pd.read_csv(os.path.join(
                result_directory, "Graph", "DOD_coordinates.csv"))
            DoD_coordinates_dict = {}
            for index, row in DoD_coordinates_df.iterrows():
                key = row['key']
                value = ast.literal_eval(row['value'])  # 문자열을 튜플로 변환
                DoD_coordinates_dict[key] = value

            delete_word_list = pd.read_csv(os.path.join(
                result_directory, 'filtered_words.csv'))['word'].tolist()

            kimkem_obj = KimKem(self.main, exception_word_list=selected_words, rekemkim=True)

            new_result_folder = os.path.join(os.path.dirname(
                result_directory), f'Result_{datetime.now().strftime('%m%d%H%M')}')
            new_graph_folder = os.path.join(new_result_folder, 'Graph')
            new_signal_folder = os.path.join(new_result_folder, 'Signal')

            os.makedirs(new_result_folder, exist_ok=True)
            os.makedirs(new_graph_folder, exist_ok=True)
            os.makedirs(new_signal_folder, exist_ok=True)

            # 그래프 Statistics csv 복사
            copy_csv(os.path.join(result_directory, "Graph", "DOD_statistics.csv"),
                     os.path.join(new_graph_folder, "DOD_statistics.csv"))
            copy_csv(os.path.join(result_directory, "Graph", "DOD_statistics.csv"),
                     os.path.join(new_graph_folder, "DOD_statistics.csv"))

            DoV_signal, DoV_coordinates = kimkem_obj.DoV_draw_graph(
                graph_folder=new_graph_folder, redraw_option=True, coordinates=DoV_coordinates_dict, graph_size=size_input, eng_keyword_list=eng_keyword_tupleList)
            DoD_signal, DoD_coordinates = kimkem_obj.DoD_draw_graph(
                graph_folder=new_graph_folder, redraw_option=True, coordinates=DoD_coordinates_dict, graph_size=size_input, eng_keyword_list=eng_keyword_tupleList)

            final_signal = kimkem_obj._get_communal_signals(
                DoV_signal, DoD_signal)
            final_signal_list = []
            for value in final_signal.values():
                final_signal_list.extend(value)

            kimkem_obj.DoV_draw_graph(graph_folder=new_graph_folder, redraw_option=True, coordinates=DoV_coordinates_dict,
                                      final_signal_list=final_signal_list, graph_name='KEM_graph.png', graph_size=size_input, eng_keyword_list=eng_keyword_tupleList)
            kimkem_obj.DoD_draw_graph(graph_folder=new_graph_folder, redraw_option=True, coordinates=DoD_coordinates_dict,
                                      final_signal_list=final_signal_list, graph_name='KIM_graph.png', graph_size=size_input, eng_keyword_list=eng_keyword_tupleList)
            kimkem_obj._save_final_signals(
                DoV_signal, DoD_signal, new_signal_folder)

            delete_word_list.extend(selected_words)
            pd.DataFrame(delete_word_list, columns=['word']).to_csv(os.path.join(
                new_result_folder, 'filtered_words.csv'), index=False, encoding='utf-8-sig')

            with open(os.path.join(new_graph_folder, 'graph_size.txt'), 'w+', encoding="utf-8", errors="ignore") as graph_size:
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

            printStatus(self.main)
            QMessageBox.information(
                self.main, 'Notification', 'KEMKIM 재분석이 완료되었습니다')
            openFileExplorer(new_result_folder)

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def interpret_kemkim(self):
        try:
            result_directory = self.file_dialog.selectedFiles()
            if len(result_directory) == 0:
                QMessageBox.warning(self.main, f"Wrong Selection",
                                    f"선택된 'Result' 디렉토리가 없습니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return
            elif len(result_directory) > 1:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", f"KemKim 폴더에 있는 하나의 'Result' 디렉토리만 선택하여 주십시오")
                return
            elif 'Result' not in os.path.basename(result_directory[0]):
                QMessageBox.warning(self.main, f"Wrong Directory",
                                    f"'Result' 디렉토리가 아닙니다\n\nKemKim 폴더의 'Result'폴더를 선택해주십시오")
                return

            result_directory = result_directory[0]
            userLogging(
                f'ANALYSIS -> interpret_kimkem_file({result_directory})')

            final_signal_csv_path = os.path.join(
                result_directory, "Signal", "Final_signal.csv")

            if not os.path.exists(final_signal_csv_path):
                QMessageBox.warning(
                    self.main, 'Import Failed', 'Final_signal.csv 파일을 불러오는데 실패했습니다\n\nResult/Signal 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                printStatus(self.main)
                return

            final_signal_df = pd.read_csv(
                final_signal_csv_path, low_memory=False)
            words = final_signal_df['word'].tolist()
            all_keyword = []
            for word_list_str in words:
                word_list = ast.literal_eval(word_list_str)
                all_keyword.append(word_list)

            startdate = 0
            enddate = 0
            topic = 0

            infotxt_path = os.path.join(os.path.dirname(
                result_directory), "kemkim_info.txt")
            if not os.path.exists(final_signal_csv_path):
                QMessageBox.warning(
                    self.main, 'Import Failed', 'kemkim_info.txt 파일을 불러오는데 실패했습니다\n\nResult 디렉토리에 파일이 위치하는지 확인하여 주십시오')
                printStatus(self.main)
                return

            with open(infotxt_path, 'r', encoding='utf-8') as info_txt:
                lines = info_txt.readlines()

            for line in lines:
                if line.startswith('분석 데이터:'):
                    # '분석 데이터:' 뒤에 오는 값을 파싱
                    recommend_csv_name = line.split(
                        '분석 데이터:')[-1].strip().replace('token_', '')
                    topic = recommend_csv_name.split('_')[1]
                if line.startswith('분석 시작일:'):
                    # '분석 데이터:' 뒤에 오는 값을 파싱
                    startdate = line.split(
                        '분석 시작일:')[-1].strip().replace('token_', '')
                    startdate = int(startdate)
                if line.startswith('분석 종료일:'):
                    # '분석 데이터:' 뒤에 오는 값을 파싱
                    enddate = line.split(
                        '분석 종료일:')[-1].strip().replace('token_', '')
                    enddate = int(enddate)

            if startdate == 0 or enddate == 0 or topic == 0:
                QMessageBox.warning(
                    self.main, 'Import Failed', 'kemkim_info.txt 파일에서 정보를 불러오는데 실패했습니다\n\nResult 디렉토리 선택 유무와 수정되지 않은 info.txt 원본 파일이 올바른 위치에 있는지 확인하여 주십시오')
                printStatus(self.main)
                return

            QMessageBox.information(
                self.main, "Information", f'Keyword를 추출할 CSV 파일을 선택하세요\n\n"{recommend_csv_name}"를 선택하세요')
            object_csv_path = QFileDialog.getOpenFileName(
                self.main, "Keyword 추출 대상 CSV 파일을 선택하세요", self.main.localDirectory, "CSV Files (*.csv);;All Files (*)")
            object_csv_path = object_csv_path[0]
            object_csv_name = os.path.basename(
                object_csv_path).replace('.csv', '')
            if object_csv_path == "":
                return

            printStatus(self.main, "CSV 데이터 키워드 필터링 중...")

            from ui.dialogs import InterpretKemkimDialog
            self.word_selector = InterpretKemkimDialog(all_keyword)
            if self.word_selector.exec_() == QDialog.Accepted:  # show() 대신 exec_() 사용
                selected_words_2dim = self.word_selector.selected_words
                selected_words = [
                    word for group in selected_words_2dim for word in group]
                selected_option = self.word_selector.selected_option
            else:
                printStatus(self.main)
                return

            # 단어 선택 안했을 때
            if len(selected_words) == 0:
                QMessageBox.warning(
                    self.main, 'Wrong Selection', '선택된 필터링 단어가 없습니다')
                return

            with open(object_csv_path, 'rb') as f:
                codec = chardet.detect(f.read())['encoding']
            object_csv_df = pd.read_csv(
                object_csv_path, low_memory=False, encoding=codec)
            if all('Text' not in word for word in list(object_csv_df.keys())):
                QMessageBox.warning(self.main, "Wrong Format",
                                    "크롤링 데이터 CSV 형식과 일치하지 않습니다")
                return
            for column in object_csv_df.columns.tolist():
                if 'Text' in column:
                    textColumn_name = column
                elif 'Date' in column:
                    dateColumn_name = column

            # 날짜 범위 설정
            object_csv_df[dateColumn_name] = pd.to_datetime(
                object_csv_df[dateColumn_name], format='%Y-%m-%d', errors='coerce')
            start_date = pd.to_datetime(str(startdate), format='%Y%m%d')
            end_date = pd.to_datetime(str(enddate), format='%Y%m%d')
            # 날짜 범위 필터링
            object_csv_df = object_csv_df[object_csv_df[dateColumn_name].between(
                start_date, end_date)]

            if selected_option == "모두 포함":
                filtered_object_csv_df = object_csv_df[object_csv_df[textColumn_name].apply(
                    lambda x: all(word in str(x) for word in selected_words))]
            else:
                filtered_object_csv_df = object_csv_df[object_csv_df[textColumn_name].apply(
                    lambda x: any(word in str(x) for word in selected_words))]

            if filtered_object_csv_df.shape[0] < 1:
                QMessageBox.warning(self.main, "No Data",
                                    "필터링 키워드를 포함하는 데이터가 존재하지 않습니다")
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
            included_signals = ','.join([signals[i] for i in range(
                len(selected_words_2dim)) if selected_words_2dim[i]])

            # 파일명 생성
            analysis_directory_name = f'Analysis_({included_signals})_{datetime.now().strftime("%m%d%H%M")}'
            analyze_directory = os.path.join(os.path.dirname(
                result_directory), analysis_directory_name)

            reply = QMessageBox.question(
                self.main, 'Notification', f'CSV 키워드 필터링이 완료되었습니다\n키워드를 포함하는 데이터는 {filtered_object_csv_df.shape[0]}개입니다\n\n데이터를 저장하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                os.makedirs(analyze_directory, exist_ok=True)
                os.makedirs(os.path.join(analyze_directory,
                            'keyword_context'), exist_ok=True)
                filtered_object_csv_df.to_csv(os.path.join(
                    analyze_directory, f"{object_csv_name}(키워드 {selected_option}).csv"), index=False, encoding='utf-8-sig')
                pd.DataFrame([selected_words_dic]).to_csv(os.path.join(
                    analyze_directory, f"filtered_words.csv"), index=False, encoding='utf-8-sig')

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
                        extracted_text = extracted_text.replace(
                            keyword, highlighted_keyword)

                        return extracted_text
                    else:
                        return None  # 키워드가 없으면 None 반환

                context_dict = {}
                for keyword in selected_words:
                    extracted_texts = filtered_object_csv_df[textColumn_name].apply(
                        lambda x: extract_surrounding_text(x, keyword))
                    keyword_texts = extracted_texts.dropna().tolist()
                    add_text = "\n\n".join(keyword_texts)
                    if keyword_texts:
                        context_dict[keyword] = add_text
                    with open(os.path.join(analyze_directory, 'keyword_context', f'{keyword}_context.txt'), 'w', encoding="utf-8", errors="ignore") as context:
                        context.write(add_text)

                context_df = pd.DataFrame(list(context_dict.items()), columns=[
                                          'Keyword', 'Context Text'])
                # 데이터프레임을 CSV 파일로 저장
                context_df.to_csv(os.path.join(analyze_directory,  'keyword_context',
                                  'keyword_context.csv'), index=False, encoding='utf-8-sig')
            else:
                printStatus(self.main)
                return

            if any('Title' in word for word in list(filtered_object_csv_df.keys())):
                reply = QMessageBox.question(
                    self.main, 'Notification', f'키워드 필터링 데이터 저장이 완료되었습니다\n\nAI 분석을 진행하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    gpt_key = get_setting('GPT_Key')
                    if gpt_key == 'default' or len(gpt_key) < 20:
                        QMessageBox.information(
                            self.main, 'Notification', f'API Key가 설정되지 않았습니다\n\n환경설정에서 ChatGPT API Key를 입력해주십시오')
                        printStatus(self.main)
                        openFileExplorer(analyze_directory)
                        return

                    printStatus(self.main, "AI 분석 중...")
                    for column in filtered_object_csv_df.columns.tolist():
                        if 'Title' in column:
                            titleColumn_name = column

                    if filtered_object_csv_df[titleColumn_name].count() > 50:
                        random_titles = filtered_object_csv_df[titleColumn_name].sample(
                            n=50, random_state=42)
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
                    gpt_response = generateLLM(gpt_query)
                    if type(gpt_response) != str:
                        QMessageBox.warning(
                            self.main, "Error", f"{gpt_response[1]}")
                        printStatus(self.main)
                        openFileExplorer(analyze_directory)
                        return

                    with open(
                            os.path.join(
                                analyze_directory, f"{object_csv_name}(키워드 {selected_option})_AI_analyze.txt"),
                            'w+', encoding="utf-8", errors="ignore") as gpt_txt:
                        gpt_txt.write(gpt_response)

                    QMessageBox.information(
                        self.main, "AI 분석 결과", gpt_response)
                    printStatus(self.main)
                    openFileExplorer(analyze_directory)

                else:
                    printStatus(self.main)
                    openFileExplorer(analyze_directory)
            else:
                QMessageBox.information(
                    self.main, "Notification", f"CSV 키워드 필터링이 완료되었습니다\n키워드를 포함하는 데이터는 {filtered_object_csv_df.shape[0]}개입니다")
                openFileExplorer(analyze_directory)

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def anaylsis_buttonMatch(self):

        self.main.analysis_timesplitfile_btn.clicked.connect(
            self.run_timesplit)
        self.main.analysis_dataanalysisfile_btn.clicked.connect(
            self.run_analysis)
        self.main.analysis_mergefile_btn.clicked.connect(
            self.run_merge)
        self.main.analysis_wordcloud_btn.clicked.connect(
            self.run_wordcloud)
        self.main.analysis_kemkim_btn.clicked.connect(self.select_kemkim)

        self.main.analysis_timesplitfile_btn.setToolTip("Ctrl+D")
        self.main.analysis_dataanalysisfile_btn.setToolTip("Ctrl+A")
        self.main.analysis_mergefile_btn.setToolTip("Ctrl+M")
        self.main.analysis_kemkim_btn.setToolTip("Ctrl+K")

    def analysis_shortcut_setting(self):
        self.updateShortcut(0)
        self.main.tabWidget_data_process.currentChanged.connect(
            self.updateShortcut)

    def updateShortcut(self, index):
        resetShortcuts(self.main)

        # 파일 불러오기
        if index == 0:
            self.main.ctrld.activated.connect(self.run_timesplit)
            self.main.ctrlm.activated.connect(self.run_merge)
            self.main.ctrla.activated.connect(self.run_analysis)
            self.main.ctrlk.activated.connect(self.select_kemkim)

            self.main.cmdd.activated.connect(self.run_timesplit)
            self.main.cmdm.activated.connect(self.run_merge)
            self.main.cmda.activated.connect(self.run_analysis)
            self.main.cmdk.activated.connect(self.select_kemkim)
