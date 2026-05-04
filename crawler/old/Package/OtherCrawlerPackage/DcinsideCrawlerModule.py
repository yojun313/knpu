import requests
import json

# API 엔드포인트 URL
api_url = "https://gall.dcinside.com/board/comment/"

# 요청 헤더
headers = {
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Host": "gall.dcinside.com",
    "Origin": "https://gall.dcinside.com",
    "Referer": "https://gall.dcinside.com/board/view/?id=dog&no=1023407",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

# 요청 데이터
data = {
    "id": "dcbest",
    "no": "253078",
    "cmt_id": "dcbest",
    "cmt_no": "253078",
    "focus_cno": "",
    "focus_pno": "",
    "e_s_n_o": "3eabc219ebdd65f539",
    "comment_page": "1",
    "sort": "",
    "prevCnt": "",
    "board_type": "",
    "_GALLTYPE_": "G"
}

# API 요청 보내기
response = requests.post(api_url, headers=headers, data=data)

# 응답 상태 코드 확인
if response.status_code == 200:
    try:
        # JSON 데이터 파싱
        data = response.json()

        # JSON 파일로 저장
        file_path = 'comments.json'
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print("댓글 데이터를 comments.json 파일로 저장했습니다.")

        # JSON 파일을 다시 읽어들여 출력
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            print("저장된 JSON 파일 내용:")
            print(json.dumps(loaded_data, ensure_ascii=False, indent=4))

        # 댓글 개수 확인
        comment_count = len(data.get("comments", []))
        print(f"수집된 댓글 개수: {comment_count}")

    except json.JSONDecodeError as e:
        print("JSON 디코딩 오류 발생:", e)
        print("응답 내용:", response.text)
else:
    print(f"API 요청에 실패했습니다. 상태 코드: {response.status_code}")
    print("응답 내용:", response.text)
