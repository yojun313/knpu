# -*- coding: utf-8 -*-
import sys
import os

NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLERPACKAGE_PATH      = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)
sys.path.append(CRAWLERPACKAGE_PATH)

from CrawlerPackage import CrawlerPackage
from ToolPackage import ToolPackage
from user_agent import generate_user_agent, generate_navigator
from datetime import datetime, timezone
import urllib3
import warnings
from bs4 import BeautifulSoup
import json
import pandas as pd
import re
from urllib.parse import urlparse, parse_qs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class NaverNewsCrawler(CrawlerPackage):
    
    def __init__(self, proxy_option = False):
        super().__init__(proxy_option)
    
    def newsURLChecker(self, url):
        parts = [
        r"https://n\.news\.naver\.com",
        r"/mnews/article",
        r"/\d{3}",
        r"/\d{9}",
        r"\?sid=\d{3}"
        ]
        for part in parts:
            if not re.search(part, url):
                return False
        return True
    
    # 파라미터로 (검색어, 시작일, 종료일) 전달
    def urlCollector(self, keyword, startDate, endDate, error_detector_option = False): # DateForm: ex)20231231
        try:
            if isinstance(keyword, str) == False:
                return 2001
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            return 2002
        try:
            urlList = []
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
            search_page_url = "https://search.naver.com/search.naver?where=news&query={}&sm=tab_srt&sort=2&photo=0&reporter_article=&pd=3&ds={}&de={}&&start={}&related=0"

            currentPage = 1
            while True:
                search_page_url_tmp = search_page_url.format(keyword, startDate, endDate, currentPage)
                main_page = self.Requester(search_page_url_tmp)
                main_page = BeautifulSoup(main_page.text, "lxml") #스크랩 모듈에 url 넘김
                site_result = main_page.select('a[class = "info"]')
                
                if site_result == []:
                    break

                for a in site_result: #스크랩한 데이터 중 링크만 추출
                    add_link = a['href']
                    if 'sports' not in add_link and 'sid=106' not in add_link and add_link not in urlList and 'entertain' not in add_link:
                        urlList.append(add_link)
                        
                    if add_link == None:
                        break
                
                currentPage += 10 # 다음페이지 이동
            
            urlList = list(set(urlList))
            returnData = {
                'urlList' : urlList,
                'urlCnt'  : len(urlList)
            }
            
            return returnData
            
        except Exception:
            error_msg  = self.error_detector(error_detector_option)
            error_data = {
                'Error Code' : 2003,
                'Error Msg' : error_msg
            }
            return error_data
            
    # 파라미터로 (url) 전달
    def articleCollector(self, newsURL, error_detector_option = False):
        if isinstance(newsURL, str) == False or self.newsURLChecker(newsURL) == False:
            return 2004
        try:
            res           = self.Requester(newsURL)
            bs            = BeautifulSoup(res.text, 'lxml')    
            news          = ''.join((i.text.replace("\n", "") for i in bs.find_all("div", {"class": "newsct_article"})))
            article_press = str(bs.find("img")).split()[1][4:].replace("\"", '') # article_press
            article_type  = bs.find("em", class_="media_end_categorize_item").text # article_type
            article_title = bs.find("div", class_="media_end_head_title").text.replace("\n", " ") # article_title
            article_date  = bs.find("span", {"class": "media_end_head_info_datestamp_time _ARTICLE_DATE_TIME"}).text.replace("\n", " ")
            reply_cnt     = 0
            statistics    = 'N'
            male          = 999
            female        = 999
            Y_10          = 999
            Y_20          = 999
            Y_30          = 999
            Y_40          = 999
            Y_50          = 999
            Y_60          = 999

            articleData = [article_press, article_type, newsURL, article_title, news, article_date, reply_cnt, statistics, male, female, Y_10, Y_20, Y_30, Y_40, Y_50, Y_60]
            returnData = {
                'articleData' : articleData
            }
            return returnData
               
        except Exception:
            error_msg  = self.error_detector(error_detector_option)
            error_data = {
                'Error Code' : 2005,
                'Error Msg' : error_msg
            }
            return error_data
    
    # 파라미터로 (url, 통계데이터 반환 옵션, 댓글 코드 반환 옵션) 전달
    def replyCollector(self, newsURL, error_detector_option = False): 
        if isinstance(newsURL, str) == False or self.newsURLChecker(newsURL) == False:
            return 2006
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
                
                response = self.Requester('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', headers, params)
                response.encoding = "UTF-8-sig"
                res               = response.text.replace("_callback(","")[:-2]
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
                    returnData = {
                        'replyList' : replyList,
                        'parentCommentNo_list' : parentCommentNo_list,
                        'statistics_data' : statistics_data,
                        'replyCnt' : len(replyList)
                    }
                    return returnData
                    

                nickname_list.extend(masked_user_ids)
                replyDate_list.extend(mod_times)
                text_list.extend(contents)
                rere_count_list.extend(reply_counts)
                r_like_list.extend(sympathy_counts)
                r_bad_list.extend(antipathy_counts)
        
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
            
            # comment_list PART
            reply_idx = 0
            for i in range(len(nickname_list)):
                reply_idx += 1
                
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
                
                replyList.append(
                    [
                    str(reply_idx),
                    str(nickname_list[i]),
                    str(replyDate_list[i]),
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
            returnData = {
                'replyList' : replyList,
                'parentCommentNo_list' : parentCommentNo_list,
                'statistics_data' : statistics_data,
                'replyCnt' : len(replyList)
            }
            
            return returnData
            
        except Exception:
            error_msg  = self.error_detector(error_detector_option)
            error_data = {
                'Error Code' : 2007,
                'Error Msg' : error_msg
            }
            return error_data
    
    # 파라미터로 (url, 댓글 코드) 전달
    def rereplyCollector(self, newsURL, parentCommentNum_list, error_detector_option = False):
        if isinstance(newsURL, str) == False or self.newsURLChecker(newsURL) == False:
            return 2008
        if isinstance(parentCommentNum_list, list) == False:
            return 2009
        
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
                    response = self.Requester(base_url_tmp_re, headers)
                    response.encoding = "UTF-8-sig"
                    res               = response.text.replace("_callback(","")[:-2]
                    temp              = json.loads(res)    
                    
                    df = pd.DataFrame(temp['result']['commentList'])

                    masked_user_ids  = list(df['maskedUserId'])
                    mod_times        = list(df['modTime'])
                    contents         = list(df['contents'])
                    sympathy_counts  = list(df['sympathyCount'])
                    antipathy_counts = list(df['antipathyCount'])

                    nickname_list.extend(masked_user_ids)
                    rereplyDate_list.extend(mod_times)
                    text_list.extend(contents)
                    r_like_list.extend(sympathy_counts)
                    r_bad_list.extend(antipathy_counts)
                    parentReplynum_list.extend([parentCommentNum_list[i]] * len(masked_user_ids))     
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
                
                rereplyList.append(
                    [
                    str(rereply_idx),
                    str(nickname_list[i]),
                    str(rereplyDate_list[i]),
                    str(text_list[i].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', '')),
                    str(r_like_list[i]),
                    str(r_bad_list[i]),
                    str(r_per_like),
                    str(r_sentiment),
                    str(newsURL),
                    parentReplynum_list[i]
                    ]     
                )
            returnData = {
                'rereplyList' : rereplyList,
                'rereplyCnt': len(rereplyList)
            }
            return returnData
        
        except Exception:
            error_msg  = self.error_detector(error_detector_option)
            error_data = {
                'Error Code' : 2010,
                'Error Msg' : error_msg
            }
            return error_data

def CrawlerTester(url):
    print("\nNaverNewsCrawler_articleCollector: ", end = '')
    target = CrawlerPackage_obj.articleCollector(newsURL=url, error_detector_option=True)
    ToolPackage_obj.CrawlerChecker(target, result_option=result_option)
    
    print("\nNaverNewsCrawler_replyCollector: ", end = '')
    target = CrawlerPackage_obj.replyCollector(newsURL=url, error_detector_option=True)
    ToolPackage_obj.CrawlerChecker(target, result_option=result_option)
    
    parentCommentNum_list = target[1]['parentCommentNo_list']
    
    print("\nNaverNewsCrawler_rereplyCollector: ", end = '')
    target = CrawlerPackage_obj.rereplyCollector(newsURL=url, parentCommentNum_list=parentCommentNum_list, error_detector_option=True)
    ToolPackage_obj.CrawlerChecker(target, result_option=result_option)
            
if __name__ == "__main__":
    
    ToolPackage_obj = ToolPackage()

    print("============ Crawler Packeage Tester ============")
    print("I. Choose Option\n")
    print("1. ALL  (Full Automatic: UrlCollector -> articleCollector & replyCollector & rereplyCollector)")
    print("2. Part (NaverNewsURL Required -> articleCollector & replyCollector & rereplyCollector)\n")
    
    option = int(input("Number: "))
    proxy_option = int(input("\nUse Proxy? (1/0): "))
    result_option = int(input("\nPrint Result (1/0): "))
    print("==================================================")
    
    CrawlerPackage_obj = NaverNewsCrawler(proxy_option=proxy_option)
    
    if option == 1:
        print("\nNaverNewsCrawler_urlCollector: ", end = '')
        returnData = CrawlerPackage_obj.urlCollector("급발진", 20240601, 20240601, error_detector_option=True)
        ToolPackage_obj.CrawlerChecker(returnData, result_option=result_option)
        
        urlList = returnData['urlList']
        
        for url in urlList:
            CrawlerTester(url)
    
    elif option == 2:
        url = input("\nTarget NaverNews URL: ")
        CrawlerTester(url)