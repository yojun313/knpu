import requests
from core.setting import set_setting, get_setting
from config import MANAGER_SERVER_API

def get_api_headers():
    """
    Returns the API headers with the current token.
    """
    token = get_setting("auth_token")
    return {
        "Authorization": f"Bearer {token}"
    }

def Request(method, url, **kwargs):
    try:
        full_url = f"{MANAGER_SERVER_API}/{url.lstrip('/')}"
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
