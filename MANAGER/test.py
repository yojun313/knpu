import pandas as pd
import re

# 예시 데이터프레임 생성
data = {
    'article': [
        'This is a long article text ... with some keyword ... and more text after the keyword ...',
        'Another article that mentions keyword somewhere in the middle of the text.',
        'This article does not mention the keyword at all.',
        'The keyword is at the beginning of this article and then continues with other content.'
    ]
}

df = pd.DataFrame(data)


# 키워드 및 주변 텍스트 추출 함수 정의
def extract_surrounding_text(text, keyword, chars_before=5, chars_after=5):
    # 키워드 위치 찾기
    match = re.search(keyword, text)
    if match:
        start = max(match.start() - chars_before, 0)
        end = min(match.end() + chars_after, len(text))
        return text[start:end]
    else:
        return None  # 키워드가 없으면 None 반환


# 키워드 리스트
keywords = ['keyword', 'another_keyword']  # 찾고자 하는 키워드 리스트

# 결과를 저장할 딕셔너리
extracted_text_dict = {}

# 각 키워드에 대해 데이터프레임에서 텍스트 추출
for keyword in keywords:
    extracted_texts = df['article'].apply(lambda x: extract_surrounding_text(x, keyword))

    # 키워드가 포함된 텍스트만 딕셔너리에 추가
    keyword_texts = extracted_texts.dropna().tolist()
    if keyword_texts:
        extracted_text_dict[keyword] = "\n\n".join(keyword_texts)

# 결과 출력
print(extracted_text_dict)
