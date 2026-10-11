import requests
from core.setting import get_setting
from config import MANAGER_SERVER_API, HOMEPAGE_EDIT_API
import os
import mimetypes
from libs.path import safe_path

PUBLIC_BASE = "https://pub-60ca29aab33f424fab345807bd058d56.r2.dev"


def get_api_headers():
    token = get_setting("auth_token")
    return {"Authorization": f"Bearer {token}"}


class APIPermissionError(requests.exceptions.HTTPError):
    """An expected authentication/authorization failure, never a bug report."""


def handle_permission_error(parent, error):
    if not isinstance(error, APIPermissionError):
        return False
    from PySide6.QtWidgets import QMessageBox

    title = "로그인 필요" if error.response.status_code == 401 else "권한 없음"
    QMessageBox.warning(parent, title, str(error))
    return True


def Request(method, url, base_api=MANAGER_SERVER_API, **kwargs):
    full_url = f"{base_api}/{url.lstrip('/')}"
    kwargs["headers"] = get_api_headers()
    response = requests.request(method.upper(), full_url, **kwargs)
    if response.status_code in (401, 403):
        message = (
            "로그인이 만료되었습니다. 다시 로그인해 주시기 바랍니다."
            if response.status_code == 401
            else "이 작업을 수행할 권한이 없습니다."
        )
        try:
            detail = response.json().get("detail")
            if isinstance(detail, str) and detail:
                message = detail
        except (ValueError, AttributeError):
            pass
        raise APIPermissionError(message, response=response)
    response.raise_for_status()
    return response


def upload_homepage_image(
    src_path: str, folder: str = "misc", file_name: str = "default"
) -> str:
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"{src_path} 파일을 찾을 수 없습니다.")
    mimetypes.init()  # mimetypes 초기화
    mime_type, _ = mimetypes.guess_type(src_path)
    if mime_type is None:
        raise ValueError(f"{src_path}의 MIME 타입을 알 수 없음")

    with open(safe_path(src_path), "rb") as file:
        files = {"file": (os.path.basename(src_path), file, mime_type)}
        data = {"folder": folder, "object_name": f"{folder}/{file_name}.jpg"}

        response = Request(
            "post", f"image/", base_api=HOMEPAGE_EDIT_API, files=files, data=data
        )
    print(response.status_code, response.text)

    return response.json()["url"]


def delete_homepage_image(target: str) -> dict:
    if target.startswith("http"):
        object_name = target.split(f"{PUBLIC_BASE}/")[-1]
    else:
        object_name = target

    response = Request(
        "delete",
        "image/",
        base_api=HOMEPAGE_EDIT_API,
        params={"object_name": object_name},
    )

    print(f"Delete Status: {response.status_code}, Response: {response.text}")

    return response.json()
