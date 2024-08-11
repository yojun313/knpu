# -*- coding: utf-8 -*-
import os
import sys

NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH      = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

from CrawlerModule import CrawlerModule
import random
from datetime import datetime, timezone
import urllib3
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import json
import re
from urllib.parse import urlparse, parse_qs
import asyncio
import aiohttp

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class NaverCafeCrawler(CrawlerModule):
    def __init__(self, proxy_option = False, print_status_option = False):
        super().__init__(proxy_option)
        self.print_status_option = print_status_option
    
    def _cafeURLChecker(self, url):
        pattern = r"https://cafe\.naver\.com/[^/]+/[^/]+\?art=[^/]+"
        match = re.match(pattern, url)
        return bool(match)
    
    async def _cafeIDExtractor(self, cafeURL, session):
    
        response = await self.asyncRequester(cafeURL, session=session)
        if response.startswith('\ufeff'):
            response= response[1:]

        soup     = BeautifulSoup(response, "html.parser")
        script_tags = soup.find_all('script')

        club_id = None
        pattern = re.compile(r"var g_sClubId = \"(.*?)\";")

        for script in script_tags:
            if script.string:
                match = pattern.search(script.string)
                if match:
                    club_id = match.group(1)
                    break

        return club_id
    
    def articleIDExtractor(self, cafeURL):
        return cafeURL.split('/')[4].split('?')[0]
    
    def _timeExtractor(self, value):
        timestamp_s = value / 1000
        date = datetime.fromtimestamp(timestamp_s, timezone.utc).date()
        return date.strftime("%Y-%m-%d")
    
    def _artExtractor(self, url):
        parsed_url = urlparse(url)
        # 쿼리 파라미터를 딕셔너리로 변환
        query_params = parse_qs(parsed_url.query)
        # 'art' 파라미터의 값을 추출
        art_code = query_params.get('art', [None])[0]
        return art_code
    
    # contentHtml 필드를 이스케이프 처리하여 JSON 문자열을 정리
    def _escape_content_html(self, json_str):
        # 정규식을 사용하여 contentHtml 필드 추출 및 이스케이프 처리
        pattern = re.compile(r'("contentHtml":\s?")(.*?)(?=",\s*")', re.DOTALL)
        match = pattern.search(json_str)
        
        if match:
            content_html = match.group(2)
            escaped_content_html = content_html.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
            json_str = json_str[:match.start(2)] + escaped_content_html + json_str[match.end(2):]
        
        return json_str
    
    def urlCollector(self, keyword, startDate, endDate):
        try:
            if isinstance(keyword, str) == False:
                return self.error_dump(2018, 'Check Keyword', keyword)
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            return self.error_dump(2019, 'Check DateForm', startDate)
        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('NaverCafe', 1, self.PrintData)

            urlList = []
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(
                ' ', '+')
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

            # 첫 데이터는 들어오는 데이터 전처리 필요
            response = self.Requester(api_url, params=params)
            json_text = response.text
            json_text = json_text[16:len(json_text) - 2]
            while True:
                data = json.loads(json_text)
                soup = BeautifulSoup(data["contents"], 'html.parser')
                result = soup.select('a[class = "title_link"]')
                url_list = [a['href'] for a in result]

                for url in url_list:
                    if url not in urlList and 'https://cafe.naver.com/' in url and 'book' not in url:
                        urlList.append(url)
                        self.IntegratedDB['UrlCnt'] += 1

                if self.print_status_option == True:
                    self.printStatus('NaverCafe', 2, self.PrintData)

                if data['nextUrl'] == '':
                    break
                else:
                    api_url = data['nextUrl']
                    response = self.Requester(api_url)
                    json_text = response.text
                    params = {}

            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData
            
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2020, error_msg, api_url)

    async def articleCollector(self, cafeURL, session):
        if isinstance(cafeURL, str) == False or self._cafeURLChecker(cafeURL) == False:
            return self.error_dump(2021, "Check cafeURL", cafeURL)
        
        try:
            returnData = {
                'articleData': [],
                'cafeID': 0
            }

            articleID = self.articleIDExtractor(cafeURL)
            cafeID = await self._cafeIDExtractor(cafeURL, session)
            artID = self._artExtractor(cafeURL)
            api_url = "https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{}/articles/{}?query=&art={}&useCafeId=true&requestFrom=A".format(cafeID, articleID, artID)
            response = await self.asyncRequester(api_url, session=session)
            if self.RequesterChecker(response) == False:
                return response
            soup = BeautifulSoup(response, 'html.parser')
            json_string = self._escape_content_html(soup.text)

            try:
                temp = json.loads(json_string)
                cafe_name    = temp['result']['cafe']['name']
                memberCount  = temp['result']['cafe']['memberCount']
                writer       = temp['result']['article']['writer']['id']
                title        = re.sub(r'[^\w\s가-힣]', '', temp['result']['article']['subject'])
                text         = ' '.join(BeautifulSoup(temp['result']['article']['contentHtml'], 'html.parser').get_text().split()).replace("\\n", "").replace("\\t", "").replace("\u200b", "").replace('\\', '')
                date         = self._timeExtractor(int(temp['result']['article']['writeDate']))
                readCount    = temp['result']['article']['readCount']
                commentCount = temp['result']['article']['commentCount']
            except:
                return returnData
            
            self.IntegratedDB['TotalArticleCnt'] += 1
            if self.print_status_option == True:
                self.printStatus('NaverCafe', 3, self.PrintData)
            
            articleData = [cafe_name, memberCount, writer, title, text, date, readCount, commentCount, cafeURL]
            returnData['articleData'] = articleData
            returnData['cafeID'] = cafeID

            return returnData
        
        except:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2022, error_msg, cafeURL)
         
    async def replyCollector(self, cafeURL, session, cafeID = 0):
        if isinstance(cafeURL, str) == False or self._cafeURLChecker(cafeURL) == False:
            return self.error_dump(2023, "Check newsURL", cafeURL)
        try:
            articleID = self.articleIDExtractor(cafeURL)
            if cafeID == 0:
                cafeID = await self._cafeIDExtractor(cafeURL, session)
            artID = self._artExtractor(cafeURL)

            replyList = []
            returnData = {
                'replyList': replyList,
                'replyCnt' : len(replyList)
            }
            
            page = 1
            reply_idx = 1

            while True:
                
                api_url = "https://apis.naver.com/cafe-web/cafe-articleapi/v2/cafes/{}/articles/{}/comments/pages/{}?requestFrom=A&orderBy=asc&art={}".format(cafeID, articleID, page, artID)
                response = await self.asyncRequester(api_url, session=session)
                if self.RequesterChecker(response) == False:
                    return response
                
                soup = BeautifulSoup(response, 'html.parser')
                json_string = self._escape_content_html(soup.text)

                try:
                    temp = json.loads(json_string)
                    comment_json = temp['result']['comments']['items']
                    if comment_json == []:
                        return returnData
                except:
                    return returnData

                for comment in comment_json:
                    writer  = comment['writer']['id']
                    date    = self._timeExtractor(comment['updateDate'])
                    content = comment['content'].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', '')
                    url     = cafeURL
                    if content != '':
                        replyList.append([reply_idx, writer, date, content, url])
                        reply_idx += 1
                    
                self.IntegratedDB['TotalReplyCnt'] += len(comment_json)
                self.IntegratedDB['TotalRereplyCnt'] += len(comment_json)
                
                if self.print_status_option == True:
                    self.printStatus('NaverCafe', 6, self.PrintData)
                    
                if len(comment_json) < 100:
                    break
                
                page += 1
                reply_idx += 1
            
            returnData['replyList'] = replyList
            returnData['replyCnt']  = len(replyList)
            
            return returnData
        
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2024, error_msg, cafeURL)

    async def asyncSingleCollector(self, cafeURL, option, session):
        semaphore = asyncio.Semaphore(10)
        async with semaphore:
            articleData = await self.articleCollector(cafeURL, session)
            if option == 1:
                return {'articleData': articleData}

            if list(articleData.keys())[0] == 'Error Code':
                replyData = {'replyList': [], 'replyCnt': 0}
            else:
                cafeID = articleData['cafeID']
                replyData = await self.replyCollector(cafeURL, session, cafeID)
            return {'articleData': articleData, 'replyData': replyData}

    async def asyncMultiCollector(self, urlList, option):
        tasks = []
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=self.socketnum))
        for cafeURL in urlList:
            tasks.append(self.asyncSingleCollector(cafeURL, option, session))

        results = await asyncio.gather(*tasks)
        await session.close()
        return results

    def RealTimeurlCollector(self, keyword, checkPage, checkedIDList):
        try:
            urlList = []
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
            search_page_url = 'https://search.naver.com/search.naver?cafe_where=&prdtype=0&query={}&sm=mtb_opt&ssc=tab.cafe.all&st=date&stnm=rel&opt_tab=0&nso=so%3Add%2Cp%3Aall&page={}'

            currentPage = 1
            for page in range(checkPage):
                search_page_url_tmp = search_page_url.format(keyword, currentPage)
                main_page = self.Requester(search_page_url_tmp)
                main_page = BeautifulSoup(main_page.text, "lxml")
                site_result = main_page.select('a[class = "title_link"]')

                for a in site_result:
                    add_link = a['href']
                    if 'naver' in add_link and self.articleIDExtractor(add_link) not in checkedIDList and 'book' not in add_link:
                        urlList.append(add_link)
                        checkedIDList.append(self.articleIDExtractor(add_link))

                currentPage += 10

            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData

        except Exception as e:
            error_msg = self.error_detector(self.error_detector_option)
            return self.error_dump(2020, error_msg, search_page_url_tmp)


async def asyncTester():
    print("============ Crawler Packeage Tester ============")
    print("I. Choose Option\n")
    print("1. ALL  (Full Automatic: UrlCollector -> articleCollector & replyCollector)")
    print("2. Part (NaverCafeURL Required -> articleCollector & replyCollector)\n")

    number = int(input("Number: "))
    proxy_option = int(input("\nUse Proxy? (1/0): "))
    option = int(input("\nOption: "))
    print("==================================================")

    CrawlerPackage_obj = NaverCafeCrawler(proxy_option=proxy_option, print_status_option=True)
    CrawlerPackage_obj.error_detector_option_on()

    if number == 1:
        print("\nNaverCafeCrawler_urlCollector: ", end='')
        urlList_returnData = CrawlerPackage_obj.urlCollector("대통령", 20230101, 20230110)
        urlList = urlList_returnData['urlList']

        results = await CrawlerPackage_obj.asyncMultiCollector(urlList, option)
        print('\n')
        for i in results:
            print(i)

    elif number == 2:
        url = input("\nTarget NaverCafe URL: ")
        result = await CrawlerPackage_obj.asycSingleCollector(url, option)
        print(result)

    
if __name__ == "__main__":
    asyncio.run(asyncTester())