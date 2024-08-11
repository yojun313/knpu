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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class NaverNewsCrawler(CrawlerModule):
    
    def __init__(self, proxy_option = False, print_status_option = False):
        super().__init__(proxy_option)
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
    
    # 파라미터로 (검색어, 시작일, 종료일) 전달
    def urlCollector(self, keyword, startDate, endDate): # DateForm: ex)20231231
        try:
            if isinstance(keyword, str) == False:
                return self.error_dump(2000, 'Check Keyword', keyword)
            
            startDate = datetime.strptime(str(startDate), '%Y%m%d').date().strftime('%Y.%m.%d')
            endDate = datetime.strptime(str(endDate), '%Y%m%d').date().strftime('%Y.%m.%d')
            
        except:
            return self.error_dump(2001, 'Check DateForm', startDate)
        
        try:
            search_page_url_tmp = ''
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('NaverNews', 1, self.PrintData)

            urlList = []
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(
                ' ', '+')
            api_url = "https://s.search.naver.com/p/newssearch/search.naver"
            currentPage = 1

            while True:
                params = {
                    "de": startDate,
                    "ds": endDate,
                    "eid": "",
                    "field": "0",
                    "force_original": "",
                    "is_dts": "0",
                    "is_sug_officeid": "0",
                    "mynews": "0",
                    "news_office_checked": "",
                    "nlu_query": "",
                    "nqx_theme": "",
                    "nso": "so:r,p:from20240801to20240802,a:all",
                    "nx_and_query": "",
                    "nx_search_hlquery": "",
                    "nx_search_query": "",
                    "nx_sub_query": "",
                    "office_category": "0",
                    "office_section_code": "0",
                    "office_type": "0",
                    "pd": "3",
                    "photo": "0",
                    "query": keyword,
                    "query_original": "",
                    "service_area": "0",
                    "sort": "1",
                    "spq": "0",
                    "start": str(currentPage),
                    "where": "news_tab_api",
                    "_callback": "jQuery112406351013586512539_1722744441764",
                    "_": "1722744441765"
                }

                response = self.Requester(api_url, params=params)
                jsonp_text = response.text
                json_text = re.sub(r'^.*?\(', '', jsonp_text)[:-2]
                data = json.loads(json_text)

                for item in data["contents"]:
                    soup = BeautifulSoup(item, 'html.parser')
                    url = naver_links = [a['href'] for a in soup.find_all('a', href=True) if
                                         a['href'].startswith('https://n.news.naver.com')]
                    if url != [] and url[0] not in urlList and 'sid=106' not in url[0]:
                        urlList.append(url[0])
                        self.IntegratedDB['UrlCnt'] += 1

                if self.print_status_option == True:
                    self.printStatus('NaverNews', 2, self.PrintData)

                if data['contents'] == []:
                    break

                currentPage += 10

            urlList = list(set(urlList))

            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData
            
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2003, error_msg, search_page_url_tmp)

    # Sync Part

    # 파라미터로 (url) 전달
    async def articleCollector(self, newsURL, session):
        if isinstance(newsURL, str) == False or self._newsURLChecker(newsURL) == False:
            return self.error_dump(2004, "Check newsURL", newsURL)
        
        try:
            if self.print_status_option == True:
                self.printStatus('NaverNews', 3, self.PrintData)
            res = await self.asyncRequester(newsURL, session=session)
            if self.RequesterChecker(res) == False:
                return res
            bs            = BeautifulSoup(res, 'lxml')
            news          = ''.join((i.text.replace("\n", "") for i in bs.find_all("div", {"class": "newsct_article"})))
            try:
                article_press = str(bs.find("img")).split()[1][4:].replace("\"", '') # article_press
                article_type  = bs.find("em", class_="media_end_categorize_item").text # article_type
                article_title = bs.find("div", class_="media_end_head_title").text.replace("\n", " ") # article_title
                article_date  = bs.find("span", {"class": "media_end_head_info_datestamp_time _ARTICLE_DATE_TIME"}).text.replace("\n", " ")
                date_obj = datetime.strptime(article_date.split()[0], "%Y.%m.%d.")
                article_date = date_obj.strftime("%Y-%m-%d")

                articleData = [article_press, article_type, newsURL, article_title, news, article_date]
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
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2005, error_msg, newsURL)
    
    # 파라미터로 (url, 통계데이터 반환 옵션, 댓글 코드 반환 옵션) 전달
    async def replyCollector(self, newsURL, session):
        if isinstance(newsURL, str) == False or self._newsURLChecker(newsURL) == False:
            return self.error_dump(2006, "Check newsURL", newsURL)
        try:
            oid  = newsURL[39:42]
            aid  = newsURL[43:53]
            page = 1
            headers = {"User-agent":generate_navigator()['user_agent'], "referer":newsURL}  
            
            nickname_list   = []
            replyDate_list  = []
            text_list       = []
            rere_count_list = []
            r_like_list     = []
            r_bad_list      = []
            replyList      = []
            statistics_data = []
            parentCommentNo_list = []

            returnData = {
                'replyList':            replyList,
                'parentCommentNo_list': parentCommentNo_list,
                'statisticsData':       statistics_data,
                'replyCnt':             len(replyList)
            }
            
            while True:
                
                if page == 101:
                    break
                
                params = {
                        'ticket'             : 'news',
                        'templateId'         : 'default_society',
                        'pool'               : 'cbox5',
                        'lang'               : 'ko',
                        'country'            : 'KR',
                        'objectId'           : f'news{oid},{aid}',
                        'pageSize'           : '100',
                        'indexSize'          : '10',
                        'page'               : str(page),
                        'currentPage'        : '0',
                        'moreParam.direction': 'next',
                        'moreParam.prev'     : '10000o90000op06guicil48ar|s',
                        'moreParam.next'     : '1000050000305guog893h1re',
                        'followSize'         : '100',
                        'includeAllStatus'   : 'true',
                        'sort'               : 'reply',
                        'initialize'         : 'true'
                    }
                response = await self.asyncRequester('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', headers=headers, params=params, session=session)
                if self.RequesterChecker(response) == False:
                    return response
                res               = response.replace("_callback(","")[:-2]
                temp              = json.loads(res)    


                # parentCommentNo_list PART
                for comment_json in temp.get("result", {}).get("commentList", []):
                    parentCommentNo_list.append(comment_json["parentCommentNo"])
                
                df = pd.DataFrame(temp['result']['commentList'])

                try:
                    masked_user_ids  = list(df['maskedUserId'])
                    mod_times        = list(df['modTime'])
                    contents         = list(df['contents'])
                    reply_counts     = list(df['replyCount'])
                    sympathy_counts  = list(df['sympathyCount'])
                    antipathy_counts = list(df['antipathyCount'])
                except:
                    if self.print_status_option:
                        self.printStatus('NaverNews', 4, self.PrintData)
                    return returnData

                nickname_list.extend(masked_user_ids)
                replyDate_list.extend(mod_times)
                text_list.extend(contents)
                rere_count_list.extend(reply_counts)
                r_like_list.extend(sympathy_counts)
                r_bad_list.extend(antipathy_counts)

                self.IntegratedDB['TotalReplyCnt'] += len(masked_user_ids)
                
                if self.print_status_option:
                    self.printStatus('NaverNews', 4, self.PrintData)
                    
                if len(masked_user_ids) < 97:
                    break
        
                page += 1

            # statistics_data PART
            try:
                commentCnt = temp['result']['count']['comment']
                male       = temp['result']['graph']['gender']['male']   # male
                female     = temp['result']['graph']['gender']['female'] # female
                Y_10       = temp['result']['graph']['old'][0]['value']
                Y_20       = temp['result']['graph']['old'][1]['value']
                Y_30       = temp['result']['graph']['old'][2]['value']
                Y_40       = temp['result']['graph']['old'][3]['value']
                Y_50       = temp['result']['graph']['old'][4]['value']
                Y_60       = temp['result']['graph']['old'][5]['value']
                statistics_data = [commentCnt, male, female, Y_10, Y_20, Y_30, Y_40, Y_50, Y_60]
            except:
                pass

            returnParentCommentNo_list = []
            for i in range(len(parentCommentNo_list)):
                if rere_count_list[i] > 0:
                    returnParentCommentNo_list.append(parentCommentNo_list[i])

            # comment_list PART
            reply_idx = 1
            for i in range(len(nickname_list)):

                r_per_like = 0.0 # 댓글 긍정 지수 구하기
                r_sum_like_angry = int(r_like_list[i]) + int(r_bad_list[i])
                if r_sum_like_angry != 0:
                    r_per_like = float(int(r_like_list[i]) / r_sum_like_angry)
                    r_per_like = float(format(r_per_like, ".2f"))
                # 댓글 긍정,부정 평가
                if r_per_like > 0.5:  # 긍정
                    r_sentiment = 1
                elif r_per_like == 0:  # 무관심
                    r_sentiment = 2
                elif r_per_like < 0.5:  # 부정
                    r_sentiment = -1
                else:  # 중립
                    r_sentiment = 0

                if text_list[i] != '':
                    replyList.append(
                        [
                        str(reply_idx),
                        str(nickname_list[i]),
                        datetime.strptime(replyDate_list[i], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                        str(text_list[i].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', '')),
                        str(rere_count_list[i]),
                        str(r_like_list[i]),
                        str(r_bad_list[i]),
                        str(r_per_like),
                        str(r_sentiment),
                        str(newsURL),
                        parentCommentNo_list[i]
                        ]
                    )
                    reply_idx += 1

            if self.print_status_option:
                self.printStatus('NaverNews', 4, self.PrintData)

            returnData['replyList']           = replyList
            returnData['parentCommentNo_list'] = returnParentCommentNo_list
            returnData['statisticsData']      = statistics_data
            returnData['replyCnt']            = len(replyList)

            return returnData

        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2007, error_msg, newsURL)
    
    # 파라미터로 (url, 댓글 코드) 전달
    async def rereplyCollector(self, newsURL, parentCommentNum_list, session):
        if isinstance(newsURL, str) == False or self._newsURLChecker(newsURL) == False:
            return self.error_dump(2008, 'Check newsURL', newsURL)
        if isinstance(parentCommentNum_list, list) == False:
            return self.error_dump(2009, 'Check parentCommentNum_list', parentCommentNum_list)
        
        try:
            oid  = newsURL[39:42]
            aid  = newsURL[43:53]
            headers = {"User-agent":generate_navigator()['user_agent'], "referer":newsURL}  
            base_url = "".join(
                            [
                                "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=news",
                                "&pool=cbox5&lang=ko&country=KR",
                                "&objectId=news{}%2C{}&categoryId=&pageSize={}&indexSize=10&groupId=&listType=OBJECT&pageType=more",
                                "&page={}&initialize=true&followSize=5&userType=&useAltSort=true&replyPageSize=20&sort={}&includeAllStatus=true&_=1696730082374",
                            ]
                        )
            
            nickname_list       = []
            rereplyDate_list    = []
            text_list           = []
            r_like_list         = []
            r_bad_list          = []
            rereplyList        = []
            parentReplynum_list = []
            
            for i in range(len(parentCommentNum_list)):
                try:
                    base_url_tmp_re = (base_url.format(oid, aid, 100, 1, "reply") + "&parentCommentNo=" + parentCommentNum_list[i])
                    response = await self.asyncRequester(base_url_tmp_re, headers, session=session)
                    if self.RequesterChecker(response) == False:
                        return response
                    res               = response.replace("_callback(","")[:-2]
                    temp              = json.loads(res)    
                    
                    df = pd.DataFrame(temp['result']['commentList'])
                    try:
                        masked_user_ids  = list(df['maskedUserId'])
                        mod_times        = list(df['modTime'])
                        contents         = list(df['contents'])
                        sympathy_counts  = list(df['sympathyCount'])
                        antipathy_counts = list(df['antipathyCount'])
                    except:
                        continue

                    nickname_list.extend(masked_user_ids)
                    rereplyDate_list.extend(mod_times)
                    text_list.extend(contents)
                    r_like_list.extend(sympathy_counts)
                    r_bad_list.extend(antipathy_counts)
                    parentReplynum_list.extend([parentCommentNum_list[i]] * len(masked_user_ids))     
                    
                    self.IntegratedDB['TotalRereplyCnt'] += len(masked_user_ids)
                    if self.print_status_option == True:
                        self.printStatus('NaverNews', 5, self.PrintData)
                except:
                    pass
            
            rereply_idx = 0
            for i in range(len(nickname_list)):
                rereply_idx += 1
                
                r_per_like = 0.0 # 댓글 긍정 지수 구하기
                r_sum_like_angry = int(r_like_list[i]) + int(r_bad_list[i])
                if r_sum_like_angry != 0:
                    r_per_like = float(int(r_like_list[i]) / r_sum_like_angry)
                    r_per_like = float(format(r_per_like, ".2f"))
                # 댓글 긍정,부정 평가
                if r_per_like > 0.5:  # 긍정
                    r_sentiment = 1
                elif r_per_like == 0:  # 무관심
                    r_sentiment = 2
                elif r_per_like < 0.5:  # 부정
                    r_sentiment = -1
                else:  # 중립
                    r_sentiment = 0

                if text_list[i] != '':
                    rereplyList.append(
                        [
                        parentReplynum_list[i],
                        str(nickname_list[i]),
                        datetime.strptime(rereplyDate_list[i], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                        str(text_list[i].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', '')),
                        str(r_like_list[i]),
                        str(r_bad_list[i]),
                        str(r_per_like),
                        str(r_sentiment),
                        str(newsURL)
                        ]
                    )
            rereplyList_returnData = {
                'rereplyList': rereplyList,
                'rereplyCnt': len(rereplyList)
            }
            return rereplyList_returnData
        
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2010, error_msg, newsURL)

    # Async Part
    async def asyncSingleCollector(self, newsURL, option, session):
        semaphore = asyncio.Semaphore(10)
        async with semaphore:
            articleData = await self.articleCollector(newsURL, session)
            replyData = await self.replyCollector(newsURL, session)
            if option == 1:
                return {'articleData': articleData, 'replyData': replyData}

            first_key = list(replyData.keys())[0]
            if first_key == 'Error Code':
                rereplyData = {
                    'rereplyList': [],
                    'rereplyCnt': 0
                }
            else:
                parentCommentNum_list = replyData['parentCommentNo_list']
                rereplyData = await self.rereplyCollector(newsURL, parentCommentNum_list, session)

            return {'articleData': articleData, 'replyData': replyData, 'rereplyData': rereplyData}

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
    print("2. Part (NaverNewsURL Required -> articleCollector & replyCollector)\n")

    number       = int(input("Number: "))
    proxy_option = int(input("\nUse Proxy? (1/0): "))
    option       = int(input("\nOption: "))
    print("==================================================")

    CrawlerPackage_obj = NaverNewsCrawler(proxy_option=proxy_option, print_status_option=True)
    CrawlerPackage_obj.error_detector_option_on()

    if number == 1:
        print("\nNaverNewsCrawler_urlCollector: ", end='')
        urlList_returnData = CrawlerPackage_obj.urlCollector("대통령", 20230101, 20230101)
        urlList = urlList_returnData['urlList']

        results = await CrawlerPackage_obj.asyncMultiCollector(urlList, option)
        print('\n')
        for i in results:
            print(i)

    elif number == 2:
        url = input("\nTarget NaverNews URL: ")
        result = await CrawlerPackage_obj.asycSingleCollector(url, option)
        print(result)


if __name__ == "__main__":
    asyncio.run(asyncTester())