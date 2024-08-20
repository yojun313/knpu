import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import imageio
import io
from PIL import Image
import numpy as np

def filter_clockwise_movements(df):
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

# 예시 데이터 생성 (연도 증가)
data = {
    'Keyword': [f'Keyword_{i}' for i in range(1, 11)],  # 단어 개수 10개로 설정
    '2017': ['strong_signal', 'weak_signal', 'latent_signal', 'well_known_signal', 'strong_signal', 'weak_signal', 'latent_signal', 'well_known_signal', 'strong_signal', 'weak_signal'],
    '2018': ['weak_signal', 'weak_signal', 'weak_signal', 'latent_signal', 'well_known_signal', 'strong_signal', 'weak_signal', 'latent_signal', 'well_known_signal', 'strong_signal'],
    '2019': ['latent_signal', 'well_known_signal', 'strong_signal', 'weak_signal', 'latent_signal', 'well_known_signal', 'strong_signal', 'weak_signal', 'latent_signal', 'well_known_signal'],
    '2020': ['weak_signal', 'well_known_signal', 'well_known_signal', 'strong_signal', 'weak_signal', 'latent_signal', 'well_known_signal', 'strong_signal', 'weak_signal', 'latent_signal'],
    '2021': ['strong_signal', 'latent_signal', 'latent_signal', 'well_known_signal', 'strong_signal', 'weak_signal', 'latent_signal', 'well_known_signal', 'strong_signal', 'weak_signal'],
}
df = pd.DataFrame(data)
df.set_index('Keyword', inplace=True)

# 함수 호출
newdf, newlist = filter_clockwise_movements(df)

print(newdf)
print(newlist)