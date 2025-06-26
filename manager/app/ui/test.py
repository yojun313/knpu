import requests
import os

API_URL = "https://home.knpu.re.kr/api/image/"  # 업로드 API 엔드포인트
image_path = "/Users/yojunsmacbookprp/Documents/MANAGER/김재준.jpg"           # 업로드할 파일 경로
# 선택할 폴더 (members/news/papers/misc)
folder = "members"

# 파일 존재 여부 검사
if not os.path.exists(image_path):
    raise FileNotFoundError(f"{image_path} 파일 없음")

# multipart/form-data 구성
with open(image_path, "rb") as file_obj:
    files = {
        # (filename, fileobj, mimetype)
        "file": (os.path.basename(image_path), file_obj, "image/png"),
    }
    data = {
        "folder": folder
    }

    print("▶︎ 업로드 요청 전송 중...")
    headers = {
        "Authorization": "Bearer ***REMOVED***"
    }
    response = requests.post(API_URL, files=files, headers=headers, data=data)

# 상태 검사
try:
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"❌ 업로드 실패: {e}")
else:
    print("✅ 업로드 성공!")
    print("업로드된 URL:", response.json().get("url"))
