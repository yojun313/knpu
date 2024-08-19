import matplotlib.pyplot as plt
import matplotlib.animation as animation
import pandas as pd
import seaborn as sns
from PIL import Image
import numpy as np

def create_top_words_animation(dataframe, output_filename='top_words_animation.gif'):
    # 데이터프레임을 pandas로 변환
    df = pd.DataFrame(dataframe).fillna(0)

    # 연도별로 상위 10개 단어를 추출
    top_words_per_year = {}
    for year in df.columns:
        top_words_per_year[year] = df[year].nlargest(10).sort_values(ascending=True)

    # 색상 팔레트 설정 (세련된 색상)
    colors = sns.color_palette("husl", 10)

    # 애니메이션 초기 설정
    fig, ax = plt.subplots(figsize=(10, 6))

    # 보간 함수 생성
    def interpolate(start, end, num_steps):
        return np.linspace(start, end, num_steps)

    def animate(i):
        year_idx = i // 20
        year = list(top_words_per_year.keys())[year_idx]
        next_year_idx = year_idx + 1 if year_idx + 1 < len(top_words_per_year) else year_idx
        next_year = list(top_words_per_year.keys())[next_year_idx]

        start_data = top_words_per_year[year]
        end_data = top_words_per_year[next_year]

        # 데이터를 정렬하여 순위를 유지하게끔 보간
        combined_data = pd.concat([start_data, end_data], axis=1).fillna(0)
        combined_data.columns = ['start', 'end']
        combined_data['start_rank'] = combined_data['start'].rank(ascending=False, method='first')
        combined_data['end_rank'] = combined_data['end'].rank(ascending=False, method='first')

        interpolated_values = interpolate(combined_data['start'].values, combined_data['end'].values, 20)[i % 20]
        interpolated_ranks = interpolate(combined_data['start_rank'].values, combined_data['end_rank'].values, 20)[i % 20]

        # 순위에 따라 재정렬
        sorted_indices = np.argsort(interpolated_ranks)
        sorted_words = combined_data.index[sorted_indices]
        sorted_values = interpolated_values[sorted_indices]

        ax.clear()
        ax.barh(sorted_words, sorted_values, color=colors)
        ax.set_xlim(0, df.max().max() + 500)  # 최대 빈도수를 기준으로 x축 설정
        ax.set_title(f'Top 10 Keywords in {year}', fontsize=16)
        ax.set_xlabel('Frequency', fontsize=14)
        ax.set_ylabel('Keywords', fontsize=14)
        plt.box(False)

    # GIF로 저장 (더 부드러운 진행을 위해 20 프레임씩 보간)
    frames = []
    for i in range((len(top_words_per_year) - 1) * 20):
        animate(i)
        plt.savefig(f"frame_{i}.png")
        frames.append(Image.open(f"frame_{i}.png"))

    # Pillow를 사용해 GIF로 저장
    frames[0].save(output_filename, save_all=True, append_images=frames[1:], duration=100, loop=0)

    # 임시로 저장된 이미지 파일 삭제
    import os
    for i in range((len(top_words_per_year) - 1) * 20):
        os.remove(f"frame_{i}.png")

    plt.close()


# 예시 데이터 (연도 확장)
dataframe = {
    '2010': {'word_a': 2000, 'word_b': 1000, 'word_c': 500, 'word_d': 1500, 'word_e': 1200, 'word_f': 800,
             'word_g': 700, 'word_h': 600, 'word_i': 1400, 'word_j': 1600},
    '2011': {'word_a': 2100, 'word_b': 1100, 'word_c': 550, 'word_d': 1500, 'word_e': 1300, 'word_f': 900,
             'word_g': 750, 'word_h': 650, 'word_i': 1350, 'word_j': 1550},
    '2012': {'word_a': 2200, 'word_b': 1200, 'word_c': 600, 'word_d': 1400, 'word_e': 1250, 'word_f': 950,
             'word_g': 800, 'word_h': 700, 'word_i': 1300, 'word_j': 1500},
    '2013': {'word_a': 2300, 'word_b': 1300, 'word_c': 650, 'word_d': 1450, 'word_e': 1350, 'word_f': 1000,
             'word_g': 850, 'word_h': 750, 'word_i': 1350, 'word_j': 1650},
    '2014': {'word_a': 2400, 'word_b': 1400, 'word_c': 700, 'word_d': 1500, 'word_e': 1400, 'word_f': 1050,
             'word_g': 900, 'word_h': 800, 'word_i': 1400, 'word_j': 1700},
    # 더 많은 연도와 단어들 추가 가능
}

# 함수 실행
create_top_words_animation(dataframe, output_filename='top_words_animation.gif')
