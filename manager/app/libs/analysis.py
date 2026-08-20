import asyncio
import warnings
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import platform
from wordcloud import WordCloud
from collections import Counter
import os
import csv
from googletrans import Translator
from PIL import Image
import re
from libs.path import safe_path

Image.MAX_IMAGE_PIXELS = None  # 크기 제한 해제
warnings.filterwarnings("ignore")

# 운영체제에 따라 한글 폰트를 설정
if platform.system() == "Darwin":  # macOS
    plt.rcParams["font.family"] = "AppleGothic"
elif platform.system() == "Windows":  # Windows
    plt.rcParams["font.family"] = "Malgun Gothic"  # 맑은 고딕 폰트 사용

# 폰트 설정 후 음수 기호가 깨지는 것을 방지
plt.rcParams["axes.unicode_minus"] = False


class DataProcess:
    def __init__(self, main_window):
        self.main = main_window

    def TimeSplitter(self, data):
        # data 형태: DataFrame
        data_columns = data.columns.tolist()

        for i in data_columns:
            if "Date" in i:
                word = i
                break

        data[word] = pd.to_datetime(data[word], format="%Y-%m-%d", errors="coerce")

        data["year"] = data[word].dt.year
        data["month"] = data[word].dt.month
        data["year_month"] = data[word].dt.to_period("M")
        data["week"] = data[word].dt.to_period("W")

        return data

    def TimeSplitToCSV(self, option, divided_group, data_path, tablename):
        # 폴더 이름과 데이터 그룹 설정
        data_group = divided_group
        if option == 1:
            folder_name = "Year Data"
            info_label = "Year"
        elif option == 2:
            folder_name = "Month Data"
            info_label = "Month"
        elif option == 3:
            folder_name = "Week Data"
            info_label = "Week"

        info = {}

        # 디렉토리 생성
        folder_path = os.path.join(data_path, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        # 데이터 그룹을 순회하며 파일 저장 및 정보 수집
        for group_name, group_data in data_group:
            info[str(group_name)] = len(group_data)
            safe_group_name = re.sub(r"[\/\\~\s:|]", "_", str(group_name))
            group_data.to_csv(
                safe_path(
                    f"{data_path}/{folder_name}/{tablename + '_' + str(safe_group_name)}.csv"
                ),
                index=False,
                encoding="utf-8-sig",
                header=True,
            )

        # 정보 파일 생성
        info_df = pd.DataFrame(list(info.items()), columns=[info_label, "Count"])
        info_df.to_csv(
            safe_path(f"{data_path}/{folder_name}/{folder_name} Count.csv"),
            index=False,
            encoding="utf-8-sig",
            header=True,
        )

        info_df.set_index(info_label, inplace=True)
        keys = list(info_df.index)
        values = info_df["Count"].tolist()

        # 데이터의 수에 따라 그래프 크기 자동 조정
        num_data_points = len(keys)
        width_per_data_point = 0.5  # 데이터 포인트 하나당 가로 크기 (조정 가능)
        base_width = 10  # 최소 가로 크기
        height = 6  # 고정된 세로 크기

        fig_width = max(base_width, num_data_points * width_per_data_point)

        plt.figure(figsize=(fig_width, height))

        # 그래프 그리기
        sns.lineplot(x=keys, y=values, marker="o")

        # 그래프 설정
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        plt.title(f"{info_label} Data Visualization")
        plt.xlabel(info_label)
        plt.ylabel("Values")

        # 그래프 저장
        plt.savefig(
            f"{data_path}/{folder_name}/{folder_name} Graph.png", bbox_inches="tight"
        )

    def wordcloud(
        self,
        parent,
        data,
        folder_path,
        date,
        max_words,
        split_option,
        exception_word_list,
        eng=False,
    ):
        self.translate_history = {}
        self.translator = Translator()

        def divide_period(csv_data, period):
            # 'Unnamed' 열 제거
            csv_data = csv_data.loc[:, ~csv_data.columns.str.contains("^Unnamed")]

            # 날짜 열을 datetime 형식으로 변환
            csv_data[self.dateColumn_name] = pd.to_datetime(
                csv_data[self.dateColumn_name].str.split().str[0],
                format="%Y-%m-%d",
                errors="coerce",
            )

            # 'YYYYMMDD' 형식의 문자열을 datetime 형식으로 변환
            start_date = pd.to_datetime(str(date[0]), format="%Y%m%d")
            end_date = pd.to_datetime(str(date[1]), format="%Y%m%d")

            # 날짜 범위 필터링
            csv_data = csv_data[
                csv_data[self.dateColumn_name].between(start_date, end_date)
            ]

            if start_date < csv_data[self.dateColumn_name].min():
                self.startdate = int(
                    csv_data[self.dateColumn_name].min().strftime("%Y%m%d")
                )

            if end_date > csv_data[self.dateColumn_name].max():
                self.enddate = int(
                    csv_data[self.dateColumn_name].max().strftime("%Y%m%d")
                )

            if period == "total":
                csv_data["period_group"] = "total"
            else:
                # 'period_month' 열 추가 (월 단위 기간으로 변환)
                csv_data["period_month"] = csv_data[self.dateColumn_name].dt.to_period(
                    "M"
                )

                # 필요한 전체 기간 생성
                full_range = pd.period_range(
                    start=csv_data["period_month"].min(),
                    end=csv_data["period_month"].max(),
                    freq="M",
                )
                full_df = pd.DataFrame(full_range, columns=["period_month"])

                # 원본 데이터와 병합하여 빈 기간도 포함하도록 함
                csv_data = pd.merge(full_df, csv_data, on="period_month", how="left")

                # 새로운 열을 추가하여 주기 단위로 기간을 그룹화
                if period == "1m":  # 월
                    csv_data["period_group"] = csv_data["period_month"].astype(str)
                elif period == "3m":  # 분기
                    csv_data["period_group"] = (
                        csv_data["period_month"].dt.year.astype(str)
                        + "Q"
                        + ((csv_data["period_month"].dt.month - 1) // 3 + 1).astype(str)
                    )
                elif period == "6m":  # 반기
                    csv_data["period_group"] = (
                        csv_data["period_month"].dt.year.astype(str)
                        + "H"
                        + ((csv_data["period_month"].dt.month - 1) // 6 + 1).astype(str)
                    )
                elif period == "1y":  # 연도
                    csv_data["period_group"] = csv_data["period_month"].dt.year.astype(
                        str
                    )
                elif period == "1w":  # 주
                    csv_data["period_group"] = (
                        csv_data[self.dateColumn_name]
                        .dt.to_period("W")
                        .apply(
                            lambda x: (
                                f"{x.start_time.strftime('%Y%m%d')}-{x.end_time.strftime('%Y%m%d')}"
                            )
                        )
                    )
                    first_date = csv_data["period_group"].iloc[0].split("-")[0]
                    end_date = csv_data["period_group"].iloc[-1].split("-")[1]
                    self.startdate = first_date
                    self.enddate = end_date
                elif period == "1d":  # 일
                    csv_data["period_group"] = (
                        csv_data[self.dateColumn_name].dt.to_period("D").astype(str)
                    )

            # 주기별로 그룹화하여 결과 반환
            period_divided_group = csv_data.groupby("period_group")

            return period_divided_group

        os.makedirs(os.path.join(folder_path, "data"), exist_ok=True)

        for column in data.columns.tolist():
            if "Text" in column:
                self.textColumn_name = column
            elif "Date" in column:
                self.dateColumn_name = column

        parent.message.emit("데이터 분할 중...")
        grouped = divide_period(data, split_option)
        period_list = list(grouped.groups.keys())

        i = 0
        iterator = grouped

        for period_start, group in iterator:
            period = period_list[i]
            parent.message.emit(
                f"{period} 워드클라우드 생성 중... ({i + 1}/{len(period_list)})"
            )
            if group.empty:
                continue

            # 단어 리스트 병합
            all_words = []
            for tokens in group[self.textColumn_name]:
                if isinstance(tokens, str):  # 토큰 리스트가 문자열로 저장된 경우
                    tokens = tokens.split(",")
                    all_words.extend(tokens)

            if exception_word_list != []:
                all_words = [
                    item.strip()
                    for item in all_words
                    if item.strip() not in exception_word_list
                ]

            # 단어 빈도 계산
            self.word_freq = dict(
                Counter(all_words).most_common(max_words)
            )  # 딕셔너리 변환
            if eng == True:
                asyncio.run(self.wordcloud_translator())

            # 워드클라우드 생성
            wordcloud = WordCloud(
                font_path=os.path.join(
                    os.path.dirname(__file__), "..", "assets", "malgun.ttf"
                ),
                background_color="white",
                width=800,
                height=600,
                max_words=max_words,
            )
            wc_generated = wordcloud.generate_from_frequencies(self.word_freq)

            # 워드클라우드 저장
            output_file = os.path.join(folder_path, f"wordcloud_{period}.png")
            if split_option == "total":
                output_file = os.path.join(
                    folder_path, f"wordcloud_{date[0]}~{date[1]}.png"
                )

            wc_generated.to_file(output_file)

            # CSV 파일로 저장
            output_file = os.path.join(folder_path, "data", f"wordcount_{period}.csv")
            if split_option == "total":
                output_file = os.path.join(
                    folder_path, "data", f"wordcount_{date[0]}~{date[1]}.csv"
                )

            with open(
                safe_path(output_file),
                mode="w",
                newline="",
                encoding="utf-8",
                errors="ignore",
            ) as file:
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
            word for word in word_dict.keys() if word not in self.translate_history
        ]

        # 병렬 번역 수행 (이미 번역된 단어 제외)
        if words_to_translate:

            async def translate_word(word):
                result = await translator.translate(
                    word, dest="en", src="auto"
                )  # await 추가
                return word, result.text  # 번역 결과 반환

            # 번역 실행 (병렬 처리)
            translated_results = await asyncio.gather(
                *(translate_word(word) for word in words_to_translate)
            )

            # 번역 결과를 캐시에 저장
            for original, translated in translated_results:
                self.translate_history[original] = translated

        # 변환된 word_freq 딕셔너리 생성 (캐시 포함)
        self.word_freq = {
            k: v
            for k, v in sorted(
                {
                    self.translate_history[word]: word_dict[word]
                    for word in word_dict.keys()
                }.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        }
