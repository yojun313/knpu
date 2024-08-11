import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def urlCollector(keyword, startDate, endDate):
    # API URL 및 파라미터 설정
    if self.print_status_option == True:
        self.IntegratedDB['UrlCnt'] = 0
        self.printStatus('NaverCafe', 1, self.PrintData)

    urlList = []
    keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
    api_url = "https://s.search.naver.com/p/cafe/47/search.naver"

    params = {
        "ac": 1,
        "aq": 0,
        "cafe_where": "",
        "date_from": startDate,
        "date_option": 8,
        "date_to": endDate,
        "display": 30,
        "m": 0,
        "nx_and_query": "",
        "nx_search_query": "",
        "nx_sub_query": "",
        "prdtype": 0,
        "prmore": 1,
        "qdt": 1,
        "query": keyword,
        "qvt": 1,
        "spq": 0,
        "ssc": "tab.cafe.all",
        "st": "date",
        "stnm": "date",
        "_callback": "getCafeContents",
        "_": "1723354030871"
    }

    response = requests.get(api_url, params=params)
    json_text = response.text
    json_text = json_text[16:len(json_text) - 2]
    while True:
        data = json.loads(json_text)
        soup = BeautifulSoup(data["contents"], 'html.parser')
        result = soup.select('a[class = "title_link"]')
        url_list = [a['href'] for a in result]

        for url in url_list:
            if url not in urlList and 'https://cafe.naver.com/' in url:
                urlList.append(url)
                self.IntegratedDB['UrlCnt'] += 1

        if self.print_status_option == True:
            self.printStatus('NaverCafe', 2, self.PrintData)

        if data['nextUrl'] == '':
            break
        else:
            api_url = data['nextUrl']
            response = requests.get(api_url)
            json_text = response.text
            params = {}

    returnData = {
        'urlList': urlList,
        'urlCnt': len(urlList)
    }
    # return part
    return returnData


startDate = '20230101'
endDate = '20230114'

print(urlCollector("아이패드", startDate, endDate))

