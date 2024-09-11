import os
import requests

def download_new_version(download_url, local_filename):
    response = requests.get(download_url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"{local_filename} 다운로드 완료")

# 최신 버전의 exe 파일 다운로드
download_url = "https://knpu.re.kr:90/download/BIGMACLAB_MANAGER_1.7.0.exe"
local_path = "/Users/yojunsmacbookprp/Desktop/BIGMACLAB_MANAGER/BIGMACLAB_MANAGER_1.7.0.exe"
download_new_version(download_url, local_path)
