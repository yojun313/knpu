import re


def _newsURLChecker(url):
    pattern = (
        r"https://n\.news\.naver\.com"  # 고정 부분
        r"/mnews/article"  # 고정 부분
        r"/\d{3}"  # 고정 부분
        r"/\d{9}"  # 고정 부분
        r"(\?sid=\d{3})?"  # 선택적 부분
    )

    if re.search(pattern, url):
        return True
    return False

print(_newsURLChecker("https://n.news.naver.com/mnews/article/078/0000011113"))
