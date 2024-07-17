import re
from datetime import datetime

def sort_urls_by_date(urls):
    # 날짜를 추출하는 정규 표현식
    date_pattern = re.compile(r'/(\d{4}-\d{2}-\d{2})/')

    def extract_date(url):
        match = date_pattern.search(url)
        if match:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        return None

    # 날짜를 기준으로 URL 정렬
    sorted_urls = sorted(urls, key=extract_date)
    return sorted_urls

# 테스트 URL 리스트
urls = [
    "https://news.sina.cn/sh/2023-01-14/detail-imyacear8951274.d.html",
    "https://news.sina.cn/sh/2022-05-20/detail-imyacear8951274.d.html",
    "https://news.sina.cn/sh/2023-07-17/detail-imyacear8951274.d.html",
    "https://news.sina.cn/sh/2021-12-25/detail-imyacear8951274.d.html"
]

# 정렬된 URL 리스트 출력
sorted_urls = sort_urls_by_date(urls)
for url in sorted_urls:
    print(url)
