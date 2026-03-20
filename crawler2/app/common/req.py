import time
import requests
from config import TRYNUM, TIMEOUT, PROXY
import random
from user_agent import generate_navigator
import os

api_headers = {
    "Authorization": "Bearer " + os.getenv('ADMIN_TOKEN'),
}

_CURRENT_PROXY_LIST = []

def set_proxy_list(proxy_list: list):
    global _CURRENT_PROXY_LIST
    _CURRENT_PROXY_LIST = proxy_list

def Request(url: str, sleep: float = 0, **kwargs):
    headers = random_heador()
    params = kwargs.pop('params', None)
    timeout = kwargs.pop('timeout', TIMEOUT)

    if sleep:
        time.sleep(sleep)

    if PROXY:
        last_exception = None
        for _ in range(TRYNUM):
            try:
                proxies = random_proxy()
                return requests.get(
                    url,
                    proxies=proxies,
                    headers=headers,
                    params=params,
                    verify=False,
                    timeout=timeout,
                    **kwargs
                )
            except requests.exceptions.RequestException as e:
                last_exception = e
        
        raise last_exception
    else:
        return requests.get(
            url,
            headers=headers,
            params=params,
            verify=False,
            timeout=timeout,
            **kwargs
        )
    
def random_proxy():
    if PROXY and _CURRENT_PROXY_LIST:
        proxy_server = random.choice(_CURRENT_PROXY_LIST)
        return {"http": f'http://{proxy_server}', 'https': f'http://{proxy_server}'}
    return None

def random_heador():
    navigator = generate_navigator()
    navigator = navigator['user_agent']
    return {"User-Agent": navigator}