# -*- coding: utf-8 -*-
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
from urllib.parse import urlparse, parse_qs
import random
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class NaverBlogCrawler(CrawlerPackage):
    
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
        
        self.replyList_returnData = {
            'replyList' : [],
            'replyCnt' : 0
        }
            
    def blogURLChecker(self, url):
        pattern = r"^https://blog\.naver\.com/[^/]+/\d+$"
        return re.match(pattern, url) is not None
    
    def urlCollector(self, keyword, startDate, endDate):
        try:
            if isinstance(keyword, str) == False:
                self.error_dump(2011, 'Check Keyword', keyword)
                return self.error_data
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            self.error_dump(2012, 'Check DateForm', startDate)
            return self.error_data
        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('NaverBlog', 1, self.PrintData)
                
            ipChange = False
            urlList = []
            if self.proxy_option == True:
                ipList  = random.sample(self.proxy_list, 1000)
            
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
            search_page_url = "https://search.naver.com/search.naver?ssc=tab.blog.all&query={}&sm=tab_opt&nso=so%3Ar%2Cp%3Afrom{}to{}&&start={}"
            
            currentPage = 1
            while True:
                search_page_url_tmp = search_page_url.format(keyword, startDate, endDate, currentPage)
                
                if self.proxy_option == True:
                    
                    proxy = {"http": 'http://' + ipList[0], 'https': 'http://' + ipList[0]}
                    main_page = self.Requester(search_page_url_tmp, proxies = proxy)
                    if main_page == 0:
                        ipChange = True
                        ipList.pop(0)
                else:
                    main_page = self.Requester(search_page_url_tmp)
                
                if ipChange == False:
                    main_page = BeautifulSoup(main_page.text, "lxml") #스크랩 모듈에 url 넘김
                    site_result = main_page.select('a[class = "title_link"]')
                    
                    if site_result == []:
                        break
                        
                    for a in site_result: #스크랩한 데이터 중 링크만 추출 
                        add_link = a['href']
                        if add_link not in urlList and 'naver' in add_link and 'tistory' not in add_link:
                            urlList.append(add_link)
                            self.IntegratedDB['UrlCnt'] += 1
                                
                            if add_link == None:
                                break
                       
                    if self.print_status_option == True: 
                        self.printStatus('NaverBlog', 2, self.PrintData)
                    
                    currentPage += 10
                else:
                    currentPage = 1
                    ipChange = False
                    urlList = []
                    self.IntegratedDB['UrlCnt'] = 0
            
            urlList = list(set(urlList))

            self.urlList_returnData['urlList'] = urlList
            self.urlList_returnData['urlCnt']  = len(urlList)
            
            return self.urlList_returnData
            
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            self.error_dump(2013, error_msg, search_page_url_tmp)
            return self.error_data
    
    def articleCollector(self, blogURL):
        trynum = 1
        if isinstance(blogURL, str) == False or self.blogURLChecker(blogURL) == False:
            self.error_dump(2014, "Check blogURL", blogURL)
            return self.error_data
        try:
            while True:
                original_url = blogURL

                article_data = {
                    "blog_ID": None,
                    "url": None,
                    "article_body": None,
                    "article_date": None,
                    "good_cnt": None,
                    "comment_cnt": None
                }
                
                split_url = blogURL.split("/")
                blogID    = split_url[3]
                logNo     = split_url[4]
                
                url = "https://blog.naver.com/PostView.naver?blogId={}&logNo={}&redirect=Dlog&widgetTypeCall=true&noTrackingCode=true&directAccess=false".format(blogID, logNo)
                headers = {
                    'User-Agent': generate_navigator()['user_agent'],
                    "referer" : blogURL
                }

                response = self.Requester(url, headers)
                soup = BeautifulSoup(response.text, "html.parser")
                '''
                try:
                    good_cnt_url = "https://blog.naver.com/api/blogs/{}/posts/{}/sympathy-users".format(blogID, logNo)
                    good_cnt = json.loads(BeautifulSoup(self.Requester(good_cnt_url, headers).text, "html.parser").text)['result']['totalCount']

                    comment_cnt_url = "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=blog&pool=blogid&lang=ko&country=&objectId={}&groupId={}".format(objectID, blogNo)
                    comment_cnt = json.loads(self.Requester(comment_cnt_url, headers).text)['result']['count']['comment']
                except:
                    good_cnt = 0
                    comment_cnt = 0
                '''
            
                article = "".join([i.text.replace("\n", "").replace("\t", "").replace("\u200b", "") for i in soup.select("div[class = 'se-module se-module-text']")])
                date = "".join([i.text for i in soup.select("span[class = 'se_publishDate pcol2']")])
                                
                if article == "":
                    trynum += 1
                    if trynum == 5:
                        return self.article_returnData
                    continue
                article_data["blog_ID"]      = str(blogID)
                article_data["url"]          = str(original_url)
                article_data["article_body"] = str(article)
                article_data["article_date"] = str(date)
                
                '''
                article_data["good_cnt"] = str(good_cnt)
                article_data["comment_cnt"] = str(comment_cnt)
                '''
                
                self.IntegratedDB['TotalArticleCnt'] += 1
                if self.print_status_option == True:
                    self.printStatus('NaverBlog', 3, self.PrintData)
                
                articleData = [blogID, original_url, article, date]
                
                self.article_returnData['articleData'] = articleData
                return self.article_returnData
        
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)
            self.error_dump(2015, error_msg, blogURL)
            return self.error_data
    
    def replyCollector(self, blogURL):
        if isinstance(blogURL, str) == False or self.blogURLChecker(blogURL) == False:
            self.error_dump(2016, "Check blogURL", blogURL)
            return self.error_data
        try:
            split_url = blogURL.split("/")
            blogID    = split_url[3]
            logNo     = split_url[4]
            
            url        = "https://blog.naver.com/PostView.naver?blogId={}&logNo={}&redirect=Dlog&widgetTypeCall=false&directAccess=false".format(blogID, logNo)
            
            trynum = 1
            while True:
                try:
                    response   = self.Requester(url)
                    soup       = BeautifulSoup(response.text, "html.parser")
                    script_tag = soup.find('script', string=re.compile(r'var\s+blogNo\s*=\s*\'(\d+)\''))
                    blogNo     = re.search(r'var\s+blogNo\s*=\s* \'(\d+)\'', script_tag.text).group(1)
                    break
                except:
                    trynum += 1
                    if trynum == 5:
                        return self.replyList_returnData
            
            objectID   = f'{blogNo}_201_{logNo}'
            
            page       = 1
            
            nickname_list   = []
            replyDate_list  = []
            text_list       = []
            rere_count_list = []
            r_like_list     = []
            r_bad_list      = []
            replyList       = []
            parentCommentNo_list = []

            headers = {
                'user-agent':generate_navigator()['user_agent'],
                'referer': url}

            while True:
                if page == 101:
                    break
                
                params = {
                            'ticket': "blog",
                            'templateId': 'default',
                            'pool': 'blogid',
                            'lang': 'ko',
                            'country': 'KR',
                            'objectId': objectID,
                            'groupId': blogNo,
                            'pageSize': '50',
                            'indexSize': '10',
                            'page': str(page),
                            'morePage.prev': '051v2o4l34sgr1t0txuehz9fxg',
                            'morePage.next': '051sz9hwab3fe1t0w1916s34yt',
                        }
                
                response = self.Requester('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', headers, params)
                response.encoding = "UTF-8-sig"
                res               = response.text
                temp              = json.loads(res)  

                
                for comment_json in temp.get("result", {}).get("commentList", []):
                    parentCommentNo_list.append(comment_json["parentCommentNo"])
                
                try:
                    df = pd.DataFrame(temp['result']['commentList'])
                except:
                    return self.replyList_returnData

                if list(df) == []:
                    return self.replyList_returnData
                
                masked_user_ids  = list(df['maskedUserId'])
                mod_times        = list(df['modTime'])
                contents         = list(df['contents'])
                reply_counts     = list(df['replyCount'])
                sympathy_counts  = list(df['sympathyCount'])
                antipathy_counts = list(df['antipathyCount'])

                nickname_list.extend(masked_user_ids)
                replyDate_list.extend(mod_times)
                text_list.extend(contents)
                rere_count_list.extend(reply_counts)
                r_like_list.extend(sympathy_counts)
                r_bad_list.extend(antipathy_counts)

                self.IntegratedDB['TotalReplyCnt'] += len(masked_user_ids)
                self.IntegratedDB['TotalRereplyCnt'] += len(masked_user_ids)
                
                if self.print_status_option:
                    self.printStatus('NaverBlog', 6, self.PrintData)
                
                if len(masked_user_ids) < 97:
                    break
                
                page += 1
            
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
                    str(blogURL),
                    parentCommentNo_list[i]
                    ]     
                )
            
            self.replyList_returnData['replyList'] = replyList
            self.replyList_returnData['replyCnt']  = len(replyList)
            
            return self.replyList_returnData
                
        except Exception as e:
            error_msg  = self.error_detector(self.error_detector_option)
            self.error_dump(2017, error_msg, blogURL)
            return self.error_data
  
