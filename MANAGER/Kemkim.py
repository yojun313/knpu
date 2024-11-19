import sys
import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
from datetime import datetime
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 크기 제한 해제
import numpy as np
import io
import csv
import traceback
import warnings
import re
import platform
from tqdm import tqdm
import gc

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
                 ani_option = None,
                 exception_word_list=[],
                 exception_filename = 'N',
                 rekemkim = False):
        self.exception_word_list = exception_word_list
        
        if rekemkim == False:
            self.csv_name = csv_name
            self.save_path = save_path
            self.token_data = token_data
            self.folder_name = csv_name.replace('.csv', '').replace('token_', '')
            self.startdate = startdate
            self.enddate = enddate
            self.period = period
            self.topword = topword
            self.weight = weight
            self.graph_wordcnt = graph_wordcnt
            self.ani_option = ani_option
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
            self.period_divided_group = self.divide_period(self.token_data, period)
            period_list = list(self.period_divided_group.groups.keys())
            
            if (len(period_list) - 1) * self.weight >= 1:
                self.write_status("시간 가중치 오류")
                self.weighterror = True

            else:
                self.folder_name = re.sub(r'(\d{8})_(\d{8})_(\d{4})_(\d{4})', f'{self.startdate}~{self.enddate}_{period}', self.folder_name)
                self.kimkem_folder_path = os.path.join(
                    self.save_path,
                    f"kemkim_{str(self.folder_name)}_{self.now.strftime('%m%d%H%M')}"
                )
                os.makedirs(self.kimkem_folder_path, exist_ok=True)
                self.write_status()

    def clear_console(self):
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")

    def write_status(self, msg=''):
        self.info = (
            f"===================================================================================================================\n"
            f"{'분석 데이터:'} {self.csv_name}\n"
            f"{'분석 시각:'} {self.now.strftime('%Y.%m.%d %H:%M')}\n"
            f"{'분석 시작일:'} {self.startdate}\n"
            f"{'분석 종료일:'} {self.enddate}\n"
            f"{'분석 기간 단위:'} {self.period}\n"
            f"{'상위 단어 개수:'} {self.topword}\n"
            f"{'계산 가중치:'} {self.weight}\n"
            f"{'애니메이션 여부:'} {self.ani_option_display}\n"
            f"{'제외 단어 여부:'} {self.except_option_display}\n"
            f"{'제외 단어 파일:'} {self.exception_filename}\n"
            f"{'분할 기준:'} {self.split_option}\n"
            f"{'분할 상위%:'} {self.split_custom}\n"
            f"===================================================================================================================\n"
        )
        self.info += f'\n진행 상황: {msg}'
        
        with open(os.path.join(self.kimkem_folder_path, 'kemkim_info.txt'),'w+') as info_txt:
            info_txt.write(self.info)
        
    def make_kimkem(self):
        try:
            if self.weighterror == True:
                return 2
            print(self.info + '\n')
            self.write_status("토큰 데이터 분할 중...")
            print("\n토큰 데이터 분할 중... ")
            # Step 2: 연도별 단어 리스트 생성 (딕셔너리)
            period_divided_dic_raw = self._initialize_period_divided_dic(self.period_divided_group)#
            period_divided_dic_raw = self.filter_dic_empty_list(period_divided_dic_raw)

            # DF 계산을 위해서 각 연도(key)마다 2차원 리스트 할당 -> 요소 리스트 하나 = 문서 하나
            period_divided_dic = self._generate_period_divided_dic(period_divided_dic_raw)#

            # TF 계산을 위해서 각 연도마다 모든 token 할당
            period_divided_dic_merged = self._merge_period_divided_dic(period_divided_dic)#

            # Step 3: 상위 공통 단어 추출 및 키워드 리스트 생성
            top_common_words = self._extract_top_common_words(period_divided_dic_merged)#
            keyword_list = self._get_keyword_list(top_common_words)#

            # 추출된 공통 키워드 존재하지 않으면 프로그램 종료
            if keyword_list == []:
                self.write_status("키워드 없음 종료")
                return 0

            self.write_status("TF/DF 계산 중...")
            print("\nTF/DF 계산 중...")
            # Step 4: TF, DF, DoV, DoD 계산 -> 결과: {key: 키워드, value: 계산값} 형식의 딕셔너리
            tf_counts = self.cal_tf(keyword_list, period_divided_dic_merged)
            df_counts = self.cal_df(keyword_list, period_divided_dic)

            del top_common_words
            del period_divided_dic_merged
            gc.collect()

            self.period_list = list(tf_counts.keys())
            self.startperiod = self.period_list[0]
            self.lastperiod = self.period_list[-1]

            self.write_status("추적 데이터 DOV/DOD 계산 중...")
            print("\n추적 데이터 DOV/DOD 계산 중...")
            trace_DoV_dict = self.cal_DoV(keyword_list, period_divided_dic, tf_counts)
            trace_DoD_dict = self.cal_DoD(keyword_list, period_divided_dic, df_counts)

            # Step 5: 결과 저장 디렉토리 설정
            self._create_output_directories()

            # Step 6: 결과 저장 (TF, DF, DoV, DoD)
            self._save_trace_results(trace_DoV_dict, trace_DoD_dict)

            DoV_signal_record = {}
            DoD_signal_record = {}
            DoV_coordinates_record = {}
            DoD_coordinates_record = {}
            Final_signal_record = {}

            print("")
            for index, period in enumerate(tqdm(self.period_list, desc="연도별 KEMKIM 데이터 생성 중", file=sys.stdout)):
                # Step 7: 평균 증가율 및 빈도 계산

                if index == 0:
                    continue

                result_folder = os.path.join(self.trace_result_folder, period)

                self.write_status(f"{period} KEMKIM 증가율 계산 중...")
                avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency = self._calculate_averages(keyword_list, trace_DoV_dict, trace_DoD_dict, tf_counts, df_counts, self.period_list[index-1], period)

                self.write_status(f"{period} KEMKIM 신호 분석 및 그래프 생성 중...")
                # Step 8: 신호 분석 및 그래프 생성
                DoV_signal_record[period], DoD_signal_record[period], DoV_coordinates_record[period], DoD_coordinates_record[period] = self._analyze_signals(avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency, os.path.join(result_folder, 'Graph'))
                Final_signal_record[period] = self._save_final_signals(DoV_signal_record[period], DoD_signal_record[period], os.path.join(result_folder, 'Signal'))

            # Trace 데이터에서 키워드별로 Signal 변화를 추적
            self.write_status("키워드 추적 데이터 생성 및 필터링 중...")
            print("\n키워드 추적 데이터 생성 및 필터링 중...")
            DoV_signal_trace = self.trace_keyword_positions(DoV_signal_record)
            DoD_signal_trace = self.trace_keyword_positions(DoD_signal_record)
            Final_signal_trace = self.trace_keyword_positions(Final_signal_record)

            signal_column_list = list(DoV_signal_trace.columns)
            signal_column_list = [f'period_{column}' for column in signal_column_list]

            DoV_signal_trace.to_csv(os.path.join(self.trace_folder, 'DoV_signal_trace.csv'), encoding='utf-8-sig', header=signal_column_list)
            DoD_signal_trace.to_csv(os.path.join(self.trace_folder, 'DoD_signal_trace.csv'), encoding='utf-8-sig', header=signal_column_list)
            Final_signal_trace.to_csv(os.path.join(self.trace_folder, 'Final_signal_trace.csv'), encoding='utf-8-sig', header=signal_column_list)

            # Signal 추적 데이터에서 시계 방향으로 시그널 이동하지 않은 키워드들을 걸러냄
            DoV_signal_trace, DoV_signal_deletewords = self.filter_clockwise_movements(DoV_signal_trace)
            DoV_signal_trace, DoD_signal_deletewords = self.filter_clockwise_movements(DoV_signal_trace)
            add_list = sorted(list(set(DoV_signal_deletewords+DoD_signal_deletewords)))

            # 좌표 추적에서 키워드 필터링
            for period in DoV_coordinates_record:
                for keyword in add_list:
                    del DoV_coordinates_record[period][keyword]
                    del DoD_coordinates_record[period][keyword]

            # 좌표 추적 csv 저장
            DoV_coordinates_record_df = pd.DataFrame(DoV_coordinates_record)
            DoD_coordinates_record_df = pd.DataFrame(DoD_coordinates_record)
            DoV_coordinates_record_df.index.name = 'Keyword'
            DoD_coordinates_record_df.index.name = 'Keyword'
            DoV_coordinates_record_df.to_csv(os.path.join(self.trace_folder, 'DoV_coordinates_trace.csv'), encoding='utf-8-sig', header = signal_column_list)
            DoD_coordinates_record_df.to_csv(os.path.join(self.trace_folder, 'DoD_coordinates_trace.csv'), encoding='utf-8-sig', header = signal_column_list)

            self.exception_word_list = self.exception_word_list + ['@@@'] + add_list if self.exception_word_list else add_list

            if self.ani_option == True:
                self.write_status("키워드 추적 그래프 생성 중...")
                print("\n키워드 추적 그래프 생성 중...")
                self.visualize_keyword_movements(DoV_signal_trace, os.path.join(self.trace_folder, 'DoV_signal_trace_graph.png'), 'TF','Increasing Rate')
                self.visualize_keyword_movements(DoD_signal_trace, os.path.join(self.trace_folder, 'DoD_signal_trace_graph.png'), 'DF', 'Increasing Rate')
                self.write_status("키워드 추적 애니메이션 생성 중...")
                print("\n키워드 추적 애니메이션 생성 중...")
                self.animate_keyword_movements(DoV_signal_trace, os.path.join(self.trace_folder, 'DoV_signal_trace_animation.gif'), 'TF', 'Increasing Rate')
                self.animate_keyword_movements(DoD_signal_trace, os.path.join(self.trace_folder, 'DoD_signal_trace_animation.gif'), 'DF', 'Increasing Rate')

            self.write_status("최종 KEM KIM 생성 중...")
            print("\n[ 최종 KEM KIM 계산 ]\n")
            pd.DataFrame(self.exception_word_list, columns=['word']).to_csv(os.path.join(self.result_folder, 'filtered_words.csv'), index=False, encoding='utf-8-sig')
            DoV_dict = self.cal_DoV(keyword_list, period_divided_dic, tf_counts, trace=False)
            DoD_dict = self.cal_DoD(keyword_list, period_divided_dic, df_counts, trace=False)
            self._save_kimkem_results(tf_counts, df_counts, DoV_dict, DoD_dict)
            print('\n평균 증가율 및 빈도 계산 중...')
            avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency = self._calculate_averages(keyword_list, DoV_dict, DoD_dict, tf_counts, df_counts, self.period_list[0], self.period_list[-1])
            print("\n신호 분석 중...")
            DoV_signal_record, DoD_signal_record, DoV_coordinates_record, DoD_coordinates_record = self._analyze_signals(avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency, os.path.join(self.result_folder, 'Graph'))
            Final_signal_record = self._save_final_signals(DoV_signal_record, DoD_signal_record, os.path.join(self.result_folder, 'Signal'))

            self.write_status("완료")
            print("완료")
            return 1
        except Exception as e:
            self.write_status("오류 중단")
            return traceback.format_exc()

    def filter_dic_empty_list(self, dictionary):

        # 딕셔너리의 키 리스트를 역순으로 가져옴
        keys = list(dictionary.keys())

        # 역순으로 검사하여 빈 리스트나 NaN이 포함된 리스트를 가진 key를 제거
        for key in reversed(keys):
            value = dictionary[key]
            if not value:
                del dictionary[key]
            else:
                break  # 빈 리스트가 아니고 NaN도 없으면 멈춤

        return dictionary

    def find_key_position(self, dic, target_key):
        try:
            return list(dic.keys()).index(target_key)
        except ValueError:
            return None  # 키가 없을 경우 None 반환

    def trace_keyword_positions(self, period_data):
        
        # 모든 단어를 수집하기 위한 집합
        all_keywords = set()

        # 연도를 정렬하여 순차적으로 처리
        periods = sorted(period_data.keys())

        # 각 연도별로 단어의 위치를 추적할 딕셔너리
        keyword_positions = {}

        for period in periods:
            period_positions = {}
            for key, words in period_data[period].items():
                for word in words:
                    all_keywords.add(word)
                    period_positions[word] = f"{key}"
            
            keyword_positions[period] = period_positions

        # set을 list로 변환하여 인덱스로 사용
        df = pd.DataFrame(index=list(all_keywords))
        df.index.name = 'Keyword'
        
        for period in periods:
            df[str(period)] = df.index.map(keyword_positions[period].get)
        
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
            for period in df.columns:
                quadrant = df.loc[keyword, period]
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

        position_periods = {}
        
        # 각 키워드의 포인트를 시각화
        for i, (keyword, trajectory) in enumerate(keyword_trajectories.items()):
            trajectory_df = pd.DataFrame(trajectory, columns=['x', 'y'])
            
            # 포인트만 표시
            plt.scatter(trajectory_df['x'], trajectory_df['y'], label=keyword, color=colors[i], alpha=0.75)

            # 각 위치에 연도 표시
            for j, (x, y) in enumerate(trajectory):
                # 해당 위치에 이미 연도가 기록되어 있는지 확인
                if (x, y) in position_periods:
                    position_periods[(x, y)].append(df.columns[j])
                else:
                    position_periods[(x, y)] = [df.columns[j]]

        # 모든 연도를 한 번에 표시
        for (x, y), periods in position_periods.items():
            keyword_at_position = None
            for keyword, trajectory in keyword_trajectories.items():
                if (x, y) in trajectory:
                    keyword_at_position = keyword
                    break
            
            # 키워드와 연도를 함께 표시
            label = f"{keyword_at_position}: " + ', '.join(map(str, periods))
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

        try:
            plt.savefig(graph_path, dpi=600, bbox_inches='tight')
        except:
            plt.savefig(graph_path, dpi=300, bbox_inches='tight')

        plt.close()
    
    def animate_keyword_movements(self, df,  gif_filename='keyword_movements.gif', x_axis_name='X-Axis', y_axis_name='Y-Axis', base_size=2, size_increment=2, frames_between_periods=3, duration = 1000):
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
            for period in df.columns:
                quadrant = df.loc[keyword, period]
                position = get_position(quadrant, size)  # 크기를 포지션에 반영
                keyword_positions[keyword].append(position)

        # 색상 팔레트 생성
        num_keywords = len(df.index)
        colors = sns.color_palette("husl", num_keywords)
        
        # GIF로 저장할 프레임 리스트
        frames = []
        
        # 중간 프레임 생성
        for t in range(len(df.columns) - 1):
            period = df.columns[t]
            next_period = df.columns[t + 1]
            
            for frame in range(frames_between_periods):
                plt.figure(figsize=(18, 18))  # 그래프 크기를 더 크게 설정
                
                # 4분면의 선 그리기
                plt.axhline(0, color='black', linewidth=1)
                plt.axvline(0, color='black', linewidth=1)
                
                # 각 키워드의 현재 위치와 다음 위치 사이의 중간 위치 계산 및 시각화
                for i, keyword in enumerate(keyword_positions.keys()):
                    x_start, y_start = keyword_positions[keyword][t]
                    x_end, y_end = keyword_positions[keyword][t + 1]
                    
                    # 중간 위치 계산
                    x = x_start + (x_end - x_start) * (frame / frames_between_periods)
                    y = y_start + (y_end - y_start) * (frame / frames_between_periods)
                    
                    plt.scatter(x, y, label=keyword, color=colors[i], alpha=0.75)
                    label = f"{keyword} ({period})"
                    plt.text(x, y, label, fontsize=6, ha='center', va='center')

                # 각 사분면의 이름을 그래프 바깥쪽에 설정
                plt.text(max_size * 1.1, max_size * 1.1, 'Strong Signal', fontsize=14, ha='center', va='center', color='black')
                plt.text(-max_size * 1.1, max_size * 1.1, 'Weak Signal', fontsize=14, ha='center', va='center', color='black')
                plt.text(-max_size * 1.1, -max_size * 1.1, 'Latent Signal', fontsize=14, ha='center', va='center', color='black')
                plt.text(max_size * 1.1, -max_size * 1.1, 'Well-Known Signal', fontsize=14, ha='center', va='center', color='black')

                # 그래프 설정
                plt.title(f'KEMKIM Keyword Movements ({period})', fontsize=18)
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

    def _initialize_period_divided_dic(self, period_divided_group):
        period_divided_dic = {}

        # 그룹화된 데이터 처리
        for group_name, group_data in period_divided_group:
            period_divided_dic[str(group_name)] = group_data[self.textColumn_name].tolist()

        return period_divided_dic

    def _generate_period_divided_dic(self, period_divided_dic_raw):
        period_divided_dic = {}
        for key, string_list in period_divided_dic_raw.items():
            word_lists = []
            for string in string_list:
                try:
                    words = string.split(', ')
                    word_lists.append(words)
                except:
                    pass
            period_divided_dic[key] = word_lists
        return period_divided_dic

    def _merge_period_divided_dic(self, period_divided_dic):
        return {key: [item for sublist in value for item in sublist] for key, value in period_divided_dic.items()}

    # self.topword 개의 top common words 뽑아냄
    def _extract_top_common_words(self, period_divided_dic_merged):
        return {k: [item for item, count in Counter(v).most_common(self.topword)] for k, v in period_divided_dic_merged.items()}

    def _get_keyword_list(self, top_common_words):
        if not top_common_words:
            return []

            # 첫 번째 리스트를 set으로 변환하여 초기화
        common_elements = set(top_common_words[list(top_common_words.keys())[0]])

        # 딕셔너리의 각 value 리스트와 교집합을 구함
        for key in top_common_words:
            common_elements.intersection_update(top_common_words[key])

        # 길이가 2 이상인 단어만 필터링하여 리스트로 반환
        return [word for word in common_elements if len(word) >= 2]

    def _create_output_directories(self):
        article_kimkem_folder = self.kimkem_folder_path
        self.data_folder = os.path.join(article_kimkem_folder, "Data")
        self.tf_folder = os.path.join(self.data_folder, "TF")
        self.df_folder = os.path.join(self.data_folder, "DF")
        self.DoV_folder = os.path.join(self.data_folder, "DoV")
        self.DoD_folder = os.path.join(self.data_folder, "DoD")
        self.result_folder = os.path.join(article_kimkem_folder, "Result")
        self.trace_folder = os.path.join(article_kimkem_folder, "Trace")
        self.trace_result_folder = os.path.join(self.trace_folder, 'Trace_Result')
        self.trace_data_folder = os.path.join(self.trace_folder, 'Trace_Data')
        self.trace_DOV_folder = os.path.join(self.trace_data_folder, 'DoV')
        self.trace_DOD_folder = os.path.join(self.trace_data_folder, 'DoD')

        # Final
        os.makedirs(self.tf_folder, exist_ok=True)
        os.makedirs(self.df_folder, exist_ok=True)
        os.makedirs(self.DoV_folder, exist_ok=True)
        os.makedirs(self.DoD_folder, exist_ok=True)
        os.makedirs(self.result_folder, exist_ok=True)
        os.makedirs(os.path.join(self.result_folder, 'Graph'))
        os.makedirs(os.path.join(self.result_folder, 'Signal'))

        # Trace
        os.makedirs(self.trace_folder, exist_ok=True)
        os.makedirs(self.trace_result_folder, exist_ok=True)
        os.makedirs(self.trace_data_folder, exist_ok=True)
        os.makedirs(self.trace_DOV_folder, exist_ok=True)
        os.makedirs(self.trace_DOD_folder, exist_ok=True)

        for period in self.period_list:
            period_path = os.path.join(self.trace_result_folder, period)
            os.makedirs(period_path, exist_ok=True)
            os.makedirs(os.path.join(period_path, 'Graph'), exist_ok=True)
            os.makedirs(os.path.join(period_path, 'Signal'), exist_ok=True)

    def _save_kimkem_results(self, tf_counts, df_counts, DoV_dict, DoD_dict):
        for period in tf_counts:
            self._save_period_data(self.tf_folder, period, tf_counts, 'TF')
            self._save_period_data(self.df_folder, period, df_counts, 'DF')
            self._save_period_data(self.DoV_folder, period, DoV_dict, 'DoV')
            self._save_period_data(self.DoD_folder, period, DoD_dict, 'DoD')

        if self.ani_option == True:
            self.create_top_words_animation(tf_counts, os.path.join(self.tf_folder, 'tf_counts_animation.gif'), self.graph_wordcnt)
            self.create_top_words_animation(df_counts, os.path.join(self.df_folder, 'df_counts_animation.gif'), self.graph_wordcnt)
            self.create_top_words_animation(DoV_dict, os.path.join(self.DoV_folder, 'DOV_animation.gif'), self.graph_wordcnt, 100)
            self.create_top_words_animation(DoD_dict, os.path.join(self.DoD_folder, 'DOD_animation.gif'), self.graph_wordcnt, 100)

    # 시그널 추적 데이터 저장
    def _save_trace_results(self, DoV_dict, DoD_dict):
        for period in DoV_dict:
            self._save_period_data(self.trace_DOV_folder, period, DoV_dict, 'DoV')
            self._save_period_data(self.trace_DOD_folder, period, DoD_dict, 'DoD')

    def _save_period_data(self, folder, period, data_dict, label):
        data_df = pd.DataFrame(list(data_dict[period].items()), columns=['keyword', label])
        data_df.to_csv(f"{folder}/{period}_{label}.csv", index=False, encoding='utf-8-sig')

    # DOV/DOD 평균 증가율(y값), TF/DF 평균값(x값) 계산
    def _calculate_averages(self, keyword_list, DoV_dict, DoD_dict, tf_counts, df_counts, min_period, max_period):
        period_diff = self.period_list.index(max_period) - self.period_list.index(min_period)

        avg_DoV_increase_rate = {}
        avg_DoD_increase_rate = {}
        avg_term_frequency = {}
        avg_doc_frequency = {}

        for word in keyword_list:
            # 미리 필요한 계산들을 변수로 저장
            min_DoV, max_DoV = DoV_dict[min_period].get(word, 0), DoV_dict[max_period].get(word, 0)
            min_DoD, max_DoD = DoD_dict[min_period].get(word, 0), DoD_dict[max_period].get(word, 0)

            avg_DoV_increase_rate[word] = self._calculate_average_increase(min_DoV, max_DoV, period_diff)
            avg_DoD_increase_rate[word] = self._calculate_average_increase(min_DoD, max_DoD, period_diff)
            avg_term_frequency[word] = self._calculate_average_frequency(tf_counts, word, min_period, max_period)
            avg_doc_frequency[word] = self._calculate_average_frequency(df_counts, word, min_period, max_period)

        return avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency

    def _calculate_average_increase(self, min_value, max_value, period_diff):
        if min_value <= 0 or max_value <= 0:  # 방어적 조건 검사 강화
            return 0
        exponent = 1 / period_diff
        growth_rate = (max_value / min_value) ** exponent
        return (growth_rate - 1) * 100

    def _calculate_average_frequency(self, counts_dict, word, min_period, max_period):
        # 딕셔너리 접근 횟수를 줄이기 위해 중복 get 호출을 제거
        min_count = counts_dict[min_period].get(word, 0)
        max_count = counts_dict[max_period].get(word, 0)
        return (min_count + max_count) * 0.5  # / 2 대신 * 0.5로 연산 최적화

    # 그래프 생성 / 시그널 분석
    def _analyze_signals(self, avg_DoV_increase_rate, avg_DoD_increase_rate, avg_term_frequency, avg_doc_frequency, folder_path):
        DoV_signal, DoV_coordinates = self.DoV_draw_graph(avg_DoV_increase_rate, avg_term_frequency, folder_path)
        DoD_signal, DoD_coordinates = self.DoD_draw_graph(avg_DoD_increase_rate, avg_doc_frequency, folder_path)

        # 파이널 시그널 추출 후 DOV/DOD 그래프에 예외어 리스트를 넣어서 KIM/KEM 그래프 생성
        final_signal = self._get_communal_signals(DoV_signal, DoD_signal)
        final_signal_list = []
        for value in final_signal.values():
            final_signal_list.extend(value)

        if len(final_signal_list) == 0:
            with open(os.path.join(folder_path, 'No_Signal.txt'), 'w') as f:
                f.write("Final Signal이 존재하지 않습니다")
        else:
            self.DoV_draw_graph(avg_DoV_increase_rate, avg_term_frequency, folder_path, final_signal_list=final_signal_list, graph_name='KEM_graph.png')
            self.DoD_draw_graph(avg_DoD_increase_rate, avg_doc_frequency, folder_path, final_signal_list=final_signal_list, graph_name='KIM_graph.png')

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

    def divide_period(self, csv_data, period):
        # 'Unnamed' 열 제거
        csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]

        # 날짜 열을 datetime 형식으로 변환
        csv_data[self.dateColumn_name] = pd.to_datetime(csv_data[self.dateColumn_name].str.split().str[0], format='%Y-%m-%d', errors='coerce')

        # 'YYYYMMDD' 형식의 문자열을 datetime 형식으로 변환
        start_date = pd.to_datetime(str(self.startdate), format='%Y%m%d')
        end_date = pd.to_datetime(str(self.enddate), format='%Y%m%d')

        # 날짜 범위 필터링
        csv_data = csv_data[csv_data[self.dateColumn_name].between(start_date, end_date)]

        if start_date < csv_data[self.dateColumn_name].min():
            self.startdate = int(csv_data[self.dateColumn_name].min().strftime('%Y%m%d'))

        if end_date > csv_data[self.dateColumn_name].max():
            self.enddate = int(csv_data[self.dateColumn_name].max().strftime('%Y%m%d'))

        # 'period_month' 열 추가 (월 단위 기간으로 변환)
        csv_data['period_month'] = csv_data[self.dateColumn_name].dt.to_period('M')

        # 필요한 전체 기간 생성
        full_range = pd.period_range(start=csv_data['period_month'].min(), end=csv_data['period_month'].max(), freq='M')
        full_df = pd.DataFrame(full_range, columns=['period_month'])

        # 원본 데이터와 병합하여 빈 기간도 포함하도록 함
        csv_data = pd.merge(full_df, csv_data, on='period_month', how='left')

        # 새로운 열을 추가하여 주기 단위로 기간을 그룹화
        if period == '1m':  # 월
            csv_data['period_group'] = csv_data['period_month'].astype(str)
        elif period == '3m':  # 분기
            csv_data['period_group'] = (csv_data['period_month'].dt.year.astype(str) + 'Q' + ((csv_data['period_month'].dt.month - 1) // 3 + 1).astype(str))
        elif period == '6m':  # 반기
            csv_data['period_group'] = (csv_data['period_month'].dt.year.astype(str) + 'H' + ((csv_data['period_month'].dt.month - 1) // 6 + 1).astype(str))
        elif period == '1y':  # 연도
            csv_data['period_group'] = csv_data['period_month'].dt.year.astype(str)
        elif period == '1w':  # 주
            csv_data['period_group'] = csv_data[self.dateColumn_name].dt.to_period('W').apply(
                lambda x: f"{x.start_time.strftime('%Y%m%d')}-{x.end_time.strftime('%Y%m%d')}"
            )
            first_date = csv_data['period_group'].iloc[0].split('-')[0]
            end_date = csv_data['period_group'].iloc[-1].split('-')[1]
            self.startdate = first_date
            self.enddate = end_date
        elif period == '1d':  # 일
            csv_data['period_group'] = csv_data[self.dateColumn_name].dt.to_period('D').astype(str)

        # 주기별로 그룹화하여 결과 반환
        period_divided_group = csv_data.groupby('period_group')

        return period_divided_group

    def create_top_words_animation(self, dataframe, output_filename='top_words_animation.gif', word_cnt=10, scale_factor=1, frames_per_transition=20):
        df = pd.DataFrame(dataframe).fillna(0)
    
        # 연도별로 상위 word_cnt개 단어를 추출
        top_words_per_period = {}
        for period in df.columns:
            top_words_per_period[period] = df[period].nlargest(word_cnt).sort_values(ascending=True)

        # 색상 팔레트 설정 (세련된 색상)
        colors = sns.color_palette("husl", word_cnt)

        # 애니메이션 초기 설정
        fig, ax = plt.subplots(figsize=(10, 6))

        # 보간 함수 생성
        def interpolate(start, end, num_steps):
            return np.linspace(start, end, num_steps)

        def animate(i):
            period_idx = i // frames_per_transition
            period = list(top_words_per_period.keys())[period_idx]
            next_period_idx = period_idx + 1 if period_idx + 1 < len(top_words_per_period) else period_idx
            next_period = list(top_words_per_period.keys())[next_period_idx]

            start_data = top_words_per_period[period]
            end_data = top_words_per_period[next_period]

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
            ax.set_title(f'Top {word_cnt} Keywords in {period}', fontsize=16)
            ax.set_xlabel('Frequency', fontsize=14)
            ax.set_ylabel('Keywords', fontsize=14)
            plt.box(False)

        # GIF로 저장 (메모리 내에서 처리하여 속도 향상)
        frames = []
        
        for i in range((len(top_words_per_period) - 1) * frames_per_transition):
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
    def cal_tf(self, keyword_list, period_divided_dic_merged):
        tf_counts = {}

        # tqdm을 사용하여 진행 바 추가
        keyword_set = set(keyword_list)  # 키워드 리스트를 set으로 변환하여 검색 시간 단축
        for key, value in tqdm(period_divided_dic_merged.items(), desc="TF ", file=sys.stdout,
                               bar_format="{l_bar}{bar}|", ascii=' ='):
            value_counter = Counter([word for word in value if word in keyword_set])  # 키워드만 카운팅

            # 내림차순으로 정렬
            keyword_counts = dict(sorted(value_counter.items(), key=lambda x: x[1], reverse=True))

            tf_counts[key] = keyword_counts

        return tf_counts
    # 연도별 keyword df 딕셔너리 반환
    def cal_df(self, keyword_list, period_divided_dic):
        df_counts = {}
        keyword_set = set(keyword_list)  # 키워드 리스트를 set으로 변환하여 검색 시간 단축

        # tqdm을 사용하여 전체 기간에 대한 진행 상태 표
        for period in tqdm(period_divided_dic, desc="DF ", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' ='):
            docs = period_divided_dic[period]

            # 각 키워드가 문서에 등장하는지 여부를 저장하는 Counter 사용
            doc_counter = Counter()
            for doc in docs:
                found_keywords = keyword_set.intersection(doc)  # 키워드 목록에 있는 단어들만 찾음
                for keyword in found_keywords:
                    doc_counter[keyword] += 1

            # 내림차순으로 정렬
            keyword_counts = dict(sorted(doc_counter.items(), key=lambda x: x[1], reverse=True))

            df_counts[period] = keyword_counts

        return df_counts

    # 연도별 keyword DoV 딕셔너리 반환
    def cal_DoV(self, keyword_list, period_divided_dic, tf_counts, trace=True):
        DoV_dict = {}
        for period in tqdm(period_divided_dic, desc="DOV ", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' ='):
            keyword_DoV_dic = {}
            
            n_j = 1 if trace else self.find_key_position(period_divided_dic, self.lastperiod) - self.find_key_position(period_divided_dic, period)

            for keyword in keyword_list:
                value = (tf_counts[period][keyword] / len(period_divided_dic[period])) * (1 - self.weight * n_j)
                keyword_DoV_dic[keyword] = value
            DoV_dict[period] = keyword_DoV_dic
        return DoV_dict

    # 연도별 keyword DoD 딕셔너리 반환
    def cal_DoD(self, keyword_list, period_divided_dic, df_counts, trace=True):
        DoD_dict = {}
        for period in tqdm(period_divided_dic, desc="DOD ", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' ='):
            keyword_DoV_dic = {}
            
            n_j = 1 if trace else self.find_key_position(period_divided_dic, self.lastperiod) - self.find_key_position(period_divided_dic, period)
            
            for keyword in keyword_list:
                value = (df_counts[period][keyword] / len(period_divided_dic[period])) * (1 - self.weight * n_j)
                keyword_DoV_dic[keyword] = value
            DoD_dict[period] = keyword_DoV_dic
        return DoD_dict

    def top_n_percent(self, lst, n):
        if not lst:
            return None  # 빈 리스트가 입력될 경우 None 반환

        if n <= 0:
            return None  # n이 0이거나 음수일 경우 None 반환

        sorted_lst = sorted(lst, reverse=True)  # 내림차순으로 정렬
        threshold_index = max(0, int(len(sorted_lst) * n / 100) - 1)  # n%에 해당하는 인덱스 계산

        return sorted_lst[threshold_index]  # 상위 n%에 가장 가까운 요소 반환

    def calculate_statistics(self, data):

        def calculate_skewness(data):
            n = len(data)
            mean = sum(data) / n
            std_dev = (sum((x - mean) ** 2 for x in data) / n) ** 0.5

            skewness = (n / ((n - 1) * (n - 2))) * sum(((x - mean) / std_dev) ** 3 for x in data)
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
        deciles = {f"{i*10}%": round(np.percentile(sorted_data, i*10), 3) for i in range(1, 10)}
        # 딕셔너리에 10분위값 추가
        result.update(deciles)

        return result
    
    def DoV_draw_graph(self, avg_DoV_increase_rate=None, avg_term_frequency=None, graph_folder=None, final_signal_list = [], graph_name = '', redraw_option = False, coordinates=False, graph_size=None, eng_keyword_list = []):
        if redraw_option == False:
            x_data = self.calculate_statistics(list(avg_term_frequency.values()))
            y_data = self.calculate_statistics(list(avg_DoV_increase_rate.values()))
            match self.split_option:
                case '평균(Mean)':
                    graph_term = x_data['mean']  # x축, 평균 단어 빈도
                    graph_DoV = y_data['mean'] # y축, 평균 증가율
                case '중앙값(Median)':
                    graph_term = x_data['median'] # x축, 중앙값 단어 빈도
                    graph_DoV = y_data['median'] # y축, 중앙값 증가율
                case '직접 입력: 상위( )%':
                    graph_term = self.top_n_percent(list(avg_term_frequency.values()), self.split_custom)  # x축, 평균 단어 빈도
                    graph_DoV = self.top_n_percent(list(avg_DoV_increase_rate.values()), self.split_custom)  # y축, 평균 증가율
            
            with open(os.path.join(graph_folder, "DOV_statistics.csv"), 'w', newline='') as csvfile:
                fieldnames = ['index', 'x', 'y']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # 헤더 작성
                writer.writeheader()
                
                # 키를 기준으로 두 딕셔너리를 반복하며 행 작성
                for key in x_data.keys():
                    writer.writerow({'index': key, 'x': x_data[key], 'y': y_data[key]})
            
            coordinates = {}
            coordinates['axis'] = (graph_term, graph_DoV)

            for key in avg_DoV_increase_rate:
                coordinates[key] = (avg_term_frequency[key], avg_DoV_increase_rate[key])
        else:
            graph_term = coordinates['axis'][0]
            graph_DoV = coordinates['axis'][1]
            
        coordinates = {k: v for k, v in coordinates.items() if k not in self.exception_word_list}
        coordinates = {key: coordinates[key] for key in sorted(coordinates)}

        if eng_keyword_list != []:
            korean_to_english = {korean: english for korean, english in eng_keyword_list}
            coordinates = {korean_to_english.get(k, k): v for k, v in coordinates.items()}

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

        plt.tick_params(axis='both', which='major', labelsize=gradesize)  # 눈금 글자 크기를 30으로 설정 (원하는 크기로 조정 가능)
        plt.axvline(x=graph_term, color='k', linestyle='--')  # x축 수직선
        plt.axhline(y=graph_DoV, color='k', linestyle='--')  # y축 수평선

        strong_signal = sorted([word for word in coordinates if coordinates[word][0] >= graph_term and coordinates[word][1] >= graph_DoV])
        weak_signal = sorted([word for word in coordinates if coordinates[word][0] <= graph_term and coordinates[word][1] >= graph_DoV])
        latent_signal = sorted([word for word in coordinates if coordinates[word][0] <= graph_term and coordinates[word][1] <= graph_DoV])
        well_known_signal = sorted([word for word in coordinates if coordinates[word][0] >= graph_term and coordinates[word][1] <= graph_DoV])
        
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
            graph_name = "TF_DOV_graph.png"

        plt.savefig(os.path.join(graph_folder, graph_name), bbox_inches='tight')
        plt.close()
        
        coordinates_df = pd.DataFrame([(k, v) for k, v in coordinates.items()], columns=['key', 'value'])
        coordinates_df.to_csv(os.path.join(graph_folder, "DOV_coordinates.csv"), index=False, encoding='utf-8-sig')

        return {'strong_signal': strong_signal, "weak_signal": weak_signal, "latent_signal": latent_signal, "well_known_signal": well_known_signal}, coordinates

    def DoD_draw_graph(self, avg_DoD_increase_rate=None, avg_doc_frequency=None, graph_folder=None, final_signal_list = [], graph_name='', redraw_option=False, coordinates=None, graph_size=None, eng_keyword_list = []):
        if redraw_option == False:
            x_data = self.calculate_statistics(list(avg_doc_frequency.values()))
            y_data = self.calculate_statistics(list(avg_DoD_increase_rate.values()))
            match self.split_option:
                case '평균(Mean)':
                    graph_doc = x_data['mean']  # x축, 평균 단어 빈도
                    graph_DoD = y_data['mean'] # y축, 평균 증가율
                case '중앙값(Median)':
                    graph_doc = x_data['median'] # x축, 평균 단어 빈도
                    graph_DoD = y_data['median'] # y축, 평균 증가율
                case '직접 입력: 상위( )%':
                    graph_doc = self.top_n_percent(list(avg_doc_frequency.values()), self.split_custom)  # x축, 평균 단어 빈도
                    graph_DoD = self.top_n_percent(list(avg_DoD_increase_rate.values()), self.split_custom)  # y축, 평균 증가율

            with open(os.path.join(graph_folder, "DOD_statistics.csv"), 'w', newline='') as csvfile:
                fieldnames = ['index', 'x', 'y']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # 헤더 작성
                writer.writeheader()
                
                # 키를 기준으로 두 딕셔너리를 반복하며 행 작성
                for key in x_data.keys():
                    writer.writerow({'index': key, 'x': x_data[key], 'y': y_data[key]})
            
            coordinates = {}
            coordinates['axis'] = (graph_doc, graph_DoD)

            for key in avg_DoD_increase_rate:
                coordinates[key] = (avg_doc_frequency[key], avg_DoD_increase_rate[key])
        else:
            graph_doc = coordinates['axis'][0]
            graph_DoD = coordinates['axis'][1]
        
        coordinates = {k: v for k, v in coordinates.items() if k not in self.exception_word_list}
        coordinates = {key: coordinates[key] for key in sorted(coordinates)}

        if eng_keyword_list != []:
            korean_to_english = {korean: english for korean, english in eng_keyword_list}
            coordinates = {korean_to_english.get(k, k): v for k, v in coordinates.items()}

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

        plt.tick_params(axis='both', which='major', labelsize=gradesize)  # 눈금 글자 크기를 30으로 설정 (원하는 크기로 조정 가능)
        plt.axvline(x=graph_doc, color='k', linestyle='--')  # x축 중앙값 수직선
        plt.axhline(y=graph_DoD, color='k', linestyle='--')  # y축 중앙값 수평선

        strong_signal = sorted([word for word in coordinates if coordinates[word][0] >= graph_doc and coordinates[word][1] >= graph_DoD])
        weak_signal = sorted([word for word in coordinates if coordinates[word][0] <= graph_doc and coordinates[word][1] >= graph_DoD])
        latent_signal = sorted([word for word in coordinates if coordinates[word][0] <= graph_doc and coordinates[word][1] <= graph_DoD])
        well_known_signal = sorted([word for word in coordinates if coordinates[word][0] >= graph_doc and coordinates[word][1] <= graph_DoD])

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
            graph_name = "DF_DOD_graph.png"

        plt.savefig(os.path.join(graph_folder, graph_name), bbox_inches='tight')
        plt.close()

        if final_signal_list == []:
            coordinates_df = pd.DataFrame([(k, v) for k, v in coordinates.items()], columns=['key', 'value'])
            coordinates_df.to_csv(os.path.join(graph_folder, "DOD_coordinates.csv"), index=False, encoding='utf-8-sig')

        return {'strong_signal': strong_signal, "weak_signal": weak_signal, "latent_signal": latent_signal, "well_known_signal": well_known_signal}, coordinates

if __name__=='__main__':
    token_data = pd.read_csv("/Users/yojunsmacbookprp/Desktop/BIGMACLAB_MANAGER/navernews_바이오의료_20100101_20240731_0815_2036/token_data/token_navernews_바이오의료_20100101_20240731_0815_2036_article.csv", low_memory=False, encoding='utf-8-sig')
    kimkem_obj = KimKem(token_data=token_data, 
                        csv_name='navernews_바이오의료_20100101_20240731_0815_2036_article.csv', 
                        save_path='C:/BIGMACLAB_MANAGER/바이오의료 KIMKEM 데이터',
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