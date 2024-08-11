import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def urlCollector(keyword, startDate, endDate):
    # API URL 및 파라미터 설정

    urlList = []
    keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
    api_url = "https://s.search.naver.com/p/review/48/search.naver"
    currentPage = 1

    params = {
        "ssc": "tab.blog.all",
        "api_type": 8,
        "query": keyword,
        "start": 1,
        "nx_search_query": "",
        "nx_and_query": "",
        "nx_sub_query": "",
        "ac": 1,
        "aq": 0,
        "spq": 0,
        "sm": "tab_jum",
        "nso": f"so:dd,p:from{startDate}to{endDate}",
        "prank": 30,
        "ngn_country": "KR",
        "lgl_rcode": "02131104",
        "fgn_region": "",
        "fgn_city": "",
        "lgl_lat": 37.449409,
        "lgl_long": 127.155387,
        "enlu_query": "IggCAGiDULjaAAAAAtdoURqXUdp9ygLvMM8qJoxy7zkJYF06kLK+78VOhRxred9auhhnSFfsCLYIjSo9ZcL044Nzze...",
        "enqx_theme": "IggCABSCULhCAAAAAr/DtntZaiMLGh3DOFtIyw/t3q4cI3VHNtryN4kMOyz+YZnp6yyiXnfmTYMeozydGMP/CzL2DpK9j0J2w==",
        "abt": [{"eid": "RQT-BOOST", "value": {"bucket": "0", "for": "impression-neo", "is_control": True}}],
        "retry_count": 0
    }

    while True:
        response = requests.get(api_url, params=params)
        json_text = response.text
        data = json.loads(json_text)

        soup = BeautifulSoup(data["contents"], 'html.parser')
        result = soup.select('a[class = "title_link"]')
        url_list = [a['href'] for a in result]

        for url in url_list:
            if url not in urlList and 'https://blog.naver.com/' in url:
                urlList.append(url)

        if data['nextUrl'] == '':
            break
        else:
            api_url = data['nextUrl']
            print(api_url)
            params = {}

    returnData = {
        'urlList': urlList,
        'urlCnt': len(urlList)
    }
    # return part
    return returnData


startDate = '20230101'
endDate = '20230101'

print(urlCollector("대통령", startDate, endDate))

