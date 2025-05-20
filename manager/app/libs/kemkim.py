from ui.status import printStatus
from core.setting import get_setting
import gc
from tqdm import tqdm
import platform
import re
import warnings
import traceback
import csv
import io
import numpy as np
import sys
import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
from datetime import datetime
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 크기 제한 해제

warnings.filterwarnings("ignore")

# 운영체제에 따라 한글 폰트를 설정
if platform.system() == 'Darwin':  # macOS
    plt.rcParams['font.family'] = 'AppleGothic'
elif platform.system() == 'Windows':  # Windows
    plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕 폰트 사용

# 폰트 설정 후 음수 기호가 깨지는 것을 방지
plt.rcParams['axes.unicode_minus'] = False


class KimKem:
    def __init__(self,
                 parent=None,
                 token_data=None,
                 csv_name=None,
                 save_path=None,
                 startdate=None,
                 enddate=None,
                 period=None,
                 topword=None,
                 weight=None,
                 graph_wordcnt=None,
                 split_option=None,
                 split_custom=None,
                 filter_option=None,
                 trace_standard=None,
                 ani_option=None,
                 exception_word_list=[],
                 exception_filename='N',
                 rekemkim=False):
        self.exception_word_list = exception_word_list
        self.main = parent
        if rekemkim == False:
            self.csv_name = csv_name
            self.save_path = save_path
            self.token_data = token_data
            self.folder_name = csv_name.replace(
                '.csv', '').replace('token_', '')
            self.startdate = startdate
            self.enddate = enddate
            self.period = period
            self.topword = topword
            self.weight = weight
            self.graph_wordcnt = graph_wordcnt
            self.filter_option = filter_option
            self.trace_standard = trace_standard
            self.ani_option = ani_option
            self.filter_option_display = 'Y' if filter_option == True else 'N'
            self.trace_standard_display = '시작연도' if trace_standard == 'startyear' else '직전연도'
            self.ani_option_display = 'Y' if ani_option == True else 'N'
            self.except_option_display = 'Y' if exception_word_list else 'N'
            self.exception_filename = exception_filename
            self.split_option = split_option
            self.split_custom = split_custom
            self.now = datetime.now()
            self.weighterror = False

            # Text Column Name 지정
            for column in token_data.columns.tolist():
                if 'Text' in column:
                    self.textColumn_name = column
                elif 'Date' in column:
                    self.dateColumn_name = column

            # Step 1: 데이터 분할 및 초기화
            self.period_divided_group = self.divide_period(
                self.token_data, period)
            period_list = list(self.period_divided_group.groups.keys())

            if (len(period_list) - 1) * self.weight >= 1:
                self.write_status("시간 가중치 오류")
                self.weighterror = True

            else:
                self.folder_name = re.sub(
                    r'(\d{8})_(\d{8})_(\d{4})_(\d{4})', f'{self.startdate}~{self.enddate}_{period}', self.folder_name)
                self.kimkem_folder_path = os.path.join(
                    self.save_path,
                    f"kemkim_{str(self.folder_name)}_{self.now.strftime('%m%d%H%M')}"
                )
                os.makedirs(self.kimkem_folder_path, exist_ok=True)
                self.write_status()

    def _save_final_signals(self, DoV_signal, DoD_signal, result_folder):
        DoV_signal_df = pd.DataFrame(
            [(k, v) for k, v in DoV_signal.items()], columns=['signal', 'word'])
        DoV_signal_df.to_csv(os.path.join(
            result_folder, "DoV_signal.csv"), index=False, encoding='utf-8-sig')

        DoD_signal_df = pd.DataFrame(
            [(k, v) for k, v in DoD_signal.items()], columns=['signal', 'word'])
        DoD_signal_df.to_csv(os.path.join(
            result_folder, "DoD_signal.csv"), index=False, encoding='utf-8-sig')

        final_signal = self._get_communal_signals(DoV_signal, DoD_signal)
        final_signal_df = pd.DataFrame(
            [(k, v) for k, v in final_signal.items()], columns=['signal', 'word'])
        final_signal_df.to_csv(os.path.join(
            result_folder, "Final_signal.csv"), index=False, encoding='utf-8-sig')

        return final_signal

    def _get_communal_signals(self, DoV_signal, DoD_signal):
        communal_strong_signal = [
            word for word in DoV_signal['strong_signal'] if word in DoD_signal['strong_signal']]
        communal_weak_signal = [
            word for word in DoV_signal['weak_signal'] if word in DoD_signal['weak_signal']]
        communal_latent_signal = [
            word for word in DoV_signal['latent_signal'] if word in DoD_signal['latent_signal']]
        communal_well_known_signal = [
            word for word in DoV_signal['well_known_signal'] if word in DoD_signal['well_known_signal']]
        return {
            'strong_signal': communal_strong_signal,
            'weak_signal': communal_weak_signal,
            'latent_signal': communal_latent_signal,
            'well_known_signal': communal_well_known_signal
        }

    def top_n_percent(self, lst, n):
        if not lst:
            return None  # 빈 리스트가 입력될 경우 None 반환

        if n <= 0:
            return None  # n이 0이거나 음수일 경우 None 반환

        sorted_lst = sorted(lst, reverse=True)  # 내림차순으로 정렬
        threshold_index = max(
            0, int(len(sorted_lst) * n / 100) - 1)  # n%에 해당하는 인덱스 계산

        return sorted_lst[threshold_index]  # 상위 n%에 가장 가까운 요소 반환

    def calculate_statistics(self, data):

        def calculate_skewness(data):
            n = len(data)
            mean = sum(data) / n
            std_dev = (sum((x - mean) ** 2 for x in data) / n) ** 0.5

            skewness = (n / ((n - 1) * (n - 2))) * \
                sum(((x - mean) / std_dev) ** 3 for x in data)
            return round(skewness, 3)

        def calculate_kurtosis(data):
            n = len(data)
            mean = sum(data) / n
            std_dev = (sum((x - mean) ** 2 for x in data) / n) ** 0.5

            kurtosis = ((n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3)) *
                        sum(((x - mean) / std_dev) ** 4 for x in data)) - (3 * (n - 1) ** 2 / ((n - 2) * (n - 3)))
            return round(kurtosis, 3)

        # 평균 계산
        mean_value = round(np.mean(data), 3)

        # 중위값 계산
        median_value = round(np.median(data), 3)

        try:
            skewness_value = calculate_skewness(data)
            kurtosis_value = calculate_kurtosis(data)
        except:
            skewness_value = 0
            kurtosis_value = 0

         # 데이터를 내림차순으로 정렬
        sorted_data = np.sort(data)[::-1]

        # 결과를 딕셔너리로 정리
        result = {
            "mean": mean_value,
            "median": median_value,
            "skewness": skewness_value,
            "kurtosis": kurtosis_value
        }

        # 10분위값 계산 (내림차순 데이터 기준)
        deciles = {
            f"{i*10}%": round(np.percentile(sorted_data, i*10), 3) for i in range(1, 10)}
        # 딕셔너리에 10분위값 추가
        result.update(deciles)

        return result

    def DoV_draw_graph(self, avg_DoV_increase_rate=None, avg_term_frequency=None, graph_folder=None, final_signal_list=[], graph_name='', redraw_option=False, coordinates=False, graph_size=None, eng_keyword_list=[]):
        if redraw_option == False:
            x_data = self.calculate_statistics(
                list(avg_term_frequency.values()))
            y_data = self.calculate_statistics(
                list(avg_DoV_increase_rate.values()))
            match self.split_option:
                case '평균(Mean)':
                    graph_term = x_data['mean']  # x축, 평균 단어 빈도
                    graph_DoV = y_data['mean']  # y축, 평균 증가율
                case '중앙값(Median)':
                    graph_term = x_data['median']  # x축, 중앙값 단어 빈도
                    graph_DoV = y_data['median']  # y축, 중앙값 증가율
                case '직접 입력: 상위( )%':
                    graph_term = self.top_n_percent(
                        # x축, 평균 단어 빈도
                        list(avg_term_frequency.values()), self.split_custom)
                    graph_DoV = self.top_n_percent(
                        # y축, 평균 증가율
                        list(avg_DoV_increase_rate.values()), self.split_custom)

            with open(os.path.join(graph_folder, "DOV_statistics.csv"), 'w', newline='') as csvfile:
                fieldnames = ['index', 'x', 'y']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # 헤더 작성
                writer.writeheader()

                # 키를 기준으로 두 딕셔너리를 반복하며 행 작성
                for key in x_data.keys():
                    writer.writerow(
                        {'index': key, 'x': x_data[key], 'y': y_data[key]})

            coordinates = {}
            coordinates['axis'] = (graph_term, graph_DoV)

            for key in avg_DoV_increase_rate:
                coordinates[key] = (avg_term_frequency[key],
                                    avg_DoV_increase_rate[key])
        else:
            graph_term = coordinates['axis'][0]
            graph_DoV = coordinates['axis'][1]

        coordinates = {k: v for k, v in coordinates.items(
        ) if k not in self.exception_word_list}
        coordinates = {key: coordinates[key] for key in sorted(coordinates)}

        if eng_keyword_list != []:
            korean_to_english = {
                korean: english for korean, english in eng_keyword_list}
            coordinates = {korean_to_english.get(
                k, k): v for k, v in coordinates.items()}

        if graph_size == None:
            plt.figure(figsize=(100, 100))
            fontsize = 50
            dotsize = 20
            labelsize = 12
            gradesize = 10

        else:
            plt.figure(figsize=(graph_size[0], graph_size[1]))
            fontsize = graph_size[2]
            dotsize = graph_size[3]
            labelsize = graph_size[4]
            gradesize = graph_size[5]

        # 눈금 글자 크기를 30으로 설정 (원하는 크기로 조정 가능)
        plt.tick_params(axis='both', which='major', labelsize=gradesize)
        plt.axvline(x=graph_term, color='k', linestyle='--')  # x축 수직선
        plt.axhline(y=graph_DoV, color='k', linestyle='--')  # y축 수평선

        strong_signal = sorted([word for word in coordinates if coordinates[word]
                               [0] >= graph_term and coordinates[word][1] >= graph_DoV])
        weak_signal = sorted([word for word in coordinates if coordinates[word]
                             [0] <= graph_term and coordinates[word][1] >= graph_DoV])
        latent_signal = sorted([word for word in coordinates if coordinates[word]
                               [0] <= graph_term and coordinates[word][1] <= graph_DoV])
        well_known_signal = sorted([word for word in coordinates if coordinates[word]
                                   [0] >= graph_term and coordinates[word][1] <= graph_DoV])

        strong_signal.remove('axis')
        weak_signal.remove('axis')
        latent_signal.remove('axis')
        well_known_signal.remove('axis')

        # 각 좌표와 해당 키를 표시, 글자 크기 변경
        for key, value in coordinates.items():
            if key != 'axis':
                if final_signal_list != [] and key not in final_signal_list:
                    continue
                plt.scatter(value[0], value[1], s=dotsize)
                plt.text(value[0], value[1], key, fontsize=fontsize)

        # 그래프 제목 및 레이블 설정
        plt.title("Keyword Emergence Map", fontsize=labelsize)
        plt.xlabel("Average Term Frequency(TF)", fontsize=labelsize)
        plt.ylabel("Time-Weighted increasing rate", fontsize=labelsize)

        # 그래프 표시
        if graph_name == '':
            graph_name = "KEM_graph.png"

        plt.savefig(os.path.join(graph_folder, graph_name),
                    bbox_inches='tight')
        plt.close()

        coordinates_df = pd.DataFrame(
            [(k, f"({float(v[0])}, {float(v[1])})")
             for k, v in coordinates.items()],
            columns=['key', 'value']
        )
        coordinates_df.to_csv(os.path.join(
            graph_folder, "DOV_coordinates.csv"), index=False, encoding='utf-8-sig')

        return {'strong_signal': strong_signal, "weak_signal": weak_signal, "latent_signal": latent_signal, "well_known_signal": well_known_signal}, coordinates

    def DoD_draw_graph(self, avg_DoD_increase_rate=None, avg_doc_frequency=None, graph_folder=None, final_signal_list=[], graph_name='', redraw_option=False, coordinates=None, graph_size=None, eng_keyword_list=[]):
        if redraw_option == False:
            x_data = self.calculate_statistics(
                list(avg_doc_frequency.values()))
            y_data = self.calculate_statistics(
                list(avg_DoD_increase_rate.values()))
            match self.split_option:
                case '평균(Mean)':
                    graph_doc = x_data['mean']  # x축, 평균 단어 빈도
                    graph_DoD = y_data['mean']  # y축, 평균 증가율
                case '중앙값(Median)':
                    graph_doc = x_data['median']  # x축, 평균 단어 빈도
                    graph_DoD = y_data['median']  # y축, 평균 증가율
                case '직접 입력: 상위( )%':
                    graph_doc = self.top_n_percent(
                        # x축, 평균 단어 빈도
                        list(avg_doc_frequency.values()), self.split_custom)
                    graph_DoD = self.top_n_percent(
                        # y축, 평균 증가율
                        list(avg_DoD_increase_rate.values()), self.split_custom)

            with open(os.path.join(graph_folder, "DOD_statistics.csv"), 'w', newline='') as csvfile:
                fieldnames = ['index', 'x', 'y']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                # 헤더 작성
                writer.writeheader()

                # 키를 기준으로 두 딕셔너리를 반복하며 행 작성
                for key in x_data.keys():
                    writer.writerow(
                        {'index': key, 'x': x_data[key], 'y': y_data[key]})

            coordinates = {}
            coordinates['axis'] = (graph_doc, graph_DoD)

            for key in avg_DoD_increase_rate:
                coordinates[key] = (avg_doc_frequency[key],
                                    avg_DoD_increase_rate[key])
        else:
            graph_doc = coordinates['axis'][0]
            graph_DoD = coordinates['axis'][1]

        coordinates = {k: v for k, v in coordinates.items(
        ) if k not in self.exception_word_list}
        coordinates = {key: coordinates[key] for key in sorted(coordinates)}

        if eng_keyword_list != []:
            korean_to_english = {
                korean: english for korean, english in eng_keyword_list}
            coordinates = {korean_to_english.get(
                k, k): v for k, v in coordinates.items()}

        if graph_size == None:
            plt.figure(figsize=(100, 100))
            fontsize = 50
            dotsize = 20
            labelsize = 12
            gradesize = 10

        else:
            plt.figure(figsize=(graph_size[0], graph_size[1]))
            fontsize = graph_size[2]
            dotsize = graph_size[3]
            labelsize = graph_size[4]
            gradesize = graph_size[5]

        # 눈금 글자 크기를 30으로 설정 (원하는 크기로 조정 가능)
        plt.tick_params(axis='both', which='major', labelsize=gradesize)
        plt.axvline(x=graph_doc, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=graph_DoD, color='k', linestyle='--')  # y축 중앙값 수평선

        strong_signal = sorted([word for word in coordinates if coordinates[word]
                               [0] >= graph_doc and coordinates[word][1] >= graph_DoD])
        weak_signal = sorted([word for word in coordinates if coordinates[word]
                             [0] <= graph_doc and coordinates[word][1] >= graph_DoD])
        latent_signal = sorted([word for word in coordinates if coordinates[word]
                               [0] <= graph_doc and coordinates[word][1] <= graph_DoD])
        well_known_signal = sorted([word for word in coordinates if coordinates[word]
                                   [0] >= graph_doc and coordinates[word][1] <= graph_DoD])

        strong_signal.remove('axis')
        weak_signal.remove('axis')
        latent_signal.remove('axis')
        well_known_signal.remove('axis')

        # 각 좌표와 해당 키를 표시
        for key, value in coordinates.items():
            if key != 'axis':
                if final_signal_list != [] and key not in final_signal_list:
                    continue
                plt.scatter(value[0], value[1], s=dotsize)
                plt.text(value[0], value[1], key, fontsize=fontsize)

        # 그래프 제목 및 레이블 설정
        plt.title("Keyword Issue Map", fontsize=labelsize)
        plt.xlabel("Average Document Frequency(DF)", fontsize=labelsize)
        plt.ylabel("Time-Weighted increasing rate", fontsize=labelsize)

        # 그래프 표시
        if graph_name == '':
            graph_name = "KIM_graph.png"

        plt.savefig(os.path.join(graph_folder, graph_name),
                    bbox_inches='tight')
        plt.close()

        coordinates_df = pd.DataFrame(
            [(k, f"({float(v[0])}, {float(v[1])})")
             for k, v in coordinates.items()],
            columns=['key', 'value']
        )
        coordinates_df.to_csv(os.path.join(
            graph_folder, "DOD_coordinates.csv"), index=False, encoding='utf-8-sig')

        return {'strong_signal': strong_signal, "weak_signal": weak_signal, "latent_signal": latent_signal, "well_known_signal": well_known_signal}, coordinates


if __name__ == '__main__':
    token_data = pd.read_csv(
        "/Users/yojunsmacbookprp/Desktop/MANAGER/navernews_바이오의료_20100101_20240731_0815_2036/token_data/token_navernews_바이오의료_20100101_20240731_0815_2036_article.csv", low_memory=False, encoding='utf-8-sig')
    kimkem_obj = KimKem(token_data=token_data,
                        csv_name='navernews_바이오의료_20100101_20240731_0815_2036_article.csv',
                        save_path='C:/MANAGER/바이오의료 KIMKEM 데이터',
                        startdate=20240301,
                        enddate=20240331,
                        period='1d',
                        topword=500,
                        weight=0.05,
                        graph_wordcnt=20,
                        split_option='평균(Mean)',
                        ani_option=False,
                        exception_word_list=[]
                        )
    kimkem_obj.make_kimkem()
