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
    
    def _articleIDExtractor(self, cafeURL):
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
                self.error_dump(2018, 'Check Keyword', keyword)
                return self.error_data
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            self.error_dump(2019, 'Check DateForm', startDate)
            return self.error_data
        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('NaverCafe', 1, self.PrintData)
                
            ipChange = False
            urlList = []
            idList  = []
            if self.proxy_option == True:
                ipList  = random.sample(self.proxy_list, 1000)
            
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
            search_page_url = "https://search.naver.com/search.naver?ssc=tab.cafe.all&cafe_where=&query={}&ie=utf8&st=date&date_option=8&date_from={}&date_to={}&srchby=text&dup_remove=1&cafe_url=&without_cafe_url=&sm=tab_opt&nso_open=1&prdtype=0&start={}"

            currentPage = 1
            while True:
                search_page_url_tmp = search_page_url.format(keyword, startDate, endDate, currentPage)
                
                if self.proxy_option == True:
                    
                    proxy = {"http": 'http://' + ipList[0], 'https': 'http://' + ipList[0]}
                    main_page = self.Requester(search_page_url_tmp, proxies = proxy)
                    if main_page == 0:
                        ipChange = True
                        ipList.pop(0)
                else:
                    main_page = self.Requester(search_page_url_tmp)
                
                if ipChange == False:
                    main_page = BeautifulSoup(main_page.text, "lxml") #스크랩 모듈에 url 넘김
                    site_result = main_page.select('a[class = "title_link"]')
                    
                    if site_result == []:
                        break
                        
                    for a in site_result: #스크랩한 데이터 중 링크만 추출
                        add_link = a['href']
                        if 'naver' in add_link and self._articleIDExtractor(add_link) not in idList and 'book' not in add_link:
                            urlList.append(add_link)
                            idList.append(self._articleIDExtractor(add_link))
                            self.IntegratedDB['UrlCnt'] += 1
                    
                    if self.print_status_option == True: 
                        self.printStatus('NaverCafe', 2, self.PrintData)
                        
                    currentPage += 10
                else:
                    currentPage = 1
                    ipChange = False
                    urlList = []
                    idList = []
                    self.IntegratedDB['UrlCnt'] = 0
            
            urlList = list(set(urlList))

            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData
            
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            self.error_dump(2020, error_msg, search_page_url_tmp)
            return self.error_data

    async def articleCollector(self, cafeURL, session):
        if isinstance(cafeURL, str) == False or self._cafeURLChecker(cafeURL) == False:
            self.error_dump(2021, "Check newsURL", cafeURL)
            return self.error_data
        
        try:
            returnData = {
                'articleData': []
            }

            articleID = self._articleIDExtractor(cafeURL)
            cafeID = await self._cafeIDExtractor(cafeURL, session)
            artID = self._artExtractor(cafeURL)
            api_url = "https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{}/articles/{}?query=&art={}&useCafeId=true&requestFrom=A".format(cafeID, articleID, artID)
            response = await self.asyncRequester(api_url, session=session)
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

            return returnData
        
        except:
            error_msg  = self.error_detector(self.error_detector_option)
            self.error_dump(2022, error_msg, cafeURL)
            return self.error_data
         
    async def replyCollector(self, cafeURL, session):
        if isinstance(cafeURL, str) == False or self._cafeURLChecker(cafeURL) == False:
            self.error_dump(2023, "Check newsURL", cafeURL)
            return self.error_data
        try:
            articleID = self._articleIDExtractor(cafeURL)
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
            self.error_dump(2024, error_msg, cafeURL)
            return self.error_data

    async def asyncSingleCollector(self, cafeURL, option, session):
        semaphore = asyncio.Semaphore(10)
        async with semaphore:
            articleData = await self.articleCollector(cafeURL, session)
            if option == 1:
                return {'articleData': articleData}

            replyData = await self.replyCollector(cafeURL, session)
            return {'articleData': articleData, 'replyData': replyData}

    async def asyncMultiCollector(self, urlList, option):
        tasks = []
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=self.socketnum))
        for cafeURL in urlList:
            tasks.append(self.asyncSingleCollector(cafeURL, option, session))

        results = await asyncio.gather(*tasks)
        await session.close()
        return results

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