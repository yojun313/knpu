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
import time
from PyQt5.QtWidgets import *
from libs.console import *
from ui.finder import *
from ui.status import *
from ui.dialogs import *
from libs.viewer import *
from core.shortcut import *
from core.setting import *
from services.api import *
from services.logging import *
from services.llm import *
from services.csv import *
from config import *

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
            if selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format",f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            reply = QMessageBox.question(self.main, 'Notification', f"선택하신 파일을 시간 분할하시겠습니까?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply != QMessageBox.Yes:
                return

            openConsole("데이터 분할")

            def split_table(csv_path):
                table_path = os.path.join(
                    os.path.dirname(csv_path),
                    f"{os.path.splitext(os.path.basename(csv_path))[0]}_split_{datetime.now():%m%d%H%M}"
                )
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

            printStatus(self.main, "데이터 분할 및 저장 중...")
            
            userLogging(f'ANALYSIS -> timesplit_file({selected_directory[0]})')
            for csv_path in selected_directory:
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
            openFileResult(self.main, f"데이터 분할이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", os.path.dirname(selected_directory[0]))
            
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

            selected_directory = self.analysis_getfiledirectory(self.file_dialog)
            if len(selected_directory) == 0:
                return
            if selected_directory[0] == False:
                QMessageBox.warning(self.main, f"Wrong Format", f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return
            if len(selected_directory) < 2:
                QMessageBox.warning(self.main, f"Wrong Selection", "2개 이상의 CSV 파일 선택이 필요합니다")
                return

            mergedfilename, ok = QInputDialog.getText(None, '파일명 입력', '병합 파일명을 입력하세요:', text='merged_file')
            if not ok or not mergedfilename:
                return
            
            userLogging(f'ANALYSIS -> merge_file({mergedfilename})')
            all_df = [readCSV(directory) for directory in selected_directory]
            all_columns = [df.columns.tolist() for df in all_df]
            same_check_result = find_different_element_index(all_columns)
            if same_check_result != None:
                QMessageBox.warning(self.main, f"Wrong Format", f"{os.path.basename(selected_directory[same_check_result])}의 CSV 형식이 다른 파일과 일치하지 않습니다")
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

            closeConsole()
            openFileResult(self.main, f"데이터 병합 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", mergedfiledir)

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def run_analysis(self):
        try:
            filepath = self.check_file()
            if not filepath:
                printStatus(self.main)
                return

            selected_options = []
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
            csv_path = filepath
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

            openFileResult(
                self.main, 
                f"{os.path.basename(csv_path)} 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", 
                os.path.join(os.path.dirname(csv_path), f"{os.path.splitext(os.path.basename(csv_path))[0]}_analysis")
            )

        except Exception as e:
            closeConsole()
            programBugLog(self.main, traceback.format_exc())

    def run_wordcloud(self):
        try:            
            filepath = self.check_file(tokenCheck=True)
            if not filepath:
                printStatus(self.main)
                return

            printStatus(self.main, "워드클라우드 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(self.main, "워드클라우드 데이터를 저장할 위치를 선택하세요", self.main.localDirectory)
            if save_path == '':
                printStatus(self.main)
                return

            printStatus(self.main, "워드클라우드 옵션을 설정하세요")
            dialog = WordcloudDialog(os.path.basename(filepath))
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

            filename = os.path.basename(filepath).replace('token_', '').replace('.csv', '')
            filename = re.sub(r'(\d{8})_(\d{8})_(\d{4})_(\d{4})',f'{startdate}~{enddate}_{period}', filename)

            exception_word_list = []
            if except_yes_selected == True:
                QMessageBox.information(self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
                printStatus(self.main, f"예외어 사전(CSV)을 선택하세요")
                exception_word_list_path = QFileDialog.getOpenFileName(self.main, "예외어 사전(CSV)를 선택하세요", self.main.localDirectory, "CSV Files (*.csv);;All Files (*)")
                exception_word_list_path = exception_word_list_path[0]
                if exception_word_list_path == "":
                    return
                
                if not os.path.exists(exception_word_list_path):
                    raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{exception_word_list_path}")
                
                with open(exception_word_list_path, 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']

                df = pd.read_csv(exception_word_list_path,
                                 low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    printStatus(self.main)
                    QMessageBox.warning(self.main, "Wrong Format", "예외어 사전 형식과 일치하지 않습니다")
                    return
                exception_word_list = df['word'].tolist()


            folder_path = os.path.join(
                save_path,
                f"wordcloud_{filename}_{datetime.now().strftime('%m%d%H%M')}"
            )

            openConsole("워드클라우드")

            userLogging(
                f'ANALYSIS -> WordCloud({os.path.basename(folder_path)})')

            printStatus(self.main, "파일 불러오는 중...")
            print("\n파일 불러오는 중...\n")
            token_data = pd.read_csv(filepath, low_memory=False)

            self.dataprocess_obj.wordcloud(
                self.main, token_data, folder_path, date, maxword, period, exception_word_list, eng=eng_yes_selected)

            closeConsole()
            openFileResult(self.main, f"{filename} 워드클라우드 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", folder_path)
            return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def select_kemkim(self):
        dialog = SelectKemkimDialog(self.run_kemkim, self.modify_kemkim, self.interpret_kemkim)
        dialog.exec_()

    def run_kemkim(self):
        try:
            filepath = self.check_file(tokenCheck=True)
            if not filepath:
                printStatus(self.main)
                return

            tokenfile_name = os.path.basename(filepath)

            printStatus(self.main, "KEM KIM 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "KEM KIM 데이터를 저장할 위치를 선택하세요", self.main.localDirectory)
            if save_path == '':
                printStatus(self.main)
                return

            printStatus(self.main, "KEM KIM 옵션을 설정하세요")
            while True:
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
                    QMessageBox.warning(self.main, "Wrong Form", f"입력 형식이 올바르지 않습니다, {e}")

            exception_word_list = []
            exception_word_list_path = 'N'
            if except_yes_selected == True:
                QMessageBox.information(self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
                printStatus(self.main, f"예외어 사전(CSV)을 선택하세요")
                exception_word_list_path = QFileDialog.getOpenFileName(self.main, "예외어 사전(CSV)를 선택하세요",
                                                                       self.main.localDirectory,
                                                                       "CSV Files (*.csv);;All Files (*)")
                exception_word_list_path = exception_word_list_path[0]
                if exception_word_list_path == "":
                    return
                if not os.path.exists(exception_word_list_path):
                    raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{exception_word_list_path}")
                    
                with open(exception_word_list_path, 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']
                
                df = pd.read_csv(exception_word_list_path, low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    QMessageBox.warning(
                        self.main, "Wrong Format", "예외어 사전 형식과 일치하지 않습니다")
                    printStatus(self.main)
                    return
                exception_word_list = df['word'].tolist()
                

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
            
            time.sleep(1)
            send_message(pid, "토큰 데이터 업로드 중...")
            
            printStatus(self.main, "KEMKIM 분석 중...")
            response = requests.post(
                download_url,
                files={"token_file": open(filepath, "rb")},
                data={"option": json.dumps(option)},
                headers=get_api_headers(),
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
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="Downloading",
                dynamic_ncols=True,
                bar_format="{desc}: |{bar}| {percentage:3.0f}% • {n_fmt}/{total_fmt} {unit} • {rate_fmt}"
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
            closeConsole()
            openFileResult(self.main, f"KEMKIM 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", extract_path)

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def modify_kemkim(self):
        def copy_csv(input_file_path, output_file_path):
            # CSV 파일 읽기
            if not os.path.exists(input_file_path):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{input_file_path}")
            
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
            if len(result_directory) > 1:
                QMessageBox.warning(
                    self.main, f"Wrong Selection", f"KemKim 폴더에 있는 하나의 'Result' 디렉토리만 선택하여 주십시오")
                return
            if 'Result' not in os.path.basename(result_directory[0]):
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
                    
                    if not os.path.exists(eng_keyword_list_path):
                        raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{eng_keyword_list_path}")
                    
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
            copy_csv(os.path.join(result_directory, "Graph", "DOV_statistics.csv"),
                     os.path.join(new_graph_folder, "DOV_statistics.csv"))
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
            openFileResult(self.main, f"KEMKIM 재분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", new_result_folder)    
            
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

            if not os.path.exists(infotxt_path):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{infotxt_path}")
            
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

            if not os.path.exists(object_csv_path):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{object_csv_path}")
            
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

    def select_tokenize(self):
        dialog = SelectTokenizeDialog(self.run_tokenize_file, self.run_modify_token, self.run_common_tokens)
        dialog.exec_()
    
    def run_tokenize_file(self):
        try:
            csv_path = self.check_file()
            if not csv_path:
                printStatus(self.main)
                return
            tokenfile_name = os.path.basename(csv_path)

            # ───────────────────────────── 2) 저장 폴더 선택
            printStatus(self.main, "토큰 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "토큰 데이터를 저장할 위치를 선택하세요", self.main.localDirectory
            )
            if save_path == '':
                printStatus(self.main)
                return

            # ───────────────────────────── 3) 열 선택 Dialog
            df_headers   = pd.read_csv(csv_path, nrows=0)
            column_names = df_headers.columns.tolist()

            dialog = TokenizeFileDialog(column_names, parent=self.main)
            if dialog.exec_() != QDialog.Accepted:
                printStatus(self.main)
                return
            selected_columns = dialog.get_selected_columns()
            if not selected_columns:
                printStatus(self.main)
                return

            # ───────────────────────────── 4) 프로세스 등록/뷰어
            pid = str(uuid.uuid4())
            register_process(pid, "Tokenizing File")
            viewer = open_viewer(pid)

            option = {
                "pid"          : pid,
                "column_names" : selected_columns,
            }

            download_url = MANAGER_SERVER_API + "/analysis/tokenize"

            # ───────────────────────────── 5) 서버 요청
            time.sleep(1)
            send_message(pid, "파일 데이터 업로드 중...")
            printStatus(self.main, "파일 토큰화 중...")

            with open(csv_path, "rb") as file_obj:
                response = requests.post(
                    download_url,
                    files={
                        "csv_file": (tokenfile_name, file_obj, "text/csv"),
                        "option"  : (None, json.dumps(option), "application/json"),
                    },
                    headers=get_api_headers(),
                    stream=True,
                    timeout=3600
                )

            # ────────── 오류 처리 ────────────────────────────────
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg  = error_data.get("message") or error_data.get("error") or "토큰화 실패"
                except Exception:
                    error_msg = response.text or "토큰화 중 알 수 없는 오류가 발생했습니다."
                QMessageBox.critical(self.main, "토큰화 실패", error_msg)
                printStatus(self.main)
                return

            csv_name   = f"token_{tokenfile_name}"
            local_csv  = os.path.join(save_path, csv_name)
            total_size = int(response.headers.get("Content-Length", 0))

            close_viewer(viewer)
            openConsole("토큰화")

            with open(local_csv, "wb") as f, tqdm(
                total=total_size,
                file=sys.stdout,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc="Downloading",
                dynamic_ncols=True,
                bar_format="{desc}: |{bar}| {percentage:3.0f}% • {n_fmt}/{total_fmt} {unit} • {rate_fmt}"
            ) as pbar:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

            printStatus(self.main)
            closeConsole()
            openFileResult(
                self.main,
                f"토큰화가 완료되었습니다.\n\n파일 탐색기에서 확인하시겠습니까?",
                os.path.dirname(local_csv)
            )

            # 로그 기록
            userLogging(f'ANALYSIS -> Tokenize({tokenfile_name}) : columns={selected_columns}')

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def run_modify_token(self):
        try:
            token_filepath = self.check_file(tokenCheck=True)
            if not token_filepath:
                printStatus(self.main)
                return

            printStatus(self.main, "조정된 토큰 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "토큰 데이터를 저장할 위치를 선택하세요", self.main.localDirectory
            )
            if save_path == '':
                printStatus(self.main)
                return

            df_headers = pd.read_csv(token_filepath, nrows=0)
            column_names = df_headers.columns.tolist()

            printStatus(self.main, "토큰 데이터가 있는 열을 선택하세요")
            dialog = TokenizeFileDialog(column_names, parent=self.main)
            if dialog.exec_() != QDialog.Accepted:
                printStatus(self.main)
                return
            selected_columns = dialog.get_selected_columns()
            if not selected_columns:
                printStatus(self.main)
                return

            window_size, ok = QInputDialog.getInt(self.main, "윈도우 크기 입력", "토큰 윈도우 크기를 입력하세요:", 1, 1)
            if not ok:
                printStatus(self.main)
                return

            use_original = False
            original_sentences = None
            reply = QMessageBox.question(
                self.main,
                "원본 파일 선택",
                "토큰화되지 않은 원본 파일을 선택하시겠습니까?\n\n원본 문장에 존재하는 합성 명사만을 추출할 수 있습니다.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                original_filepath, _ = QFileDialog.getOpenFileName(self.main, "원본 CSV 파일 선택", self.main.localDirectory, "CSV Files (*.csv)")
                if original_filepath:
                    original_df = pd.read_csv(original_filepath)
                    if len(original_df) != len(pd.read_csv(token_filepath)):
                        QMessageBox.critical(self.main, "행 수 불일치", "원본 파일과 토큰화 파일의 행 수가 일치하지 않습니다.")
                        printStatus(self.main)
                        return
                    original_sentences = list(original_df.iloc[:, 0].astype(str))
                    use_original = True

            def sliding_window_tokens(text, window_size, original_text=None):
                if not isinstance(text, str):
                    return ''

                tokens = [token.strip() for token in text.split(',')]
                if window_size <= 1:
                    candidates = tokens
                else:
                    candidates = [''.join(tokens[i:i+window_size]) for i in range(len(tokens) - window_size + 1)]

                if original_text is not None:
                    # 원본 문장에 포함된 단어만 필터링
                    candidates = [word for word in candidates if word in original_text]
                return ', '.join(candidates)

            printStatus(self.main, "토큰 파일 읽는 중...")
            token_df = readCSV(token_filepath)

            printStatus(self.main, "토큰 파일 조정 중...")
            for column in selected_columns:
                if use_original:
                    token_df[column] = [
                        sliding_window_tokens(token_df.at[i, column], window_size, original_sentences[i])
                        for i in range(len(token_df))
                    ]
                else:
                    token_df[column] = token_df[column].apply(lambda x: sliding_window_tokens(x, window_size))

            base_filename = os.path.basename(token_filepath)
            name, ext = os.path.splitext(base_filename)
            new_filename = f"{name}_window={window_size}.csv"

            printStatus(self.main, "조정된 토큰 파일 저장 중...")
            token_df.to_csv(os.path.join(save_path, new_filename), index=False, encoding='utf-8-sig')

            printStatus(self.main)
            openFileResult(self.main, f"토큰 파일 조정이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", save_path)
            return

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    
    def run_common_tokens(self):
        try:
            # ───── 1) 토큰 CSV 반복 선택 ─────────────────────────────
            token_paths = []
            while True:
                printStatus(self.main, "토큰 CSV 파일을 하나씩 선택하세요")
                fpath, _ = QFileDialog.getOpenFileName(
                    self.main,
                    "토큰 CSV 파일을 선택하세요",
                    self.main.localDirectory if not token_paths else os.path.dirname(token_paths[-1]),
                    "CSV Files (*.csv);;All Files (*)"
                )
                if fpath == "":                       # 취소 → 루프 종료
                    break

                if 'token' not in fpath:
                    QMessageBox.warning(self.main, "Wrong File",
                                        f"토큰 CSV 가 아닙니다:\n{os.path.basename(fpath)}")
                    continue

                token_paths.append(fpath)

                # 추가 선택 여부 확인
                reply = QMessageBox.question(
                    self.main,
                    "추가 선택",
                    "파일이 추가되었습니다.\n\n다른 토큰 CSV를 더 선택하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply != QMessageBox.Yes:
                    break

            # 선택된 파일이 2개 미만이면 중단
            if len(token_paths) < 2:
                QMessageBox.information(self.main, "No Enough File",
                                        "두 개 이상의 토큰 CSV를 선택하셔야 합니다.")
                printStatus(self.main)
                return

            # 2) 기간(주기) 선택 ----------------------------------------------------
            period_options = ['1일', '1주일', '1달', '3달', '6달', '1년']
            period_choice, ok = QInputDialog.getItem(
                self.main, "기간 선택", "토큰을 묶을 기간을 선택하세요:",
                period_options, 0, False
            )
            if not ok:
                printStatus(self.main)
                return

            # 3) 결과 저장 폴더 선택 -------------------------------------------------
            printStatus(self.main, "결과를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "결과를 저장할 위치를 선택하세요", self.main.localDirectory
            )
            if save_path == '':
                printStatus(self.main)
                return
            
            file_name, ok = QInputDialog.getText(
                self.main,
                "파일명 입력",
                "저장할 CSV 파일명을 입력하세요:",
                text=f"common_tokens_{period_choice}"
            )
            if not ok or not file_name.strip():
                printStatus(self.main)          # 취소 / 빈 입력 → 종료
                return
            file_name = file_name.strip()
            if not file_name.lower().endswith(".csv"):
                file_name += ".csv"

            # 4) 토큰 열 선택(모든 파일에 동일한 열이라고 가정) -------------------------
            df_headers = pd.read_csv(token_paths[0], nrows=0)
            column_names = df_headers.columns.tolist()
            dialog = TokenizeFileDialog(column_names, parent=self.main)
            if dialog.exec_() != QDialog.Accepted:
                printStatus(self.main)
                return
            token_columns = dialog.get_selected_columns()
            if not token_columns:
                printStatus(self.main, "❗ 토큰 열을 하나 이상 선택해 주세요.")
                return
            
            missing_info = []  # (파일명, 빠진 열) 리스트
            for p in token_paths:
                cols = pd.read_csv(p, nrows=0).columns
                for tc in token_columns:
                    if tc not in cols:
                        missing_info.append((os.path.basename(p), tc))

            if missing_info:
                # 파일별 누락 열 목록을 문자열로 정리
                msg_lines = [f"{fname}  →  '{col}' 열 없음" for fname, col in missing_info]
                QMessageBox.warning(
                    self.main,
                    "Wrong Format",
                    "다음 파일에 선택한 토큰 열이 없습니다:\n\n" + "\n".join(msg_lines)
                )
                printStatus(self.main)
                return

            # 5) 기간 키 생성 helper -------------------------------------------------
            def period_key(series, choice):
                """
                choice : '1일'|'1주일'|'1달'|'3달'|'6달'|'1년'
                return  : Series[str]  (기간별 key)
                """
                if choice == '1일':
                    return series.dt.strftime('%Y-%m-%d')
                if choice == '1주일':      # ISO 주(월~일) 기준
                    return series.dt.to_period('W').astype(str)
                if choice == '1달':
                    return series.dt.to_period('M').astype(str)
                if choice == '3달':        # 분기
                    return series.dt.to_period('Q').astype(str)
                if choice == '6달':        # 반기
                    # to_period('2Q')는 pandas>=2.2 필요. fallback 수동 계산
                    return (series.dt.year.astype(str) + '-' +
                            ((series.dt.month.sub(1)//6)+1).astype(str) + 'H')
                if choice == '1년':
                    return series.dt.to_period('A').astype(str)

            # 6) 개별 파일 → {period: set(tokens)} dict 로 변환 ------------------------
            def extract_token_set(cell):
                if pd.isna(cell):
                    return []
                return [tok.strip() for tok in str(cell).split(',') if tok.strip()]

            file_period_dicts = []  # 각 파일별 {period: set(...)} 저장
            for path in token_paths:
                df = readCSV(path)
                # 날짜 컬럼 찾기
                date_col = next((c for c in df.columns if 'Date' in c), None)
                if date_col is None:
                    QMessageBox.warning(self.main, "Wrong Format",
                                        f"'Date' 컬럼이 없습니다: {os.path.basename(path)}")
                    return
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df = df.dropna(subset=[date_col])

                df['period_key'] = period_key(df[date_col], period_choice)

                period_group = {}
                for p_key, g in df.groupby('period_key'):
                    tok_set = set()
                    for col in token_columns:
                        tok_lists = g[col].dropna().apply(extract_token_set)
                        for lst in tok_lists:
                            tok_set.update(lst)
                    period_group[p_key] = tok_set
                file_period_dicts.append(period_group)

            # 7) 교집합 계산 ---------------------------------------------------------
            #   (모든 파일에 존재하는 기간만, 그리고 토큰 교집합도 존재해야)
            common_periods = set.intersection(*[set(d.keys()) for d in file_period_dicts])
            results = []
            for per in sorted(common_periods):
                common_tok = set.intersection(*[d[per] for d in file_period_dicts])
                if common_tok:  # 교집합 비어있을 때 제외
                    results.append({
                        'Period': per,
                        'Common Tokens': ', '.join(sorted(common_tok))
                    })

            if not results:
                QMessageBox.information(self.main, "No Intersection",
                                        "선택한 기간·파일 조합에서 교집합 토큰이 없습니다.")
                printStatus(self.main)
                return

            # 8) CSV 저장 ------------------------------------------------------------
            out_df = pd.DataFrame(results)
            out_file = os.path.join(save_path, file_name)
            out_df.to_csv(out_file, index=False, encoding='utf-8-sig')

            printStatus(self.main)
            openFileResult(
                self.main,
                f"교집합 토큰 추출이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                save_path
            )

        except Exception as e:
            programBugLog(self.main, traceback.format_exc())

    def check_file(self, tokenCheck=False):
        selected_directory = self.analysis_getfiledirectory(
                self.file_dialog)
        if len(selected_directory) == 0:
            QMessageBox.warning(
                self.main, f"Wrong Selection", f"선택된 CSV 토큰 파일이 없습니다")
            return 0
        if selected_directory[0] == False:
            QMessageBox.warning(self.main, f"Wrong Format",
                                f"{selected_directory[1]}는 CSV 파일이 아닙니다.")
            return 0
        if len(selected_directory) != 1:
            QMessageBox.warning(
                self.main, f"Wrong Selection", "한 개의 CSV 파일만 선택하여 주십시오")
            return 0
        if tokenCheck == True and 'token' not in selected_directory[0]:
            QMessageBox.warning(self.main, f"Wrong File", "토큰 파일이 아닙니다")
            return 0
        return selected_directory[0]
    
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
        self.main.analysis_tokenization_btn.clicked.connect(self.select_tokenize)

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