def CrawlerTester(url):
    print("\nNaverBlogCrawler_articleCollector: ", end = '')
    target = CrawlerPackage_obj.articleCollector(blogURL=url)
    ToolPackage_obj.CrawlerChecker(target, result_option=result_option)

    print("\nNaverBlogCrawler_replyCollector: ", end = '')
    target = CrawlerPackage_obj.replyCollector(blogURL=url)
    ToolPackage_obj.CrawlerChecker(target, result_option=result_option)

    
if __name__ == "__main__":
    
    ToolPackage_obj = ToolPackage()

    print("============ Crawler Packeage Tester ============")
    print("I. Choose Option\n")
    print("1. ALL  (Full Automatic: UrlCollector -> articleCollector & replyCollector)")
    print("2. Part (NaverBlogURL Required -> articleCollector & replyCollector)\n")

    option = int(input("Number: "))
    proxy_option = int(input("\nUse Proxy? (1/0): "))
    result_option = int(input("\nPrint Result (1/0): "))
    print("==================================================")

    CrawlerPackage_obj = NaverBlogCrawler(proxy_option=proxy_option)
    CrawlerPackage_obj.error_detector_option_on()

    if option == 1:
        print("\nNaverBlogCrawler_urlCollector: ", end = '')
        returnData = CrawlerPackage_obj.urlCollector("무고죄", 20240601, 20240601)
        ToolPackage_obj.CrawlerChecker(returnData, result_option=result_option)
        
        urlList = returnData['urlList']
        
        for url in urlList:
            CrawlerTester(url)

    elif option == 2:
        url = input("\nTarget NaverBlog URL: ")
        CrawlerTester(url)