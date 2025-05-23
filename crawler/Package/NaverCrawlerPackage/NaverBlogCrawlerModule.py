# -*- coding: utf-8 -*-
import os
import sys

NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH      = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

from CrawlerModule import CrawlerModule
from user_agent import generate_navigator
from datetime import datetime
import urllib3
import warnings
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
import json
import pandas as pd
import re
import asyncio
import aiohttp
import urllib.parse


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

class NaverBlogCrawler(CrawlerModule):
    
    def __init__(self, proxy_option = False, print_status_option = False):
        super().__init__(proxy_option)
        self.print_status_option = print_status_option
            
    def _blogURLChecker(self, url):
        pattern = r"^https://blog\.naver\.com/[^/]+/\d+$"
        return re.match(pattern, url) is not None
    
    def urlCollector(self, keyword, startDate, endDate):
        try:
            if isinstance(keyword, str) == False:
                return self.error_dump(2011, 'Check Keyword', keyword)
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            return self.error_dump(2012, 'Check DateForm', startDate)
        try:
            def parse_query(query):
                # 문자열을 공백으로 분리
                terms = query.split()

                # 첫 번째 단어를 nx_search_query에 할당
                if '+' in query or '-' in query:
                    nx_search_query = terms[0] if terms else ""
                elif "|" in query:
                    nx_search_query = query
                else:
                    nx_search_query = ""

                # + 기호가 붙은 단어 찾기
                and_terms = [term[1:] for term in terms if term.startswith('+')]

                # - 기호가 붙은 단어 찾기
                sub_terms = [term[1:] for term in terms if term.startswith('-')]

                nx_search_hlquery = ""
                if '"' in query:
                    nx_search_hlquery = query
                    nx_search_query = query.replace('"', '')
                    and_terms.append(query)

                # 딕셔너리 반환
                query_params = {
                    "nx_search_query": nx_search_query,
                    "nx_search_hlquery": nx_search_hlquery,
                    "nx_and_query": " ".join(and_terms) if and_terms else "",
                    "nx_sub_query": " ".join(sub_terms) if sub_terms else "",
                }
                return query_params
            
            def extract_blogurls(text):
                    # 정규식 패턴 정의
                pattern = r'https://blog\.naver\.com/[a-zA-Z0-9_-]+/\d+'

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
                self.printStatus('NaverBlog', 1, self.PrintData)

            query_dict = parse_query(keyword)

            urlList = []
            params = {
                "ssc": "tab.blog.all",
                "api_type": "8",
                "query": f"{keyword}",
                "start": "01",
                "nx_search_query": f"{query_dict['nx_search_query']}",
                "nx_and_query": f"{query_dict['nx_and_query']}",
                "nx_sub_query": f"{query_dict['nx_sub_query']}",
                "ac": "1",
                "aq": "0",
                "spq": "0",
                "sm": "tab_opt",
                "nso": f"so:r,p:from{startDate}to{endDate}",
                "prank": "30",
                "ngn_country": "KR",
                "fgn_region": "",
                "fgn_city": "",
                "abt": ""
            }
            base_url = "https://s.search.naver.com/p/review/49/search.naver"

            response = self.Requester(base_url, params=params)
            if self.RequesterChecker(response) == False:
                return response
            json_text = response.text
            
            while True:
                pre_urlList = extract_blogurls(json_text)

                for url in pre_urlList:
                    if url not in urlList and 'book' not in url:
                        urlList.append(url)
                        self.IntegratedDB['UrlCnt'] += 1

                if self.print_status_option == True:
                    self.printStatus('NaverBlog', 2, self.PrintData)

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
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2013, error_msg, api_url)
    
    async def articleCollector(self, blogURL, session):
        trynum = 1
        if isinstance(blogURL, str) == False or self._blogURLChecker(blogURL) == False:
            return self.error_dump(2014, "Check blogURL", blogURL)
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

                returnData = {
                    'articleData': []
                }
                
                split_url = blogURL.split("/")
                blogID    = split_url[3]
                logNo     = split_url[4]
                
                url = "https://blog.naver.com/PostView.naver?blogId={}&logNo={}&redirect=Dlog&widgetTypeCall=true&noTrackingCode=true&directAccess=false".format(blogID, logNo)
                headers = {
                    'User-Agent': generate_navigator()['user_agent'],
                    "referer" : blogURL
                }

                response = await self.asyncRequester(url, headers, session=session)
                if self.RequesterChecker(response) == False:
                    return response
                soup = BeautifulSoup(response, "html.parser")
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
                date_only = re.match(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", date)
                if date_only:
                    year, month, day = date_only.groups()
                    # 월과 일이 한 자리수일 경우 앞에 0을 추가
                    month = month.zfill(2)
                    day = day.zfill(2)
                    date = f"{year}-{month}-{day}"

                if article == "":
                    return returnData

                article_data["blog_ID"]      = str(blogID)
                article_data["url"]          = str(original_url)
                article_data["article_body"] = str(article)
                article_data["article_date"] = str(date)
                
                '''
                article_data["good_cnt"] = str(good_cnt)
                article_data["comment_cnt"] = str(comment_cnt)
                '''
                
                self.IntegratedDB['totalArticleCnt'] += 1
                if self.print_status_option == True:
                    self.printStatus('NaverBlog', 3, self.PrintData)
                
                articleData = [blogID, original_url, article, date]

                returnData['articleData'] = articleData

                return returnData
        
        except Exception:
            print("error")
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2015, error_msg, blogURL)
    
    async def replyCollector(self, blogURL, session):
        if isinstance(blogURL, str) == False or self._blogURLChecker(blogURL) == False:
            return self.error_dump(2016, "Check blogURL", blogURL)
        try:
            split_url = blogURL.split("/")
            blogID    = split_url[3]
            logNo     = split_url[4]
            
            url        = "https://blog.naver.com/PostView.naver?blogId={}&logNo={}&redirect=Dlog&widgetTypeCall=false&directAccess=false".format(blogID, logNo)

            returnData = {
                'replyList': [],
                'replyCnt': 0
            }

            trynum = 1
            while True:
                try:
                    response   = await self.asyncRequester(url, session=session)
                    if self.RequesterChecker(response) == False:
                        return response
                    soup       = BeautifulSoup(response, "html.parser")
                    script_tag = soup.find('script', string=re.compile(r'var\s+blogNo\s*=\s*\'(\d+)\''))
                    blogNo     = re.search(r'var\s+blogNo\s*=\s* \'(\d+)\'', script_tag.text).group(1)
                    break
                except:
                    trynum += 1
                    if trynum == 5:
                        return returnData
            
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
                
                response = await self.asyncRequester('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', headers, params, session=session)
                if self.RequesterChecker(response) == False:
                    return response
                res               = response
                temp              = json.loads(res)  

                for comment_json in temp.get("result", {}).get("commentList", []):
                    parentCommentNo_list.append(comment_json["parentCommentNo"])
                
                try:
                    df = pd.DataFrame(temp['result']['commentList'])
                except:
                    return returnData

                if list(df) == []:
                    return returnData
                
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

                self.IntegratedDB['totalReplyCnt'] += len(masked_user_ids)
                self.IntegratedDB['totalRereplyCnt'] += len(masked_user_ids)
                
                if self.print_status_option:
                    self.printStatus('NaverBlog', 6, self.PrintData)
                
                if len(masked_user_ids) < 97:
                    break
                
                page += 1
            
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
                    replyList.append([
                            str(reply_idx),
                            str(nickname_list[i]),
                            datetime.strptime(replyDate_list[i], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                            str(text_list[i].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', '')),
                            str(rere_count_list[i]),
                            str(r_like_list[i]),
                            str(r_bad_list[i]),
                            str(r_per_like),
                            str(r_sentiment),
                            str(blogURL),
                            parentCommentNo_list[i]
                    ])
                    reply_idx += 1

            returnData['replyList'] = replyList
            returnData['replyCnt'] = len(replyList)

            return returnData

                
        except Exception as e:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2017, error_msg, blogURL)
  

    async def asyncSingleCollector(self, blogURL, option, session):
        semaphore = asyncio.Semaphore(10)
        async with semaphore:
            articleData = await self.articleCollector(blogURL, session)
            if option == 1:
                return {'articleData': articleData}

            replyData = await self.replyCollector(blogURL, session)
            return {'articleData': articleData, 'replyData': replyData}

    async def asyncMultiCollector(self, urlList, option):
        tasks = []
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=self.socketnum))
        for blogURL in urlList:
            tasks.append(self.asyncSingleCollector(blogURL, option, session))

        results = await asyncio.gather(*tasks)
        await session.close()
        return results

