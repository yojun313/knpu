import sys
import os

NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH      = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

from CrawlerPackage import CrawlerPackage
from ToolPackage import ToolPackage
from user_agent import generate_user_agent, generate_navigator
from datetime import datetime, timezone
import urllib3
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import json
import pandas as pd
import re
from urllib.parse import urlunparse, parse_qs, urlencode
import random
import requests
import time
import copy
from datetime import datetime


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class ChinaSinaCrawler(CrawlerPackage):
    
    def __init__(self, proxy_option = False, print_status_option = False):
        super().__init__(proxy_option)
        self.print_status_option = print_status_option
        self.error_detector_option = False
    
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
    
    def newsURLChecker(self, newsURL):
        if 'https://news.sina.com.cn' in newsURL:
            return 1
        elif 'https://news.sina.cn' in newsURL:
            return 2
        elif 'https://mil.news.sina.com.cn' in newsURL:
            return 3
        else:
            return False
    
    def jsonFormatter(self, input_str):
        # 첫 번째 '{'의 인덱스를 찾습니다.
        start_index = input_str.index('{')
        # 마지막 '}'의 인덱스를 찾습니다.
        end_index = input_str.rindex('}') + 1
        # JSON 문자열을 추출합니다.
        json_str = input_str[start_index:end_index]
        # JSON 문자열을 딕셔너리로 변환합니다.
        return json_str
    
    def urlCollector(self, keyword, startDate, endDate):
        try:
            if isinstance(keyword, str) == False:
                self.error_dump(2032, 'Check Keyword', keyword)
                return self.error_data
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            self.error_dump(2033, 'Check DateForm', startDate)
            return self.error_data
        
        try:
            endCnt = 0
            urlList = []
            previus_links = []
            previus_search_page_url = 'https://www.baidu.com/'
            startDate = self.DateInverter(str(startDate))
            endDate   = self.DateInverter(str(endDate))
            site      = 'news.sina.com.cn'
            
            page = 0
            while True:
                print(f'\r{len(urlList)}', end = '')
                # 요청 -> 응답 횟수
                if endCnt > 5:
                    urlList = self.sortUrlList(urlList)
                    
                    returnData = {
                        'urlList' : urlList,
                        'urlCnt'  : len(urlList)
                    }
                    return returnData
                
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
                soup = BeautifulSoup(main_page.text, 'html.parser')
                
                result_divs = soup.find_all('div', class_='result')
                links = [div.get('mu') for div in result_divs if div.get('mu')]
                
                if links == previus_links or links == []:
                    endCnt += 1
                
                for url in links:
                    if url not in urlList: 
                        if 'news.sina.cn' in url or 'news.sina.com.cn' in url:
                            urlList.append(url)
                        
                previus_links = copy.deepcopy(links)
                previus_search_page_url = search_page_url
                
                if links != []:
                    page += 10
                    
        except Exception:
            error_msg = self.error_detector(self.error_detector_option)
            self.error_dump(2034, error_msg, search_page_url)
            return self.error_data

     
    def articleCollector(self, newsURL):
        
        newsURL_type = self.newsURLChecker(newsURL)
        if isinstance(newsURL_type, int) == False:
            self.error_dump(2035, "Check newsURL", newsURL)
            return self.error_data
        
        try:
            main_page = self.Requester(newsURL)
            main_page.encoding = 'utf-8'
            soup      = BeautifulSoup(main_page.text, 'lxml')
            
            if newsURL_type == 1 or newsURL_type == 3:
                
                title = soup.find('h1', {'class': 'main-title'}).text
                paragraphs = soup.find('div', {'class': 'article', 'id': 'article'}).find_all('p')
                text   = " ".join(p.get_text(strip=True) for p in paragraphs)
                source = soup.find('a', {'class': 'source'}).text
                date   = newsURL.split('/')[4]
                keywords = ', '.join([key.text for key in soup.find('div', {'class': 'keywords'}).find_all('a')])
                
                articleData = [title, text, date, source, keywords, newsURL]

            elif newsURL_type == 2:
                
                title = soup.find('h1', {'class': 'art_tit_h1'}).text
                paragraphs = soup.find('section', {'class': 'art_pic_card art_content'}).find_all('p')
                text   = " ".join(p.get_text(strip=True) for p in paragraphs)
                source = soup.find('h2', {'class': 'weibo_user'}).text
                date   = newsURL.split('/')[4]
                keywords = ''
                
                articleData = [title, text, date, source, keywords, newsURL]

            returnData = {
                'articleData' : articleData
            }
            
            return returnData
            
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            self.error_dump(2036, error_msg, newsURL)
            return self.error_data
    
    def replyCollector(self, newsURL):
        
        #response = self.Requester('https://comment.sina.com.cn/page/info?version=1&format=json&channel=gn&newsid=comos-ncemisz7254091&group=undefined&compress=0&ie=utf-8&oe=utf-8&page=1&page_size=10&t_size=3&h_size=3&thread=1&uid=unlogin_user&callback=jsonp_1721225908987&_=1721225908987') 
        #print(response.text)
        
        
        
        
        
        
        newsURL_type = self.newsURLChecker(newsURL)
        if isinstance(newsURL_type, int) == False:
            self.error_dump(2037, "Check newsURL", newsURL)
            return self.error_data
        
        
        newsid = newsURL.split('/')[5].split('-')[1]
        if newsid[0] == 'i':
            newsid = newsid[1:].split('.')[0]
        else:
            newsid = newsid.split('.')[0]
        
        replyList = []
        reply_num = 1
        
        try:
            # https://news.sina.com.cn/c/2024-07-17/doc-incemisz7254091.shtml
            if newsURL_type == 1:
                page = 1
                
                while True:
                    api_url = f'https://comment.sina.com.cn/page/info?version=1&format=json&channel=gn&newsid=comos-{newsid}&group=undefined&compress=0&ie=utf-8&oe=utf-8&page={page}&page_size=10&t_size=3&h_size=3&thread=1&uid=unlogin_user&callback=jsonp_{int(time.time())}&_={int(time.time())}'
                    main_page = self.Requester(api_url)
                    main_page.encoding = 'UTF-8'
                    main_page = self.jsonFormatter(main_page.text)
                    temp = json.loads(main_page)
                    
                    comment_json = temp['result']['cmntlist']
                    
                    if comment_json == []:
                        returnData = {
                            'replyList' : replyList,
                            'replyCnt'  : len(replyList)
                        }
                        return returnData
                    
                    for data in comment_json:
                        nickname = data['nick']
                        date     = data['time']
                        like     = data['rank']
                        text     = data['content'].replace('\u200b', '')

                        replyData = [reply_num, nickname, date, text, like, newsURL]
                        replyList.append(replyData)
                        reply_num += 1
                            
                    page += 1
                    
            # https://news.sina.cn/sh/2023-01-29/detail-imycwefp0361917.d.html
            if newsURL_type == 2:
                default_url = 'https://cmnt.sina.cn/aj/v2/list'
                referURL = f'https://cmnt.sina.cn/index?product=comos&index={newsid}&tj_ch=news&is_clear=0'
                page = 1
                while True:
                    params = {
                        'channel': 'sh',
                        'newsid': f'comos-{newsid}',
                        'group': 'group',
                        'thread': '1',
                        'page': page,
                        '_callback': 'jsonp1'
                    }
                    headers = {
                        'User-Agent': generate_navigator()['user_agent'],
                        'Referer'   : referURL
                    }
                    
                    main_page = self.Requester(default_url, headers=headers, params=params)
                    main_page.encoding = 'UTF-8'
                    main_page = self.jsonFormatter(main_page.text)
                    temp = json.loads(main_page)
                    print(temp)
                    


        except Exception as e:
            print(e)
            
    
           
object = ChinaSinaCrawler(proxy_option=True)
replyList = object.replyCollector('https://news.sina.com.cn/c/2024-07-17/doc-incemisz7254091.shtml')       
for i in replyList['replyList']:
    print(i)
'''
urlList = object.urlCollector('人民', 20230101, 20230131)  
for url in urlList['urlList']:
    print(url)
'''


