import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import os
from PIL import Image

def create_coordinates_animation(yearly_coordinates_dict, output_filename='coordinates_animation.gif'):
    
    def calculate_axis_avg(yearly_coordinates_dict):
        x_values = []
        y_values = []

        # 각 연도의 axis 값을 추출하여 리스트에 추가
        for year, data in yearly_coordinates_dict.items():
            axis_coords = data['axis']
            x_values.append(axis_coords[0])
            y_values.append(axis_coords[1])

        # x와 y의 평균값 계산
        avg_x = np.mean(x_values)
        avg_y = np.mean(y_values)

        return avg_x, avg_y
    
    # 모든 연도의 axis 평균값 계산
    avg_x, avg_y = calculate_axis_avg(yearly_coordinates_dict)

    # 연도 순서대로 정렬
    years = sorted(yearly_coordinates_dict.keys())

    # 첫 번째 연도의 데이터 사용하여 플롯 초기화
    first_year_data = yearly_coordinates_dict[years[0]]
    words = [key for key in first_year_data.keys() if key != 'axis']  # 'axis'를 제외한 단어들

    # 초기 좌표 설정
    fig, ax = plt.subplots(figsize=(10, 10))
    initial_coords = np.array([first_year_data[word] for word in words])
    scatter = ax.scatter(initial_coords[:, 0], initial_coords[:, 1])

    # 텍스트 추가
    texts = [ax.text(coord[0], coord[1], word, fontsize=12) for coord, word in zip(initial_coords, words)]

    # x, y 축의 범위 설정
    ax.set_xlim(min(initial_coords[:, 0]) - 1, max(initial_coords[:, 0]) + 1)
    ax.set_ylim(min(initial_coords[:, 1]) - 1, max(initial_coords[:, 1]) + 1)

    # x축 y축 교점을 모든 연도의 평균값으로 설정
    plt.axvline(x=avg_x, color='k', linestyle='--')  # x축 교점 수직선
    plt.axhline(y=avg_y, color='k', linestyle='--')  # y축 교점 수평선

    # 좌표와 해당 키를 표시
    def draw_coordinates(coords, texts):
        scatter.set_offsets(coords)
        for j, text in enumerate(texts):
            text.set_position((coords[j][0], coords[j][1]))

    def interpolate_coords(start_coords, end_coords, num_steps):
        return np.linspace(start_coords, end_coords, num_steps)

    def animate(i):
        year_idx = i // 20
        year = years[year_idx]
        next_year_idx = year_idx + 1 if year_idx + 1 < len(years) else year_idx
        next_year = years[next_year_idx]

        # 현재와 다음 연도의 좌표 데이터 추출
        current_data = yearly_coordinates_dict[year]
        next_data = yearly_coordinates_dict[next_year]

        current_coords = np.array([current_data[word] for word in words])
        next_coords = np.array([next_data[word] for word in words])

        # 보간을 통해 좌표 값 계산
        interpolated_coords = interpolate_coords(current_coords, next_coords, 20)[i % 20]

        draw_coordinates(interpolated_coords, texts)
        ax.set_title(f'Keyword Positions in {year}', fontsize=16)

    # GIF로 저장 (더 부드러운 진행을 위해 20 프레임씩 보간)
    frames = []
    output_folder = os.path.dirname(output_filename)
    
    for i in range((len(years) - 1) * 20):
        animate(i)
        frame_filename = os.path.join(output_folder, f"frame_{i}.png")
        plt.savefig(frame_filename)
        frames.append(Image.open(frame_filename))

    # Pillow를 사용해 GIF로 저장
    frames[0].save(output_filename, save_all=True, append_images=frames[1:], duration=100, loop=0)

    # 임시로 저장된 이미지 파일 삭제
    for i in range((len(years) - 1) * 20):
        os.remove(os.path.join(output_folder, f"frame_{i}.png"))

    plt.close()

# 예시 yearly_coordinates_dict
yearly_coordinates_dict = {
    '2020': {
        'axis': (2.0, 3.0),
        'word1': (1.0, 2.0),
        'word2': (2.0, 3.0),
        'word3': (3.0, 4.0),
    },
    '2021': {
        'axis': (2.0, 3.0),
        'word1': (2.0, 3.0),
        'word2': (3.0, 4.0),
        'word3': (4.0, 5.0),
    },
    '2022': {
        'axis': (2.0, 3.0),
        'word1': (3.0, 4.0),
        'word2': (4.0, 5.0),
        'word3': (5.0, 6.0),
    }
}

# 애니메이션 생성 함수 실행
create_coordinates_animation(yearly_coordinates_dict, 'coordinates_animation.gif')
