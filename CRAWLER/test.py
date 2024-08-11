import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def urlCollector(keyword, startDate, endDate):
    # API URL 및 파라미터 설정

    startDate = datetime.strptime(str(startDate), '%Y%m%d').date().strftime('%Y.%m.%d')
    endDate = datetime.strptime(str(endDate), '%Y%m%d').date().strftime('%Y.%m.%d')

    urlList = []
    keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
    api_url = "https://s.search.naver.com/p/newssearch/search.naver"
    currentPage = 1

    while True:
        params = {
            "de": startDate,
            "ds": endDate,
            "eid": "",
            "field": "0",
            "force_original": "",
            "is_dts": "0",
            "is_sug_officeid": "0",
            "mynews": "0",
            "news_office_checked": "",
            "nlu_query": "",
            "nqx_theme": "",
            "nso": "so:r,p:from20240801to20240802,a:all",
            "nx_and_query": "",
            "nx_search_hlquery": "",
            "nx_search_query": "",
            "nx_sub_query": "",
            "office_category": "0",
            "office_section_code": "0",
            "office_type": "0",
            "pd": "3",
            "photo": "0",
            "query": keyword,
            "query_original": "",
            "service_area": "0",
            "sort": "1",
            "spq": "0",
            "start": str(currentPage),
            "where": "news_tab_api",
            "_callback": "jQuery112406351013586512539_1722744441764",
            "_": "1722744441765"
        }

        response = requests.get(api_url, params=params, verify=False)
        jsonp_text = response.text
        json_text = re.sub(r'^.*?\(', '', jsonp_text)[:-2]
        data = json.loads(json_text)

        for item in data["contents"]:
            soup = BeautifulSoup(item, 'html.parser')
            url = naver_links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].startswith('https://n.news.naver.com')]
            if url != [] and url[0] not in urlList:
                urlList.append(url[0])

        if data['contents'] == []:
            print(urlList)
            return urlList

        currentPage += 10



startDate = '20230101'
endDate = '20230101'

urlCollector("아이패드", startDate, endDate)

