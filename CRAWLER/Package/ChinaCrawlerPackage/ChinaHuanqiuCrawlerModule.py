import os
import sys

CHINACRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH      = os.path.dirname(CHINACRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

from CrawlerModule import CrawlerModule
from user_agent import generate_navigator
import urllib3
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import re
from urllib.parse import urlunparse, urlencode
import time
import copy
from datetime import datetime


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class ChinaHuanqiuCrawler(CrawlerModule):
    def __init__(self, proxy_option = False, print_status_option = False):
        super().__init__(proxy_option)
        self.print_status_option = print_status_option
        
        self.urlList_returnData = {
            'urlList': [],
            'urlCnt' : 0
        }
        
        self.article_returnData = {
            'articleData': []
        }
        
    def DateInverter(self, date_str):
        return int(time.mktime(time.strptime(date_str, '%Y%m%d')))

    def sortUrlList(self, urls):
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
    
    def urlCollector(self, keyword, startDate, endDate):
        try:
            if isinstance(keyword, str) == False:
                self.error_dump(2039, 'Check Keyword', keyword)
                return self.error_data
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            self.error_dump(2040, 'Check DateForm', startDate)
            return self.error_data
        
        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('ChinaSina', 1, self.PrintData)
                
            endCnt = 0
            urlList = []
            previus_links = []
            previus_search_page_url = 'https://www.baidu.com/'
            startDate = self.DateInverter(str(startDate))
            endDate   = self.DateInverter(str(endDate))
            site      = 'huanqiu.com'
            
            page = 0
            while True:
                # 요청 -> 응답 횟수
                if endCnt > 5:
                    self.urlList_returnData['urlList'] = urlList
                    self.urlList_returnData['urlCnt']  = len(urlList)
                    return self.urlList_returnData
                
                query_params = {
                    'wd': keyword,
                    'pn': page,
                    'oq': keyword,
                    'ct': '2097152',
                    'ie': 'utf-8',
                    'si': site,
                    'fenlei': '256',
                    'rsv_idx': '1',
                    'gpc': f'stf={startDate},{endDate}|stftype=2'
                }

                search_page_url = urlunparse(('https', 'www.baidu.com', '/s', '', urlencode(query_params), ''))
                headers = {
                    'User-Agent': generate_navigator()['user_agent'],
                    'Referer'   : previus_search_page_url
                }
                
                main_page = self.Requester(url=search_page_url, headers=headers)
                soup = BeautifulSoup(main_page, 'html.parser')
                
                result_divs = soup.find_all('div', class_='result')
                links = [div.get('mu') for div in result_divs if div.get('mu')]
                
                if links == previus_links or links == []:
                    endCnt += 1
                
                for url in links:
                    if url not in urlList: 
                        urlList.append(url)
                        print(url)
                        self.IntegratedDB['UrlCnt'] += 1
                
                if self.print_status_option == True:
                    self.printStatus('ChinaSina', 2, self.PrintData)

                previus_links = copy.deepcopy(links)
                previus_search_page_url = search_page_url
                
                if links != []:
                    page += 10
                    
        except Exception:
            error_msg = self.error_detector(self.error_detector_option)
            self.error_dump(2041, error_msg, 'search_page_url')
            return self.error_data
            
object = ChinaHuanqiuCrawler(True, False)
object.error_detector_option_on()
urlList = object.urlCollector('罪行', '20230101', '20231231')