async def asyncTester():
    print("============ Crawler Packeage Tester ============")
    print("I. Choose Option\n")
    print("1. ALL  (Full Automatic: UrlCollector -> articleCollector & replyCollector)")
    print("2. Part (NaverBlogURL Required -> articleCollector & replyCollector)\n")

    number = int(input("Number: "))
    proxy_option = int(input("\nUse Proxy? (1/0): "))
    option = int(input("\nOption: "))
    print("==================================================")

    CrawlerPackage_obj = NaverBlogCrawler(proxy_option=proxy_option, print_status_option=True)
    CrawlerPackage_obj.error_detector_option_on()

    if number == 1:
        print("\nNaverBlogCrawler_urlCollector: ", end='')
        urlList_returnData = CrawlerPackage_obj.urlCollector("테러 +예고", 20230102, 20230102)
        urlList = urlList_returnData['urlList']

        results = await CrawlerPackage_obj.asyncMultiCollector(urlList, option)
        print('\n')
        for i in results:
            print(i)

    elif number == 2:
        url = input("\nTarget NaverBlog URL: ")
        result = await CrawlerPackage_obj.asycSingleCollector(url, option)
        print(result)


if __name__ == "__main__":
    #asyncio.run(asyncTester())
    CrawlerPackage_obj = NaverBlogCrawler(proxy_option=0, print_status_option=True)
    CrawlerPackage_obj.error_detector_option_on()
    urlList_returnData = CrawlerPackage_obj.urlCollector("포항공대 | 카이스트", 20230101, 20230101)
    urlList = urlList_returnData['urlList']

    print(urlList)