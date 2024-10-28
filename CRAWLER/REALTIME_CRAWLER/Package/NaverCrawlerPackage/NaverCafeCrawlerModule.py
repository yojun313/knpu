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
import urllib.parse
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class NaverCafeCrawler(CrawlerModule):
    def __init__(self, print_status_option = False):
        super().__init__()
        self.print_status_option = print_status_option
    
    def _cafeURLChecker(self, url):
        pattern = r"https://cafe\.naver\.com/[^/]+/[^/]+\?art=[^/]+"
        match = re.match(pattern, url)
        return bool(match)
    
    def extract_cafeurls(self, text):
            """Extract blog URLs from the HTML response."""
            pattern = r'https://cafe\.naver\.com/[a-zA-Z0-9_-]+/\d+\?art=[a-zA-Z0-9._-]+'
            urls = re.findall(pattern, text)
            return list(set(urls))

    def extract_nexturl(self, text):
        """Extract next page URL from the HTML response."""
        pattern = r'https://s\.search\.naver\.com/p/cafe[^"]*'
        match = re.search(pattern, text)
        return match.group(0) if match else None
    
    def _cafeIDExtractor(self, cafeURL):
        headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
        response = self.Requester_get(cafeURL, headers = headers)
        if isinstance(response, dict): print(response)
        if response.text.startswith('\ufeff'):
            response= response[1:]

        soup     = BeautifulSoup(response.text, "html.parser")
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
        date = datetime.fromtimestamp(timestamp_s)
        return date.strftime("%Y-%m-%d"), date.strftime("%H:%M")
    
    def _artExtractor(self, url):
        parsed_url = urlparse(url)
        # 쿼리 파라미터를 딕셔너리로 변환
        query_params = parse_qs(parsed_url.query)
        # 'art' 파라미터의 값을 추출
        art_code = query_params.get('art', [None])[0]
        return art_code
    

    def _escape_content_html(self, json_str):
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
            def extract_cafeurls(text):
                # 정규식 패턴 정의
                pattern = r'https://cafe\.naver\.com/[a-zA-Z0-9_-]+/\d+\?art=[a-zA-Z0-9._-]+'

                # 정규식으로 모든 매칭되는 패턴 찾기
                urls = re.findall(pattern, text)
                urls = list(dict.fromkeys(urls))
                return urls
            
            def extract_nexturl(text):
                # 정규식 패턴 정의
                pattern = r'https://s\.search\.naver\.com/p/cafe[^"]*'

                # 정규식으로 매칭되는 패턴 찾기
                match = re.search(pattern, text)

                if match:
                    return match.group(0)
                else:
                    return None

            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('NaverCafe', 1, self.PrintData)

            urlList = []
            keyword = urllib.parse.quote_plus(keyword)
            api_url = f"https://s.search.naver.com/p/cafe/47/search.naver?ac=0&aq=0&cafe_where=&date_from={startDate}&date_option=8&date_to={endDate}&display=30&m=0&nlu_query=&prdtype=0&prmore=1&qdt=1&query={keyword}&qvt=1&spq=0&ssc=tab.cafe.all&st=date&start=1&stnm=date&_callback=getCafeContents&_=1724218724778"

            # 첫 데이터는 들어오는 데이터 전처리 필요
            response = self.Requester_get(api_url)
            if self.RequesterChecker(response) == False:
                return response
            json_text = response.text

            while True:
                pre_urlList = extract_cafeurls(json_text)

                for url in pre_urlList:
                    if url not in urlList and 'book' not in url:
                        urlList.append(url)
                        self.IntegratedDB['UrlCnt'] += 1

                if self.print_status_option == True:
                    self.printStatus('NaverCafe', 2, self.PrintData)

                nextUrl = extract_nexturl(json_text)
                if nextUrl == None:
                    break
                else:
                    api_url = nextUrl
                    response = self.Requester_get(api_url)
                    json_text = response.text

            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData
            
        except Exception:
            error_msg  = self.error_detector()
            return self.error_dump(2020, error_msg, api_url)

    def articleCollector(self, cafeURL, speed):
        if isinstance(cafeURL, str) == False or self._cafeURLChecker(cafeURL) == False:
            return self.error_dump(2021, "Check cafeURL", cafeURL)
        
        try:
            returnData = {
                'articleData': [],
                'cafeID': 0
            }

            articleID = self.articleIDExtractor(cafeURL)
            cafeID = self._cafeIDExtractor(cafeURL)
            time.sleep(speed)
            artID = self._artExtractor(cafeURL)
            api_url = "https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{}/articles/{}?query=&art={}&useCafeId=true&requestFrom=A".format(cafeID, articleID, artID)
            response =  self.Requester_get(api_url)
            time.sleep(speed)
            if self.RequesterChecker(response) == False:
                return response
            soup = BeautifulSoup(response.text, 'html.parser')
            json_string = self._escape_content_html(soup.text)

            try:
                temp = json.loads(json_string)
                cafe_name    = temp['result']['cafe']['name']
                memberCount  = temp['result']['cafe']['memberCount']
                writer       = temp['result']['article']['writer']['id']
                title        = re.sub(r'[^\w\s가-힣]', '', temp['result']['article']['subject'])
                text         = ' '.join(BeautifulSoup(temp['result']['article']['contentHtml'], 'html.parser').get_text().split()).replace("\\n", "").replace("\\t", "").replace("\u200b", "").replace('\\', '').replace('\ufeff', '')
                date, arttime= self._timeExtractor(int(temp['result']['article']['writeDate']))
                readCount    = temp['result']['article']['readCount']
                commentCount = temp['result']['article']['commentCount']
            except:
                return returnData
            
            self.IntegratedDB['TotalArticleCnt'] += 1
            if self.print_status_option == True:
                self.printStatus('NaverCafe', 3, self.PrintData)
            
            articleData = [cafe_name, memberCount, writer, title, text, date, arttime, readCount, commentCount, cafeURL]
            returnData['articleData'] = articleData
            returnData['cafeID'] = cafeID

            return returnData
        
        except:
            error_msg  = self.error_detector()
            return self.error_dump(2022, error_msg, cafeURL)
         
    def replyCollector(self, cafeURL, speed, cafeID = 0):
        if isinstance(cafeURL, str) == False or self._cafeURLChecker(cafeURL) == False:
            return self.error_dump(2023, "Check newsURL", cafeURL)
        try:
            articleID = self.articleIDExtractor(cafeURL)
            if cafeID == 0:
                cafeID = self._cafeIDExtractor(cafeURL)
                time.sleep(speed)
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
                response = self.Requester_get(api_url)
                time.sleep(speed)
                if self.RequesterChecker(response) == False:
                    return response
                
                soup = BeautifulSoup(response.text, 'html.parser')
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
                    date, arttime= self._timeExtractor(comment['updateDate'])
                    content = comment['content'].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', '')
                    url     = cafeURL
                    if content != '':
                        replyList.append([reply_idx, writer, date, arttime, content, url])
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
            error_msg  = self.error_detector()
            return self.error_dump(2024, error_msg, cafeURL)

    def RealTimeurlCollector(self, keyword, checkPage, previous_urls, speed):
        try:
            urlList = []
            self.lastpage = False
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
            search_page_url = f"https://s.search.naver.com/p/cafe/47/search.naver?ac=0&aq=0&cafe_where=&date_from=&date_option=0&date_to=&display=30&m=0&prdtype=0&prmore=1&qdt=1&query={keyword}&qvt=1&spq=0&ssc=tab.cafe.all&st=date&start=1&stnm=rel&_callback=getCafeContents&_=1727370818602"

            response = self.Requester_get(search_page_url)
            time.sleep(speed)
            if self.RequesterChecker(response) == False:
                return response
            json_text = response.text
            
            pre_urlList = self.extract_cafeurls(json_text)

            for url in pre_urlList:
                if url not in urlList and 'book' not in url:
                    urlList.append(url)
                    self.IntegratedDB['UrlCnt'] += 1
                    
            if checkPage >= 2:
                for i in range(checkPage-1):
                    if self.lastpage == True:
                        break
                    nextUrl = self.extract_nexturl(json_text)
                    nextUrl = nextUrl.encode().decode('unicode_escape')
                    if nextUrl == None:
                        break
                    
                    else:
                        api_url = nextUrl
                        response = self.Requester_get(api_url)
                        time.sleep(speed)
                        json_text = response.text
                        pre_urlList = self.extract_cafeurls(json_text)

                        for url in pre_urlList:
                            if url not in urlList and 'book' not in url:
                                urlList.append(url)
                                self.IntegratedDB['UrlCnt'] += 1
                                
                        for url in pre_urlList:
                            if url in previous_urls:
                                self.lastpage = True
                                break
            
            elif checkPage == 1:
                pass
            
            elif checkPage == 0:
                for url in pre_urlList:
                    if url in previous_urls:
                        self.lastpage = True
                        break
                while self.lastpage == False:
                    nextUrl = self.extract_nexturl(json_text)
                    if nextUrl == None:
                        break
                    
                    else:
                        api_url = nextUrl
                        response = self.Requester_get(api_url)
                        time.sleep(speed)
                        json_text = response.text
                        
                        pre_urlList = self.extract_cafeurls(json_text)

                        for url in pre_urlList:
                            if url not in urlList and 'book' not in url:
                                urlList.append(url)
                                self.IntegratedDB['UrlCnt'] += 1
                                
                        for url in pre_urlList:
                            if url in previous_urls:
                                self.lastpage = True
                                break

            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData
        
        except Exception as e:
            error_msg = self.error_detector()
            return self.error_dump(2020, error_msg, search_page_url)


    
if __name__ == "__main__":
    print("hello")