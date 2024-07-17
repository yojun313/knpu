import json

def extract_json_from_string(input_str):
    try:
        # 첫 번째 '{'의 인덱스를 찾습니다.
        start_index = input_str.index('{')
        # 마지막 '}'의 인덱스를 찾습니다.
        end_index = input_str.rindex('}') + 1
        # JSON 문자열을 추출합니다.
        json_str = input_str[start_index:end_index]
        # JSON 문자열을 딕셔너리로 변환합니다.
        json_data = json.loads(json_str)
        return json_data
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error extracting JSON: {e}")
        return None

# 예제 사용법
input_str = 'Zepto1721225570616({"status":1,"msg":"","data":[]});'
json_data = extract_json_from_string(input_str)
print(json_data)
