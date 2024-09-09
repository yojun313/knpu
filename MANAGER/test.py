import pandas as pd

# 예시 데이터프레임
data = {'Article Text': [
    '사과와 바나나는 맛있다',
    '나는 당근과 오이를 좋아해',
    '포도와 바나나는 건강에 좋다',
    '사과는 신선하고 당근은 건강하다',
    '오렌지와 배는 맛있다'
]}

tableDF = pd.DataFrame(data)

# 포함 단어 리스트
incl_words = ['사과', '바나나']

# 제외 단어 리스트
excl_words = ['당근', '오이']

# incl_words에 있는 단어 중 하나라도 포함된 행을 필터링
tableDF = tableDF[tableDF['Article Text'].apply(lambda cell: any(word in cell for word in incl_words))]

# excl_words에 있는 단어가 하나도 포함되지 않은 행을 필터링
tableDF = tableDF[tableDF['Article Text'].apply(lambda cell: all(word not in cell for word in excl_words))]

# 결과 출력
print(tableDF)
