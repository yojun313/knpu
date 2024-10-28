# -*- coding: utf-8 -*-
import os
import sys

NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH      = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

import time
from CrawlerModule import CrawlerModule
import json
import re
import warnings
from datetime import datetime
import pandas as pd
import urllib3
from bs4 import BeautifulSoup
from user_agent import generate_navigator
import asyncio
import aiohttp
import urllib.parse


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class NaverNewsCrawler(CrawlerModule):
    
    def __init__(self, print_status_option = False):
        super().__init__()
        self.print_status_option = print_status_option

        self.delay = 1
        self.rate_limit = 5
        self.last_request_time = 0
    
    def _newsURLChecker(self, url):
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
    
    def extract_newsurls(self, text):
            """Extract blog URLs from the HTML response."""
            pattern = r'https://n\.news\.naver\.com/mnews/article/\d+/\d+\?sid=\d+'
            urls = re.findall(pattern, text)
            return list(set(urls))

    def extract_nexturl(self, text):
        # 정규식 패턴 정의
        pattern = r'https://s\.search\.naver\.com/p/newssearch[^"]*'
        # 정규식으로 매칭되는 패턴 찾기
        match = re.search(pattern, text)
        if match:
            return match.group(0)
        else:
            return None
        
    def extract_time_from_text(self, text):
        # 정규식으로 날짜와 시간을 추출
        match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})\. (오전|오후) (\d{1,2}):(\d{2})', text)
        if match:
            # 오전/오후, 시간, 분을 추출
            period = match.group(4)  # 오전 또는 오후
            hour = int(match.group(5))  # 시간 (1~12)
            minute = match.group(6)  # 분

            # 오전/오후에 따라 24시간 형식으로 변환
            if period == '오전' and hour == 12:
                hour = 0  # 오전 12시는 00시로 변환
            elif period == '오후' and hour != 12:
                hour += 12  # 오후 시간은 12를 더해줌

            # HH:MM 형식으로 변환
            time = f"{hour:02d}:{minute}"
            return time
    
    # 파라미터로 (검색어, 시작일, 종료일) 전달
    def urlCollector(self, keyword, startDate, endDate): # DateForm: ex)20231231
        try:
            if isinstance(keyword, str) == False:
                return self.error_dump(2000, 'Check Keyword', keyword)
            
            startDate_formed = datetime.strptime(str(startDate), '%Y%m%d').date().strftime('%Y.%m.%d')
            endDate_formed = datetime.strptime(str(endDate), '%Y%m%d').date().strftime('%Y.%m.%d')
            
        except:
            return self.error_dump(2001, 'Check DateForm', startDate)
        
        try:
            def extract_newsurls(text):
                # 정규식 패턴 정의 (조금 더 일반화된 형태로)
                pattern = r'https://n\.news\.naver\.com/mnews/article/\d+/\d+\?sid=\d+'

                # 정규식으로 모든 매칭되는 패턴 찾기
                urls = re.findall(pattern, text)
                urls = list(dict.fromkeys(urls))

                return urls
            def extract_nexturl(text):
                # 정규식 패턴 정의
                pattern = r'https://s\.search\.naver\.com/p/newssearch[^"]*'

                # 정규식으로 매칭되는 패턴 찾기
                match = re.search(pattern, text)

                if match:
                    return match.group(0)
                else:
                    return None

            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('NaverNews', 1, self.PrintData)

            urlList = []
            keyword = urllib.parse.quote_plus(keyword)
            api_url = f"https://s.search.naver.com/p/newssearch/search.naver?de={endDate_formed}&ds={startDate_formed}&eid=&field=0&force_original=&is_dts=1&is_sug_officeid=0&mynews=0&news_office_checked=&nlu_query=&nqx_theme=&office_category=0&office_section_code=0&office_type=0&pd=3&photo=0&query={keyword}&query_original=&service_area=0&sort=1&spq=0&start=1&where=news_tab_api&_callback=jQuery112409864105848430387_1723710693433&_=1723710693436"
             
            response = self.Requester(api_url)
            if self.RequesterChecker(response) == False:
                return response
            json_text = response.text
            
            while True:
                pre_urlList = extract_newsurls(json_text)

                for url in pre_urlList:
                    if url not in urlList and 'sid=106' not in url:
                        urlList.append(url)
                        self.IntegratedDB['UrlCnt'] += 1

                if self.print_status_option == True:
                    self.printStatus('NaverNews', 2, self.PrintData)

                nextUrl = extract_nexturl(json_text)
                if nextUrl == None:
                    break
                else:
                    api_url = nextUrl
                    response = self.Requester(api_url)
                    json_text = response.text

            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData
                
        except Exception:
            error_msg  = self.error_detector()
            return self.error_dump(2003, error_msg, f"")
        
    def RealTimeurlCollector(self, keyword, checkPage, previous_urls, speed):
        try:
            urlList = []
            self.lastpage = False
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
            search_page_url = f"https://s.search.naver.com/p/newssearch/search.naver?query={keyword}&spq=0&sort=1&start=1&where=news_tab_api&nso=so:dd,p:all,a:all"

            response = self.Requester_get(search_page_url)
            time.sleep(speed)
            if self.RequesterChecker(response) == False:
                return response
            json_text = response.text
            
            pre_urlList = self.extract_newsurls(json_text)

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
                        pre_urlList = self.extract_newsurls(json_text)

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
                        
                        pre_urlList = self.extract_newsurls(json_text)

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
        
    def articleCollector(self, newsURL, speed):
        if isinstance(newsURL, str) == False or self._newsURLChecker(newsURL) == False:
            return self.error_dump(2004, "Check newsURL", newsURL)
        
        try:
            if self.print_status_option == True:
                self.printStatus('NaverNews', 3, self.PrintData)
            res = self.Requester_get(newsURL)
            time.sleep(speed)
            if self.RequesterChecker(res) == False:
                return res
            bs            = BeautifulSoup(res.text, 'lxml')
            news          = ''.join((i.text.replace("\n", "") for i in bs.find_all("div", {"class": "newsct_article"})))
            try:
                article_press = str(bs.find("img")).split()[1][4:].replace("\"", '') # article_press
                article_type  = bs.find("em", class_="media_end_categorize_item").text # article_type
                article_title = bs.find("div", class_="media_end_head_title").text.replace("\n", " ") # article_title
                article_date  = bs.find("span", {"class": "media_end_head_info_datestamp_time _ARTICLE_DATE_TIME"}).text.replace("\n", " ")
                article_time = self.extract_time_from_text(article_date)
                date_obj = datetime.strptime(article_date.split()[0], "%Y.%m.%d.")
                article_date = date_obj.strftime("%Y-%m-%d")

                articleData = [article_press, article_type, newsURL, article_title, news, article_date, article_time]
            except:
                articleData = []

            returnData = {
                'articleData': articleData
            }
            self.IntegratedDB['TotalArticleCnt'] += 1
            if self.print_status_option == True:
                self.printStatus('NaverNews', 3, self.PrintData)

            return returnData
               
        except Exception:
            error_msg  = self.error_detector()
            return self.error_dump(2005, error_msg, newsURL)




if __name__ == "__main__":
    print("hello")