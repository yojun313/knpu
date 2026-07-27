import asyncio
import time
import requests
import aiohttp
from config import TRYNUM, TIMEOUT, PROXY
import random
from user_agent import generate_navigator
import os

api_headers = {
    "Authorization": "Bearer " + os.getenv("ADMIN_TOKEN"),
}

_CURRENT_PROXY_LIST = []


def set_proxy_list(proxy_list: list):
    global _CURRENT_PROXY_LIST
    _CURRENT_PROXY_LIST = proxy_list


def Request(url: str, headers=None, sleep: float = 0, **kwargs):
    if headers is None:
        headers = random_heador()
    params = kwargs.pop("params", None)
    timeout = kwargs.pop("timeout", TIMEOUT)

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
                    **kwargs,
                )
            except requests.exceptions.RequestException as e:
                last_exception = e

        raise last_exception
    else:
        return requests.get(
            url, headers=headers, params=params, verify=False, timeout=timeout, **kwargs
        )


class AsyncResponse:
    __slots__ = ("status_code", "text")

    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise aiohttp.ClientResponseError(
                request_info=None,
                history=(),
                status=self.status_code,
                message=f"HTTP {self.status_code}",
            )


async def RequestAsync(
    session: aiohttp.ClientSession,
    url: str,
    headers=None,
    params=None,
    timeout: float | None = None,
    sleep: float = 0,
    **kwargs,
) -> AsyncResponse:
    if headers is None:
        headers = random_heador()

    if sleep:
        await asyncio.sleep(sleep)

    client_timeout = aiohttp.ClientTimeout(total=timeout or TIMEOUT)

    proxy = None
    tries = 1
    if PROXY:
        tries = TRYNUM

    last_exception = None
    for _ in range(tries):
        if PROXY:
            proxy_dict = random_proxy()
            proxy = proxy_dict["http"] if proxy_dict else None
        try:
            async with session.get(
                url,
                headers=headers,
                params=params,
                proxy=proxy,
                timeout=client_timeout,
                ssl=False,
                **kwargs,
            ) as resp:
                text = await resp.text()
                return AsyncResponse(resp.status, text)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_exception = e
            continue

    raise last_exception


def random_proxy():
    if PROXY and _CURRENT_PROXY_LIST:
        proxy_server = random.choice(_CURRENT_PROXY_LIST)
        return {"http": f"http://{proxy_server}", "https": f"http://{proxy_server}"}
    return None


def random_heador():
    navigator = generate_navigator()
    navigator = navigator["user_agent"]
    return {"User-Agent": navigator}
