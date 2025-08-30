import asyncio
import warnings
from PyQt5.QtWidgets import QMessageBox
import pandas as pd
import sys
import matplotlib.pyplot as plt
import seaborn as sns
import platform
from wordcloud import WordCloud
from collections import Counter
import os
import csv
from googletrans import Translator
from tqdm import tqdm
from ui.status import printStatus
from PIL import Image
from core.setting import get_setting
import re
from libs.path import safe_path

Image.MAX_IMAGE_PIXELS = None  # 크기 제한 해제
warnings.filterwarnings("ignore")

# 운영체제에 따라 한글 폰트를 설정
if platform.system() == 'Darwin':  # macOS
    plt.rcParams['font.family'] = 'AppleGothic'
elif platform.system() == 'Windows':  # Windows
    plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕 폰트 사용

# 폰트 설정 후 음수 기호가 깨지는 것을 방지
plt.rcParams['axes.unicode_minus'] = False


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

        data[word] = pd.to_datetime(
            data[word], format='%Y-%m-%d', errors='coerce')

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
            group_data.to_csv(f"{data_path}/{folder_name}/{tablename+'_'+str(group_name)}.csv",
                              index=False, encoding='utf-8-sig', header=True)

        # 정보 파일 생성
        info_df = pd.DataFrame(list(info.items()), columns=[
                               info_label, 'Count'])
        info_df.to_csv(f"{data_path}/{folder_name}/{folder_name} Count.csv",
                       index=False, encoding='utf-8-sig', header=True)

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
        plt.savefig(
            f"{data_path}/{folder_name}/{folder_name} Graph.png", bbox_inches='tight')

    def calculate_figsize(self, data_length, base_width=12, height=6, max_width=50):
        # Increase width proportionally to the number of data points, but limit the maximum width
        width = min(base_width + (data_length / 20), max_width)
        return (width, height)

    def NaverNewsArticleAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))
            
        if 'Article Press' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning",
                                f"NaverNews Article CSV 형태와 일치하지 않습니다")
            return

        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(
            data['Article Date'], errors='coerce')
        # 'Article ReplyCnt' 열을 숫자로 변환하고, 변환이 안 되는 값은 NaN으로 처리
        data['Article ReplyCnt'] = pd.to_numeric(
            data['Article ReplyCnt'], errors='coerce').fillna(0)

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 시간에 따른 기사 및 댓글 수 분석
        time_analysis = data.groupby(data['Article Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'}).reset_index()
        time_analysis['Article Date'] = time_analysis['Article Date'].dt.to_timestamp()

        # 시간에 따른 기사 및 댓글 수 분석 (일별)
        day_analysis = data.groupby(data['Article Date'].dt.to_period("D")).agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'}).reset_index()
        day_analysis['Article Date'] = day_analysis['Article Date'].dt.to_timestamp()

        # 기사 유형별 분석
        article_type_analysis = data.groupby('Article Type').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'}).reset_index()

        # 언론사별 분석 (상위 10개 언론사만)
        top_10_press = data['Article Press'].value_counts().head(10).index
        press_analysis = data[data['Article Press'].isin(top_10_press)].groupby('Article Press').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'}).reset_index()

        # 상관관계 분석 (숫자형 컬럼만 선택)
        numeric_columns = ['Article ReplyCnt']
        correlation_matrix = data[numeric_columns].corr()

        # 시각화 및 분석 결과 저장 디렉토리 설정
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(
            csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(
            csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig', index=False)
        day_analysis.to_csv(os.path.join(
            csv_output_dir, "day_analysis.csv"), encoding='utf-8-sig', index=False)
        article_type_analysis.to_csv(os.path.join(csv_output_dir, "article_type_analysis.csv"), encoding='utf-8-sig',
                                     index=False)
        press_analysis.to_csv(os.path.join(
            csv_output_dir, "press_analysis.csv"), encoding='utf-8-sig', index=False)
        # correlation_matrix.to_csv(os.path.join(output_dir, "correlation_matrix.csv"), encoding='utf-8-sig', index=False)

        # For time_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(time_analysis)))
        sns.lineplot(data=time_analysis, x='Article Date',
                     y='Article Count', label='Article Count')
        sns.lineplot(data=time_analysis, x='Article Date',
                     y='Article ReplyCnt', label='Reply Count')
        plt.title('Monthly Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "monthly_article_reply_count.png"))
        plt.close()

        # For day_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(day_analysis)))
        sns.lineplot(data=day_analysis, x='Article Date',
                     y='Article Count', label='Article Count')
        sns.lineplot(data=day_analysis, x='Article Date',
                     y='Article ReplyCnt', label='Reply Count')
        plt.title('Daily Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "daily_article_reply_count.png"))
        plt.close()

        # For article_type_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(article_type_analysis)))
        article_type_analysis = article_type_analysis.sort_values(
            'Article Count', ascending=False)
        sns.barplot(x='Article Type', y='Article Count',
                    data=article_type_analysis, palette="viridis")
        plt.title('Article Count by Type')
        plt.xlabel('Article Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_type_count.png"))
        plt.close()

        # For press_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(press_analysis)))
        press_analysis = press_analysis.sort_values(
            'Article Count', ascending=False)
        sns.barplot(x='Article Press', y='Article Count',
                    data=press_analysis, palette="plasma")
        plt.title('Top 10 Press by Article Count')
        plt.xlabel('Press')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "press_article_count.png"))
        plt.close()

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
        
        4. 일별 기사 및 댓글 수 분석 (daily_article_reply_count.png):
           - 이 선 그래프는 시간에 따른 일별 기사 수와 댓글 수를 보여줍니다.
           - x축은 날짜를, y축은 수량을 나타냅니다.
           - 특정 일에 기사 및 댓글 수가 급증하는 패턴을 파악하는 데 유용합니다.
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(safe_path(description_file_path), 'w', encoding="utf-8", errors="ignore") as file:
            file.write(description_text)

    def NaverNewsStatisticsAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))
        
        if 'Male' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning",
                                f"NaverNews Statistics CSV 형태와 일치하지 않습니다")
            return

        # 'Article Date'를 datetime 형식으로 변환 (오류 발생 시 NaT로 변환)
        data['Article Date'] = pd.to_datetime(
            data['Article Date'], errors='coerce')

        # 'Article ReplyCnt'를 숫자(float)로 변환
        data['Article ReplyCnt'] = pd.to_numeric(
            data['Article ReplyCnt'], errors='coerce').fillna(0)

        # 백분율 값을 실제 댓글 수로 변환하기 전에 각 열을 숫자로 변환하고, 변환 불가 시 0으로 채움
        for col in ['Male', 'Female', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y']:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
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
        }).rename(columns={'id': 'Article Count'}).reset_index()
        time_analysis['Article Date'] = time_analysis['Article Date'].dt.to_timestamp()

        # 시간에 따른 기사 및 댓글 수 분석 (일별)
        day_analysis = data.groupby(data['Article Date'].dt.to_period("D")).agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'}).reset_index()
        day_analysis['Article Date'] = day_analysis['Article Date'].dt.to_timestamp()

        # 기사 유형별 분석
        article_type_analysis = data.groupby('Article Type').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'}).reset_index()

        # 언론사별 분석 (상위 10개 언론사만)
        top_10_press = data['Article Press'].value_counts().head(10).index
        press_analysis = data[data['Article Press'].isin(top_10_press)].groupby('Article Press').agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'}).reset_index()

        # 상관관계 분석 (숫자형 컬럼만 선택)
        numeric_columns = ['Article ReplyCnt', 'Male',
                           'Female', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y']
        correlation_matrix = data[numeric_columns].corr()

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(
            csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(
            csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig', index=False)
        day_analysis.to_csv(os.path.join(
            csv_output_dir, "day_analysis.csv"), encoding='utf-8-sig', index=False)
        article_type_analysis.to_csv(os.path.join(csv_output_dir, "article_type_analysis.csv"), encoding='utf-8-sig',
                                     index=False)
        press_analysis.to_csv(os.path.join(
            csv_output_dir, "press_analysis.csv"), encoding='utf-8-sig', index=False)
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig',
                                  index=False)

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 월별 기사 및 댓글 수 추세
        plt.figure(figsize=self.calculate_figsize(len(time_analysis)))
        sns.lineplot(data=time_analysis, x='Article Date',
                     y='Article Count', label='Article Count')
        sns.lineplot(data=time_analysis, x='Article Date',
                     y='Article ReplyCnt', label='Reply Count')
        plt.title('Monthly Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "monthly_article_reply_count.png"))
        plt.close()

        # For day_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(day_analysis)))
        sns.lineplot(data=day_analysis, x='Article Date',
                     y='Article Count', label='Article Count')
        sns.lineplot(data=day_analysis, x='Article Date',
                     y='Article ReplyCnt', label='Reply Count')
        plt.title('Daily Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "daily_article_reply_count.png"))
        plt.close()

        # 2. 기사 유형별 기사 및 댓글 수
        plt.figure(figsize=self.calculate_figsize(len(article_type_analysis)))
        article_type_analysis = article_type_analysis.sort_values(
            'Article Count', ascending=False)
        sns.barplot(x='Article Type', y='Article Count',
                    data=article_type_analysis, palette="viridis")
        plt.title('Article Count by Type')
        plt.xlabel('Article Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_type_count.png"))
        plt.close()

        # 3. 상위 10개 언론사별 기사 및 댓글 수
        plt.figure(figsize=self.calculate_figsize(len(press_analysis)))
        press_analysis = press_analysis.sort_values(
            'Article Count', ascending=False)
        sns.barplot(x='Article Press', y='Article Count',
                    data=press_analysis, palette="plasma")
        plt.title('Top 10 Press by Article Count')
        plt.xlabel('Press')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "press_article_count.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        plt.figure(figsize=self.calculate_figsize(
            len(correlation_matrix), height=8))
        sns.heatmap(correlation_matrix, annot=True,
                    cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 성별 댓글 수 분석
        gender_reply_count = {
            'Male': data['Male'].sum(), 'Female': data['Female'].sum()}
        gender_reply_df = pd.DataFrame(list(gender_reply_count.items()), columns=[
                                       'Gender', 'Reply Count'])
        plt.figure(figsize=self.calculate_figsize(
            len(gender_reply_df), base_width=8))
        sns.barplot(x='Gender', y='Reply Count',
                    data=gender_reply_df, palette="pastel")
        plt.title('Total Number of Replies by Gender')
        plt.xlabel('Gender')
        plt.ylabel('Reply Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "gender_reply_count.png"))
        plt.close()
        gender_reply_df.to_csv(os.path.join(csv_output_dir, "gender_reply_count.csv"), index=False,
                               encoding='utf-8-sig')

        # 6. 연령대별 댓글 수 분석
        age_group_reply_count = {age: data[age].sum() for age in [
            '10Y', '20Y', '30Y', '40Y', '50Y', '60Y']}
        age_group_reply_df = pd.DataFrame(list(age_group_reply_count.items()), columns=[
                                          'Age Group', 'Reply Count'])
        plt.figure(figsize=self.calculate_figsize(
            len(age_group_reply_df), base_width=10))
        sns.barplot(x='Age Group', y='Reply Count',
                    data=age_group_reply_df, palette="coolwarm")
        plt.title('Total Number of Replies by Age Group')
        plt.xlabel('Age Group')
        plt.ylabel('Reply Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "age_group_reply_count.png"))
        plt.close()
        age_group_reply_df.to_csv(os.path.join(csv_output_dir, "age_group_reply_count.csv"), index=False,
                                  encoding='utf-8-sig')

        # 그래프 설명 작성 (한국어)
        description_text = """
        그래프 설명:

        1. 월별 기사 및 댓글 수 추세 (monthly_article_reply_count.png):
           - 월별 기사 수와 댓글 수의 변화를 보여줍니다.

        2. 기사 유형별 기사 및 댓글 수 (article_type_count.png):
           - 기사 유형별 기사의 수를 나타냅니다.

        3. 상위 10개 언론사별 기사 및 댓글 수 (press_article_count.png):
           - 상위 10개 언론사에서 작성한 기사 수를 나타냅니다.

        4. 상관관계 행렬 히트맵 (correlation_matrix.png):
           - 주요 지표들 간의 상관관계를 시각화한 히트맵입니다.

        5. 성별 댓글 수 분석 (gender_reply_count.png):
           - 남성과 여성의 총 댓글 수를 보여줍니다.

        6. 연령대별 댓글 수 분석 (age_group_reply_count.png):
           - 각 연령대별 총 댓글 수를 나타냅니다.
           
        7. 일별 기사 및 댓글 수 분석 (daily_article_reply_count.png):
           - 이 선 그래프는 시간에 따른 일별 기사 수와 댓글 수를 보여줍니다.
           - x축은 날짜를, y축은 수량을 나타냅니다.
           - 특정 일에 기사 및 댓글 수가 급증하는 패턴을 파악하는 데 유용합니다.
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(safe_path(description_file_path), 'w', encoding="utf-8", errors="ignore") as file:
            file.write(description_text)

    def NaverNewsReplyAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))
    
        if 'Reply Date' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning",
                                f"NaverNews Reply CSV 형태와 일치하지 않습니다")
            return

        # 'Reply Date'를 datetime 형식으로 변환
        data['Reply Date'] = pd.to_datetime(
            data['Reply Date'], errors='coerce')

        # 각 열을 숫자로 변환
        for col in ['Rereply Count', 'Reply Like', 'Reply Bad', 'Reply LikeRatio', 'Reply Sentiment']:
            data[col] = pd.to_numeric(data[col], errors='coerce')

        # Reply Text 열이 문자열이 아닌 값이 있거나 NaN일 경우 대비
        data['Reply Text'] = data['Reply Text'].astype(str).fillna('')

        # 댓글 길이 추가
        data['Reply Length'] = data['Reply Text'].apply(
            lambda x: len(x) if isinstance(x, str) else 0)

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 날짜별 댓글 수 분석
        time_analysis = data.groupby(data['Reply Date'].dt.date).agg({
            'id': 'count',
            'Reply Like': 'sum',
            'Reply Bad': 'sum'
        }).rename(columns={'id': 'Reply Count'})

        # 월별 댓글 수, 좋아요, 싫어요 합계 분석
        month_analysis = data.groupby(data['Reply Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Reply Like': 'sum',
            'Reply Bad': 'sum'
        }).rename(columns={'id': 'Reply Count'}).reset_index()
        month_analysis['Reply Date'] = month_analysis['Reply Date'].dt.to_timestamp()

        # 댓글 감성 분석 결과 빈도
        sentiment_counts = data['Reply Sentiment'].value_counts()

        # 상관관계 분석
        correlation_matrix = data[
            ['Reply Like', 'Reply Bad', 'Rereply Count', 'Reply LikeRatio', 'Reply Sentiment', 'Reply Length']].corr()

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
        basic_stats.to_csv(os.path.join(
            csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(
            csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig')
        month_analysis.to_csv(os.path.join(
            csv_output_dir, "month_analysis.csv"), encoding='utf-8-sig', index=False)
        sentiment_counts.to_csv(os.path.join(
            csv_output_dir, "sentiment_counts.csv"), encoding='utf-8-sig')
        correlation_matrix.to_csv(os.path.join(
            csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig')
        writer_reply_count.to_csv(os.path.join(
            csv_output_dir, "writer_reply_count.csv"), encoding='utf-8-sig')

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 날짜별 댓글 수 추세
        data_length = len(time_analysis)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.lineplot(data=time_analysis,
                     x=time_analysis.index, y='Reply Count')
        plt.title('Daily Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "daily_reply_count.png"))
        plt.close()

        # For month_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(month_analysis)))
        sns.lineplot(data=month_analysis, x='Reply Date',
                     y='Reply Count', label='Reply Count')
        sns.lineplot(data=month_analysis, x='Reply Date',
                     y='Reply Like', label='Likes')
        sns.lineplot(data=month_analysis, x='Reply Date',
                     y='Reply Bad', label='Dislikes')
        plt.title('Monthly Reply Count, Likes, and Dislikes Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_reply_count.png"))
        plt.close()

        # 2. 댓글 감성 분석 결과 분포
        data_length = len(sentiment_counts)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=8))
        sns.countplot(x='Reply Sentiment', data=data)
        plt.title('Reply Sentiment Distribution')
        plt.xlabel('Sentiment')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "reply_sentiment_distribution.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        data_length = len(correlation_matrix)
        plt.figure(figsize=self.calculate_figsize(data_length, height=8))
        sns.heatmap(correlation_matrix, annot=True,
                    cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 작성자별 댓글 수 분포 (상위 10명)
        top_10_writers = writer_reply_count.head(10)  # 상위 10명 작성자 선택
        data_length = len(top_10_writers)
        plt.figure(figsize=self.calculate_figsize(data_length))
        sns.barplot(x=top_10_writers.index,
                    y=top_10_writers.values, palette="viridis")
        plt.title('Top 10 Writers by Number of Replies')
        plt.xlabel('Writer')
        plt.ylabel('Number of Replies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "writer_reply_count.png"))
        plt.close()

        top_n = 10
        top_writers = writer_reply_count.sort_values(
            ascending=False).head(top_n).index

        filtered_reply_dir = os.path.join(csv_output_dir, 'user_replies')
        os.makedirs(filtered_reply_dir)
        # 각 상위 작성자의 댓글을 별도 CSV 파일로 저장
        for index, writer in enumerate(top_writers):
            writer_data = data[data['Reply Writer'] == writer]
            writer_csv_path = os.path.join(
                filtered_reply_dir, f"{index+1}_{writer}_replies.csv").replace('*', '')
            writer_data.to_csv(
                writer_csv_path, encoding='utf-8-sig', index=False)

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
           
        5. 월별 댓글 통계 분석 (monthly_reply_count.png):
           - 이 그래프는 월별 댓글 수, 좋아요 수, 싫어요 수의 변화를 보여줍니다.
           - x축은 날짜를, y축은 수량을 나타냅니다.
           - 이를 통해 특정 월에 댓글 활동이 증가하거나 감소한 패턴을 파악할 수 있습니다.
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(safe_path(description_file_path), 'w', encoding="utf-8", errors="ignore") as file:
            file.write(description_text)

    def NaverNewsRereplyAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))
            
        if 'Rereply Date' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning",
                                f"NaverNews Rereply CSV 형태와 일치하지 않습니다")
            return

        # 'Rereply Date'를 datetime 형식으로 변환 (오류 발생 시 NaT로 변환)
        data['Rereply Date'] = pd.to_datetime(
            data['Rereply Date'], errors='coerce')

        # 숫자형 컬럼을 숫자(float)로 변환, 변환 불가 시 0으로 채움
        for col in ['Rereply Like', 'Rereply Bad', 'Rereply LikeRatio', 'Rereply Sentiment']:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)

        # 'Rereply Text'가 결측값이 아닌지 확인하고 길이를 계산
        data['Rereply Text'] = data['Rereply Text'].fillna('')
        data['Rereply Length'] = data['Rereply Text'].apply(len)

        # 날짜별 댓글 수 분석
        time_analysis = data.groupby(data['Rereply Date'].dt.date).agg({
            'id': 'count',
            'Rereply Like': 'sum',
            'Rereply Bad': 'sum'
        }).rename(columns={'id': 'Rereply Count'}).reset_index()

        # 월별 댓글 수, 좋아요, 싫어요 합계 분석
        month_analysis = data.groupby(data['Rereply Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Rereply Like': 'sum',
            'Rereply Bad': 'sum'
        }).rename(columns={'id': 'Rereply Count'}).reset_index()
        month_analysis['Rereply Date'] = month_analysis['Rereply Date'].dt.to_timestamp()

        # 댓글 감성 분석 결과 빈도
        sentiment_counts = data['Rereply Sentiment'].value_counts()

        # 상관관계 분석 (숫자형 컬럼만 선택)
        numeric_columns = ['Rereply Like', 'Rereply Bad',
                           'Rereply Length', 'Rereply LikeRatio', 'Rereply Sentiment']
        correlation_matrix = data[numeric_columns].corr()

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
        basic_stats = data.describe(include='all')
        basic_stats.to_csv(os.path.join(
            csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(
            csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig', index=False)
        month_analysis.to_csv(os.path.join(
            csv_output_dir, "month_analysis.csv"), encoding='utf-8-sig', index=False)
        sentiment_counts.to_csv(os.path.join(
            csv_output_dir, "sentiment_counts.csv"), encoding='utf-8-sig')
        correlation_matrix.to_csv(os.path.join(
            csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig')
        writer_reply_count.to_csv(os.path.join(
            csv_output_dir, "writer_rereply_count.csv"), encoding='utf-8-sig')

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 날짜별 댓글 수 추세
        plt.figure(figsize=self.calculate_figsize(len(time_analysis)))
        sns.lineplot(data=time_analysis, x='Rereply Date', y='Rereply Count')
        plt.title('Daily Rereply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Rereplies')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "daily_rereply_count.png"))
        plt.close()

        # For month_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(month_analysis)))
        sns.lineplot(data=month_analysis, x='Rereply Date',
                     y='Rereply Count', label='Rereply Count')
        sns.lineplot(data=month_analysis, x='Rereply Date',
                     y='Rereply Like', label='Likes')
        sns.lineplot(data=month_analysis, x='Rereply Date',
                     y='Rereply Bad', label='Dislikes')
        plt.title('Monthly Rereply Count, Likes, and Dislikes Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_reply_count.png"))
        plt.close()

        # 2. 댓글 감성 분석 결과 분포
        data_length = len(sentiment_counts)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=8))
        sns.countplot(x='Rereply Sentiment', data=data.fillna(''))
        plt.title('Rereply Sentiment Distribution')
        plt.xlabel('Sentiment')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "rereply_sentiment_distribution.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        data_length = len(correlation_matrix)
        plt.figure(figsize=self.calculate_figsize(data_length, height=8))
        sns.heatmap(correlation_matrix, annot=True,
                    cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 작성자별 댓글 수 분포 (상위 10명)
        top_10_writers = writer_reply_count.head(10)
        plt.figure(figsize=self.calculate_figsize(len(top_10_writers)))
        sns.barplot(x=top_10_writers.index,
                    y=top_10_writers.values, palette="viridis")
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
        with open(safe_path(description_file_path), 'w', encoding="utf-8", errors="ignore") as file:
            file.write(description_text)

    def NaverCafeArticleAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))

        if 'NaverCafe Name' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning",
                                f"NaverCafe Article CSV 형태와 일치하지 않습니다")
            return
        # 'Article Date'를 datetime 형식으로 변환
        data['Article Date'] = pd.to_datetime(data['Article Date'])
        for col in ['NaverCafe MemberCount', 'Article ReadCount', 'Article ReplyCount']:
            data[col] = pd.to_numeric(
                data[col], errors='coerce')  # 각 열을 숫자로 변환

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
        numerical_cols = ['NaverCafe MemberCount',
                          'Article ReadCount', 'Article ReplyCount']
        correlation_matrix = data[numerical_cols].corr()

        # 결과를 저장할 디렉토리 생성
        output_dir = os.path.join(os.path.dirname(file_path),
                                  os.path.basename(file_path).replace('.csv', '') + '_analysis')
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(
            csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        cafe_analysis.to_csv(os.path.join(
            csv_output_dir, "cafe_analysis.csv"), encoding='utf-8-sig')
        writer_analysis.to_csv(os.path.join(
            csv_output_dir, "writer_analysis.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(
            csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig')
        correlation_matrix.to_csv(os.path.join(
            csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig')

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
        sns.lineplot(data=time_analysis,
                     x=time_analysis.index.to_timestamp(), y='Article Count')
        plt.title('Monthly Article Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Number of Articles')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "monthly_article_count.png"))
        plt.close()

        # 4. 작성자별 게시글 수 분포 (상위 10명)
        top_10_writers = writer_analysis.sort_values(
            'Article Count', ascending=False).head(10)
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
        with open(safe_path(description_file_path), 'w', encoding="utf-8", errors="ignore") as file:
            file.write(description_text)

    def NaverCafeReplyAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))

        # 'Article URL' 열이 있는지 확인
        if 'Article URL' not in list(data.columns):
            QMessageBox.warning(self.main, "Warning",
                                "NaverCafe Reply CSV 형태와 일치하지 않습니다")
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
        writer_analysis.to_csv(os.path.join(
            csv_output_dir, "writer_analysis.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(
            csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig')

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
        sns.lineplot(data=time_analysis,
                     x=time_analysis.index.to_timestamp(), y='Reply Count')
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
        with open(safe_path(description_file_path), 'w', encoding="utf-8", errors="ignore") as file:
            file.write(description_text)

    def YouTubeArticleAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))

        # 1) 필수 컬럼 검증
        if 'YouTube Channel' not in data.columns:
            QMessageBox.warning(self.main, "Warning",
                                "YouTube Article CSV 형태와 일치하지 않습니다.")
            return

        # 2) 날짜, 숫자 컬럼 변환
        data['Article Date'] = pd.to_datetime(
            data['Article Date'], errors='coerce')

        # 'Article ViewCount', 'Article Like', 'Article ReplyCount' -> 숫자형으로
        data.rename(columns={
            'Article ViewCount': 'views',
            'Article Like': 'likes',
            'Article ReplyCount': 'comments_count'
        }, inplace=True)

        for col in ['views', 'likes', 'comments_count']:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)

        # 3) 결과 저장용 디렉토리 생성
        output_dir = os.path.join(
            os.path.dirname(file_path),
            os.path.basename(file_path).replace('.csv', '') + '_analysis'
        )
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # --------------------------------------------------------------------------------
        # 4) 기본 통계
        # --------------------------------------------------------------------------------
        basic_stats = data.describe(include='all')

        # --------------------------------------------------------------------------------
        # 5) 월별, 일별, 주별로 그룹화하기 위해 날짜가 유효한 데이터만 사용
        # --------------------------------------------------------------------------------
        valid_data = data.dropna(subset=['Article Date']).copy()

        # --------------------------------------------------------------------------------
        # 5-1) 월별 분석
        # --------------------------------------------------------------------------------
        monthly_data = valid_data.groupby(valid_data['Article Date'].dt.to_period("M")).agg(
            video_count=('Article Date', 'count'),
            views=('views', 'sum'),
            likes=('likes', 'sum'),
            comments_count=('comments_count', 'sum')
        ).reset_index()
        # Period -> Timestamp 변환
        monthly_data['Article Date'] = monthly_data['Article Date'].dt.to_timestamp()

        # --------------------------------------------------------------------------------
        # 5-2) 일별 분석
        # --------------------------------------------------------------------------------
        daily_data = valid_data.groupby(valid_data['Article Date'].dt.to_period("D")).agg(
            video_count=('Article Date', 'count'),
            views=('views', 'sum'),
            likes=('likes', 'sum'),
            comments_count=('comments_count', 'sum')
        ).reset_index()
        daily_data['Article Date'] = daily_data['Article Date'].dt.to_timestamp()

        # --------------------------------------------------------------------------------
        # 5-3) 주별 분석 (매주 일요일 기준 W-SUN)
        # --------------------------------------------------------------------------------
        weekly_data = valid_data.groupby(valid_data['Article Date'].dt.to_period("W-SUN")).agg(
            video_count=('Article Date', 'count'),
            views=('views', 'sum'),
            likes=('likes', 'sum'),
            comments_count=('comments_count', 'sum')
        ).reset_index()
        weekly_data['Article Date'] = weekly_data['Article Date'].dt.to_timestamp()

        # --------------------------------------------------------------------------------
        # 6) 요일별 분석
        # --------------------------------------------------------------------------------
        valid_data['DayOfWeek'] = valid_data['Article Date'].dt.day_name()
        dow_analysis = valid_data.groupby('DayOfWeek').agg(
            video_count=('Article Date', 'count'),
            views=('views', 'sum'),
            likes=('likes', 'sum'),
            comments_count=('comments_count', 'sum')
        ).reset_index()

        # --------------------------------------------------------------------------------
        # 7) 채널별 분석 (상위 10개)
        # --------------------------------------------------------------------------------
        top_10_channels = data['YouTube Channel'].value_counts().head(10).index
        channel_analysis = data[data['YouTube Channel'].isin(top_10_channels)].groupby('YouTube Channel').agg(
            video_count=('Article Date', 'count'),
            total_views=('views', 'sum'),
            total_likes=('likes', 'sum'),
            total_comments=('comments_count', 'sum')
        ).reset_index()

        # --------------------------------------------------------------------------------
        # 8) 상위 10개 영상(Article Title) 분석
        # --------------------------------------------------------------------------------
        top_10_videos = data.sort_values('views', ascending=False).head(10)[
            ['Article Title', 'YouTube Channel',
                'views', 'likes', 'comments_count']
        ].reset_index(drop=True)

        # --------------------------------------------------------------------------------
        # 9) 추가 지표 계산 (Like-View 비율, Comment-View 비율 등)
        # --------------------------------------------------------------------------------
        data['like_view_ratio'] = data.apply(
            lambda x: x['likes'] / x['views'] if x['views'] > 0 else 0,
            axis=1
        )
        data['comment_view_ratio'] = data.apply(
            lambda x: x['comments_count'] /
            x['views'] if x['views'] > 0 else 0,
            axis=1
        )

        # --------------------------------------------------------------------------------
        # 10) 상관관계 분석 (추가 지표 포함)
        # --------------------------------------------------------------------------------
        numeric_columns = ['views', 'likes', 'comments_count',
                           'like_view_ratio', 'comment_view_ratio']
        correlation_matrix = data[numeric_columns].corr()

        # --------------------------------------------------------------------------------
        # 11) 분석 결과 CSV 저장
        # --------------------------------------------------------------------------------
        basic_stats.to_csv(os.path.join(
            csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        monthly_data.to_csv(os.path.join(
            csv_output_dir, "monthly_analysis.csv"), encoding='utf-8-sig', index=False)
        daily_data.to_csv(os.path.join(
            csv_output_dir, "daily_analysis.csv"), encoding='utf-8-sig', index=False)
        weekly_data.to_csv(os.path.join(
            csv_output_dir, "weekly_analysis.csv"), encoding='utf-8-sig', index=False)
        dow_analysis.to_csv(os.path.join(
            csv_output_dir, "day_of_week_analysis.csv"), encoding='utf-8-sig', index=False)
        channel_analysis.to_csv(os.path.join(
            csv_output_dir, "channel_analysis.csv"), encoding='utf-8-sig', index=False)
        top_10_videos.to_csv(os.path.join(
            csv_output_dir, "top_10_videos.csv"), encoding='utf-8-sig', index=False)
        correlation_matrix.to_csv(os.path.join(
            csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig')

        # --------------------------------------------------------------------------------
        # 12) 시각화
        # --------------------------------------------------------------------------------

        # (1) 월별 추세
        plt.figure(figsize=self.calculate_figsize(len(monthly_data)))
        sns.lineplot(data=monthly_data, x='Article Date',
                     y='views', label='Views')
        sns.lineplot(data=monthly_data, x='Article Date',
                     y='likes', label='Likes')
        sns.lineplot(data=monthly_data, x='Article Date',
                     y='comments_count', label='Comments')
        plt.title('월별 조회수, 좋아요, 댓글 수 추세')
        plt.xlabel('월')
        plt.ylabel('합계')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_trend.png"))
        plt.close()

        # (2) 일별 추세
        plt.figure(figsize=self.calculate_figsize(len(daily_data)))
        sns.lineplot(data=daily_data, x='Article Date',
                     y='views', label='Views')
        sns.lineplot(data=daily_data, x='Article Date',
                     y='likes', label='Likes')
        sns.lineplot(data=daily_data, x='Article Date',
                     y='comments_count', label='Comments')
        plt.title('일별 조회수, 좋아요, 댓글 수 추이')
        plt.xlabel('일자')
        plt.ylabel('합계')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "daily_trend.png"))
        plt.close()

        # (3) 주별 추세
        plt.figure(figsize=self.calculate_figsize(len(weekly_data)))
        sns.lineplot(data=weekly_data, x='Article Date',
                     y='views', label='Views')
        sns.lineplot(data=weekly_data, x='Article Date',
                     y='likes', label='Likes')
        sns.lineplot(data=weekly_data, x='Article Date',
                     y='comments_count', label='Comments')
        plt.title('주별 조회수, 좋아요, 댓글 수 추이')
        plt.xlabel('주(시작일 기준)')
        plt.ylabel('합계')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "weekly_trend.png"))
        plt.close()

        # (4) 요일별 분석
        plt.figure(figsize=self.calculate_figsize(len(dow_analysis)))
        dow_order = ["Monday", "Tuesday", "Wednesday",
                     "Thursday", "Friday", "Saturday", "Sunday"]
        dow_analysis['DayOfWeek'] = pd.Categorical(
            dow_analysis['DayOfWeek'], categories=dow_order, ordered=True)
        dow_analysis_sorted = dow_analysis.sort_values('DayOfWeek')
        sns.barplot(data=dow_analysis_sorted, x='DayOfWeek', y='views')
        plt.title('요일별 총 조회수')
        plt.xlabel('요일')
        plt.ylabel('조회수')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "day_of_week_views.png"))
        plt.close()

        # (5) 상위 10개 채널(조회수 기준)
        plt.figure(figsize=self.calculate_figsize(len(channel_analysis)))
        channel_analysis_sorted = channel_analysis.sort_values(
            'total_views', ascending=False)
        sns.barplot(data=channel_analysis_sorted,
                    x='YouTube Channel', y='total_views')
        plt.title('상위 10개 채널별 총 조회수')
        plt.xlabel('채널명')
        plt.ylabel('조회수')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "top_channels_views.png"))
        plt.close()

        # (6) 상위 10개 영상(조회수 기준)
        plt.figure(figsize=self.calculate_figsize(len(top_10_videos)))
        sns.barplot(data=top_10_videos, x='Article Title', y='views')
        plt.title('상위 10개 영상 (조회수 기준)')
        plt.xlabel('영상 제목')
        plt.ylabel('조회수')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "top_10_videos.png"))
        plt.close()

        # (7) 히스토그램 (Like-View 비율, Comment-View 비율 분포)
        #     - 극단값 제거(상위 1%)를 위해 quantile(0.99)을 사용해 x축 제한
        #     - 필요 시 로그 스케일(ax.set_xscale('log'))도 고려할 수 있음.

        # Like-View Ratio
        plt.figure(figsize=self.calculate_figsize(10))
        ax1 = sns.histplot(data=data, x='like_view_ratio', kde=True)
        like_99 = data['like_view_ratio'].quantile(0.99)
        ax1.set_xlim(0, like_99)  # x축 범위를 0~상위 1% 분위수까지만
        # ax1.set_xscale('log')   # 로그 스케일 예시(주석 해제 시 사용 가능)

        plt.title('Like-View Ratio Distribution')
        plt.xlabel('Like / View 비율')
        plt.ylabel('빈도')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "like_view_ratio_distribution.png"))
        plt.close()

        # Comment-View Ratio
        plt.figure(figsize=self.calculate_figsize(10))
        ax2 = sns.histplot(data=data, x='comment_view_ratio', kde=True)
        comment_99 = data['comment_view_ratio'].quantile(0.99)
        ax2.set_xlim(0, comment_99)
        # ax2.set_xscale('log')  # 로그 스케일 예시

        plt.title('Comment-View Ratio Distribution')
        plt.xlabel('Comment / View 비율')
        plt.ylabel('빈도')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "comment_view_ratio_distribution.png"))
        plt.close()

        # (8) 상관관계 히트맵
        plt.figure(figsize=self.calculate_figsize(
            len(correlation_matrix), height=8))
        sns.heatmap(correlation_matrix, annot=True,
                    cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('숫자형 지표 상관관계 (추가 지표 포함)')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # --------------------------------------------------------------------------------
        # 13) 그래프 설명 텍스트 작성
        # --------------------------------------------------------------------------------
        description_text = """
        그래프/분석 결과 설명:

        1. 기본 통계 (basic_stats.csv):
           - 데이터 전체에 대한 기초 통계량을 제공합니다.

        2. 월별 트렌드 (monthly_trend.png, monthly_analysis.csv):
           - 월별 조회수(views), 좋아요(likes), 댓글 수(comments_count)를 합산하여 선 그래프로 표시합니다.
           - 해당 기간의 전체 추이를 한눈에 파악할 수 있습니다.

        3. 일별 트렌드 (daily_trend.png, daily_analysis.csv):
           - 일자별 조회수, 좋아요, 댓글 수 변화를 선 그래프로 확인할 수 있습니다.

        4. 주별 트렌드 (weekly_trend.png, weekly_analysis.csv):
           - 매주 (일요일 기준) 간격으로 조회수, 좋아요, 댓글 수 추이를 요약합니다.

        5. 요일별 분석 (day_of_week_views.png, day_of_week_analysis.csv):
           - 월/일 단위가 아닌 일주일 간의 특정 요일(Mon~Sun)별로 조회수, 좋아요, 댓글 수를 비교합니다.
           - 업로드하기 좋은 요일 등을 파악할 때 활용할 수 있습니다.

        6. 상위 10개 채널 (top_channels_views.png, channel_analysis.csv):
           - 'YouTube Channel'별로 조회수, 좋아요, 댓글 수 총합을 구한 뒤, 조회수가 높은 상위 10개 채널을 바 그래프로 시각화합니다.

        7. 상위 10개 영상 (top_10_videos.png, top_10_videos.csv):
           - 조회수가 가장 높은 10개 영상의 제목, 채널명, 조회수, 좋아요, 댓글 수 정보를 표시합니다.

        8. Like-View 비율 & Comment-View 비율 분포 (like_view_ratio_distribution.png, comment_view_ratio_distribution.png):
           - 극단값(상위 1% 구간)을 잘라낸 뒤, (likes / views), (comments_count / views)의 분포를 히스토그램으로 표시합니다.
           - 로그 스케일 변환 등으로 추가 분석 가능.

        9. 상관관계 히트맵 (correlation_matrix.png, correlation_matrix.csv):
           - views, likes, comments_count, like_view_ratio, comment_view_ratio 간의 상관관계를 나타냅니다.
           - 예: Like-View 비율과 Comment-View 비율이 강한 양의 상관관계를 보이는지, Likes와 Views 간에 어떤 상관이 있는지 등을 시각적으로 파악할 수 있습니다.
        """
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(safe_path(description_file_path), 'w', encoding="utf-8", errors="ignore") as file:
            file.write(description_text)

    def YouTubeReplyAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))

        # 0) 필수 컬럼 검증
        required_cols = [
            "Reply Writer",  # 댓글 작성자
            "Reply Date",  # 댓글 작성 시간
            "Reply Text",  # 댓글 내용
            "Reply Like",  # 댓글 좋아요 수
            "Article URL",  # 영상 URL
            "Article Day"  # (영상)이 올라온 날짜
        ]
        missing = [col for col in required_cols if col not in data.columns]
        if missing:
            QMessageBox.warning(
                self.main,
                "Warning",
                f"필수 컬럼이 누락되었습니다: {missing}\nCSV 형태를 확인하세요."
            )
            return

        # 1) 날짜형 / 숫자형 변환
        # - 댓글이 작성된 날짜
        data["Reply Date"] = pd.to_datetime(
            data["Reply Date"], errors="coerce")
        # - 게시물이 올라온 날짜
        data["Article Day"] = pd.to_datetime(
            data["Article Day"], errors="coerce")

        # - 좋아요 수: 숫자 변환
        data["Reply Like"] = pd.to_numeric(
            data["Reply Like"], errors="coerce").fillna(0)

        # 2) 결과 저장용 디렉토리 생성
        output_dir = os.path.join(
            os.path.dirname(file_path),
            os.path.basename(file_path).replace(".csv", "") + "_analysis"
        )
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 3) 기본 통계 (기술 통계량)
        basic_stats = data.describe(include="all")  # 범주형/수치형 모두 기술통계

        # 4) 유효한 날짜 데이터만 따로 관리
        #    (댓글 날짜, 기사 날짜 모두 제대로 변환된 행만 분석에 활용)
        valid_data = data.dropna(subset=["Reply Date", "Article Day"]).copy()

        # 5) 날짜 차이(댓글 작성 시점 vs 게시물 업로드 시점)
        #    -> '작성 시점 - 업로드 시점' 일수 계산
        valid_data["ReplyTimeDelta"] = (
            valid_data["Reply Date"] - valid_data["Article Day"]).dt.days

        #    예: ReplyTimeDelta = 0 이면 같은 날 올라온 댓글
        #        ReplyTimeDelta = 1 이면 업로드 다음 날 달린 댓글
        #        음수가 나오면 업로드 전 시점(잘못된 데이터)일 수도 있음

        # 6) 그룹화 분석
        #    6-1) 일별 댓글 추이
        daily_data = valid_data.groupby(valid_data["Reply Date"].dt.to_period("D")).agg(
            reply_count=("Reply Text", "count"),
            total_like=("Reply Like", "sum"),
            avg_time_diff=("ReplyTimeDelta", "mean")  # 일별로 댓글-게시물 간 평균 시차
        ).reset_index()
        daily_data["Reply Date"] = daily_data["Reply Date"].dt.to_timestamp()

        #    6-2) 월별 댓글 추이
        monthly_data = valid_data.groupby(valid_data["Reply Date"].dt.to_period("M")).agg(
            reply_count=("Reply Text", "count"),
            total_like=("Reply Like", "sum"),
            avg_time_diff=("ReplyTimeDelta", "mean")
        ).reset_index()
        monthly_data["Reply Date"] = monthly_data["Reply Date"].dt.to_timestamp()

        #    6-3) 요일별 분석 (댓글 작성 요일)
        valid_data["ReplyDayOfWeek"] = valid_data["Reply Date"].dt.day_name()
        dow_data = valid_data.groupby("ReplyDayOfWeek").agg(
            reply_count=("Reply Text", "count"),
            total_like=("Reply Like", "sum"),
            avg_time_diff=("ReplyTimeDelta", "mean")
        ).reset_index()

        #    6-4) 게시물(Article URL)별 분석
        article_analysis = data.groupby("Article URL").agg(
            reply_count=("Reply Text", "count"),
            total_like=("Reply Like", "sum")
        ).reset_index()

        #    6-5) 게시물 업로드 날짜(Article Day) 기준 분석
        #         업로드 날짜가 같으면 같은 날 업로드된 다른 게시물로 간주
        #         날짜 변환 안 된건 제외(valid_data만 사용 가능)
        day_post_analysis = valid_data.groupby(valid_data["Article Day"].dt.to_period("D")).agg(
            article_reply_count=("Reply Text", "count"),
            article_reply_like=("Reply Like", "sum"),
            avg_reply_time=("ReplyTimeDelta", "mean")  # 업로드일 기준 평균 댓글 시차
        ).reset_index()
        day_post_analysis["Article Day"] = day_post_analysis["Article Day"].dt.to_timestamp(
        )

        #    6-6) 댓글 작성자별(Reply Writer) 분석
        writer_analysis = data.groupby("Reply Writer").agg(
            reply_count=("Reply Text", "count"),
            total_like=("Reply Like", "sum")
        ).reset_index()

        # 7) 상위 10개 항목
        #    - 작성자, 게시물
        top_10_writers = writer_analysis.sort_values(
            "reply_count", ascending=False).head(10)
        top_10_articles = article_analysis.sort_values(
            "reply_count", ascending=False).head(10)

        # 8) 상위 10개 댓글(좋아요 기준)
        top_10_liked_replies = data.sort_values("Reply Like", ascending=False).head(10)[
            ["Reply Writer", "Reply Text", "Reply Date",
                "Reply Like", "Article URL", "Article Day"]
        ].reset_index(drop=True)

        # 9) 통계 지표 확장
        #    - 예: Reply Like 분포 시각화를 위해 상위 1% 자르기
        #    - 코릴레이션은 Like와 TimeDelta 정도만 해볼 수 있음
        numeric_cols = ["Reply Like"]
        # ReplyTimeDelta도 숫자형이면 상관관계에 추가
        if "ReplyTimeDelta" in valid_data.columns:
            numeric_cols.append("ReplyTimeDelta")

        # 상관관계 (valid_data만 사용해도 됨, 여기서는 전체 data 중 null 제외)
        # null이 있으면 corr() 계산에서 제외됨.
        correlation_matrix = valid_data[numeric_cols].corr()

        # 10) CSV 저장
        basic_stats.to_csv(os.path.join(
            csv_output_dir, "basic_stats.csv"), encoding="utf-8-sig")
        daily_data.to_csv(os.path.join(
            csv_output_dir, "daily_analysis.csv"), encoding="utf-8-sig", index=False)
        monthly_data.to_csv(os.path.join(
            csv_output_dir, "monthly_analysis.csv"), encoding="utf-8-sig", index=False)
        dow_data.to_csv(os.path.join(
            csv_output_dir, "day_of_week_analysis.csv"), encoding="utf-8-sig", index=False)
        article_analysis.to_csv(os.path.join(
            csv_output_dir, "article_analysis.csv"), encoding="utf-8-sig", index=False)
        day_post_analysis.to_csv(os.path.join(csv_output_dir, "article_day_analysis.csv"), encoding="utf-8-sig",
                                 index=False)
        writer_analysis.to_csv(os.path.join(
            csv_output_dir, "writer_analysis.csv"), encoding="utf-8-sig", index=False)
        top_10_writers.to_csv(os.path.join(
            csv_output_dir, "top_10_writers.csv"), encoding="utf-8-sig", index=False)
        top_10_articles.to_csv(os.path.join(
            csv_output_dir, "top_10_articles.csv"), encoding="utf-8-sig", index=False)
        top_10_liked_replies.to_csv(os.path.join(csv_output_dir, "top_10_liked_replies.csv"), encoding="utf-8-sig",
                                    index=False)
        correlation_matrix.to_csv(os.path.join(
            csv_output_dir, "correlation_matrix.csv"), encoding="utf-8-sig")

        # 11) 시각화
        #     - calculate_figsize(len(x)) 함수가 있다고 가정. (없으면 (10,6) 등 직접 입력)
        # (1) 일별 댓글 추이
        plt.figure(figsize=self.calculate_figsize(len(daily_data)))
        sns.lineplot(data=daily_data, x="Reply Date",
                     y="reply_count", label="Reply Count")
        sns.lineplot(data=daily_data, x="Reply Date",
                     y="total_like", label="Total Like")
        plt.title("일별 댓글/좋아요 추이")
        plt.xlabel("날짜")
        plt.ylabel("합계")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "daily_trend.png"))
        plt.close()

        # (2) 월별 댓글 추이
        plt.figure(figsize=self.calculate_figsize(len(monthly_data)))
        sns.lineplot(data=monthly_data, x="Reply Date",
                     y="reply_count", label="Reply Count")
        sns.lineplot(data=monthly_data, x="Reply Date",
                     y="total_like", label="Total Like")
        plt.title("월별 댓글/좋아요 추이")
        plt.xlabel("월")
        plt.ylabel("합계")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_trend.png"))
        plt.close()

        # (3) 요일별 댓글 수
        dow_order = ["Monday", "Tuesday", "Wednesday",
                     "Thursday", "Friday", "Saturday", "Sunday"]
        dow_data["ReplyDayOfWeek"] = pd.Categorical(
            dow_data["ReplyDayOfWeek"], categories=dow_order, ordered=True)
        sorted_dow_data = dow_data.sort_values("ReplyDayOfWeek")

        plt.figure(figsize=self.calculate_figsize(len(sorted_dow_data)))
        sns.barplot(data=sorted_dow_data, x="ReplyDayOfWeek", y="reply_count")
        plt.title("요일별 댓글 수")
        plt.xlabel("요일")
        plt.ylabel("댓글 수")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "day_of_week_reply_count.png"))
        plt.close()

        # (4) Article Day 기준 (게시물 업로드 날짜별) 댓글 수
        plt.figure(figsize=self.calculate_figsize(len(day_post_analysis)))
        sns.lineplot(data=day_post_analysis, x="Article Day",
                     y="article_reply_count", label="Reply Count")
        sns.lineplot(data=day_post_analysis, x="Article Day",
                     y="article_reply_like", label="Reply Like")
        plt.title("영상 업로드 날짜별 댓글 수/좋아요 추이")
        plt.xlabel("영상 업로드 날짜")
        plt.ylabel("합계")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_day_trend.png"))
        plt.close()

        # (5) 댓글 작성자 (상위 10명)
        plt.figure(figsize=self.calculate_figsize(len(top_10_writers)))
        sns.barplot(data=top_10_writers, x="Reply Writer", y="reply_count")
        plt.title("상위 10명 댓글 작성자")
        plt.xlabel("작성자")
        plt.ylabel("댓글 수")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "top_10_writers.png"))
        plt.close()

        # (6) 게시물(Article URL)별 댓글 수 (상위 10)
        plt.figure(figsize=self.calculate_figsize(len(top_10_articles)))
        sns.barplot(data=top_10_articles, x="Article URL", y="reply_count")
        plt.title("상위 10 영상별 댓글 수")
        plt.xlabel("Article URL")
        plt.ylabel("댓글 수")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "top_10_articles.png"))
        plt.close()

        # (8) ReplyTimeDelta(댓글 작성 - 업로드 날짜)의 분포
        #     0보다 작으면 업로드 이전에 작성된(?) 이상치일 수 있음
        plt.figure(figsize=self.calculate_figsize(10))
        ax2 = sns.histplot(data=valid_data, x="ReplyTimeDelta", kde=True)
        # 상위 1% 잘라내고 싶다면:
        delta_99 = valid_data["ReplyTimeDelta"].quantile(0.99)
        delta_min = valid_data["ReplyTimeDelta"].min()  # 음수도 있을 수 있음
        ax2.set_xlim(delta_min, delta_99)
        plt.title("댓글-영상 시차(일) 분포 (상위 1% 제외)")
        plt.xlabel("ReplyTimeDelta (Days)")
        plt.ylabel("빈도")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "reply_time_delta_distribution.png"))
        plt.close()

        # (9) 상관관계 히트맵
        plt.figure(figsize=self.calculate_figsize(
            len(correlation_matrix), height=8))
        sns.heatmap(correlation_matrix, annot=True,
                    cmap="coolwarm", vmin=-1, vmax=1)
        plt.title("댓글 데이터 상관관계")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 12) 분석/그래프 설명 txt
        description_text = """
        [댓글 데이터 분석 결과 설명]

        1. basic_stats.csv
           - 전체 CSV 데이터에 대한 기본 통계(최솟값, 최댓값, 평균 등).

        2. daily_analysis.csv / daily_trend.png
           - 일자(Reply Date) 기준으로 댓글 수, 좋아요 수 합계를 선 그래프로 표시합니다.

        3. monthly_analysis.csv / monthly_trend.png
           - 월별 댓글/좋아요 추이를 확인할 수 있습니다.

        4. day_of_week_analysis.csv / day_of_week_reply_count.png
           - 요일별(Monday~Sunday) 댓글 수를 바 그래프로 시각화했습니다.

        5. article_day_analysis.csv / article_day_trend.png
           - 'Article Day'(영상이 올라온 날짜)별 댓글 수/좋아요 추이를 나타냅니다.
           - 업로드 후 댓글이 언제 많이 달리는지 파악하는 데 도움이 됩니다.

        6. article_analysis.csv이정리한 CSV.

        7. writer_analysis.csv
           - 'Reply Writer'(작성자)별로 댓글 수, 좋아요 수 합계를 분석한 CSV.

        8. top_10_writers.csv / top_10_writers.png
           - 댓글 수 기준 상위 10명 작성자 정보를 정리하고, 바 그래프로 표시합니다.

        9. top_10_articles.csv / top_10_articles.png
           - 댓글 수 기준 상위 10개 Article URL을 정리하고, 바 그래프로 시각화합니다.

        10. top_10_liked_replies.csv
            - 좋아요(Reply Like)가 가장 많은 댓글 10개를 추출합니다.

        11. reply_like_distribution.png
            - 댓글 좋아요 수의 분포를 히스토그램과 KDE곡선으로 표시합니다.
            - 상위 1% 구간은 잘라내어 x축 범위를 제한했습니다.

        12. reply_time_delta_distribution.png
            - (댓글 작성 날짜 - 게시물 업로드 날짜)를 일(day) 단위로 계산한 시차 분포를 히스토그램으로 확인합니다.

        13. correlation_matrix.csv / correlation_matrix.png
            - 'Reply Like', 'ReplyTimeDelta' 등의 수치 컬럼 간 상관관계를 나타냅니다.

        """
        with open(safe_path(os.path.join(output_dir, "description.txt")), "w", encoding="utf-8", errors="ignore") as f:
            f.write(description_text)

    def YouTubeRereplyAnalysis(self, data, file_path):
        if 'id' not in data.columns:
            # 1부터 시작하는 연속 번호를 부여
            data.insert(0, 'id', range(1, len(data) + 1))

        # 0) 필수 컬럼 검증
        required_cols = [
            "Rereply Writer",  # 대댓글 작성자
            "Rereply Date",  # 대댓글 작성 시간
            "Rereply Text",  # 대댓글 내용
            "Rereply Like",  # 대댓글 좋아요 수
            "Article URL",  # 영상 URL
            "Article Day"  # (영상)이 올라온 날짜
        ]
        missing = [col for col in required_cols if col not in data.columns]
        if missing:
            QMessageBox.warning(
                self.main,
                "Warning",
                f"필수 컬럼이 누락되었습니다: {missing}\nCSV 형태를 확인하세요."
            )
            return

        # 1) 날짜형 / 숫자형 변환
        # - 대댓글이 작성된 날짜
        data["Rereply Date"] = pd.to_datetime(
            data["Rereply Date"], errors="coerce")
        # - 게시물이 올라온 날짜
        data["Article Day"] = pd.to_datetime(
            data["Article Day"], errors="coerce")

        # - 좋아요 수: 숫자 변환
        data["Rereply Like"] = pd.to_numeric(
            data["Rereply Like"], errors="coerce").fillna(0)

        # 2) 결과 저장용 디렉토리 생성
        output_dir = os.path.join(
            os.path.dirname(file_path),
            os.path.basename(file_path).replace(".csv", "") + "_analysis"
        )
        csv_output_dir = os.path.join(output_dir, "csv_files")
        graph_output_dir = os.path.join(output_dir, "graphs")
        os.makedirs(csv_output_dir, exist_ok=True)
        os.makedirs(graph_output_dir, exist_ok=True)

        # 3) 기본 통계 (기술 통계량)
        basic_stats = data.describe(include="all")  # 범주형/수치형 모두 기술통계

        # 4) 유효한 날짜 데이터만 따로 관리
        #    (대댓글 날짜, 영상 날짜 모두 제대로 변환된 행만 분석에 활용)
        valid_data = data.dropna(subset=["Rereply Date", "Article Day"]).copy()

        # 5) 날짜 차이(대댓글 작성 시점 vs 게시물 업로드 시점)
        #    -> '작성 시점 - 업로드 시점' 일수 계산
        valid_data["RereplyTimeDelta"] = (
            valid_data["Rereply Date"] - valid_data["Article Day"]).dt.days
        #    예: RereplyTimeDelta = 0 이면 같은 날 올라온 대댓글
        #        RereplyTimeDelta = 1 이면 업로드 다음 날 달린 대댓글
        #        음수가 나오면 업로드 전 시점(잘못된 데이터)일 수도 있음

        # 6) 그룹화 분석
        #    6-1) 일별 대댓글 추이
        daily_data = valid_data.groupby(valid_data["Rereply Date"].dt.to_period("D")).agg(
            rereply_count=("Rereply Text", "count"),
            total_like=("Rereply Like", "sum"),
            avg_time_diff=("RereplyTimeDelta", "mean")  # 일별로 대댓글-게시물 간 평균 시차
        ).reset_index()
        daily_data["Rereply Date"] = daily_data["Rereply Date"].dt.to_timestamp()

        #    6-2) 월별 대댓글 추이
        monthly_data = valid_data.groupby(valid_data["Rereply Date"].dt.to_period("M")).agg(
            rereply_count=("Rereply Text", "count"),
            total_like=("Rereply Like", "sum"),
            avg_time_diff=("RereplyTimeDelta", "mean")
        ).reset_index()
        monthly_data["Rereply Date"] = monthly_data["Rereply Date"].dt.to_timestamp()

        #    6-3) 요일별 분석 (대댓글 작성 요일)
        valid_data["RereplyDayOfWeek"] = valid_data["Rereply Date"].dt.day_name()
        dow_data = valid_data.groupby("RereplyDayOfWeek").agg(
            rereply_count=("Rereply Text", "count"),
            total_like=("Rereply Like", "sum"),
            avg_time_diff=("RereplyTimeDelta", "mean")
        ).reset_index()

        #    6-4) 게시물(Article URL)별 분석
        article_analysis = data.groupby("Article URL").agg(
            rereply_count=("Rereply Text", "count"),
            total_like=("Rereply Like", "sum")
        ).reset_index()

        #    6-5) 게시물 업로드 날짜(Article Day) 기준 분석
        day_post_analysis = valid_data.groupby(valid_data["Article Day"].dt.to_period("D")).agg(
            article_rereply_count=("Rereply Text", "count"),
            article_rereply_like=("Rereply Like", "sum"),
            avg_rereply_time=("RereplyTimeDelta", "mean")  # 업로드일 기준 평균 대댓글 시차
        ).reset_index()
        day_post_analysis["Article Day"] = day_post_analysis["Article Day"].dt.to_timestamp(
        )

        #    6-6) 대댓글 작성자별(Rereply Writer) 분석
        writer_analysis = data.groupby("Rereply Writer").agg(
            rereply_count=("Rereply Text", "count"),
            total_like=("Rereply Like", "sum")
        ).reset_index()

        # 7) 상위 10개 항목
        #    - 작성자, 게시물
        top_10_writers = writer_analysis.sort_values(
            "rereply_count", ascending=False).head(10)
        top_10_articles = article_analysis.sort_values(
            "rereply_count", ascending=False).head(10)

        # 8) 상위 10개 대댓글(좋아요 기준)
        top_10_liked_rereplies = data.sort_values("Rereply Like", ascending=False).head(10)[
            ["Rereply Writer", "Rereply Text", "Rereply Date",
                "Rereply Like", "Article URL", "Article Day"]
        ].reset_index(drop=True)

        # 9) 통계 지표 확장
        #    - 예: Rereply Like 분포 시각화를 위해 상위 1% 자르기
        #    - 코릴레이션은 Like와 TimeDelta 정도만 해볼 수 있음
        numeric_cols = ["Rereply Like"]
        # RereplyTimeDelta도 숫자형이면 상관관계에 추가
        if "RereplyTimeDelta" in valid_data.columns:
            numeric_cols.append("RereplyTimeDelta")

        # 상관관계 (valid_data만 사용)
        correlation_matrix = valid_data[numeric_cols].corr()

        # 10) CSV 저장
        basic_stats.to_csv(os.path.join(
            csv_output_dir, "basic_stats.csv"), encoding="utf-8-sig")
        daily_data.to_csv(os.path.join(
            csv_output_dir, "daily_analysis.csv"), encoding="utf-8-sig", index=False)
        monthly_data.to_csv(os.path.join(
            csv_output_dir, "monthly_analysis.csv"), encoding="utf-8-sig", index=False)
        dow_data.to_csv(os.path.join(
            csv_output_dir, "day_of_week_analysis.csv"), encoding="utf-8-sig", index=False)
        article_analysis.to_csv(os.path.join(
            csv_output_dir, "article_analysis.csv"), encoding="utf-8-sig", index=False)
        day_post_analysis.to_csv(os.path.join(csv_output_dir, "article_day_analysis.csv"), encoding="utf-8-sig",
                                 index=False)
        writer_analysis.to_csv(os.path.join(
            csv_output_dir, "writer_analysis.csv"), encoding="utf-8-sig", index=False)
        top_10_writers.to_csv(os.path.join(
            csv_output_dir, "top_10_writers.csv"), encoding="utf-8-sig", index=False)
        top_10_articles.to_csv(os.path.join(
            csv_output_dir, "top_10_articles.csv"), encoding="utf-8-sig", index=False)
        top_10_liked_rereplies.to_csv(os.path.join(csv_output_dir, "top_10_liked_rereplies.csv"), encoding="utf-8-sig",
                                      index=False)
        correlation_matrix.to_csv(os.path.join(
            csv_output_dir, "correlation_matrix.csv"), encoding="utf-8-sig")

        # 11) 시각화
        #     - calculate_figsize(len(x)) 함수가 있다고 가정. (없으면 (10,6) 등 직접 입력)
        # (1) 일별 대댓글 추이
        plt.figure(figsize=self.calculate_figsize(len(daily_data)))
        sns.lineplot(data=daily_data, x="Rereply Date",
                     y="rereply_count", label="Rereply Count")
        sns.lineplot(data=daily_data, x="Rereply Date",
                     y="total_like", label="Total Like")
        plt.title("일별 대댓글/좋아요 추이")
        plt.xlabel("날짜")
        plt.ylabel("합계")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "daily_trend.png"))
        plt.close()

        # (2) 월별 대댓글 추이
        plt.figure(figsize=self.calculate_figsize(len(monthly_data)))
        sns.lineplot(data=monthly_data, x="Rereply Date",
                     y="rereply_count", label="Rereply Count")
        sns.lineplot(data=monthly_data, x="Rereply Date",
                     y="total_like", label="Total Like")
        plt.title("월별 대댓글/좋아요 추이")
        plt.xlabel("월")
        plt.ylabel("합계")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_trend.png"))
        plt.close()

        # (3) 요일별 대댓글 수
        dow_order = ["Monday", "Tuesday", "Wednesday",
                     "Thursday", "Friday", "Saturday", "Sunday"]
        dow_data["RereplyDayOfWeek"] = pd.Categorical(
            dow_data["RereplyDayOfWeek"], categories=dow_order, ordered=True)
        sorted_dow_data = dow_data.sort_values("RereplyDayOfWeek")

        plt.figure(figsize=self.calculate_figsize(len(sorted_dow_data)))
        sns.barplot(data=sorted_dow_data,
                    x="RereplyDayOfWeek", y="rereply_count")
        plt.title("요일별 대댓글 수")
        plt.xlabel("요일")
        plt.ylabel("대댓글 수")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "day_of_week_rereply_count.png"))
        plt.close()

        # (4) Article Day 기준 (게시물 업로드 날짜별) 대댓글 수
        plt.figure(figsize=self.calculate_figsize(len(day_post_analysis)))
        sns.lineplot(data=day_post_analysis, x="Article Day",
                     y="article_rereply_count", label="Rereply Count")
        sns.lineplot(data=day_post_analysis, x="Article Day",
                     y="article_rereply_like", label="Rereply Like")
        plt.title("영상 업로드 날짜별 대댓글 수/좋아요 추이")
        plt.xlabel("영상 업로드 날짜")
        plt.ylabel("합계")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_day_trend.png"))
        plt.close()

        # (5) 대댓글 작성자 (상위 10명)
        plt.figure(figsize=self.calculate_figsize(len(top_10_writers)))
        sns.barplot(data=top_10_writers, x="Rereply Writer", y="rereply_count")
        plt.title("상위 10명 대댓글 작성자")
        plt.xlabel("작성자")
        plt.ylabel("대댓글 수")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "top_10_writers.png"))
        plt.close()

        # (6) 게시물(Article URL)별 대댓글 수 (상위 10)
        plt.figure(figsize=self.calculate_figsize(len(top_10_articles)))
        sns.barplot(data=top_10_articles, x="Article URL", y="rereply_count")
        plt.title("상위 10 영상별 대댓글 수")
        plt.xlabel("Article URL")
        plt.ylabel("대댓글 수")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "top_10_articles.png"))
        plt.close()

        # (8) RereplyTimeDelta(대댓글 작성 - 업로드 날짜)의 분포
        plt.figure(figsize=self.calculate_figsize(10))
        ax2 = sns.histplot(data=valid_data, x="RereplyTimeDelta", kde=True)
        # 상위 1% 잘라내고 싶다면:
        delta_99 = valid_data["RereplyTimeDelta"].quantile(0.99)
        delta_min = valid_data["RereplyTimeDelta"].min()
        ax2.set_xlim(delta_min, delta_99)
        plt.title("대댓글-영상 시차(일) 분포 (상위 1% 제외)")
        plt.xlabel("RereplyTimeDelta (Days)")
        plt.ylabel("빈도")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir,
                    "rereply_time_delta_distribution.png"))
        plt.close()

        # (9) 상관관계 히트맵
        plt.figure(figsize=self.calculate_figsize(
            len(correlation_matrix), height=8))
        sns.heatmap(correlation_matrix, annot=True,
                    cmap="coolwarm", vmin=-1, vmax=1)
        plt.title("대댓글 데이터 상관관계")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 12) 분석/그래프 설명 txt
        description_text = """
        [대댓글 데이터 분석 결과 설명]

        1. basic_stats.csv
           - 전체 CSV 데이터에 대한 기본 통계(최솟값, 최댓값, 평균 등).

        2. daily_analysis.csv / daily_trend.png
           - 일자(Rereply Date) 기준으로 대댓글 수, 좋아요 수 합계를 선 그래프로 표시합니다.

        3. monthly_analysis.csv / monthly_trend.png
           - 월별 대댓글/좋아요 추이를 확인할 수 있습니다.

        4. day_of_week_analysis.csv / day_of_week_rereply_count.png
           - 요일별(Monday~Sunday) 대댓글 수를 바 그래프로 시각화했습니다.

        5. article_day_analysis.csv / article_day_trend.png
           - 'Article Day'(영상이 올라온 날짜)별 대댓글 수/좋아요 추이를 나타냅니다.
           - 업로드 후 대댓글이 언제 많이 달리는지 파악하는 데 도움이 됩니다.

        6. article_analysis.csv
           - Article URL별 대댓글 수, 좋아요 수 합계를 정리한 CSV.

        7. writer_analysis.csv
           - 'Rereply Writer'(작성자)별로 대댓글 수, 좋아요 수 합계를 분석한 CSV.

        8. top_10_writers.csv / top_10_writers.png
           - 대댓글 수 기준 상위 10명 작성자 정보를 정리하고, 바 그래프로 표시합니다.

        9. top_10_articles.csv / top_10_articles.png
           - 대댓글 수 기준 상위 10개 Article URL을 정리하고, 바 그래프로 시각화합니다.

        10. top_10_liked_rereplies.csv
            - 좋아요(Rereply Like)가 가장 많은 대댓글 10개를 추출합니다.

        11. rereply_time_delta_distribution.png
            - (대댓글 작성 날짜 - 게시물 업로드 날짜)를 일(day) 단위로 계산한 시차 분포를 히스토그램으로 확인합니다.

        12. correlation_matrix.csv / correlation_matrix.png
            - 'Rereply Like', 'RereplyTimeDelta' 등의 수치 컬럼 간 상관관계를 나타냅니다.
        """
        with open(safe_path(os.path.join(output_dir, "description.txt")), "w", encoding="utf-8", errors="ignore") as f:
            f.write(description_text)

    def wordcloud(self, parent, data, folder_path, date, max_words, split_option, exception_word_list, eng=False):
        parent = parent
        self.translate_history = {}
        self.translator = Translator()

        def divide_period(csv_data, period):
            # 'Unnamed' 열 제거
            csv_data = csv_data.loc[:, ~
                                    csv_data.columns.str.contains('^Unnamed')]

            # 날짜 열을 datetime 형식으로 변환
            csv_data[self.dateColumn_name] = pd.to_datetime(
                csv_data[self.dateColumn_name].str.split().str[0], format='%Y-%m-%d', errors='coerce')

            # 'YYYYMMDD' 형식의 문자열을 datetime 형식으로 변환
            start_date = pd.to_datetime(str(date[0]), format='%Y%m%d')
            end_date = pd.to_datetime(str(date[1]), format='%Y%m%d')

            # 날짜 범위 필터링
            csv_data = csv_data[csv_data[self.dateColumn_name].between(
                start_date, end_date)]

            if start_date < csv_data[self.dateColumn_name].min():
                self.startdate = int(
                    csv_data[self.dateColumn_name].min().strftime('%Y%m%d'))

            if end_date > csv_data[self.dateColumn_name].max():
                self.enddate = int(
                    csv_data[self.dateColumn_name].max().strftime('%Y%m%d'))

            if period == 'total':
                csv_data['period_group'] = 'total'
            else:
                # 'period_month' 열 추가 (월 단위 기간으로 변환)
                csv_data['period_month'] = csv_data[self.dateColumn_name].dt.to_period(
                    'M')

                # 필요한 전체 기간 생성
                full_range = pd.period_range(start=csv_data['period_month'].min(), end=csv_data['period_month'].max(),
                                             freq='M')
                full_df = pd.DataFrame(full_range, columns=['period_month'])

                # 원본 데이터와 병합하여 빈 기간도 포함하도록 함
                csv_data = pd.merge(full_df, csv_data,
                                    on='period_month', how='left')

                # 새로운 열을 추가하여 주기 단위로 기간을 그룹화
                if period == '1m':  # 월
                    csv_data['period_group'] = csv_data['period_month'].astype(
                        str)
                elif period == '3m':  # 분기
                    csv_data['period_group'] = (csv_data['period_month'].dt.year.astype(str) + 'Q' + (
                        (csv_data['period_month'].dt.month - 1) // 3 + 1).astype(str))
                elif period == '6m':  # 반기
                    csv_data['period_group'] = (csv_data['period_month'].dt.year.astype(str) + 'H' + (
                        (csv_data['period_month'].dt.month - 1) // 6 + 1).astype(str))
                elif period == '1y':  # 연도
                    csv_data['period_group'] = csv_data['period_month'].dt.year.astype(
                        str)
                elif period == '1w':  # 주
                    csv_data['period_group'] = csv_data[self.dateColumn_name].dt.to_period('W').apply(
                        lambda x: f"{x.start_time.strftime('%Y%m%d')}-{x.end_time.strftime('%Y%m%d')}"
                    )
                    first_date = csv_data['period_group'].iloc[0].split('-')[0]
                    end_date = csv_data['period_group'].iloc[-1].split('-')[1]
                    self.startdate = first_date
                    self.enddate = end_date
                elif period == '1d':  # 일
                    csv_data['period_group'] = csv_data[self.dateColumn_name].dt.to_period(
                        'D').astype(str)

            # 주기별로 그룹화하여 결과 반환
            period_divided_group = csv_data.groupby('period_group')

            return period_divided_group

        os.makedirs(os.path.join(folder_path, 'data'), exist_ok=True)

        for column in data.columns.tolist():
            if 'Text' in column:
                self.textColumn_name = column
            elif 'Date' in column:
                self.dateColumn_name = column

        print("\n데이터 분할 중...\n")
        printStatus(parent, "데이터 분할 중...")
        grouped = divide_period(data, split_option)
        period_list = list(grouped.groups.keys())

        i = 0

        if get_setting('ProcessConsole') == 'default':
            iterator = tqdm(grouped, desc="WordCloud ", file=sys.stdout,
                            bar_format="{l_bar}{bar}|", ascii=' =')
        else:
            iterator = grouped

        for period_start, group in iterator:
            printStatus(parent, f"wordcloud_{period_list[i]} 생성 중...")
            if group.empty:
                continue

            # 단어 리스트 병합
            all_words = []
            for tokens in group[self.textColumn_name]:
                if isinstance(tokens, str):  # 토큰 리스트가 문자열로 저장된 경우
                    tokens = tokens.split(',')
                    all_words.extend(tokens)

            if exception_word_list != []:
                all_words = [
                    item.strip() for item in all_words if item.strip() not in exception_word_list]

            # 단어 빈도 계산
            self.word_freq = dict(
                Counter(all_words).most_common(max_words))  # 딕셔너리 변환
            if eng == True:
                printStatus(parent, f"단어 영문 변환 중...")
                asyncio.run(self.wordcloud_translator())

            # 워드클라우드 생성
            wordcloud = WordCloud(font_path=os.path.join(os.path.dirname(
                __file__), '..', 'assets', 'malgun.ttf'), background_color='white', width=800, height=600, max_words=max_words)
            wc_generated = wordcloud.generate_from_frequencies(self.word_freq)

            # 워드클라우드 저장
            output_file = os.path.join(
                folder_path, f'wordcloud_{period_list[i]}.png')
            if split_option == 'total':
                output_file = os.path.join(
                    folder_path, f'wordcloud_{date[0]}~{date[1]}.png')

            wc_generated.to_file(output_file)

            # CSV 파일로 저장
            output_file = os.path.join(
                folder_path, 'data', f'wordcount_{period_list[i]}.csv')
            if split_option == 'total':
                output_file = os.path.join(
                    folder_path, 'data', f'wordcount_{date[0]}~{date[1]}.csv')

            with open(safe_path(output_file), mode="w", newline="", encoding="utf-8", errors="ignore") as file:
                writer = csv.writer(file)
                # 헤더 작성
                writer.writerow(["word", "count"])
                # 데이터 작성
                for word, count in self.word_freq.items():
                    writer.writerow([word, count])

            i += 1

    async def wordcloud_translator(self):
        translator = Translator()

        # 번역할 한글 단어 목록 (self.word_freq의 키값들 중 번역되지 않은 단어만)
        word_dict = self.word_freq
        words_to_translate = [
            word for word in word_dict.keys() if word not in self.translate_history]

        # 병렬 번역 수행 (이미 번역된 단어 제외)
        if words_to_translate:
            async def translate_word(word):
                """ 개별 단어를 비동기적으로 번역하고 반환하는 함수 """
                result = await translator.translate(word, dest='en', src='auto')  # ✅ await 추가
                return word, result.text  # ✅ 번역 결과 반환

            # 번역 실행 (병렬 처리)
            translated_results = await asyncio.gather(*(translate_word(word) for word in words_to_translate))

            # 번역 결과를 캐시에 저장
            for original, translated in translated_results:
                self.translate_history[original] = translated

        # 변환된 word_freq 딕셔너리 생성 (캐시 포함)
        self.word_freq = {k: v for k, v in sorted(
            {self.translate_history[word]: word_dict[word]
                for word in word_dict.keys()}.items(),
            key=lambda item: item[1],
            reverse=True
        )}

    def HateAnalysis(self, data: pd.DataFrame, file_path: str):
        """
        Hate / Clean / 레이블 컬럼이 포함된 CSV를 받아 자동으로
        option1 : Hate   열만 있음
        option2 : 10개 레이블(여성/가족‥clean) 열이 있음
        option3 : Clean  열만 있음
        을 판별하고 ▸ 기본 통계 ▸ 월·일별·7일 Rolling 평균
        ▸ 상위 Top-N 기간 ▸ 상관관계 히트맵 ▸ 분포·추세 그래프
        를 `<원본>_hate_analysis/` 폴더에 저장한다.
        """

        # ─────────────────────────────────────────────
        # 0) 날짜 열 확인
        # ─────────────────────────────────────────────
        date_col = next((c for c in data.columns if "Date" in c), None)
        if date_col is None:
            QMessageBox.warning(self.main, "Warning", "'Date' 가 포함된 열을 찾을 수 없습니다.")
            return
        data[date_col] = pd.to_datetime(data[date_col], errors="coerce")

        # ─────────────────────────────────────────────
        # 1) 모드 판별 & 대상 열
        # ─────────────────────────────────────────────
        LABEL_COLS = {
            "여성/가족", "남성", "성소수자", "인종/국적",
            "연령", "지역", "종교", "기타 혐오", "악플/욕설", "clean",
        }
        mode, target_cols = None, []

        if "Hate" in data.columns:                 # option1
            mode, target_cols = 1, ["Hate"]

        else:
            present_lbl = [c for c in LABEL_COLS if c in data.columns]
            if len(present_lbl) >= 8:              # option2
                mode, target_cols = 2, present_lbl
            elif set(present_lbl) == {"clean"}:    # option3
                mode, target_cols = 3, ["clean"]

        if mode is None:
            QMessageBox.warning(self.main, "Warning", "Hate / Clean / 레이블 열이 없습니다.")
            return

        # ─────────────────────────────────────────────
        # 2) 결과 폴더
        # ─────────────────────────────────────────────
        out_dir   = os.path.join(
            os.path.dirname(file_path),
            os.path.splitext(os.path.basename(file_path))[0] + "_hate_analysis"
        )
        csv_dir   = os.path.join(out_dir, "csv_files")
        graph_dir = os.path.join(out_dir, "graphs")
        os.makedirs(csv_dir,   exist_ok=True)
        os.makedirs(graph_dir, exist_ok=True)

        def _safe_fname(label: str) -> str:
            return re.sub(r'[\\/*?:"<>|]', "_", label)

        # ─────────────────────────────────────────────
        # 3) 기본 통계
        # ─────────────────────────────────────────────
        basic_stats = data[target_cols].describe()
        basic_stats.to_csv(os.path.join(csv_dir, "basic_stats.csv"), encoding="utf-8-sig")

        # ─────────────────────────────────────────────
        # 4) 기간별 평균 & 7-일 Rolling
        # ─────────────────────────────────────────────
        monthly = (
            data.groupby(data[date_col].dt.to_period("M"))[target_cols]
                .mean().reset_index()
        )
        monthly[date_col] = monthly[date_col].dt.to_timestamp()
        monthly.to_csv(os.path.join(csv_dir, "monthly_mean.csv"),
                    encoding="utf-8-sig", index=False)

        daily = (
            data.groupby(data[date_col].dt.to_period("D"))[target_cols]
                .mean().reset_index()
        )
        daily[date_col] = daily[date_col].dt.to_timestamp()
        daily.to_csv(os.path.join(csv_dir, "daily_mean.csv"),
                    encoding="utf-8-sig", index=False)

        # 7-일 이동평균(트렌드 부드럽게 보기용)
        rolling7 = (
            data.set_index(date_col)
                .sort_index()[target_cols]
                .rolling("7D").mean()
                .reset_index()
        )
        rolling7.to_csv(os.path.join(csv_dir, "rolling7_mean.csv"),
                        encoding="utf-8-sig", index=False)

        # ─────────────────────────────────────────────
        # 5) Top-N 기간 (가장 높은 Hate/clean)
        # ─────────────────────────────────────────────
        topN = 10
        top_days = (
            daily.sort_values(target_cols[0], ascending=False)
                .head(topN)
        )
        top_days.to_csv(os.path.join(csv_dir, "top10_days.csv"),
                        encoding="utf-8-sig", index=False)

        top_months = (
            monthly.sort_values(target_cols[0], ascending=False)
                .head(topN)
        )
        top_months.to_csv(os.path.join(csv_dir, "top10_months.csv"),
                        encoding="utf-8-sig", index=False)

        # ─────────────────────────────────────────────
        # 6) 상관관계(옵션2 전용 또는 Hate+Clean 동시 존재 시)
        # ─────────────────────────────────────────────
        corr_cols = target_cols.copy()
        if "Hate" in data.columns and "clean" in data.columns:
            corr_cols = ["Hate", "clean"]
        if len(corr_cols) > 1:
            corr = data[corr_cols].corr()
            corr.to_csv(os.path.join(csv_dir, "correlation.csv"), encoding="utf-8-sig")

            plt.figure(figsize=self.calculate_figsize(len(corr), height=6))
            sns.heatmap(corr, annot=True, cmap="coolwarm", vmin=-1, vmax=1)
            plt.title("Correlation Matrix")
            plt.tight_layout()
            plt.savefig(os.path.join(graph_dir, "correlation_heatmap.png"))
            plt.close()

        # ─────────────────────────────────────────────
        # 7) 그래프
        # ─────────────────────────────────────────────
        # (1) 월별 추세
        plt.figure(figsize=self.calculate_figsize(len(monthly)))
        for col in target_cols[:6]:
            sns.lineplot(data=monthly, x=date_col, y=col, label=col)
        plt.title("월별 평균 점수 추세")
        plt.xlabel("Month"); plt.ylabel("Mean Score")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_dir, "monthly_trend.png"))
        plt.close()

        # (2) 7-일 이동 평균 추세(부드러운 라인)
        plt.figure(figsize=self.calculate_figsize(len(rolling7)))
        for col in target_cols[:6]:
            sns.lineplot(data=rolling7, x=date_col, y=col, label=col)
        plt.title("7-Day Rolling Mean Trend")
        plt.xlabel("Date"); plt.ylabel("Rolling Mean")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_dir, "rolling7_trend.png"))
        plt.close()

        # (3) 점수 분포
        for col in target_cols:
            plt.figure(figsize=self.calculate_figsize(10))
            sns.histplot(data[col], kde=True, bins=50)
            plt.title(f"{col} 영역 혐오도 분포")
            plt.xlabel("Score"); plt.ylabel("Frequency")
            plt.tight_layout()
            plt.savefig(os.path.join(graph_dir, f"{_safe_fname(col)}_distribution.png"))
            plt.close()

        # (4) 레이블 히트맵(option2 전용)
        if mode == 2:
            heat_df = monthly.set_index(date_col)[target_cols]
            plt.figure(figsize=self.calculate_figsize(len(heat_df), height=8))
            sns.heatmap(
                heat_df.T,
                cmap="Reds", vmin=0, vmax=1,
                cbar_kws={"label": "월별 평균 확률"}
            )
            plt.title("월별 레이블 평균 히트맵")
            plt.tight_layout()
            plt.savefig(os.path.join(graph_dir, "label_heatmap.png"))
            plt.close()

        # ─────────────────────────────────────────────
        # 8) 설명 텍스트
        # ─────────────────────────────────────────────
        desc = [
            "★ 혐오 통계 분석 결과 안내",
            "",
            f"자동 판별된 모드  : option {mode}",
            "  option1 : Hate 열",
            "  option2 : 10개 레이블 열",
            "  option3 : Clean 열",
            "",
            "■ CSV",
            "  · basic_stats.csv      : 기초 통계",
            "  · monthly_mean.csv     : 월별 평균",
            "  · daily_mean.csv       : 일별 평균",
            "  · rolling7_mean.csv    : 7-일 이동 평균",
            "  · top10_days / months  : 가장 높은 점수 TOP 10",
            "  · correlation.csv      : 상관관계(해당 시)",
            "",
            "■ Graphs",
            "  · monthly_trend.png    : 월별 추세",
            "  · rolling7_trend.png   : 7-일 이동 평균 추세",
            "  · *_distribution.png   : 점수 분포 히스토그램",
            "  · correlation_heatmap.png : 상관관계 히트맵(해당 시)",
            "  · label_heatmap.png    : 레이블 히트맵(option2)",
        ]
        with open(safe_path(os.path.join(out_dir, "description.txt")), "w",
                encoding="utf-8", errors="ignore") as f:
            f.write("\n".join(desc))
