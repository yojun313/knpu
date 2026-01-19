import os
import gc
import re
import ast
import csv
import platform
import warnings
import traceback
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import chardet
from libs.analysis import DataProcess
from libs.kemkim import KimKem
import uuid
import asyncio
from googletrans import Translator
import mimetypes
from contextlib import ExitStack
import json
import requests
import itertools
from PySide6.QtWidgets import QMessageBox, QFileDialog, QInputDialog, QDialog
from libs.console import *
from libs.path import *
from ui.finder import *
from ui.status import *
from ui.dialogs import *
from libs.viewer import *
from core.shortcut import *
from core.setting import *
from core.thread import *
from services.api import *
from services.logging import *
from services.llm import *
from services.csv import *
from config import *
from PySide6.QtCore import QThread, Signal
from .page_worker import Manager_Worker

warnings.filterwarnings("ignore")

# 운영체제에 따라 한글 폰트를 설정
if platform.system() == 'Darwin':  # macOS
    plt.rcParams['font.family'] = 'AppleGothic'
elif platform.system() == 'Windows':  # Windows
    plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕 폰트 사용

# 폰트 설정 후 음수 기호가 깨지는 것을 방지
plt.rcParams['axes.unicode_minus'] = False

class Manager_Analysis(Manager_Worker):
    def __init__(self, main_window):
        self.main = main_window
        self.dataprocess_obj = DataProcess(self.main)
        self.analysis_makeFileFinder()
        self.anaylsis_buttonMatch()
        self.console_open = False
    
    def analysis_makeFileFinder(self):
        self.file_dialog = makeFileFinder(self.main, self.main.localDirectory)
        self.main.analysis_filefinder_layout.addWidget(self.file_dialog)

    def analysis_getfiledirectory_csv(self, file_dialog):
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
    
    def analysis_getfiledirectory_audio(self, file_dialog):
        selected_directory = file_dialog.selectedFiles()
        
        if selected_directory == []:
            return selected_directory
        
        allowed_ext = ('.wav', '.mp3', '.m4a', '.flac', '.ogg')
        
        for directory in selected_directory:
            if not directory.lower().endswith(allowed_ext):
                return [False, directory]

        for index, directory in enumerate(selected_directory):
            if index != 0:
                selected_directory[index] = os.path.join(
                    os.path.dirname(selected_directory[0]),
                    directory
                )

        return selected_directory

    def run_timesplit(self):
        class TimeSplitWorker(QThread):
            finished = Signal(bool, str, str)  # (성공 여부, 메시지, 결과 경로)
            error = Signal(str)
            message = Signal(str)             # 진행 상황 메시지 시그널

            def __init__(self, file_list, dataprocess_obj, parent=None):
                super().__init__(parent)
                self.file_list = file_list
                self.dataprocess_obj = dataprocess_obj

            def run(self):
                try:
                    for csv_path in self.file_list:
                        filename = os.path.basename(csv_path)
                        self.message.emit(f"[{filename}] 출력 폴더 생성 중...")
                        table_path = os.path.join(
                            os.path.dirname(csv_path),
                            f"{os.path.splitext(filename)[0]}_split_{datetime.now():%m%d%H%M}"
                        )

                        base_table_path = table_path
                        for i in itertools.count():
                            candidate = base_table_path if i == 0 else f"{base_table_path}_{i}"
                            try:
                                os.makedirs(candidate, exist_ok=False)
                                table_path = candidate
                                break
                            except FileExistsError:
                                continue
                        
                        self.message.emit(f"[{filename}] CSV 파일 읽는 중...")
                        table_df = readCSV(csv_path)

                        # 시간 컬럼 존재 여부 체크
                        if not any('Date' in col for col in table_df.columns.tolist()) or table_df.columns.tolist() == []:
                            self.finished.emit(False, f"{filename}은(는) 시계열 분할이 불가능한 파일입니다.", "")
                            return

                        self.message.emit(f"[{filename}] 시계열 분할 중...")
                        table_df = self.dataprocess_obj.TimeSplitter(table_df)

                        year_group = table_df.groupby('year')
                        month_group = table_df.groupby('year_month')
                        week_group = table_df.groupby('week')

                        self.message.emit(f"[{filename}] 연 단위 저장 중...")
                        self.dataprocess_obj.TimeSplitToCSV(1, year_group, table_path, os.path.splitext(filename)[0])

                        self.message.emit(f"[{filename}] 월 단위 저장 중...")
                        self.dataprocess_obj.TimeSplitToCSV(2, month_group, table_path, os.path.splitext(filename)[0])

                        self.message.emit(f"[{filename}] 주 단위 저장 중...")
                        self.dataprocess_obj.TimeSplitToCSV(3, week_group, table_path, os.path.splitext(filename)[0])

                        del year_group
                        del month_group
                        del week_group
                        gc.collect()

                    self.finished.emit(True, f"{os.path.basename(self.file_list[0])} 데이터 분할이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", table_path)

                except Exception:
                    self.error.emit(traceback.format_exc())

        try:
            # 1. 파일 선택
            selected_directory = self.analysis_getfiledirectory_csv(self.file_dialog)
            if len(selected_directory) == 0:
                return
            if selected_directory[0] == False:
                QMessageBox.warning(self.main, "Wrong Format", f"{selected_directory[1]}는 CSV 파일이 아닙니다")
                return

            # 2. 사용자 확인
            reply = QMessageBox.question(
                self.main,
                'Notification',
                f"선택하신 파일을 연/월/주 단위로 분할하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            # 3. 로그 기록
            userLogging(f'ANALYSIS -> timesplit_file({selected_directory[0]})')

            thread_name = f"시계열 분할: {os.path.basename(selected_directory[0])}"
            register_thread(thread_name)
            printStatus(self.main)
            
            statusDialog = TaskStatusDialog(thread_name, self.main)
            statusDialog.show()

            worker = TimeSplitWorker(selected_directory, self.dataprocess_obj, self.main)
            self.connectWorkerForStatusDialog(worker, statusDialog, thread_name)
            worker.start()

            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def run_merge(self):
        class MergeWorker(QThread):
            finished = Signal(bool, str, str)
            error = Signal(str)
            message = Signal(str)

            def __init__(self, selected_directory, mergedfilename, save_dir, parent=None):
                super().__init__(parent)
                self.selected_directory = selected_directory
                self.mergedfilename = mergedfilename
                self.save_dir = save_dir

            def run(self):
                try:
                    self.message.emit("CSV 파일 읽는 중...")
                    all_df = [readCSV(directory) for directory in self.selected_directory]

                    self.message.emit("파일 형식을 검사 중...")
                    all_columns = [df.columns.tolist() for df in all_df]

                    def find_different_element_index(lst):
                        if not lst: return None
                        if lst.count(lst[0]) == 1: return 0
                        for i in range(1, len(lst)):
                            if lst[i] != lst[0]:
                                return i
                        return None

                    same_check_result = find_different_element_index(all_columns)
                    if same_check_result is not None:
                        self.finished.emit(False, f"{os.path.basename(self.selected_directory[same_check_result])}의 CSV 형식이 다릅니다.", "")
                        return

                    self.message.emit("CSV 파일을 병합 중...")
                    merged_df = pd.DataFrame()
                    for df in all_df:
                        merged_df = pd.concat([merged_df, df], ignore_index=True)

                    self.message.emit("결과 파일 저장 중...")
                    output_path = os.path.join(self.save_dir, self.mergedfilename + ".csv")
                    merged_df.to_csv(output_path, index=False, encoding="utf-8-sig")

                    self.finished.emit(
                        True,
                        f"{os.path.basename(output_path)} 데이터 병합이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                        self.save_dir
                    )

                except Exception:
                    self.error.emit(traceback.format_exc())

        try:
            dialog = MergeOptionDialog(self.main, base_dir=self.main.localDirectory)
            if dialog.exec() != QDialog.Accepted:
                return

            data = dialog.data
            selected_directory = data["selected_directory"]
            mergedfilename = data["mergedfilename"]
            save_dir = data["save_dir"]

            userLogging(f'ANALYSIS -> merge_file({mergedfilename})')

            thread_name = f"데이터 병합: {mergedfilename}"
            register_thread(thread_name)
            printStatus(self.main)

            statusDialog = TaskStatusDialog(thread_name, self.main)
            statusDialog.show()

            worker = MergeWorker(selected_directory, mergedfilename, save_dir, self.main)
            self.connectWorkerForStatusDialog(worker, statusDialog, thread_name)
            worker.start()

            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def run_analysis(self):
        class RunAnalysisWorker(QThread):
            finished = Signal(bool, str, str)   # (성공 여부, 메시지, 파일경로)
            error = Signal(str)
            message = Signal(str)              # 메시지 업데이트용 시그널

            def __init__(self, csv_path, selected_options, dataprocess_obj, hate_mode, parent=None):
                super().__init__(parent)
                self.csv_path = csv_path
                self.selected_options = selected_options
                self.dataprocess_obj = dataprocess_obj
                self.hate_mode = hate_mode

            def run(self):
                try:
                    csv_filename = os.path.basename(self.csv_path)
                    self.message.emit("CSV 파일을 불러오는 중...")
                    csv_data = pd.read_csv(self.csv_path, low_memory=False)

                    self.message.emit("분석 작업 실행 중...")
                    opt = self.selected_options
                    match opt:
                        case ['article 분석', 'Naver News']:
                            result = self.dataprocess_obj.NaverNewsArticleAnalysis(csv_data, self.csv_path)
                        case ['statistics 분석', 'Naver News']:
                            result = self.dataprocess_obj.NaverNewsStatisticsAnalysis(csv_data, self.csv_path)
                        case ['reply 분석', 'Naver News']:
                            result = self.dataprocess_obj.NaverNewsReplyAnalysis(csv_data, self.csv_path)
                        case ['rereply 분석', 'Naver News']:
                            result = self.dataprocess_obj.NaverNewsRereplyAnalysis(csv_data, self.csv_path)
                        case ['article 분석', 'Naver Cafe']:
                            result = self.dataprocess_obj.NaverCafeArticleAnalysis(csv_data, self.csv_path)
                        case ['reply 분석', 'Naver Cafe']:
                            result = self.dataprocess_obj.NaverCafeReplyAnalysis(csv_data, self.csv_path)
                        case ['article 분석', 'Google YouTube']:
                            result = self.dataprocess_obj.YouTubeArticleAnalysis(csv_data, self.csv_path)
                        case ['reply 분석', 'Google YouTube']:
                            result = self.dataprocess_obj.YouTubeReplyAnalysis(csv_data, self.csv_path)
                        case ['rereply 분석', 'Google YouTube']:
                            result = self.dataprocess_obj.YouTubeRereplyAnalysis(csv_data, self.csv_path)
                        case [o, _] if o.lower().startswith("hate") or "혐오" in o:
                            result = self.dataprocess_obj.HateAnalysis(csv_data, self.csv_path)
                        case _:
                            self.finished.emit(False, "지원되지 않는 옵션입니다.", "")
                            return

                    del csv_data
                    gc.collect()

                    self.message.emit("결과 파일 저장 경로 생성 중...")
                    if result:
                        output_dir = os.path.join(
                            os.path.dirname(self.csv_path),
                            f"{os.path.splitext(csv_filename)[0]}_analysis" if not self.hate_mode
                            else f"{os.path.splitext(csv_filename)[0]}_hate_analysis"
                        )
                        self.finished.emit(True, f"{csv_filename} 통계 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", output_dir)
                    else:
                        self.finished.emit(False, "분석 실패", "")

                except Exception:
                    self.error.emit(traceback.format_exc())

        try:
            # 1) 파일 선택
            filepath = self.check_csv_file()
            if not filepath:
                printStatus(self.main)
                return

            filename = os.path.basename(filepath)
            if 'token' in filename:
                QMessageBox.warning(self.main, "Warning", "토큰 파일은 통계 분석할 수 없습니다.")
                return

            # 2) 옵션 선택 Dialog
            dialog = StatAnalysisDialog(filename=filename)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                printStatus(self.main)
                return

            selected_options = [cb.text() for cb in dialog.checkbox_group if cb.isChecked()]
            selected_options.append(dialog.combobox.currentText())
            if len(selected_options) < 2:
                QMessageBox.warning(self.main, "Error", "선택 옵션이 부족합니다.")
                return

            hate_mode = selected_options[0].lower().startswith("hate") or "혐오" in selected_options[0]

            userLogging(f'ANALYSIS -> analysis_file({filepath})')

            statusDialog = TaskStatusDialog(f"통계 분석: {filename}", self.main)
            statusDialog.show()
            statusDialog.update_message("작업을 준비 중입니다...")

            thread_name = f"통계 분석: {filename}"
            register_thread(thread_name)
            printStatus(self.main)

            worker = RunAnalysisWorker(filepath, selected_options, self.dataprocess_obj, hate_mode, self.main)
            self.connectWorkerForStatusDialog(worker, statusDialog, thread_name)
            worker.start()

            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

        except Exception:
            programBugLog(self.main, traceback.format_exc())
       
    def run_wordcloud(self):
        class WordcloudWorker(QThread):
            finished = Signal(bool, str, str)  # (성공 여부, 메시지, 결과 경로)
            error = Signal(str)
            message = Signal(str)

            def __init__(self, filepath, save_path, date, period, maxword,
                        exception_word_list, eng_yes_selected, filename, dataprocess_obj, parent=None):
                super().__init__(parent)
                self.filepath = filepath
                self.save_path = save_path
                self.date = date
                self.period = period
                self.maxword = maxword
                self.exception_word_list = exception_word_list
                self.eng_yes_selected = eng_yes_selected
                self.filename = filename
                self.dataprocess_obj = dataprocess_obj

            def run(self):
                try:
                    self.message.emit("토큰 데이터를 불러오는 중...")
                    token_data = pd.read_csv(self.filepath, low_memory=False)

                    folder_path = os.path.join(
                        self.save_path,
                        f"wordcloud_{self.filename}_{datetime.now().strftime('%m%d%H%M')}"
                    )

                    self.message.emit("워드클라우드 분석 중...")
                    self.dataprocess_obj.wordcloud(
                        self,
                        token_data,
                        folder_path,
                        self.date,
                        self.maxword,
                        self.period,
                        self.exception_word_list,
                        eng=self.eng_yes_selected
                    )

                    self.finished.emit(True, f"{self.filename} 워드클라우드 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", folder_path)

                except Exception:
                    self.error.emit(traceback.format_exc())

        try:
            # 1. 파일 선택
            filepath = self.check_csv_file(tokenCheck=True)
            if not filepath:
                printStatus(self.main)
                return

            # 2. 저장 경로 설정
            printStatus(self.main, "워드클라우드 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "워드클라우드 데이터를 저장할 위치를 선택하세요", self.main.localDirectory)
            if save_path == '':
                printStatus(self.main)
                return

            # 3. 옵션 설정
            printStatus(self.main, "워드클라우드 옵션을 설정하세요")
            dialog = WordcloudDialog(os.path.basename(filepath))
            dialog.exec()
            if dialog.data is None:
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
            filename = re.sub(r'(\d{8})_(\d{8})_(\d{4})_(\d{4})',
                            f'{startdate}~{enddate}_{period}', filename)

            # 4. 예외어 처리
            exception_word_list = []
            if except_yes_selected:
                QMessageBox.information(self.main, "Information", f"예외어 사전(CSV)을 선택하세요")
                printStatus(self.main, f"예외어 사전(CSV)을 선택하세요")
                exception_word_list_path = QFileDialog.getOpenFileName(
                    self.main, "예외어 사전(CSV)를 선택하세요",
                    self.main.localDirectory, "CSV Files (*.csv);;All Files (*)")[0]
                if exception_word_list_path == "":
                    return

                if not os.path.exists(exception_word_list_path):
                    raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{exception_word_list_path}")

                with open(safe_path(exception_word_list_path), 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']

                df = pd.read_csv(exception_word_list_path, low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    printStatus(self.main)
                    QMessageBox.warning(self.main, "Wrong Format", "예외어 사전 형식과 일치하지 않습니다")
                    return
                exception_word_list = df['word'].tolist()

            userLogging(f'ANALYSIS -> WordCloud({filename})')
            
            thread_name = f"워드클라우드: {filename}"
            statusDialog = TaskStatusDialog(thread_name, self.main)
            statusDialog.show()

            register_thread(thread_name)
            printStatus(self.main)

            # 7. 워커 실행
            worker = WordcloudWorker(
                filepath,
                save_path,
                date,
                period,
                maxword,
                exception_word_list,
                eng_yes_selected,
                filename,
                self.dataprocess_obj,
                self.main
            )
            self.connectWorkerForStatusDialog(worker, statusDialog, thread_name)
            worker.start()

            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def select_kemkim(self):
        dialog = SelectKemkimDialog(
            self.run_kemkim, self.modify_kemkim, self.interpret_kemkim)
        dialog.exec()

    def run_kemkim(self):
        class KemkimWorker(BaseWorker):
            def __init__(self, pid, filepath, option, save_path, tokenfile_name, parent=None):
                super().__init__(parent)
                self.pid = pid
                self.filepath = filepath
                self.option = option
                self.save_path = save_path
                self.tokenfile_name = tokenfile_name

            def run(self):
                try:
                    upload_url = MANAGER_SERVER_API + "/analysis/kemkim"
                    response = self.upload_file(
                        self.filepath,
                        upload_url,
                        extra_fields={"option": json.dumps(self.option)},
                        label="토큰 데이터 업로드 중"
                    )
                    extract_path = self.download_file(response, self.save_path, label="결과 다운로드 중", extract=True)
                    self.finished.emit(True, f"{self.tokenfile_name} KEMKIM 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", extract_path)

                except Exception:
                    self.error.emit(traceback.format_exc())
                    
        try:
            filepath = self.check_csv_file(tokenCheck=True)
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
                result = dialog.exec()
                try:
                    if result != QDialog.DialogCode.Accepted or dialog.data is None:
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
                    
                    try:
                        start_dt = pd.to_datetime(str(startdate), format='%Y%m%d', errors='coerce')
                        end_dt   = pd.to_datetime(str(enddate),   format='%Y%m%d', errors='coerce')
                    except Exception:
                        start_dt = end_dt = pd.NaT

                    if pd.isna(start_dt) or pd.isna(end_dt):
                        QMessageBox.warning(self.main, "Wrong Form",
                                            "시작일/종료일 형식이 올바르지 않습니다.\nYYYYMMDD 형식으로 입력하세요.")
                        continue

                    if end_dt < start_dt:
                        QMessageBox.warning(self.main, "Wrong Form",
                                            "종료일이 시작일보다 앞설 수 없습니다.")
                        continue

                    startdate = start_dt.strftime('%Y%m%d')
                    enddate   = end_dt.strftime('%Y%m%d')
                    
                    # Calculate total periods based on the input period
                    def months_between_inclusive(s: datetime, e: datetime) -> int:
                        # s와 e가 같은 달이면 1, 그 이상이면 월 차이 + 1 (양끝 달 포함)
                        return (e.year - s.year) * 12 + (e.month - s.month) + 1

                    if period == '1y':
                        # 연도 포함 개수(양끝 포함)
                        years = (end_dt.year - start_dt.year) + 1
                        total_periods = years / int(period[:-1])  # period[:-1] == '1'
                    elif period in ['6m', '3m', '1m']:
                        months = months_between_inclusive(start_dt, end_dt)
                        step = int(period[:-1])  # 6, 3, 1
                        total_periods = months / step
                    elif period == '1w':
                        if start_dt.strftime('%A') != 'Monday':
                            QMessageBox.warning(self.main, "Wrong Form",
                                                "분석 시작일이 월요일이 아닙니다\n\n1주 단위 분석에서는 시작일=월요일, 종료일=일요일")
                            continue
                        if end_dt.strftime('%A') != 'Sunday':
                            QMessageBox.warning(self.main, "Wrong Form",
                                                "분석 종료일이 일요일이 아닙니다\n\n1주 단위 분석에서는 시작일=월요일, 종료일=일요일")
                            continue
                        total_days = (end_dt - start_dt).days + 1  # ← 양끝 포함
                        total_periods = total_days // 7
                    else:
                        # 일 단위 가정
                        total_days = (end_dt - start_dt).days
                        total_periods = total_days

                    # Check if the total periods exceed the limit when multiplied by the weight
                    if total_periods * weight >= 1:
                        QMessageBox.warning(self.main, "Wrong Form",
                                            "분석 가능 기간 개수를 초과합니다\n시간가중치를 줄이거나, Period 값을 늘리거나 시작일~종료일 사이의 간격을 줄이십시오")
                        continue

                    if split_option in ['평균(Mean)', '중앙값(Median)'] and (split_custom is None or str(split_custom).strip() == ''):
                        pass
                    else:
                        split_custom = float(split_custom)
                    break
                except Exception as e:
                    QMessageBox.warning(
                        self.main, "Wrong Form", f"입력 형식이 올바르지 않습니다, {e}")

            exception_word_list = []
            exception_word_list_path = 'N'
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
                if not os.path.exists(exception_word_list_path):
                    raise FileNotFoundError(
                        f"파일을 찾을 수 없습니다\n\n{exception_word_list_path}")

                with open(safe_path(exception_word_list_path), 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']

                df = pd.read_csv(exception_word_list_path,
                                 low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    QMessageBox.warning(
                        self.main, "Wrong Format", "예외어 사전 형식과 일치하지 않습니다")
                    printStatus(self.main)
                    return
                exception_word_list = df['word'].tolist()

            pid = str(uuid.uuid4())
            register_process(pid, "KEMKIM")

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

            downloadDialog = DownloadDialog(f"KEMKIM 분석: {tokenfile_name}", pid, self.main)
            downloadDialog.show()

            # thread_name 설정 및 등록
            thread_name = f"KEMKIM 분석: {tokenfile_name}"
            register_thread(thread_name)
            printStatus(self.main)

            worker = KemkimWorker(pid, filepath, option, save_path, tokenfile_name, self.main)
            self.connectWorkerForDownloadDialog(worker, downloadDialog, thread_name)
            worker.start()

            # GC 방지용 리스트에 저장
            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

        except Exception:
            programBugLog(self.main, traceback.format_exc())
    
    def modify_kemkim(self):
        def copy_csv(input_file_path, output_file_path):
            # CSV 파일 읽기
            if not os.path.exists(input_file_path):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{input_file_path}")

            with open(safe_path(input_file_path), 'r') as csvfile:
                reader = csv.reader(csvfile)

                # 모든 데이터를 읽어옵니다 (헤더 포함)
                rows = list(reader)

            # 읽은 데이터를 그대로 새로운 CSV 파일로 저장하기
            with open(safe_path(output_file_path), 'w', newline='') as csvfile:
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

            userLogging(f'ANALYSIS -> rekimkem_file({result_directory[0]})')
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
            if self.word_selector.exec() == QDialog.DialogCode.Accepted:
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
                        raise FileNotFoundError(
                            f"파일을 찾을 수 없습니다\n\n{eng_keyword_list_path}")

                    with open(safe_path(eng_keyword_list_path), 'rb') as f:
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
                                result = await translator.translate(word, dest='en', src='auto')  # await 추가
                                return word, result.text  # 원래 단어와 번역된 단어 튜플 반환

                            # 번역 실행 (병렬 처리)
                            translated_results = await asyncio.gather(
                                *(translate_word(word) for word in words_to_translate))

                            # 번역 결과를 캐시에 저장
                            for original, translated in translated_results:
                                translate_history[original] = translated

                        # (원래 단어, 번역된 단어) 튜플 리스트로 변환
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

            kimkem_obj = KimKem(
                self.main, exception_word_list=selected_words, rekemkim=True)

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

            with open(safe_path(os.path.join(new_graph_folder, 'graph_size.txt')), 'w+', encoding="utf-8", errors="ignore") as graph_size:
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
            openFileResult(
                self.main, f"KEMKIM 재분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", new_result_folder)

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
            userLogging(f'ANALYSIS -> interpret_kimkem_file({result_directory})')

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

            with open(safe_path(infotxt_path), 'r', encoding='utf-8') as info_txt:
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
            if self.word_selector.exec() == QDialog.DialogCode.Accepted:
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

            with open(safe_path(object_csv_path), 'rb') as f:
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
                self.main, 'Notification', f'CSV 키워드 필터링이 완료되었습니다\n키워드를 포함하는 데이터는 {filtered_object_csv_df.shape[0]}개입니다\n\n데이터를 저장하시겠습니까?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
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
                    with open(safe_path(os.path.join(analyze_directory, 'keyword_context', f'{keyword}_context.txt')), 'w', encoding="utf-8", errors="ignore") as context:
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
                    self.main, 'Notification', f'키워드 필터링 데이터 저장이 완료되었습니다\n\nAI 분석을 진행하시겠습니까?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    gpt_key = get_setting('GPT_Key')
                    if get_setting('LLM_model') == 'ChatGPT' and (gpt_key == 'default' or len(gpt_key) < 20):
                        QMessageBox.information(
                            self.main, 'Notification', f'OpenAI API Key가 설정되지 않았습니다\n\n환경설정에서 OpenAI API Key를 입력해주십시오')
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
                    gpt_response = generateLLM(gpt_query, get_setting('LLM_model'))
                    if type(gpt_response) != str:
                        QMessageBox.warning(
                            self.main, "Error", f"{gpt_response[1]}")
                        printStatus(self.main)
                        openFileExplorer(analyze_directory)
                        return

                    with open(safe_path(
                            os.path.join(
                                analyze_directory, f"{object_csv_name}(키워드 {selected_option})_AI_analyze.txt")),
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
        dialog = SelectTokenizeDialog(
            self.run_tokenize_file, self.run_modify_token, self.run_common_tokens)
        dialog.exec()

    def run_tokenize_file(self):
        class TokenizeWorker(BaseWorker):
            def __init__(self, pid, csv_path, save_path, tokenfile_name, selected_columns, include_word_list, parent=None):
                super().__init__(parent)
                self.csv_path = csv_path
                self.save_path = save_path
                self.tokenfile_name = tokenfile_name
                self.selected_columns = selected_columns
                self.include_word_list = include_word_list
                self.pid = pid

            def run(self):
                try:
                    option = {
                        "pid": self.pid,
                        "column_names": self.selected_columns,
                        "include_words": self.include_word_list,
                    }
                    upload_url = MANAGER_SERVER_API + "/analysis/tokenize"
                    response = self.upload_file(
                        self.csv_path,
                        upload_url,
                        extra_fields={"option": json.dumps(option)},
                        label="CSV 업로드 중"
                    )

                    local_csv = self.download_file(response, self.save_path, f"token_{self.tokenfile_name}", label="결과 다운로드 중")
                    self.finished.emit(True, f"{self.tokenfile_name} 토큰화가 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", os.path.dirname(local_csv))

                except Exception:
                    self.error.emit(traceback.format_exc())

        try:
            # ───────────────────────────── 1) 파일 선택
            csv_path = self.check_csv_file()
            if not csv_path:
                printStatus(self.main)
                return

            tokenfile_name = os.path.basename(csv_path)
            if "token" in tokenfile_name:
                QMessageBox.warning(
                    self.main, "Wrong File", "이미 토큰화된 파일입니다.\n다른 CSV 파일을 선택해주세요.")
                printStatus(self.main)
                return

            # ───────────────────────────── 2) 저장 경로 선택
            printStatus(self.main, "토큰 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "토큰 데이터를 저장할 위치를 선택하세요", os.path.dirname(csv_path)
            )
            if save_path == '':
                printStatus(self.main)
                return

            # ───────────────────────────── 3) 열 선택
            df_headers = pd.read_csv(csv_path, nrows=0)
            column_names = df_headers.columns.tolist()

            printStatus(self.main, "토큰화할 CSV 열을 선택하세요")
            dialog = SelectColumnsDialog(column_names, parent=self.main)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                printStatus(self.main)
                return

            selected_columns = dialog.get_selected_columns()
            if not selected_columns:
                printStatus(self.main)
                return

            # ───────────────────────────── 4) 필수 포함 단어
            reply = QMessageBox.question(
                self.main, "필수 포함 명사 입력",
                "필수 포함 단어사전 입력하시겠습니까?\n\nEx) \"포항, 공대\" X | \"포항공대\"",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes
            )

            include_word_list = []
            if reply == QMessageBox.StandardButton.Yes:
                printStatus(self.main, "필수 포함 단어 리스트(CSV)을 선택하세요")
                include_word_list_path = QFileDialog.getOpenFileName(
                    self.main,
                    "필수 포함 단어 리스트(CSV)를 선택하세요",
                    self.main.localDirectory,
                    "CSV Files (*.csv);;All Files (*)"
                )[0]
                if include_word_list_path == "":
                    return
                if not os.path.exists(include_word_list_path):
                    raise FileNotFoundError(f"파일을 찾을 수 없습니다\n\n{include_word_list_path}")

                with open(safe_path(include_word_list_path), 'rb') as f:
                    codec = chardet.detect(f.read())['encoding']

                df = pd.read_csv(include_word_list_path, low_memory=False, encoding=codec)
                if 'word' not in list(df.keys()):
                    QMessageBox.warning(
                        self.main, "Wrong Format", "필수 포함 단어 리스트 형식과 일치하지 않습니다")
                    printStatus(self.main)
                    return
                include_word_list = df['word'].tolist()

            pid = str(uuid.uuid4())
            register_process(pid, "Tokenizing File")
            
            thread_name = f"CSV 토큰화: {tokenfile_name}"
            register_thread(thread_name)
            printStatus(self.main)
            
            downloadDialog = DownloadDialog(thread_name, pid, self.main)
            downloadDialog.show()

            worker = TokenizeWorker(pid, csv_path, save_path, tokenfile_name, selected_columns, include_word_list, self.main)
            self.connectWorkerForDownloadDialog(worker, downloadDialog, thread_name)
            worker.start()

            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def run_modify_token(self):
        try:
            token_filepath = self.check_csv_file(tokenCheck=True)
            if not token_filepath:
                printStatus(self.main)
                return

            printStatus(self.main, "조정된 토큰 데이터를 저장할 위치를 선택하세요")
            save_path = QFileDialog.getExistingDirectory(
                self.main, "토큰 데이터를 저장할 위치를 선택하세요", os.path.dirname(
                    token_filepath)
            )
            if save_path == '':
                printStatus(self.main)
                return

            df_headers = pd.read_csv(token_filepath, nrows=0)
            column_names = df_headers.columns.tolist()

            printStatus(self.main, "토큰 데이터가 있는 열을 선택하세요")
            dialog = SelectColumnsDialog(column_names, parent=self.main)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                printStatus(self.main)
                return
            selected_columns = dialog.get_selected_columns()
            if not selected_columns:
                printStatus(self.main)
                return

            window_size, ok = QInputDialog.getInt(
                self.main,
                "윈도우 크기 입력",
                "토큰 윈도우 크기를 입력하세요:",
                1, 1
            )
            if not ok:
                printStatus(self.main)
                return

            def sliding_window_tokens(text, window_size):
                if not isinstance(text, str):
                    return ''

                tokens = [token.strip() for token in text.split(',')]
                if window_size <= 1:
                    candidates = tokens
                else:
                    candidates = [''.join(tokens[i:i+window_size])
                                  for i in range(len(tokens)-window_size+1)]

                return ', '.join(candidates)

            printStatus(self.main, "토큰 파일 읽는 중...")
            token_df = readCSV(token_filepath)

            printStatus(self.main, "토큰 파일 조정 중...")
            for column in selected_columns:
                token_df[column] = token_df[column].apply(
                    lambda x: sliding_window_tokens(x, window_size)
                )

            base_filename = os.path.basename(token_filepath)
            name, ext = os.path.splitext(base_filename)
            new_filename = f"{name}_window={window_size}.csv"

            printStatus(self.main, "조정된 토큰 파일 저장 중...")
            token_df.to_csv(
                os.path.join(save_path, new_filename),
                index=False,
                encoding='utf-8-sig'
            )

            printStatus(self.main)
            openFileResult(
                self.main,
                f"토큰 파일 조정이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?",
                save_path
            )
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
                    self.main.localDirectory if not token_paths else os.path.dirname(
                        token_paths[-1]),
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
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply != QMessageBox.StandardButton.Yes:
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
            dialog = SelectColumnsDialog(column_names, parent=self.main)
            if dialog.exec() != QDialog.DialogCode.Accepted:
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
                msg_lines = [
                    f"{fname}  →  '{col}' 열 없음" for fname, col in missing_info]
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
            common_periods = set.intersection(
                *[set(d.keys()) for d in file_period_dicts])
            results = []
            for per in sorted(common_periods):
                common_tok = set.intersection(
                    *[d[per] for d in file_period_dicts])
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

    def select_etc_analysis(self):
        dialog = SelectEtcAnalysisDialog(self.run_hate_measure, self.run_whisper, self.run_youtube_download, self.run_detection)
        dialog.exec()

    def run_hate_measure(self):
        class HateMeasureWorker(BaseWorker):
            def __init__(self, pid, csv_path, save_dir, csv_fname, text_col, option_num, parent=None):
                super().__init__(parent)
                self.pid = pid
                self.csv_path = csv_path
                self.save_dir = save_dir
                self.csv_fname = csv_fname
                self.text_col = text_col
                self.option_num = option_num

            def run(self):
                try:
                    option_payload = {
                        "pid": self.pid,
                        "option_num": self.option_num,
                        "text_col": self.text_col,
                    }

                    url = MANAGER_SERVER_API + "/analysis/hate"

                    # 1. 업로드
                    response = self.upload_file(
                        self.csv_path,
                        url,
                        extra_fields={
                            "option": (None, json.dumps(option_payload), "application/json")
                        },
                        label="CSV 업로드 중"
                    )

                    # 2. 응답 코드 검사
                    if response.status_code != 200:
                        try:
                            err = response.json()
                            msg = err.get("message") or err.get("error") or "분석 실패"
                        except Exception:
                            msg = response.text or "분석 중 알 수 없는 오류가 발생했습니다."
                        self.error.emit(msg)
                        return

                    # 3. 다운로드
                    filename = f"hate_{self.csv_fname}"
                    self.download_file(response, self.save_dir, filename, label="결과 다운로드 중")

                    self.finished.emit(True, f"{self.csv_fname} 혐오도 분석이 완료되었습니다\n\n파일 탐색기에서 확인하시겠습니까?", self.save_dir)

                except Exception:
                    self.error.emit(traceback.format_exc())

        try:            
            # 1) CSV 선택
            csv_path = self.check_csv_file()
            if not csv_path:
                printStatus(self.main)
                return

            csv_fname = os.path.basename(csv_path)

            # 2) 결과 저장 폴더
            printStatus(self.main, "결과 CSV를 저장할 위치를 선택하세요")
            save_dir = QFileDialog.getExistingDirectory(
                self.main, "결과 파일 저장 위치 선택", os.path.dirname(csv_path)
            )
            if save_dir == "":
                printStatus(self.main)
                return

            # 3) 텍스트 열 선택
            df_headers = pd.read_csv(csv_path, nrows=0)
            column_names = df_headers.columns.tolist()

            dialog = SelectColumnsDialog(column_names, parent=self.main)
            dialog.setWindowTitle("혐오도 분석할 텍스트 열 선택")
            if dialog.exec() != QDialog.DialogCode.Accepted:
                printStatus(self.main)
                return

            sel_cols = dialog.get_selected_columns()
            if len(sel_cols) != 1:
                QMessageBox.warning(
                    self.main, "Wrong Selection", "텍스트 열을 하나만 선택해 주세요.")
                printStatus(self.main)
                return

            text_col = sel_cols[0]
            option_num = 2

            pid = str(uuid.uuid4())
            register_process(pid, "혐오도 분석")
            
            thread_name = f"혐오도 분석: {csv_fname}"
            register_thread(thread_name)
            printStatus(self.main)
            
            downloadDialog = DownloadDialog(thread_name, pid, self.main)
            downloadDialog.show()
        
            worker = HateMeasureWorker(pid, csv_path, save_dir, csv_fname, text_col, option_num, self.main)
            self.connectWorkerForDownloadDialog(worker, downloadDialog, thread_name)
            worker.start()

            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

            # 로그
            userLogging(f'ANALYSIS -> HateMeasure({csv_fname}) : col={text_col}, opt={option_num}')

        except Exception:
            programBugLog(self.main, traceback.format_exc())
    
    def run_whisper(self):
        class WhisperWorker(BaseWorker):
            def __init__(self, pid, audio_path, save_dir, audio_fname, language, model_level, parent=None):
                super().__init__(parent)
                self.pid = pid
                self.audio_path = audio_path
                self.save_dir = save_dir
                self.audio_fname = audio_fname
                self.language = language
                self.model_level = model_level

            def run(self):
                try:
                    option_payload = {
                        "pid": self.pid,
                        "language": self.language,
                        "model": self.model_level,
                    }

                    url = MANAGER_SERVER_API + "/analysis/whisper"

                    response = self.upload_file(
                        self.audio_path,
                        url,
                        extra_fields={
                            "option": (None, json.dumps(option_payload), "application/json")
                        },
                        label="음성 업로드 중"
                    )

                    if response.status_code != 200:
                        try:
                            err = response.json()
                            msg = err.get("message") or err.get("error") or "음성 인식 실패"
                        except Exception:
                            msg = response.text or "음성 인식 중 오류 발생"
                        self.error.emit(msg)
                        return

                    result = response.json()
                    text = result.get("text", "")
                    text_with_time = result.get("text_with_time", "")
                    output_text = text_with_time or text

                    base, _ = os.path.splitext(self.audio_fname)
                    filename = f"{base}_whisper_{datetime.now().strftime('%m%d%H%M')}.txt"
                    output_path = os.path.join(self.save_dir, filename)

                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(output_text)

                    self.finished.emit(
                        True,
                        f"{self.audio_fname} 음성 인식이 완료되었습니다.\n\n파일을 확인하시겠습니까?",
                        self.save_dir
                    )

                except Exception:
                    self.error.emit(traceback.format_exc())
        try:
            audio_path = self.check_audio_file()
            if not audio_path:
                printStatus(self.main)
                return

            audio_fname = os.path.basename(audio_path)

            printStatus(self.main, "결과 파일 저장 위치를 선택하세요")
            save_dir = QFileDialog.getExistingDirectory(
                self.main, "결과 파일 저장 위치 선택", os.path.dirname(audio_path)
            )
            if save_dir == "":
                printStatus(self.main)
                return

            dialog = WhisperOptionDialog(self.main)
            if dialog.exec() != QDialog.Accepted:
                printStatus(self.main)
                return

            opt = dialog.get_option()
            language = opt["language"]
            model_level = opt["model_level"]

            pid = str(uuid.uuid4())
            register_process(pid, "음성 인식")

            thread_name = f"음성 인식: {audio_fname}"
            register_thread(thread_name)
            printStatus(self.main)

            downloadDialog = DownloadDialog(thread_name, pid, self.main)
            downloadDialog.show()

            worker = WhisperWorker(
                pid,
                audio_path,
                save_dir,
                audio_fname,
                language,
                model_level,
                self.main
            )

            self.connectWorkerForDownloadDialog(worker, downloadDialog, thread_name)
            worker.start()

            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

            userLogging(
                f"ANALYSIS -> Whisper({audio_fname}) : lang={language}, model={model_level}"
            )

        except Exception:
            programBugLog(self.main, traceback.format_exc())

    def run_youtube_download(self):
        
        class YouTubeDownloadWorker(BaseWorker):
            def __init__(self, pid, urls, save_dir, fmt, save_whisper, parent=None):
                super().__init__(parent)
                self.pid = pid
                self.urls = urls
                self.save_dir = save_dir
                self.fmt = fmt
                self.save_whisper = save_whisper

            def run(self):
                try:
                    option_payload = {
                        "pid": self.pid,
                        "urls": self.urls,
                        "format": self.fmt,
                        "save_whisper": self.save_whisper
                    }

                    response = requests.post(
                        MANAGER_SERVER_API + "/analysis/youtube",
                        data={"option": json.dumps(option_payload)},
                        headers=get_api_headers(),
                        stream=True,
                        timeout=600
                    )

                    if response.status_code != 200:
                        try:
                            msg = response.json().get("message", "YouTube 다운로드 실패")
                        except Exception:
                            msg = response.text
                        self.error.emit(msg)
                        return

                    zip_name = f"youtube_{datetime.now().strftime('%m%d%H%M')}.zip"

                    extract_path = self.download_file(
                        response,
                        self.save_dir,
                        zip_name,
                        extract=True
                    )

                    self.finished.emit(
                        True,
                        "YouTube 다운로드가 완료되었습니다.\n파일을 확인하시겠습니까?",
                        extract_path
                    )

                except Exception:
                    self.error.emit(traceback.format_exc())

        dialog = YouTubeDownloadDialog(self.main, self.main.localDirectory)
        if dialog.exec() != QDialog.Accepted:
            return

        data = dialog.data
        urls = data["urls"]
        fmt = data["format"]
        save_whisper = data["save_whisper"]
        save_dir = data["save_dir"]

        pid = str(uuid.uuid4())
        register_process(pid, "YouTube Download")

        thread_name = "YouTube 다운로드"
        register_thread(thread_name)
        printStatus(self.main)

        downloadDialog = DownloadDialog(thread_name, pid, self.main)
        downloadDialog.show()

        worker = YouTubeDownloadWorker(pid, urls, save_dir, fmt, save_whisper, self.main)
        self.connectWorkerForDownloadDialog(worker, downloadDialog, thread_name)
        worker.start()

        if not hasattr(self, "_workers"):
            self._workers = []
        self._workers.append(worker)

        userLogging(
            f"ANALYSIS -> YouTubeDownload(count={len(urls)}, fmt={fmt}, whisper={save_whisper})"
        )
    
    def run_detection(self):
        class YoloWorker(BaseWorker):
            def __init__(
                self,
                pid,
                media,
                file_paths,
                save_dir,
                conf_thres,
                model_name = "yolo11n",
                # dino options
                run_dino=False,
                dino_prompt="",
                parent=None,
            ):
                super().__init__(parent)
                self.pid = pid
                self.media = media
                self.file_paths = file_paths
                self.save_dir = save_dir
                self.conf_thres = conf_thres
                self.model_name = model_name

                self.run_dino = run_dino
                self.dino_prompt = dino_prompt

            def _run_dino(self):
                dino_url = MANAGER_SERVER_API + "/analysis/dino"

                option_payload = {
                    "pid": self.pid,
                    "box_threshold": self.conf_thres,
                    "media": self.media,
                }

                prompt = (self.dino_prompt or "").strip()
                if not prompt:
                    raise RuntimeError("Prompt가 비어있습니다.")

                with ExitStack() as stack:
                    files = []
                    for path in self.file_paths:
                        f = stack.enter_context(open(path, "rb"))
                        ctype, _ = mimetypes.guess_type(path)
                        ctype = ctype or "application/octet-stream"
                        files.append(("files", (os.path.basename(path), f, ctype)))

                    resp = requests.post(
                        dino_url,
                        data={
                            "prompt": prompt,
                            "option": json.dumps(option_payload),
                        },
                        headers=get_api_headers(),
                        files=files,
                        stream=True,
                        timeout=1800 if self.media == "video" else 600,
                    )

                if resp.status_code != 200:
                    try:
                        err = resp.json()
                        msg = err.get("message") or err.get("error") or "Grounding DINO 처리 실패"
                    except Exception:
                        msg = resp.text or "Grounding DINO 처리 중 오류"
                    raise RuntimeError(msg)

                zip_name = (
                    f"detect_{self.media}_{datetime.now().strftime('%m%d%H%M')}.zip"
                )

                extract_path = self.download_file(
                    resp,
                    self.save_dir,
                    zip_name,
                    extract=True,
                )

                return extract_path

            def _run_yolo(self):
                option_payload = {
                    "pid": self.pid, 
                    "media": self.media,
                    "model": self.model_name  # 서버가 이 키를 읽어서 모델을 로드함
                }
                yolo_url = MANAGER_SERVER_API + "/analysis/yolo"

                with ExitStack() as stack:
                    files = []
                    for path in self.file_paths:
                        f = stack.enter_context(open(path, "rb"))
                        ctype, _ = mimetypes.guess_type(path)
                        ctype = ctype or "application/octet-stream"
                        files.append(("files", (os.path.basename(path), f, ctype)))

                    response = requests.post(
                        yolo_url,
                        data={
                            "option": json.dumps(option_payload),
                            "conf_thres": str(self.conf_thres),
                        },
                        headers=get_api_headers(),
                        files=files,
                        stream=True,
                        timeout=600,
                    )

                if response.status_code != 200:
                    try:
                        err = response.json()
                        msg = err.get("message") or err.get("error") or "YOLO 처리 실패"
                    except Exception:
                        msg = response.text or "YOLO 처리 중 오류 발생"
                    raise RuntimeError(msg)

                zip_name = f"detect_{self.media}_{datetime.now().strftime('%m%d%H%M')}.zip"
                extract_path = self.download_file(
                    response,
                    self.save_dir,
                    zip_name,
                    extract=True,
                )
                return extract_path

            def run(self):
                try:
                    if self.run_dino:
                        result_dir = self._run_dino()
                        msg = "Prompt 객체 검출이 완료되었습니다.\n파일을 확인하시겠습니까?"
                    else:
                        result_dir = self._run_yolo()
                        msg = "YOLO 객체 검출이 완료되었습니다.\n파일을 확인하시겠습니까?"

                    self.finished.emit(True, msg, result_dir or self.save_dir)

                except Exception:
                    self.error.emit(traceback.format_exc())
        try:
            dialog = DetectOptionDialog(self.main, base_dir=self.main.localDirectory)
            if dialog.exec() != QDialog.Accepted:
                return

            data = dialog.data
            media = data["media"]
            file_paths = data["file_paths"]
            conf_thres = data["conf_thres"]
            save_dir = data["save_dir"]
            model_name = data.get("model", "yolo11n")

            # dino 옵션
            run_dino = bool(data.get("run_dino", False))
            dino_prompt = data.get("dino_prompt", "")

            pid = str(uuid.uuid4())

            if run_dino:
                register_process(pid, f"Prompt Detect ({media})")
                thread_name = f"Prompt Detect ({media}, {len(file_paths)} files)"
            else:
                register_process(pid, f"Image Detect ({media})")
                thread_name = f"Image Detect ({media}, {len(file_paths)} files)"

            register_thread(thread_name)
            printStatus(self.main)

            downloadDialog = DownloadDialog(thread_name, pid, self.main)
            downloadDialog.show()

            worker = YoloWorker(
                pid=pid,
                media=media,
                file_paths=file_paths,
                save_dir=save_dir,
                conf_thres=conf_thres,
                model_name=model_name,
                run_dino=run_dino,
                dino_prompt=dino_prompt,
                parent=self.main,
            )
            self.connectWorkerForDownloadDialog(worker, downloadDialog, thread_name)
            worker.start()

            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

            if run_dino:
                userLogging(
                    f"ANALYSIS -> DINO(count={len(file_paths)}, prompt={dino_prompt}, conf={conf_thres})"
                )
            else:
                userLogging(
                    f"ANALYSIS -> YOLO(media={media}, count={len(file_paths)}, conf={conf_thres})"
                )

        except Exception:
            programBugLog(self.main, traceback.format_exc())
  
    def check_csv_file(self, tokenCheck=False):
        selected_directory = self.analysis_getfiledirectory_csv(
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

    def check_audio_file(self):
        selected_directory = self.analysis_getfiledirectory_audio(self.file_dialog)

        if len(selected_directory) == 0:
            QMessageBox.warning(self.main, "Wrong Selection", "선택된 오디오 파일이 없습니다")
            return 0

        if selected_directory[0] == False:
            QMessageBox.warning(self.main, "Wrong Format", f"{selected_directory[1]} 는 오디오 파일이 아닙니다.")
            return 0

        if len(selected_directory) != 1:
            QMessageBox.warning(self.main, "Wrong Selection", "한 개의 오디오 파일만 선택하여 주십시오")
            return 0

        return selected_directory[0]

    def anaylsis_buttonMatch(self):
        self.main.analysis_timesplitfile_btn.clicked.connect(self.run_timesplit)
        self.main.analysis_dataanalysisfile_btn.clicked.connect(self.run_analysis)
        self.main.analysis_mergefile_btn.clicked.connect(self.run_merge)
        self.main.analysis_wordcloud_btn.clicked.connect(self.run_wordcloud)
        self.main.analysis_kemkim_btn.clicked.connect(self.select_kemkim)
        self.main.analysis_tokenization_btn.clicked.connect(self.select_tokenize)
        self.main.analysis_etc_btn.clicked.connect(self.select_etc_analysis)

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
