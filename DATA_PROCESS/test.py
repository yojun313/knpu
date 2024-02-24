import pandas as pd

# 데이터프레임 생성 예시
data = {
    'A': [1, 2, 3, 4, 5],
    'B': ['apple', 'banana', 'cherry', 'date', 'apple']
}

df = pd.DataFrame(data)

# 특정 열에서 특정 문자열을 포함하는 행 제거
df = df[~df['B'].str.contains('apple')]  # 'B' 열에서 'apple'을 포함하는 행을 제거

print(df)
