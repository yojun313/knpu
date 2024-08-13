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
import json
import re
from urllib.parse import urlunparse, urlencode
import time
import copy
from datetime import datetime, timedelta
import calendar
import asyncio
import aiohttp

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class ChinaSinaCrawler(CrawlerModule):
    
    def __init__(self, proxy_option = False, print_status_option = False):
        super().__init__(proxy_option)
        self.print_status_option = print_status_option
    
    def DateSplitter(self, start_date, end_date):
        # 날짜 문자열을 datetime 객체로 변환
        start = datetime.strptime(str(start_date), '%Y%m%d')
        end = datetime.strptime(str(end_date), '%Y%m%d')

        result = []
        current = start

        while current <= end:
            # 현재 날짜의 월의 마지막 날 계산
            _, last_day = calendar.monthrange(current.year, current.month)
            month_end = datetime(current.year, current.month, last_day)

            # 월의 마지막 날이 종료 날짜보다 크면 종료 날짜로 설정
            if month_end > end:
                month_end = end

            # 월의 시작일과 종료일 추가
            result.append([str(current.strftime('%Y%m%d')), str(month_end.strftime('%Y%m%d'))])

            # 다음 달의 첫 번째 날로 이동
            next_month = current.replace(day=28) + timedelta(days=4)  # 이 방법으로 다음 달로 이동
            current = next_month.replace(day=1)  # 다음 달의 첫 번째 날로 설정
        
        return result

    def _DateInverter(self, date_str):
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
    
    # sina.cn, sina.com.cn 등 구분
    def _newsURLChecker(self, newsURL):
        if 'https://news.sina.com.cn' in newsURL:
            return 1
        elif 'https://news.sina.cn' in newsURL:
            return 2
        elif 'https://mil.news.sina.com.cn' in newsURL:
            return 3
        else:
            return False
    
    # 댓글 api 요청 위한 채널 파라미터 추출
    def _newsChannelChecker(self, newsURL):
        param = newsURL.split('/')[3]
        channel = ''
        if param in ['c', 'gov', 'sx']: 
            channel = 'gn'
        elif param in ['o', 'zx', 'znl', 's', 'sh']:
            channel = 'sh'
        else:
            channel = ['gn', 'sh']
            
        return channel
    
    def _newsidFormChecker(self, newsURL):
        try:
            num = int(newsURL.split('/')[4][0]) # ex) https://news.sina.com.cn/zx/gj/2024-01-02/doc-inaacqsy5385670.shtml
            return 1
        except:                                 # ex) https://news.sina.com.cn/c/2024-07-17/doc-incemisz7254091.shtml
            return 2
    
    # json string 깔끔하게 정리
    def _jsonFormatter(self, input_str):
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
                return self.error_dump(2032, 'Check Keyword', keyword)
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            return self.error_dump(2033, 'Check DateForm', startDate)
        
        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('ChinaSina', 1, self.PrintData)
                
            endCnt = 0
            urlList = []
            previus_links = []
            previus_search_page_url = 'https://www.baidu.com/'
            startDate = self._DateInverter(str(startDate))
            endDate   = self._DateInverter(str(endDate))
            site      = 'news.sina.com.cn'
            
            page = 0
            while True:
                # 요청 -> 응답 횟수
                if endCnt > 5:
                    urlList = self.sortUrlList(list(set(urlList)))
                    returnData = {
                        'urlList': urlList,
                        'urlCnt' : len(urlList)
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
                if self.RequesterChecker(main_page) == False:
                    return main_page
                soup = BeautifulSoup(main_page.text, 'html.parser')
                
                result_divs = soup.find_all('div', class_='result')
                links = [div.get('mu') for div in result_divs if div.get('mu')]
                
                if links == previus_links or links == []:
                    endCnt += 1
                
                for url in links:
                    if url not in urlList: 
                        if 'news.sina.cn' in url or 'news.sina.com.cn' in url and url.count('/') >= 5:
                            urlList.append(url)
                            self.IntegratedDB['UrlCnt'] += 1
                
                if self.print_status_option == True:
                    self.printStatus('ChinaSina', 2, self.PrintData)

                previus_links = copy.deepcopy(links)
                previus_search_page_url = search_page_url
                
                if links != []:
                    page += 10
                    
        except Exception:
            error_msg = self.error_detector(self.error_detector_option)
            return self.error_dump(2034, error_msg, search_page_url)

    async def articleCollector(self, newsURL, session):
        
        newsURL_type = self._newsURLChecker(newsURL)
        if isinstance(newsURL_type, int) == False:
            return self.error_dump(2035, "Check newsURL", newsURL)
        
        try:
            main_page = await self.asyncRequester(newsURL, session=session)
            if self.RequesterChecker(main_page) == False:
                return main_page
            soup      = BeautifulSoup(main_page, 'lxml')

            # 뉴스 날짜
            if self._newsidFormChecker(newsURL) == True:
                date   = newsURL.split('/')[4]
            else:
                date   = newsURL.split('/')[5]
            
            if newsURL_type == 1 or newsURL_type == 3:
                
                title = soup.find('h1', {'class': 'main-title'}).text
                paragraphs = soup.find('div', {'class': 'article', 'id': 'article'}).find_all('p')
                text   = " ".join(p.get_text(strip=True) for p in paragraphs)

            elif newsURL_type == 2:
                
                title = soup.find('h1', {'class': 'art_tit_h1'}).text
                paragraphs = soup.find('section', {'class': 'art_pic_card art_content'}).find_all('p')
                text   = " ".join(p.get_text(strip=True) for p in paragraphs)
                
            articleData = [title, text, date, newsURL]
            
            self.IntegratedDB['TotalArticleCnt'] += 1
            if self.print_status_option == True:
                self.printStatus('ChinaSina', 3, self.PrintData)

            returnData = {
                'articleData': articleData
            }
            return returnData
        
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2036, error_msg, newsURL)
    
    async def replyCollector(self, newsURL, session):
        newsURL_type = self._newsURLChecker(newsURL)
        if isinstance(newsURL_type, int) == False:
            return self.error_dump(2037, "Check newsURL", newsURL)
        
        try:
            if self._newsidFormChecker(newsURL) == True:
                newsid = newsURL.split('/')[5].split('-')[1]
            else:
                newsid = newsURL.split('/')[6].split('-')[1]
                
            if newsid[0] == 'i':
                newsid = newsid[1:].split('.')[0]
            else:
                newsid = newsid.split('.')[0]
                
            channelid = self._newsChannelChecker(newsURL)
            channelidList_exists = False
            # 예외처리로 channel id를 모르는 경우 리스트로 둘 다 받아 둘다 시도
            if isinstance(channelid, list) == True:
                channelidList = copy.deepcopy(channelid)
                channelidList_exists = True
                channelid = channelidList[0]

            replyList = []
            reply_num = 1
            page      = 1

            returnData = {
                'replyList': replyList,
                'replyCnt': len(replyList)
            }
            
            while True:
                # https://news.sina.com.cn/c/2024-07-17/doc-incemisz7254091.shtml
                if newsURL_type == 1:
                    default_url = 'https://comment.sina.com.cn/page/info'
                    api_url = f'https://comment.sina.com.cn/page/info?version=1&format=json&channel={channelid}&newsid=comos-{newsid}&group=undefined&compress=0&ie=utf-8&oe=utf-8&page={page}&page_size=10&t_size=3&h_size=3&thread=1&uid=unlogin_user&callback=jsonp_{int(time.time())}&_={int(time.time())}'
                    main_page = await self.asyncRequester(api_url, session=session)
                    if self.RequesterChecker(main_page) == False:
                        return main_page

                        # https://news.sina.cn/sh/2023-01-29/detail-imycwefp0361917.d.html
                elif newsURL_type == 2:
                    default_url = 'https://cmnt.sina.cn/aj/v2/list'
                    referURL = f'https://cmnt.sina.cn/index?product=comos&index={newsid}&tj_ch=news&is_clear=0'
                    params = {
                        'channel': str(channelid),
                        'newsid': f'comos-{newsid}',
                        'group': 'group',
                        'thread': '1',
                        'page': page,
                        '_callback': 'jsonp1'
                    }
                    headers = {
                        'User-Agent': generate_navigator()['user_agent'],
                        'Referer': referURL
                    }
                    main_page = await self.asyncRequester(default_url, headers=headers, params=params, session=session)
                    if self.RequesterChecker(main_page) == False:
                        return main_page
                try:
                    main_page = self._jsonFormatter(main_page)
                    temp = json.loads(main_page)
                    comment_json = temp['result']['cmntlist']
                except:
                    if channelidList_exists == True:
                        # channelid 전환
                        if len(channelidList) > 1:
                            channelidList.pop(0)
                            channelid = channelidList[0]
                            continue
                    
                    return returnData

                # 댓글 없을 때
                if comment_json == []:
                    returnData['replyList'] = replyList
                    returnData['replyCnt'] = len(replyList)
                    return returnData

                for data in comment_json:
                    nickname = data['nick']
                    date = data['time'].split()[0]
                    like = data['rank']
                    text = data['content'].replace('\u200b', '')

                    replyData = [reply_num, nickname, date, text, like, newsURL]
                    replyList.append(replyData)
                    reply_num += 1
                    
                self.IntegratedDB['TotalReplyCnt'] += len(comment_json)
                if self.print_status_option:
                    self.printStatus('ChinaSina', 4, self.PrintData)

                page += 1

        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2038, error_msg, newsURL)
            
    async def asyncSingleCollector(self, newsURL, option, session):
        semaphore = asyncio.Semaphore(10)
        async with semaphore:
            articleData = await self.articleCollector(newsURL, session)
            if option == 1:
                return {'articleData': articleData}
            replyData = await self.replyCollector(newsURL, session)
            return {'articleData': articleData, 'replyData': replyData}

    async def asyncMultiCollector(self, urlList, option):
        tasks = []
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=self.socketnum))
        for newsURL in urlList:
            tasks.append(self.asyncSingleCollector(newsURL, option, session))

        results = await asyncio.gather(*tasks)
        await session.close()
        return results

async def asyncTester():
    print("============ Crawler Packeage Tester ============")
    print("I. Choose Option\n")
    print("1. ALL  (Full Automatic: UrlCollector -> articleCollector & replyCollector)")
    print("2. Part (ChinaSinaURL Required -> articleCollector & replyCollector)\n")

    number       = int(input("Number: "))
    proxy_option = int(input("\nUse Proxy? (1/0): "))
    option       = int(input("\nOption: "))
    print("==================================================")

    CrawlerPackage_obj = ChinaSinaCrawler(proxy_option=proxy_option, print_status_option=True)
    CrawlerPackage_obj.error_detector_option_on()

    if number == 1:
        print("\nChinaSinaCrawler_urlCollector: ", end='')
        urlList_returnData = CrawlerPackage_obj.urlCollector("人民", 20240101, 20240105)
        urlList = urlList_returnData['urlList']

        results = await CrawlerPackage_obj.asyncMultiCollector(urlList, option)
        print('\n')
        for i in results:
            print(i)

    elif number == 2:
        url = input("\nTarget ChinaSina URL: ")
        result = await CrawlerPackage_obj.asycSingleCollector(url, option)
        print(result)

if __name__ == "__main__":
    asyncio.run(asyncTester())

