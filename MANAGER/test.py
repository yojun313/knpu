import re

def keyword_splitter(keyword):
    # 구분자를 기준으로 단어 분리
    word_list = re.split(r'\s*[+-]\s*', keyword)
    
    # 원래 기호가 포함된 구분자를 추출
    signs = re.findall(r'[+-]', keyword)
    
    # 맨 처음 단어는 query 변수에 할당
    query = word_list[0].strip()
    
    plus_list = []
    minus_list = []
    
    # 남은 단어들을 + 또는 - 기호에 따라 리스트에 분류
    for sign, word in zip(signs, word_list[1:]):
        if sign == '+':
            plus_list.append(word.strip())
        elif sign == '-':
            minus_list.append(word.strip())
    
    print("Query:", query)
    print("Plus list:", plus_list)
    print("Minus list:", minus_list)

keyword_splitter("테러 +예고 -안녕 +\"테러\"")