# -*- coding: utf-8 -*-
import os
import sys

CHINACRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH      = os.path.dirname(CHINACRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

from CrawlerModule import CrawlerModule
from datetime import datetime
from bs4 import BeautifulSoup
import json
import re
import asyncio

class ChinaDailyCrawler(CrawlerModule):
    
    def __init__(self, proxy_option = False, print_status_option = False):
        super().__init__(proxy_option)
        self.print_status_option = print_status_option
    
    def _keywordParser(self, keyword):
        # 검색어를 담을 리스트 초기화
        includeList = []
        excludeList = []

        # '-'로 검색어 분리
        parts = keyword.split('-')

        # 메인 검색어 처리
        includeList.extend(parts[0].split('+'))

        # 제외 검색어 처리 (있는 경우)
        if len(parts) > 1:
            excludeList.extend(parts[1].split('+'))

        return includeList, excludeList
    
    def _timeFormatter(self, date):
        # 문자열을 datetime 객체로 변환
        date_obj = datetime.strptime(str(date), "%Y%m%d")
        
        # datetime 객체를 원하는 문자열 형식으로 변환
        formatted_date = date_obj.strftime("%Y-%m-%d")
        
        return formatted_date
    
    def _escape_content_html(self, json_str):
        # 이스케이프 함수 정의
        def escape_match(match):
            plain_text = match.group(2)
            escaped_plain_text = plain_text.replace('\\', '').replace('"', '').replace('\n', '').replace('\r', '')
            return match.group(1) + escaped_plain_text
        
        # plainText 패턴 처리
        json_str = re.sub(r'("plainText":\s?")(.*?)(?=",\s*")', escape_match, json_str, flags=re.DOTALL)
        
        # highlightContent 패턴 처리
        json_str = re.sub(r'("highlightContent":\s?")(.*?)(?=",\s*")', escape_match, json_str, flags=re.DOTALL)
        
        return json_str
    
    def articleCollector(self, keyword, startDate, endDate):
        try:
            if isinstance(keyword, str) == False:
                return self.error_dump(2029, 'Check Keyword', keyword)
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            return self.error_dump(2030, 'Check DateForm', startDate + endDate)
    
        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('ChinaDaily', option=1, printData=self.PrintData)
            
            includeList, excludeList = self._keywordParser(keyword)
            includeWord = '+'.join(includeList).replace('&', '%26')
            excludeWord = '+'.join(excludeList).replace('&', '%26')
            
            startDate = self._timeFormatter(startDate)
            endDate = self._timeFormatter(endDate)
            
            articleList = []
            page = 0
            base_search_page_url = "https://newssearch.chinadaily.com.cn/rest/en/search"
            
            while True:
                referer_url = 'https://newssearch.chinadaily.com.cn/en/search?cond=%7B%22publishedDateFrom%22%3A%22{}%22%2C%22publishedDateTo%22%3A%22{}%22%2C%22fullMust%22%3A%22{}%22%2C%22fullNot%22%3A%22{}%22%2C%22channel%22%3A%5B%222%40cndy%22%2C%222%40webnews%22%2C%222%40bw%22%2C%222%40hk%22%2C%22ismp%40cndyglobal%22%5D%2C%22type%22%3A%5B%22story%22%2C%22comment%22%2C%22blog%22%5D%2C%22curType%22%3A%22story%22%2C%22sort%22%3A%22dp%22%2C%22duplication%22%3A%22on%22%7D&language=en&page={}'.format(startDate, endDate, includeWord, excludeWord, page)
                params = {
                        "publishedDateFrom": str(startDate),
                        "publishedDateTo": str(endDate),
                        "fullMust": includeWord,
                        "fullNot": excludeWord,
                        "channel": "",
                        "type": "",
                        "curType": "story",
                        "sort": "dp",
                        "duplication": "on",
                        "page": page,
                        "type[0]": "story",
                        "type[1]": "comment",
                        "type[2]": "blog",
                        "channel[0]": "2@cndy",
                        "channel[1]": "2@webnews",
                        "channel[2]": "2@bw",
                        "channel[3]": "2@hk",
                        "channel[4]": "ismp@cndyglobal",
                        "source": ""
                }
                
                main_page = self.Requester(base_search_page_url, params=params)
                if self.RequesterChecker(main_page) == False:
                    return main_page
                soup = BeautifulSoup(main_page.text, "lxml").text
                soup = self._escape_content_html(soup)
                try:
                    json_data = json.loads(soup)
                                
                    contents = json_data['content']
                
                    if contents == []:
                        returnData = {
                            'articleList' : articleList,
                            'articleCnt'  : len(articleList)
                        }
                        return returnData
                    
                    for content in contents:
                        source    = content['source']
                        title     = content['title']
                        text      = content['plainText'] 
                        date      = content['pubDateStr'].split()[0]
                        theme     = content['columnName']
                        url       = content['url']
                        searchURL = referer_url 
                        
                        if text != "":
                            articleList.append([source, title, text, date, theme, url, searchURL])
                            self.IntegratedDB['TotalArticleCnt'] += 1

                    if self.print_status_option == True:
                        self.printStatus('ChinaDaily', 3, self.PrintData)
                    page += 1
                except:
                    page += 1
        
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2031, error_msg, referer_url)

if __name__ == "__main__":
    print("hello")