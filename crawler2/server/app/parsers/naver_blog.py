import time
import json
import re
import warnings
from datetime import datetime, timedelta, timezone
import urllib3
from bs4 import BeautifulSoup
from user_agent import generate_navigator
import urllib.parse
import random
import logging
from db import load_proxy_list, checkStatus, get_userinfo
from db.util import makeDBname 
from config import SLEEP_TIME, PROXY
from common.req import Request, set_proxy_list
from common.naver_lib import parse_naver_query
from common.storage import makeDB, updateCrawlStatus, initCrawlLog, appendCrawlLog
from common.csv import makeCSV, addToCSV
from common.columns import naverblog_article_column, naverblog_reply_column
from common.controller import stopOperator, finishOperator

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

class NaverBlogCrawler:
    
    def __init__(self, requester, keyword, startDate, endDate, option, speed):
        
        if PROXY:
            proxy_list = load_proxy_list()
            set_proxy_list(proxy_list)
        
        self.DBname = makeDBname('naverblog', keyword, startDate, endDate)
        self.requester = requester
        self.keyword = keyword
        self.startDate = startDate
        self.endDate = endDate
        self.option = option
        self.speed = speed
        
        self.articleDB = self.DBname + '_article'
        self.replyDB = self.DBname + '_reply'
        
        self.startTime = time.time()
        
        self.startDate_form = datetime.strptime(startDate, '%Y%m%d').date()
        self.endDate_form = datetime.strptime(endDate, '%Y%m%d').date()

        self.currentDate = self.startDate_form
        self.date_range = (self.endDate_form - self.startDate_form).days + 1
        self.deltaD = timedelta(days=1)

        notification = get_userinfo(self.requester)
        if not notification:
            raise ValueError(f"사용자 정보를 찾을 수 없습니다: {self.requester}")
        self.Email = notification['Email']
        self.PushoverKey = notification['PushOver']
        self.requesterUid = notification['userUid']
        
        self.running = True
        self.DBuid = None
        self.status = {
            'percentage': '0',
            'currentdate': self.currentDate.strftime('%Y-%m-%d'),
            'urlCnt': 0,
            'articleCnt': 0,
            'commentCnt': 0,
            'replyCnt': 0,
        }
        
        self.DBPath, self.DBuid = makeDB(
            DBname=self.DBname,
            DBtype='naverblog',
            startdate=self.startDate,
            enddate=self.endDate,
            option=self.option,
            keyword=self.keyword,
            requester=self.requester,
            requesterUid=self.requesterUid
        )
                    
        
    def collectUrl(self, keyword, startDate, endDate):
        try:
            def extractUrl(text):
                # 정규식 패턴 정의 (조금 더 일반화된 형태로)
                pattern = r'https://blog\.naver\.com/[a-zA-Z0-9_-]+/\d+'

                # 정규식으로 모든 매칭되는 패턴 찾기
                urls = re.findall(pattern, text)
                urls = list(dict.fromkeys(urls))

                return urls

            def extractNextAPI(text):
                try:
                    json_data = json.loads(text)
                    if 'url' in json_data and json_data['url']:
                        return json_data['url']
                    else:
                        return None
                except Exception as e:
                    logger.info(f"Error occurred while extracting next URL: {e}")
                    return None

            def extractAPI(html_text):
                pattern = r'url:\s*"(https://s\.search\.naver\.com/p/review/50/search\.naver\?[^"]+)"'
                match = re.search(pattern, html_text)
                if match:
                    return match.group(1)
                return None

            query_dict = parse_naver_query(keyword)
            urlList = []

            # 1단계: 상세검색(날짜 범위 + nx 쿼리 파라미터) 조건으로 최초 검색 페이지 요청 후 API URL 추출
            search_params = {
                "ssc": "tab.blog.all",
                "query": keyword,
                "query_original": f"{keyword}",
                "sm": "tab_opt",
                "nso": f"so:r,p:from{startDate}to{endDate}",
                "nx_and_query": f"{query_dict['nx_and_query']}",
                "nx_search_hlquery": f"{query_dict['nx_search_hlquery']}",
                "nx_search_query": f"{query_dict['nx_search_query']}",
                "nx_sub_query":f"{query_dict['nx_sub_query']}",
                "qdt": "1",
            }
            search_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            search_response = Request("https://search.naver.com/search.naver", params=search_params, headers=search_headers)
            search_response.raise_for_status()
            html_text = search_response.text

            # 1단계 HTML에서 블로그 URL 수집
            for url in extractUrl(html_text):
                if url not in urlList and 'book' not in url:
                    urlList.append(url)
                    self.status['urlCnt'] += 1

            api_url = extractAPI(html_text)
            if api_url is None:
                logger.info(f"No API URL found in search page HTML for keyword: {keyword}, date: {startDate}~{endDate}")
                return urlList

            # 2단계: 추출된 API로 요청 (기존 방식 유지)
            response = Request(api_url)
            response.raise_for_status()
            json_text = response.text
            
            while True:
                if self.running == False: break
                
                pre_urlList = extractUrl(json_text)
                if not pre_urlList:
                    time.sleep(SLEEP_TIME)
                    
                for url in pre_urlList:
                    if url not in urlList and 'book' not in url:
                        urlList.append(url)
                        self.status['urlCnt'] += 1

                nextUrl = extractNextAPI(json_text)
                if nextUrl is None:
                    break
                else:
                    time.sleep(SLEEP_TIME)
                    api_url = nextUrl
                    response = Request(api_url)
                    response.raise_for_status()
                    json_text = response.text

            return urlList
        except Exception as e:
            logger.info(f"Error occurred while collecting news URLs: {e}")
            appendCrawlLog(self.DBuid, "error", f"URL 수집 실패 ({keyword}): {e}")
            return []

    def collectArticle(self, blogURL):
        try:
            split_url = blogURL.split("/")
            blogID    = split_url[3]
            logNo     = split_url[4]

            url = "https://blog.naver.com/PostView.naver?blogId={}&logNo={}&redirect=Dlog&widgetTypeCall=true&noTrackingCode=true&directAccess=false".format(blogID, logNo)
            headers = {
                'User-Agent': generate_navigator()['user_agent'],
                "referer" : blogURL
            }

            res = Request(url, headers=headers)
            res.raise_for_status()
            res = res.text
            bs = BeautifulSoup(res, "html.parser")

            try:
                article = "".join([i.text.replace("\n", "").replace("\t", "").replace("\u200b", "") for i in bs.select("div[class = 'se-module se-module-text']")])
                date = "".join([i.text for i in bs.select("span[class = 'se_publishDate pcol2']")])
                date_only = re.match(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", date)
                if date_only:
                    year, month, day = date_only.groups()
                    month = month.zfill(2)
                    day = day.zfill(2)
                    date = f"{year}-{month}-{day}"
                if article == "":
                    return []

                articleData = [blogID, blogURL, article, date]
            except Exception as e:
                logger.info(f"Error occurred while extracting article data: {e}")
                articleData = []

            return articleData

        except Exception as e:
            logger.info(f"Error occurred while collecting article data: {e}")
            appendCrawlLog(self.DBuid, "error", f"본문 수집 실패 ({blogURL}): {e}")
            return []

    def collectCmt(self, blogURL, username=False):
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
                if self.running == False: break

                try:
                    res = Request(url)
                    res.raise_for_status()
                    res = res.text
                    bs = BeautifulSoup(res, "html.parser")
                except Exception as e:
                    logger.info(f"Request failed (attempt {trynum}): {e}")
                    trynum += 1
                    if trynum >= 5:
                        return returnData
                    continue

                script_tag = bs.find('script', string=re.compile(r'var\s+blogNo\s*=\s*\'(\d+)\''))  # type: ignore[arg-type]
                match = re.search(r'var\s+blogNo\s*=\s*\'(\d+)\'', script_tag.text if script_tag else '')
                if match:
                    blogNo = match.group(1)
                    break
                else:
                    return returnData
                
            objectID   = f'{blogNo}_201_{logNo}'
            
            page       = 1
            PAGE_SIZE  = 50

            all_comments = []
            replyList    = []

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
                            'pageSize': str(PAGE_SIZE),
                            'indexSize': '10',
                            'page': str(page),
                            'morePage.prev': '051v2o4l34sgr1t0txuehz9fxg',
                            'morePage.next': '051sz9hwab3fe1t0w1916s34yt',
                        }

                res = Request('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', headers=headers, params=params)
                res.raise_for_status()
                res = res.text
                temp = json.loads(res)

                try:
                    comments = temp.get('result', {}).get('commentList', [])
                except Exception as e:
                    logger.info(f"Error occurred while parsing comment list: {e}")
                    return returnData

                all_comments.extend(comments)

                if len(comments) < PAGE_SIZE:
                    break

                page += 1

            # comment_list PART
            reply_idx = 1
            for c in all_comments:
                contents = c.get('contents', '')
                if not contents or c.get('deleted', False) or c.get('secret', False):
                    continue

                masked_user_id   = c.get('maskedUserId') or ''
                mod_time         = c.get('modTime', '')
                reply_count      = c.get('replyCount', 0)
                sympathy_count   = c.get('sympathyCount', 0)
                antipathy_count  = c.get('antipathyCount', 0)
                reply_level      = c.get('replyLevel', 1)
                parent_comment_no = c.get('parentCommentNo', '')

                r_per_like = 0.0
                r_sum = int(sympathy_count) + int(antipathy_count)
                if r_sum != 0:
                    r_per_like = float(format(int(sympathy_count) / r_sum, ".2f"))

                if r_per_like > 0.5:
                    r_sentiment = 1
                elif r_per_like == 0:
                    r_sentiment = 2
                elif r_per_like < 0.5:
                    r_sentiment = -1
                else:
                    r_sentiment = 0

                targetlist = [
                    str(reply_idx),
                    str(masked_user_id),
                    datetime.strptime(mod_time, "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                    contents.replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', ''),
                    str(reply_level),
                    str(reply_count),
                    str(sympathy_count),
                    str(antipathy_count),
                    str(r_per_like),
                    str(r_sentiment),
                    str(blogURL),
                    parent_comment_no
                ]
                replyList.append(targetlist)
                reply_idx += 1

            returnData['replyList'] = replyList
            returnData['replyCnt'] = len(replyList)

            return returnData

        except Exception as e:
            logger.info(f"Error occurred while collecting comment data: {e}")
            appendCrawlLog(self.DBuid, "error", f"댓글 수집 실패 ({blogURL}): {e}")
            return returnData
    
    def reportStatus(self):
        return self.status
    
    def main(self):
        initCrawlLog(self.DBuid, (
            f"User: {self.requester}\n"
            f"Object: naverblog\n"
            f"Option: {self.option}\n"
            f"Keyword: {self.keyword}\n"
            f"Date Range: {self.startDate} ~ {self.endDate}"
        ))

        makeCSV(self.DBPath, self.articleDB, naverblog_article_column)

        if self.option in [1]:
            makeCSV(self.DBPath, self.replyDB, naverblog_reply_column)
        
        for dayCount in range(self.date_range + 1):
            currentDate_str = self.currentDate.strftime('%Y%m%d')
            
            if checkStatus(self.DBuid) == False:
                self.running = False
            
            if self.running == False: #DB 외 경로로 중단 신호 오는 것 고려해 checkDB와 분리, self.status 업데이트 전 중단
                stopOperator(DBpath=self.DBPath, DBtype='naverblog', DBname=self.DBname, startTime=self.startTime, pushoverKey=self.PushoverKey, userEmail=self.Email, status=self.status, DBuid=self.DBuid)
                break

            if dayCount == self.date_range: # 토큰화 및 파일 저장, 알림
                finishOperator(DBpath=self.DBPath, DBtype='naverblog', DBname=self.DBname, startTime=self.startTime, pushoverKey=self.PushoverKey, userEmail=self.Email, status=self.status, DBuid=self.DBuid)
                break
            
            if self.date_range > 0:
                percent = str(round(((dayCount + 1) / self.date_range) * 100, 1))
                self.status['percentage'] = percent
                self.status['currentdate'] = currentDate_str
            
            urlList = self.collectUrl(
                keyword=self.keyword,
                startDate=currentDate_str,
                endDate=currentDate_str
            )
            
            for blogUrl in urlList:
                try:
                    if self.running == False: break
                    # 기사 본문 수집
                    articleData = self.collectArticle(blogUrl)
                    if not articleData:
                        continue
                    else:
                        self.status['articleCnt'] += 1
                        
                    # 기사 날짜 저장 (댓글 행의 마지막 컬럼인 'Article Day'용)
                    article_day = articleData[3] 

                    # 옵션 2: 기사만 수집 (댓글수 0으로 기록)
                    if self.option == 2:
                        addToCSV(self.DBPath, self.articleDB, [articleData + [0]], naverblog_article_column)
                    
                    # 옵션 1: 댓글 포함
                    
                    elif self.option in [1, 4]:
                        try:
                            # 댓글 수집 (옵션 4일 때만 유저 정보 포함)
                            is_username = True if self.option == 4 else False
                            cmtData = self.collectCmt(blogUrl, username=is_username)

                            reply_cnt = cmtData.get('replyCnt', 0)
                            self.status['commentCnt'] += reply_cnt

                            # 기사 저장 (실제 댓글수 포함)
                            addToCSV(self.DBPath, self.articleDB, [articleData + [reply_cnt]], naverblog_article_column)

                            # 댓글 리스트 저장
                            replies = cmtData.get('replyList', [])
                            if replies:
                                processed_replies = [r + [article_day] for r in replies]
                                current_reply_col = naverblog_reply_column
                                addToCSV(self.DBPath, self.replyDB, processed_replies, current_reply_col)

                        except Exception as e:
                            logger.info(f"Error occurred while processing comment data for {blogUrl}: {e}")
                        
                        
                    time.sleep(SLEEP_TIME)

                except Exception as e:
                    logger.info(f"Error occurred while processing {blogUrl}: {e}")
                    appendCrawlLog(self.DBuid, "error", f"블로그 처리 실패 ({blogUrl}): {e}")
                    continue
            
            # 날짜 단위 진행률을 DB에 직접 업데이트
            updateCrawlStatus(
                self.DBuid,
                self.status['percentage'] + "%",
                self.status['articleCnt'],
                self.status['commentCnt'],
                self.status['replyCnt'],
            )

            self.currentDate += self.deltaD
            
def controller():
    option_dic = {
        1: "\n1. 기사 + 댓글\n2. 기사 + 댓글/대댓글\n3. 기사\n4. 기사 + 댓글(추가정보)\n",
        2: "\n1. 블로그 본문\n2. 블로그 본문 + 댓글/대댓글\n",
        3: "\n1. 카페 본문\n2. 카페 본문 + 댓글/대댓글\n",
        4: "\n1. 영상 정보 + 댓글/대댓글 (100개 제한)\n2. 영상 정보 + 댓글/대댓글(무제한)\n",
        5: "\n1. 기사\n",
        6: "\n1. 기사\n2. 기사 + 댓글\n"
    }
    print("================ Crawler Controller ================")
    name = input("본인의 이름을 입력하세요: ")

    print("\n[ 크롤링 대상 ]\n")
    print("1. Naver News\n2. Naver Blog\n3. Naver Cafe\n4. YouTube\n5. ChinaDaily\n6. ChinaSina")

    while True:
        control_ask = int(input("\n입력: "))
        if control_ask in [1, 2, 3, 4, 5, 6]:
            break
        else:
            print("다시 입력하세요")

    startDate = input("\nStart Date (ex: 20230101): ")
    endDate = input("End Date (ex: 20231231): ")
    keyword = input("\nKeyword: ")

    print(option_dic[control_ask])

    while True:
        option = int(input("Option: "))
        if option in [1, 2, 3, 4]:
            break
        else:
            print("다시 입력하세요")

    speed = input("\n속도를 입력하십시오(1~10):  ")
    
    NaverBlogCrawler_obj = NaverBlogCrawler(name, keyword, startDate, endDate, option, speed)
    NaverBlogCrawler_obj.main()
        
def tester(name= '최우철', startDate = str(20260301), endDate = str(20260305), keyword = '경찰대', option = 1, speed = 1):
    NaverBlogCrawler_obj = NaverBlogCrawler(name, keyword, startDate, endDate, option, speed)
    NaverBlogCrawler_obj.main()

if __name__ == "__main__":
    controller()