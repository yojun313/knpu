# -*- coding: utf-8 -*-
import sys
import os

NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLERPACKAGE_PATH      = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)
sys.path.append(CRAWLERPACKAGE_PATH)

from CrawlerPackage import CrawlerPackage
from ToolPackage import ToolPackage
from datetime import datetime
from bs4 import BeautifulSoup
import json
import re

class ChinaDailyCrawler(CrawlerPackage):
    
    def __init__(self, proxy_option = False):
        super().__init__(proxy_option)
        self.proxy_option = proxy_option
        
    def keywordParser(self, keyword):
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
    
    def timeFormatter(self, date):
        # 문자열을 datetime 객체로 변환
        date_obj = datetime.strptime(str(date), "%Y%m%d")
        
        # datetime 객체를 원하는 문자열 형식으로 변환
        formatted_date = date_obj.strftime("%Y-%m-%d")
        
        return formatted_date

    def remove_inner_quotes(self, match):
        return match.group(0).replace('\\"', '').replace('"', '')
    
    def escape_content_html(self, json_str):
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
    
    def articleCollector(self, keyword, startDate, endDate, error_detector_option = False):
        try:
            if isinstance(keyword, str) == False:
                return 2029
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            return 2030
    
        try:
            includeList, excludeList = self.keywordParser(keyword)
            includeWord = '+'.join(includeList).replace('&', '%26')
            excludeWord = '+'.join(excludeList).replace('&', '%26')
            
            startDate = self.timeFormatter(startDate)
            endDate = self.timeFormatter(endDate)
            
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
                soup = BeautifulSoup(main_page.text, "lxml").text
                soup = self.escape_content_html(soup)
                try:
                    json_data = json.loads(soup)
                                
                    contents = json_data['content']
                
                    if contents == []:
                        return {
                            'articleList' : articleList,
                            'articleCnt'  : len(articleList)
                        }
                    
                    for content in contents:
                        title     = content['title']
                        text      = content['plainText'] 
                        date      = content['pubDateStr']
                        theme     = content['columnName']
                        source    = content['source']
                        url       = content['url']
                        searchURL = referer_url 
                        print([title, text, date, theme, source, url, searchURL])
                        print("\n\n\n\n")
                        
                        articleList.append([title, text, date, theme, source, url, searchURL])

                    page += 1
                except:
                    page += 1
        
        except Exception:
            error_msg  = self.error_detector(error_detector_option)
            error_data = {
                'Error Code' : 2031,
                'Error Msg' : error_msg
            }
            return error_data

if __name__ == "__main__":
    ToolPackage_obj = ToolPackage()
    
    CrawlerPackage_obj = ChinaDailyCrawler(proxy_option=True)
    CrawlerPackage_obj.articleCollector('china', 20230101, 20230131, True)