import requests
from core.setting import get_setting
from config import MANAGER_SERVER_API, HOMEPAGE_EDIT_API
import os
import mimetypes
from libs.path import safe_path


def get_api_headers():
    """
    Returns the API headers with the current token.
    """
    token = get_setting("auth_token")
    return {
        "Authorization": f"Bearer {token}"
    }

def Request(method, url, base_api = MANAGER_SERVER_API, **kwargs):
    try:
        full_url = f"{base_api}/{url.lstrip('/')}"
        kwargs["headers"] = get_api_headers()

        # 요청 메서드 분기
        method = method.lower()
        if method == 'get':
            response = requests.get(full_url, **kwargs)
        elif method == 'post':
            response = requests.post(full_url, **kwargs)
        elif method == 'put':
            response = requests.put(full_url, **kwargs)
        elif method == 'delete':
            response = requests.delete(full_url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()
        return response

    except requests.exceptions.HTTPError as http_err:
        try:
            error_message = http_err.response.json().get("message", str(http_err))
        except Exception:
            error_message = str(http_err)
        raise Exception(f"[HTTP Error] {error_message}")
    except requests.exceptions.RequestException as err:
        raise Exception(f"[Request Failed] {str(err)}")
    

def upload_homepage_image(src_path: str, folder: str = "misc", file_name: str = "default") -> str:
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"{src_path} 파일을 찾을 수 없습니다.")
    mimetypes.init()  # mimetypes 초기화
    mime_type, _ = mimetypes.guess_type(src_path)
    if mime_type is None:
        raise ValueError(f"{src_path}의 MIME 타입을 알 수 없음")

    with open(safe_path(src_path), "rb") as file:
        files = {
            "file": (os.path.basename(src_path), file, mime_type)
        }
        data = {
            "folder": folder,
            "object_name": f"{folder}/{file_name}.jpg"
        }
        
        response = Request('post', f"image/", base_api=HOMEPAGE_EDIT_API, files=files, data=data)
    print(response.status_code, response.text)
        
    return response.json()["url"]


