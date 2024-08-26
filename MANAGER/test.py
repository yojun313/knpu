def remove_trailing_empty_values(dictionary):
    # 딕셔너리의 키 리스트를 역순으로 가져옴
    keys = list(dictionary.keys())

    # 역순으로 빈 리스트를 가진 key를 제거
    for key in reversed(keys):
        if dictionary[key] == []:
            del dictionary[key]
        else:
            break  # 빈 리스트가 아닌 값을 만나면 멈춤

    return dictionary

# 예시 딕셔너리
my_dict = {
    'a': [1, 2],
    'b': [],
    'c': [],
    'd': [3],
    'e': []
}

# 함수 호출
updated_dict = remove_trailing_empty_values(my_dict)
print(updated_dict)
