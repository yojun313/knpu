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
import random


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
                try:
                    json_data = json.loads(text)
                    if 'url' in json_data and json_data['url']:
                        return json_data['url']
                    else:
                        return None
                except:
                    return None

            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('NaverNews', 1, self.PrintData)

            query_dict = self.parse_naver_query(keyword)

            urlList = []
            
            params = {
                "abt": "null",
                "cluster_rank": str(random.choice([63, 64, 65])),
                "de": f"{endDate_formed}",
                "ds": f"{startDate_formed}",
                "eid": "",
                "field": "0",
                "force_original": random.choice(["", "1"]),
                "is_dts": "1",
                "is_sug_officeid": "0",
                "mynews": "0",
                "news_office_checked": "",
                "nlu_query": "",
                "nqx_theme": "",  # 이미지의 JSON 반영
                "nso": f"so:r,p:from{startDate}to{endDate},a:all",
                "nx_and_query": f"{query_dict['nx_and_query']}",
                "nx_search_hlquery": f"{query_dict['nx_search_hlquery']}",
                "nx_search_query": f"{query_dict['nx_search_query']}",
                "nx_sub_query": f"{query_dict['nx_sub_query']}",
                "office_category": "0",
                "office_section_code": "0",
                "office_type": "0",
                "pd": "3",
                "photo": "0",
                "query": f"{keyword}",
                "query_original": f"{keyword}",
                "rev": "0",
                "service_area": "0",
                "sm": "tab_smr",
                "sort": "0",
                "spq": "0",
                "ssc": "tab.news.all",
                "start": "1"  # 이미지에서 31로 표시됨 (필요에 따라 변경)
            }
                        
            # 파라미터를 쿼리 문자열로 변환
            query_string = urllib.parse.urlencode(params)

            # API URL 생성
            api_url = f"https://s.search.naver.com/p/newssearch/3/api/tab/more?{query_string}"

            # 요청 보내기
            response = self.Requester(api_url)
            if self.RequesterChecker(response) == False:
                return response
            
            if hasattr(response, "status_code") and response.status_code != 200:
                return self.error_dump(0, f"Non-200 response: {response.status_code}", api_url)
            json_text = response.text
            
            while True:
                pre_urlList = extract_newsurls(json_text)
                if not pre_urlList:
                    time.sleep(1)
                    
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
                    time.sleep(1)
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
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2003, error_msg, f"")

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
            self.IntegratedDB['totalArticleCnt'] += 1
            if self.print_status_option == True:
                self.printStatus('NaverNews', 3, self.PrintData)

            return returnData
               
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2005, error_msg, newsURL)
    
    # 파라미터로 (url, 통계데이터 반환 옵션, 댓글 코드 반환 옵션) 전달
    async def replyCollector(self, newsURL, session, username=False):
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
                try:
                    res = response.replace("_callback(", "")[:-2]
                    temp              = json.loads(res)
                except:
                    return returnData

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

                self.IntegratedDB['totalReplyCnt'] += len(masked_user_ids)
                
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

            tasks = []  # 병렬 실행을 위한 작업 리스트
            task_indices = []  # ReplyUsername을 실행할 인덱스 저장 (결과를 올바른 위치에 배치)
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
                    targetlist = [
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
                    if username == True:
                        tasks.append(self.ReplyUsername(oid, aid, parentCommentNo_list[i], newsURL, session))
                        task_indices.append(len(replyList))  # 결과를 배치할 인덱스 저장

                    replyList.append(targetlist)
                    reply_idx += 1

            if username and tasks:
                results = await asyncio.gather(*tasks)

                # 병렬 실행 결과를 replyList에 반영
                for idx, add_data in zip(task_indices, results):
                    replyList[idx][1] = f"{replyList[idx][1]}_{add_data[0]}_{add_data[1]}"
                    replyList[idx].extend(add_data[1:])  # 추가 데이터 삽입

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

    async def ReplyUsername(self, oid, aid, commentNo, newsURL, session):
        # API 엔드포인트
        url = "https://apis.naver.com/commentBox/cbox/web_naver_user_info_jsonp.json"
        # 요청 파라미터
        params = {
            "ticket": "news",
            "templateId": "default_society",
            "pool": "cbox5",
            "lang": "ko",
            "country": "KR",
            "objectId": f'news{oid},{aid}',
            "categoryId": "",
            "pageSize": 1,
            "indexSize": 10,
            "groupId": "",
            "listType": "user",
            "pageType": "more",
            "commentNo": commentNo,
            "targetUserInKey": "",
            "_": "1739271277330"
        }
        self.printStatus('NaverNews', 4, self.PrintData, commentNo=commentNo)
        # GET 요청 보내기
        headers = {"User-agent": generate_navigator()['user_agent'], "referer": newsURL}
        response = await self.asyncRequester(url, params=params, headers=headers, session=session)
        res = '{' + response.replace("_callback(", "")[:-2].split("{", 1)[-1]
        data = json.loads(res)

        nickname = data['result']['user']['nickname']
        commentCnt = data['result']['commentUserStats']['commentCount']
        replyCnt = data['result']['commentUserStats']['replyCount']
        likecnt = data['result']['commentUserStats']['sympathyCount']

        return [nickname, commentCnt, replyCnt, likecnt]


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
                    
                    self.IntegratedDB['totalRereplyCnt'] += len(masked_user_ids)
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
            if option == 3:
                return {'articleData': articleData}

            username = False
            if option == 4:
                username = True
            replyData = await self.replyCollector(newsURL, session, username=username)
            if option == 1 or option == 4:
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
        urlList_returnData = CrawlerPackage_obj.urlCollector("아이패드", 20230102, 20230102)
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
    #asyncio.run(asyncTester())
    CrawlerPackage_obj = NaverNewsCrawler(proxy_option=True, print_status_option=True)
    print(CrawlerPackage_obj.urlCollector('경찰대학', 20110101, 20111231)['urlCnt'])