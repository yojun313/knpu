# -*- coding: utf-8 -*-
import os
import sys

# 경로 설정: CrawlerModule을 상위 폴더에서 가져오기 위한 설정
NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)  # 상위 폴더 경로 (Package 폴더)
sys.path.append(PACKAGE_PATH)

from CrawlerModule import CrawlerModule  # 상위 폴더에서 CrawlerModule 가져오기

import pandas as pd
import time
from datetime import datetime, timedelta
import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
from user_agent import generate_navigator


class NaverBlogCrawler(CrawlerModule):
    def __init__(self, print_status_option=False):
        super().__init__()
        self.print_status_option = print_status_option

    def _blogURLChecker(self, url):
        """Check if a given URL is a valid Naver Blog URL."""
        pattern = r"^https://blog\.naver\.com/[^/]+/\d+$"
        return re.match(pattern, url) is not None
    
    def extract_blogurls(self, text):
                """Extract blog URLs from the HTML response."""
                pattern = r'https://blog\.naver\.com/[a-zA-Z0-9_-]+/\d+'
                urls = re.findall(pattern, text)
                return list(set(urls))

    def extract_nexturl(self, text):
        """Extract next page URL from the HTML response."""
        pattern = r'https://s\.search\.naver\.com/p/review[^"]*'
        match = re.search(pattern, text)
        return match.group(0) if match else None
    
    def extract_date_time(self, text):
        # 오늘과 어제 날짜를 yyyy-mm-dd 형식으로 생성
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 정규식 패턴 정의
        patterns = [
            (r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{1,2}):(\d{2})', "%Y-%m-%d", "%H:%M"),  # 2024. 9. 19. 9:02
            (r'(\d{1,2})시간 전', None, "%H:00"),  # n시간 전 (분을 00으로 설정)
            (r'(\d{1,2})분 전', None, "%H:%M"),  # n분 전
        ]
        
        extracted_date = None
        extracted_time = None
        
        for pattern, date_format, time_format in patterns:
            match = re.search(pattern, text)
            if match:
                if "시간 전" in text:
                    # n시간 전 형식 처리 (분을 00으로 설정)
                    hours_ago = int(match.group(1))
                    time_delta = datetime.now() - timedelta(hours=hours_ago)
                    extracted_time = time_delta.strftime("%H:00")  # 분을 '00'으로 설정
                    extracted_date = time_delta.strftime("%Y-%m-%d")
                elif "분 전" in text:
                    # n분 전 형식 처리
                    minutes_ago = int(match.group(1))
                    time_delta = datetime.now() - timedelta(minutes=minutes_ago)
                    extracted_time = time_delta.strftime("%H:%M")  # 현재 시간에서 분을 뺀 후 시간 추출
                    extracted_date = time_delta.strftime("%Y-%m-%d")
                elif date_format and time_format:
                    # 날짜와 시간 모두 있는 경우
                    year, month, day, hour, minute = map(int, match.groups())
                    extracted_date = f"{year:04d}-{month:02d}-{day:02d}"
                    extracted_time = f"{hour:02d}:{minute:02d}"
                break

        return extracted_date, extracted_time

    def urlCollector(self, keyword, startDate, endDate):
        """Collect URLs of Naver blogs based on a keyword and date range."""
        try:
            if not isinstance(keyword, str):
                return self.error_dump(2011, 'Check Keyword', keyword)
            datetime.strptime(str(startDate), '%Y%m%d')
            datetime.strptime(str(endDate), '%Y%m%d')
        except:
            return self.error_dump(2012, 'Check DateForm', startDate)

        try:
            urlList = []
            keyword = requests.utils.quote(keyword)
            api_url = f"https://s.search.naver.com/p/review/48/search.naver?ssc=tab.blog.all&api_type=8&query={keyword}&start=1&ac=0&aq=0&spq=0&sm=tab_opt&nso=so%3Add%2Cp%3Afrom{startDate}to{endDate}&prank=30&ngn_country=KR&lgl_rcode=15200104&fgn_region=&fgn_city=&lgl_lat=36.7512&lgl_long=126.9629&abt=&retry_count=0"

            # Requester_get 메서드 사용 (GET 요청)
            response = self.Requester_get(api_url)
            if not self.RequesterChecker(response):
                return response
            json_text = response.text
            while True:
                pre_urlList = self.extract_blogurls(json_text)
                for url in pre_urlList:
                    if url not in urlList and 'book' not in url:
                        urlList.append(url)
                        self.IntegratedDB['UrlCnt'] += 1

                nextUrl = self.extract_nexturl(json_text)
                if nextUrl is None:
                    break
                else:
                    response = self.Requester_get(nextUrl)
                    json_text = response.text

            return {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
        except Exception:
            error_msg = self.error_detector()  # 인자 없이 호출
            return self.error_dump(2013, error_msg, api_url)

    def articleCollector(self, blogURL, speed):
        """Collect blog article content from a given URL."""
        if not isinstance(blogURL, str) or not self._blogURLChecker(blogURL):
            return self.error_dump(2014, "Check blogURL", blogURL)

        try:
            split_url = blogURL.split("/")
            blogID = split_url[3]
            logNo = split_url[4]
            url = f"https://blog.naver.com/PostView.naver?blogId={blogID}&logNo={logNo}&redirect=Dlog&widgetTypeCall=true&noTrackingCode=true&directAccess=false"

            headers = {
                'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                "referer": blogURL
            }

            # Requester_get 메서드 사용 (GET 요청)
            response = self.Requester_get(url, headers=headers)
            time.sleep(speed)
            if not self.RequesterChecker(response):
                return response

            soup = BeautifulSoup(response.text, "html.parser")
            article = "".join([i.text.replace("\n", "").replace("\t", "").replace("\u200b", "") for i in soup.select("div[class='se-module se-module-text']")])
            rawdate = "".join([i.text for i in soup.select("span[class='se_publishDate pcol2']")])

            date, arttime = self.extract_date_time(rawdate)

            if not article:
                article = "".join([i.text.replace("\n", "").replace("\t", "").replace("\u200b", "") for i in soup.select("div[class='se_textarea']")])

            articleData = [blogID, blogURL, article, date, arttime]


            self.IntegratedDB['TotalArticleCnt'] += 1
            if self.print_status_option:
                self.printStatus('NaverBlog', 3, self.PrintData)

            return {'articleData': articleData}
        except Exception:
            error_msg = self.error_detector()
            return self.error_dump(2015, error_msg, blogURL)

    def replyCollector(self, blogURL, speed):
        """Collect replies (comments) from a blog post."""
        if not isinstance(blogURL, str) or not self._blogURLChecker(blogURL):
            return self.error_dump(2016, "Check blogURL", blogURL)

        try:
            split_url = blogURL.split("/")
            blogID = split_url[3]
            logNo = split_url[4]
            url = f"https://blog.naver.com/PostView.naver?blogId={blogID}&logNo={logNo}&redirect=Dlog&widgetTypeCall=false&directAccess=false"

            returnData = {
                'replyList': [],
                'replyCnt': 0
            }

            # Requester_get 메서드 사용 (GET 요청)
            response = self.Requester_get(url)
            time.sleep(speed)
            if not self.RequesterChecker(response):
                return response

            try:
                soup = BeautifulSoup(response.text, "html.parser")
                script_tag = soup.find('script', string=re.compile(r'var\s+blogNo\s*=\s*\'(\d+)\''))
                blogNo = re.search(r'var\s+blogNo\s*=\s* \'(\d+)\'', script_tag.text).group(1)
            except:
                return returnData
            
            objectID = f'{blogNo}_201_{logNo}'

            page = 1
            nickname_list, replyDate_list, text_list, rere_count_list = [], [], [], []
            replyList, r_like_list, r_bad_list, parentCommentNo_list = [], [], [], []

            headers = {
                'user-agent': generate_navigator()['user_agent'],
                'referer': url
            }

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
                    'page': str(page),
                }

                # Requester_get 메서드 사용 (GET 요청)
                response = self.Requester_get('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', headers, params)
                time.sleep(speed)
                if not self.RequesterChecker(response):
                    return response
                if '"message":"댓글을 허용하지 않는 포스트 입니다."' in response.text:
                    return returnData
                temp = json.loads(response.text)
                for comment_json in temp.get("result", {}).get("commentList", []):
                    parentCommentNo_list.append(comment_json["parentCommentNo"])

                df = pd.DataFrame(temp['result']['commentList'])

                if df.empty:
                    return returnData

                nickname_list.extend(df['maskedUserId'])
                replyDate_list.extend(df['modTime'])
                text_list.extend(df['contents'])
                rere_count_list.extend(df['replyCount'])
                r_like_list.extend(df['sympathyCount'])
                r_bad_list.extend(df['antipathyCount'])

                self.IntegratedDB['TotalReplyCnt'] += len(df)
                self.IntegratedDB['TotalRereplyCnt'] += len(df)

                if len(df) < 97:
                    break
                page += 1

            # Process each comment
            reply_idx = 1
            for i in range(len(nickname_list)):

                if text_list[i]:
                    replyList.append([
                        reply_idx,
                        nickname_list[i],
                        datetime.strptime(replyDate_list[i], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                        datetime.strptime(replyDate_list[i], "%Y-%m-%dT%H:%M:%S%z").strftime("%H:%M"),
                        text_list[i].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', ''),
                        blogURL
                    ])
                    reply_idx += 1

            returnData['replyList'] = replyList
            returnData['replyCnt'] = len(replyList)

            return returnData

        except Exception as e:
            error_msg = self.error_detector()
            return self.error_dump(2017, error_msg, blogURL)

    def RealTimeurlCollector(self, keyword, checkPage, previous_urls, speed):
        try:
            urlList = []
            self.lastpage = False
            keyword = keyword.replace('&', '%26').replace('+', '%2B').replace('"', '%22').replace('|', '%7C').replace(' ', '+')
            search_page_url = f"https://s.search.naver.com/p/review/48/search.naver?ssc=tab.blog.all&api_type=8&query={keyword}&start=1&ac=0&aq=0&spq=0&sm=tab_opt&nso=so:dd,p:all&prank=30&ngn_country=KR&lgl_rcode=15200104&fgn_region=&fgn_city=&lgl_lat=36.7512&lgl_long=126.9629&abt=&retry_count=0"

            response = self.Requester_get(search_page_url)
            time.sleep(speed)
            if self.RequesterChecker(response) == False:
                return response
            json_text = response.text
            
            pre_urlList = self.extract_blogurls(json_text)

            for url in pre_urlList:
                if url not in urlList and 'book' not in url:
                    urlList.append(url)
                    self.IntegratedDB['UrlCnt'] += 1
                    
            if checkPage >= 2:
                for i in range(checkPage-1):
                    if self.lastpage == True:
                        break
                    nextUrl = self.extract_nexturl(json_text)
                    if nextUrl == None:
                        break
                    
                    else:
                        api_url = nextUrl
                        response = self.Requester_get(api_url)
                        time.sleep(speed)
                        json_text = response.text
                        pre_urlList = self.extract_blogurls(json_text)

                        for url in pre_urlList:
                            if url not in urlList and 'book' not in url:
                                urlList.append(url)
                                self.IntegratedDB['UrlCnt'] += 1
                                
                        for url in pre_urlList:
                            if url in previous_urls:
                                self.lastpage = True
                                break
            
            elif checkPage == 1:
                pass
            
            elif checkPage == 0:
                for url in pre_urlList:
                    if url in previous_urls:
                        self.lastpage = True
                        break
                while self.lastpage == False:
                    nextUrl = self.extract_nexturl(json_text)
                    if nextUrl == None:
                        break
                    
                    else:
                        api_url = nextUrl
                        response = self.Requester_get(api_url)
                        time.sleep(speed)
                        json_text = response.text
                        
                        pre_urlList = self.extract_blogurls(json_text)

                        for url in pre_urlList:
                            if url not in urlList and 'book' not in url:
                                urlList.append(url)
                                self.IntegratedDB['UrlCnt'] += 1
                                
                        for url in pre_urlList:
                            if url in previous_urls:
                                self.lastpage = True
                                break

            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData

        except Exception as e:
            error_msg = self.error_detector(self.error_detector_option)
            return self.error_dump(2020, error_msg, search_page_url)


if __name__ == "__main__":
    # 테스트 코드
    print("hello")
