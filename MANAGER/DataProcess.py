from PyQt5.QtWidgets import QMessageBox
import pandas as pd
import sys
import matplotlib.pyplot as plt
import seaborn as sns
import platform
from wordcloud import WordCloud
from collections import Counter
import os
from tqdm import tqdm
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 크기 제한 해제
import warnings
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
            group_data.to_csv(f"{data_path}/{folder_name}/{tablename+'_'+str(group_name)}.csv", index=False, encoding='utf-8-sig', header=True)

        # 정보 파일 생성
        info_df = pd.DataFrame(list(info.items()), columns=[info_label, 'Count'])
        info_df.to_csv(f"{data_path}/{folder_name}/{folder_name} Count.csv", index=False, encoding='utf-8-sig', header=True)

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
        data['Article Date'] = pd.to_datetime(data['Article Date'], errors='coerce')
        # 'Article ReplyCnt' 열을 숫자로 변환하고, 변환이 안 되는 값은 NaN으로 처리
        data['Article ReplyCnt'] = pd.to_numeric(data['Article ReplyCnt'], errors='coerce').fillna(0)

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 시간에 따른 기사 및 댓글 수 분석
        time_analysis = data.groupby(data['Article Date'].dt.to_period("M")).agg({
            'id': 'count',
            'Article ReplyCnt': 'sum'
        }).rename(columns={'id': 'Article Count'}).reset_index()
        time_analysis['Article Date'] = time_analysis['Article Date'].dt.to_timestamp()

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
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig', index=False)
        article_type_analysis.to_csv(os.path.join(csv_output_dir, "article_type_analysis.csv"), encoding='utf-8-sig',
                                     index=False)
        press_analysis.to_csv(os.path.join(csv_output_dir, "press_analysis.csv"), encoding='utf-8-sig', index=False)
        # correlation_matrix.to_csv(os.path.join(output_dir, "correlation_matrix.csv"), encoding='utf-8-sig', index=False)

        # For time_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(time_analysis)))
        sns.lineplot(data=time_analysis, x='Article Date', y='Article Count', label='Article Count')
        sns.lineplot(data=time_analysis, x='Article Date', y='Article ReplyCnt', label='Reply Count')
        plt.title('Monthly Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_article_reply_count.png"))
        plt.close()

        # For article_type_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(article_type_analysis)))
        article_type_analysis = article_type_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x='Article Type', y='Article Count', data=article_type_analysis, palette="viridis")
        plt.title('Article Count by Type')
        plt.xlabel('Article Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_type_count.png"))
        plt.close()

        # For press_analysis graph
        plt.figure(figsize=self.calculate_figsize(len(press_analysis)))
        press_analysis = press_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x='Article Press', y='Article Count', data=press_analysis, palette="plasma")
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
        """

        # 설명을 txt 파일로 저장
        description_file_path = os.path.join(output_dir, "description.txt")
        with open(description_file_path, 'w') as file:
            file.write(description_text)

    def NaverNewsStatisticsAnalysis(self, data, file_path):
        if 'Male' not in list(data.columns):
            QMessageBox.warning(self.main, f"Warning", f"NaverNews Statistics CSV 형태와 일치하지 않습니다")
            return

        # 'Article Date'를 datetime 형식으로 변환 (오류 발생 시 NaT로 변환)
        data['Article Date'] = pd.to_datetime(data['Article Date'], errors='coerce')

        # 'Article ReplyCnt'를 숫자(float)로 변환
        data['Article ReplyCnt'] = pd.to_numeric(data['Article ReplyCnt'], errors='coerce').fillna(0)

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
        numeric_columns = ['Article ReplyCnt', 'Male', 'Female', '10Y', '20Y', '30Y', '40Y', '50Y', '60Y']
        correlation_matrix = data[numeric_columns].corr()

        # 결과를 CSV로 저장
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig', index=False)
        article_type_analysis.to_csv(os.path.join(csv_output_dir, "article_type_analysis.csv"), encoding='utf-8-sig',
                                     index=False)
        press_analysis.to_csv(os.path.join(csv_output_dir, "press_analysis.csv"), encoding='utf-8-sig', index=False)
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig',
                                  index=False)

        # 시각화 그래프를 이미지 파일로 저장

        # 1. 월별 기사 및 댓글 수 추세
        plt.figure(figsize=self.calculate_figsize(len(time_analysis)))
        sns.lineplot(data=time_analysis, x='Article Date', y='Article Count', label='Article Count')
        sns.lineplot(data=time_analysis, x='Article Date', y='Article ReplyCnt', label='Reply Count')
        plt.title('Monthly Article and Reply Count Over Time')
        plt.xlabel('Date')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "monthly_article_reply_count.png"))
        plt.close()

        # 2. 기사 유형별 기사 및 댓글 수
        plt.figure(figsize=self.calculate_figsize(len(article_type_analysis)))
        article_type_analysis = article_type_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x='Article Type', y='Article Count', data=article_type_analysis, palette="viridis")
        plt.title('Article Count by Type')
        plt.xlabel('Article Type')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "article_type_count.png"))
        plt.close()

        # 3. 상위 10개 언론사별 기사 및 댓글 수
        plt.figure(figsize=self.calculate_figsize(len(press_analysis)))
        press_analysis = press_analysis.sort_values('Article Count', ascending=False)
        sns.barplot(x='Article Press', y='Article Count', data=press_analysis, palette="plasma")
        plt.title('Top 10 Press by Article Count')
        plt.xlabel('Press')
        plt.ylabel('Count')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "press_article_count.png"))
        plt.close()

        # 4. 상관관계 행렬 히트맵
        plt.figure(figsize=self.calculate_figsize(len(correlation_matrix), height=8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Correlation Matrix of Key Metrics')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "correlation_matrix.png"))
        plt.close()

        # 5. 성별 댓글 수 분석
        gender_reply_count = {'Male': data['Male'].sum(), 'Female': data['Female'].sum()}
        gender_reply_df = pd.DataFrame(list(gender_reply_count.items()), columns=['Gender', 'Reply Count'])
        plt.figure(figsize=self.calculate_figsize(len(gender_reply_df), base_width=8))
        sns.barplot(x='Gender', y='Reply Count', data=gender_reply_df, palette="pastel")
        plt.title('Total Number of Replies by Gender')
        plt.xlabel('Gender')
        plt.ylabel('Reply Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "gender_reply_count.png"))
        plt.close()
        gender_reply_df.to_csv(os.path.join(csv_output_dir, "gender_reply_count.csv"), index=False,
                               encoding='utf-8-sig')

        # 6. 연령대별 댓글 수 분석
        age_group_reply_count = {age: data[age].sum() for age in ['10Y', '20Y', '30Y', '40Y', '50Y', '60Y']}
        age_group_reply_df = pd.DataFrame(list(age_group_reply_count.items()), columns=['Age Group', 'Reply Count'])
        plt.figure(figsize=self.calculate_figsize(len(age_group_reply_df), base_width=10))
        sns.barplot(x='Age Group', y='Reply Count', data=age_group_reply_df, palette="coolwarm")
        plt.title('Total Number of Replies by Age Group')
        plt.xlabel('Age Group')
        plt.ylabel('Reply Count')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_output_dir, "age_group_reply_count.png"))
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
        data['Reply Date'] = pd.to_datetime(data['Reply Date'], errors='coerce')

        # 각 열을 숫자로 변환
        for col in ['Rereply Count', 'Reply Like', 'Reply Bad', 'Reply LikeRatio', 'Reply Sentiment']:
            data[col] = pd.to_numeric(data[col], errors='coerce')

        # Reply Text 열이 문자열이 아닌 값이 있거나 NaN일 경우 대비
        data['Reply Text'] = data['Reply Text'].astype(str).fillna('')

        # 댓글 길이 추가
        data['Reply Length'] = data['Reply Text'].apply(lambda x: len(x) if isinstance(x, str) else 0)

        # 기본 통계 분석
        basic_stats = data.describe(include='all')

        # 날짜별 댓글 수 분석
        time_analysis = data.groupby(data['Reply Date'].dt.date).agg({
            'id': 'count',
            'Reply Like': 'sum',
            'Reply Bad': 'sum'
        }).rename(columns={'id': 'Reply Count'})

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
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig')
        sentiment_counts.to_csv(os.path.join(csv_output_dir, "sentiment_counts.csv"), encoding='utf-8-sig')
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig')
        writer_reply_count.to_csv(os.path.join(csv_output_dir, "writer_reply_count.csv"), encoding='utf-8-sig')

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

        # 'Rereply Date'를 datetime 형식으로 변환 (오류 발생 시 NaT로 변환)
        data['Rereply Date'] = pd.to_datetime(data['Rereply Date'], errors='coerce')

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

        # 댓글 감성 분석 결과 빈도
        sentiment_counts = data['Rereply Sentiment'].value_counts()

        # 상관관계 분석 (숫자형 컬럼만 선택)
        numeric_columns = ['Rereply Like', 'Rereply Bad', 'Rereply Length', 'Rereply LikeRatio', 'Rereply Sentiment']
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
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig', index=False)
        sentiment_counts.to_csv(os.path.join(csv_output_dir, "sentiment_counts.csv"), encoding='utf-8-sig')
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig')
        writer_reply_count.to_csv(os.path.join(csv_output_dir, "writer_rereply_count.csv"), encoding='utf-8-sig')

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

        # 2. 댓글 감성 분석 결과 분포
        data_length = len(sentiment_counts)
        plt.figure(figsize=self.calculate_figsize(data_length, base_width=8))
        sns.countplot(x='Rereply Sentiment', data=data.fillna(''))
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
        top_10_writers = writer_reply_count.head(10)
        plt.figure(figsize=self.calculate_figsize(len(top_10_writers)))
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
        basic_stats.to_csv(os.path.join(csv_output_dir, "basic_stats.csv"), encoding='utf-8-sig')
        cafe_analysis.to_csv(os.path.join(csv_output_dir, "cafe_analysis.csv"), encoding='utf-8-sig')
        writer_analysis.to_csv(os.path.join(csv_output_dir, "writer_analysis.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig')
        correlation_matrix.to_csv(os.path.join(csv_output_dir, "correlation_matrix.csv"), encoding='utf-8-sig')

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
        writer_analysis.to_csv(os.path.join(csv_output_dir, "writer_analysis.csv"), encoding='utf-8-sig')
        time_analysis.to_csv(os.path.join(csv_output_dir, "time_analysis.csv"), encoding='utf-8-sig')

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

    def wordcloud(self, parent, data, folder_path, date, max_words, split_option, exception_word_list):
        parent = parent
        def divide_period(csv_data, period):
            # 'Unnamed' 열 제거
            csv_data = csv_data.loc[:, ~csv_data.columns.str.contains('^Unnamed')]

            # 날짜 열을 datetime 형식으로 변환
            csv_data[self.dateColumn_name] = pd.to_datetime(csv_data[self.dateColumn_name].str.split().str[0],
                                                            format='%Y-%m-%d', errors='coerce')

            # 'YYYYMMDD' 형식의 문자열을 datetime 형식으로 변환
            start_date = pd.to_datetime(str(date[0]), format='%Y%m%d')
            end_date = pd.to_datetime(str(date[1]), format='%Y%m%d')

            # 날짜 범위 필터링
            csv_data = csv_data[csv_data[self.dateColumn_name].between(start_date, end_date)]

            if start_date < csv_data[self.dateColumn_name].min():
                self.startdate = int(csv_data[self.dateColumn_name].min().strftime('%Y%m%d'))

            if end_date > csv_data[self.dateColumn_name].max():
                self.enddate = int(csv_data[self.dateColumn_name].max().strftime('%Y%m%d'))

            # 'period_month' 열 추가 (월 단위 기간으로 변환)
            csv_data['period_month'] = csv_data[self.dateColumn_name].dt.to_period('M')

            # 필요한 전체 기간 생성
            full_range = pd.period_range(start=csv_data['period_month'].min(), end=csv_data['period_month'].max(),
                                         freq='M')
            full_df = pd.DataFrame(full_range, columns=['period_month'])

            # 원본 데이터와 병합하여 빈 기간도 포함하도록 함
            csv_data = pd.merge(full_df, csv_data, on='period_month', how='left')

            # 새로운 열을 추가하여 주기 단위로 기간을 그룹화
            if period == '1m':  # 월
                csv_data['period_group'] = csv_data['period_month'].astype(str)
            elif period == '3m':  # 분기
                csv_data['period_group'] = (csv_data['period_month'].dt.year.astype(str) + 'Q' + (
                            (csv_data['period_month'].dt.month - 1) // 3 + 1).astype(str))
            elif period == '6m':  # 반기
                csv_data['period_group'] = (csv_data['period_month'].dt.year.astype(str) + 'H' + (
                            (csv_data['period_month'].dt.month - 1) // 6 + 1).astype(str))
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

        os.makedirs(folder_path, exist_ok=True)

        for column in data.columns.tolist():
            if 'Text' in column:
                self.textColumn_name = column
            elif 'Date' in column:
                self.dateColumn_name = column

        print("\n데이터 분할 중...")
        parent.printStatus("데이터 분할 중...")
        grouped = divide_period(data, split_option)
        period_list = list(grouped.groups.keys())

        i = 0

        if parent.SETTING['ProcessConsole'] == 'default':
            iterator = tqdm(grouped, desc="WordCloud ", file=sys.stdout, bar_format="{l_bar}{bar}|", ascii=' =')
        else:
            iterator = grouped

        for period_start, group in iterator:
            parent.printStatus(f"wordcloud_{period_list[i]} 생성 중...")
            if group.empty:
                continue

            # 단어 리스트 병합
            all_words = []
            for tokens in group[self.textColumn_name]:
                if isinstance(tokens, str):  # 토큰 리스트가 문자열로 저장된 경우
                    tokens = tokens.split(',')
                    all_words.extend(tokens)

            all_words = [item for item in all_words if item not in exception_word_list]

            # 단어 빈도 계산
            word_freq = Counter(all_words)

            # 워드클라우드 생성
            wordcloud = WordCloud(font_path=os.path.join(os.path.dirname(__file__), 'source', 'malgun.ttf'), background_color='white', width=800, height=600, max_words=max_words)
            wc_generated = wordcloud.generate_from_frequencies(word_freq)

            # 워드클라우드 저장
            output_file = os.path.join(folder_path, f'wordcloud_{period_list[i]}.png')
            wc_generated.to_file(output_file)

            i += 1



