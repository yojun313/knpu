import requests
from config import API_URL
from common.req import api_headers

def get_user(username:str = ""):
    res = requests.post(API_URL + '/users/', headers=api_headers()).json()
    res.raise_for_status()
    if username:
        for user in res['data']:
            if user['username'] == username:
                return user
        raise ValueError("User not found")
    else:
        return res['data']