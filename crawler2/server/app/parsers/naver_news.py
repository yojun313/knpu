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
from db import load_proxy_list, checkDB, get_userinfo
from db.util import makeDBname 
from config import SLEEP_TIME, PROXY
from common.req import Request, set_proxy_list
from common.naver_lib import parse_naver_query
from common.storage import makeDB, updateCrawlStatus
from common.csv import makeCSV, addToCSV
from common.columns import navernews_article_column, navernews_statistics_column, navernews_reply_column, navernews_rereply_column, navernews_4_reply_column
from common.controller import stopOperator, finishOperator

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)

class NaverNewsCrawler:
    
    def __init__(self, requester, keyword, startDate, endDate, option, speed):
        
        if PROXY:
            proxy_list = load_proxy_list()
            set_proxy_list(proxy_list)
        
        self.DBname = makeDBname('navernews', keyword, startDate, endDate)
        self.requester = requester
        self.keyword = keyword
        self.startDate = startDate
        self.endDate = endDate
        self.option = option
        self.speed = speed
        
        self.articleDB = self.DBname + '_article'
        self.statisticsDB = self.DBname + '_statistics'
        self.replyDB = self.DBname + '_reply'
        self.rereplyDB = self.DBname + '_rereply'
        
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
        self.status = {
            'percentage': '0',
            'currentdate': self.currentDate.strftime('%Y-%m-%d'),
            'urlCnt': 0,
            'articleCnt': 0,
            'commentCnt': 0,
            'replyCnt': 0,
        }
                    
        
    def collectUrl(self, keyword, startDate, endDate): 
        try:
            startDate_formed = datetime.strptime(str(startDate), '%Y%m%d').date().strftime('%Y.%m.%d')
            endDate_formed = datetime.strptime(str(endDate), '%Y%m%d').date().strftime('%Y.%m.%d')
        
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
                except Exception as e:
                    logger.info(f"Error occurred while extracting next URL: {e}")
                    return None

            query_dict = parse_naver_query(keyword)

            urlList = []
            params = {
                "abt": "null",
                "cluster_rank": str(random.choice([63, 64, 65])),
                "de": endDate_formed,
                "ds": startDate_formed,
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
                "nx_sub_query":f"{query_dict['nx_sub_query']}",
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
                "start": "1"  
            }
                        
            # 파라미터를 쿼리 문자열로 변환
            query_string = urllib.parse.urlencode(params)

            # API URL 생성
            api_url = f"https://s.search.naver.com/p/newssearch/3/api/tab/more?{query_string}"

            # 요청 보내기
            response = Request(api_url)
            response.raise_for_status()
            json_text = response.text
            
            while True:
                if self.running == False: break
                
                pre_urlList = extract_newsurls(json_text)
                if not pre_urlList:
                    time.sleep(SLEEP_TIME)
                    
                for url in pre_urlList:
                    if url not in urlList and 'sid=106' not in url:
                        urlList.append(url)
                        self.status['urlCnt'] += 1

                nextUrl = extract_nexturl(json_text)
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
            return []

    def collectArticle(self, newsURL):        
        try:
            res = Request(newsURL)
            res.raise_for_status()
            res = res.text 
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
            except Exception as e:
                logger.info(f"Error occurred while extracting article data: {e}")
                articleData = []

            return articleData

        except Exception as e:
            logger.info(f"Error occurred while collecting article data: {e}")
            return []

    def collectCmt(self, newsURL, username=False):
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
                
                if self.running == False: break
                
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
                res = Request('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', headers=headers, params=params)
                res.raise_for_status()
                res = res.text
                
                try:
                    res = res.replace("_callback(", "")[:-2]
                    temp              = json.loads(res)
                except:
                    return returnData

                # parentCommentNo_list PART
                for comment_json in temp.get("result", {}).get("commentList", []):
                    parentCommentNo_list.append(comment_json["parentCommentNo"])
                
                try:
                    comments = temp.get('result', {}).get('commentList', [])
                    masked_user_ids  = [c['maskedUserId'] for c in comments]
                    mod_times        = [c['modTime'] for c in comments]
                    contents         = [c['contents'] for c in comments]
                    reply_counts     = [c['replyCount'] for c in comments]
                    sympathy_counts  = [c['sympathyCount'] for c in comments]
                    antipathy_counts = [c['antipathyCount'] for c in comments]
                except:
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

            returnParentCommentNo_list = []
            for i in range(len(parentCommentNo_list)):
                if rere_count_list[i] > 0:
                    returnParentCommentNo_list.append(parentCommentNo_list[i])

            reply_idx = 1
            for i in range(len(nickname_list)):
                r_per_like = 0.0
                r_sum_like_angry = int(r_like_list[i]) + int(r_bad_list[i])
                if r_sum_like_angry != 0:
                    r_per_like = float(int(r_like_list[i]) / r_sum_like_angry)
                    r_per_like = float(format(r_per_like, ".2f"))

                if r_per_like > 0.5:
                    r_sentiment = 1
                elif r_per_like == 0:
                    r_sentiment = 2
                elif r_per_like < 0.5:
                    r_sentiment = -1
                else:
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

                    if username:
                        add_data = self.collectUsername(oid, aid, parentCommentNo_list[i], newsURL)
                        if add_data:
                            targetlist[1] = f"{targetlist[1]}_{add_data[0]}_{add_data[1]}"
                            targetlist.extend(add_data[1:])

                    replyList.append(targetlist)
                    reply_idx += 1


            returnData['replyList'] = replyList
            returnData['parentCommentNo_list'] = returnParentCommentNo_list
            returnData['statisticsData'] = statistics_data
            returnData['replyCnt'] = len(replyList)

            return returnData

        except Exception as e:
            logger.info(f"Error occurred while collecting comment data: {e}")
            return returnData

    def collectUsername(self, oid, aid, commentNo, newsURL):
        try:
            url = "https://apis.naver.com/commentBox/cbox/web_naver_user_info_jsonp.json"
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

            headers = {"User-agent": generate_navigator()['user_agent'], "referer": newsURL}

            response = Request(url, params=params, headers=headers)
            response.raise_for_status()

            res_text = response.text
            json_str = res_text[res_text.find("(") + 1 : res_text.rfind(")")]
            data = json.loads(json_str)

            nickname = data['result']['user']['nickname']
            stats = data['result']['commentUserStats']
            commentCnt = stats['commentCount']
            replyCnt = stats['replyCount']
            likecnt = stats['sympathyCount']

            return [nickname, commentCnt, replyCnt, likecnt]
        except Exception as e:
            logger.info(f"collectUsername 실패 (commentNo: {commentNo}): {e}")
            return None

    def collectReply(self, newsURL, parentCommentNum_list):        
        try:
            oid  = newsURL[39:42]
            aid  = newsURL[43:53]
            headers = {"User-agent": generate_navigator()['user_agent'], "referer": newsURL}  
            
            base_url = (
                "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=news"
                "&pool=cbox5&lang=ko&country=KR"
                "&objectId=news{}%2C{}&categoryId=&pageSize={}&indexSize=10&groupId=&listType=OBJECT&pageType=more"
                "&page={}&initialize=true&followSize=5&userType=&useAltSort=true&replyPageSize=20&sort={}&includeAllStatus=true&_=1696730082374"
            )
            
            nickname_list       = []
            rereplyDate_list    = []
            text_list           = []
            r_like_list         = []
            r_bad_list          = []
            rereplyList        = []
            parentReplynum_list = []
            
            returnData = {
                'rereplyList': rereplyList,
                'rereplyCnt': len(rereplyList)
            }
            
            for i in range(len(parentCommentNum_list)):
                try:
                    if self.running == False: break
                    
                    target_url = (base_url.format(oid, aid, 100, 1, "reply") + "&parentCommentNo=" + parentCommentNum_list[i])
                    
                    response = Request(target_url, headers=headers)
                    response.raise_for_status()
                    
                    res_text = response.text
                    json_str = res_text[res_text.find("(") + 1 : res_text.rfind(")")]
                    temp = json.loads(json_str)    
                    
                    comment_data = temp.get('result', {}).get('commentList', [])
                    if not comment_data:
                        continue

                    try:
                        masked_user_ids  = [c['maskedUserId'] for c in comment_data]
                        mod_times        = [c['modTime'] for c in comment_data]
                        contents         = [c['contents'] for c in comment_data]
                        sympathy_counts  = [c['sympathyCount'] for c in comment_data]
                        antipathy_counts = [c['antipathyCount'] for c in comment_data]
                    except:
                        continue

                    nickname_list.extend(masked_user_ids)
                    rereplyDate_list.extend(mod_times)
                    text_list.extend(contents)
                    r_like_list.extend(sympathy_counts)
                    r_bad_list.extend(antipathy_counts)
                    parentReplynum_list.extend([parentCommentNum_list[i]] * len(masked_user_ids))     

                except Exception as e:
                    logger.info(f"Error occurred while collecting reply data: {e}")
                    continue
            
            for i in range(len(nickname_list)):
                r_per_like = 0.0
                r_sum_like_angry = int(r_like_list[i]) + int(r_bad_list[i])
                if r_sum_like_angry != 0:
                    r_per_like = float(int(r_like_list[i]) / r_sum_like_angry)
                    r_per_like = float(format(r_per_like, ".2f"))

                if r_per_like > 0.5:
                    r_sentiment = 1
                elif r_per_like == 0:
                    r_sentiment = 2
                elif r_per_like < 0.5:
                    r_sentiment = -1
                else:
                    r_sentiment = 0

                if text_list[i] != '':
                    rereplyList.append([
                        parentReplynum_list[i],
                        str(nickname_list[i]),
                        datetime.strptime(rereplyDate_list[i], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                        str(text_list[i].replace("\n", " ").replace("\r", " ").replace("\t", " ").replace('<br>', '')),
                        str(r_like_list[i]),
                        str(r_bad_list[i]),
                        str(r_per_like),
                        str(r_sentiment),
                        str(newsURL)
                    ])
            
            returnData['rereplyList'] = rereplyList
            returnData['rereplyCnt'] = len(rereplyList)
            return returnData
        
        except Exception as e:
            logger.info(f"Error occurred while collecting reply data: {e}")
            return returnData
    
    def reportStatus(self):
        return self.status
    
    def main(self):
        self.DBPath, self.DBuid = makeDB(
            DBname=self.DBname,
            DBtype='navernews',
            startdate=self.startDate,
            enddate=self.endDate,
            option=self.option,
            keyword=self.keyword,
            requester=self.requester,
            requesterUid=self.requesterUid
        )

        makeCSV(self.DBPath, self.articleDB, navernews_article_column)

        if self.option in [1, 2, 4]:
            makeCSV(self.DBPath, self.statisticsDB, navernews_statistics_column)
            if self.option == 4:
                makeCSV(self.DBPath, self.replyDB, navernews_4_reply_column)
            else:
                makeCSV(self.DBPath, self.replyDB, navernews_reply_column)
            if self.option == 2:
                makeCSV(self.DBPath, self.rereplyDB, navernews_rereply_column)
        
        for dayCount in range(self.date_range + 1):
            currentDate_str = self.currentDate.strftime('%Y%m%d')
            
            if checkDB(self.DBuid) == False:
                self.running = False
            
            if self.running == False: #DB 외 경로로 중단 신호 오는 것 고려해 checkDB와 분리, self.status 업데이트 전 중단
                stopOperator(DBpath=self.DBPath, DBtype='navernews', DBname=self.DBname, startTime=self.startTime, pushoverKey=self.PushoverKey, userEmail=self.Email, status=self.status, DBuid=self.DBuid)
                break

            if dayCount == self.date_range: # 토큰화 및 파일 저장, 알림
                finishOperator(DBpath=self.DBPath, DBtype='navernews', DBname=self.DBname, startTime=self.startTime, pushoverKey=self.PushoverKey, userEmail=self.Email, status=self.status, DBuid=self.DBuid)
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
            
            for newsUrl in urlList:
                try:
                    if self.running == False: break
                    # 기사 본문 수집
                    articleData = self.collectArticle(newsUrl)
                    if not articleData:
                        continue
                    else:
                        self.status['articleCnt'] += 1
                        
                    # 기사 날짜 저장 (댓글 행의 마지막 컬럼인 'Article Day'용)
                    article_day = articleData[5] 

                    # 옵션 3: 기사만 수집 (댓글수 0으로 기록)
                    if self.option == 3:
                        addToCSV(self.DBPath, self.articleDB, [articleData + [0]], navernews_article_column)
                    
                    # 옵션 1, 2, 4: 댓글 및 통계 포함
                    
                    elif self.option in [1, 2, 4]:
                        try:
                            # 댓글 수집 (옵션 4일 때만 유저 정보 포함)
                            is_username = True if self.option == 4 else False
                            cmtData = self.collectCmt(newsUrl, username=is_username)
                            
                            reply_cnt = cmtData.get('replyCnt', 0)
                            self.status['commentCnt'] += reply_cnt
                            
                            # 기사 저장 (실제 댓글수 포함)
                            addToCSV(self.DBPath, self.articleDB, [articleData + [reply_cnt]], navernews_article_column)
                            
                            # 통계 데이터 저장
                            stats = cmtData.get('statisticsData', [])
                        
                        except Exception as e:
                            logger.info(f"Error occurred while processing comment data for {newsUrl}: {e}")
                        
                        if stats:
                            # 통계 컬럼 구성에 맞춰 기사 정보 + 통계 데이터 결합
                            addToCSV(self.DBPath, self.statisticsDB, [articleData + stats], navernews_statistics_column)
                        
                        # 댓글 리스트 저장
                        replies = cmtData.get('replyList', [])
                        if replies:
                            # 각 댓글 끝에 article_day 추가
                            processed_replies = [r + [article_day] for r in replies]
                            current_reply_col = navernews_4_reply_column if self.option == 4 else navernews_reply_column
                            addToCSV(self.DBPath, self.replyDB, processed_replies, current_reply_col)
                        
                        # 옵션 2: 대댓글 수집 및 저장
                        if self.option == 2:
                            try:
                                parent_nos = cmtData.get('parentCommentNo_list', [])
                                if parent_nos:
                                    rereplyData = self.collectReply(newsUrl, parent_nos)
                                    rereplies = rereplyData.get('rereplyList', [])
                                    if rereplies:
                                        processed_rereplies = [rr + [article_day] for rr in rereplies]
                                        self.status['replyCnt'] += rereplyData.get('rereplyCnt', 0)
                                        addToCSV(self.DBPath, self.rereplyDB, processed_rereplies, navernews_rereply_column)
                                    
                            except Exception as e:
                                logger.info(f"Error occurred while processing reply data for {newsUrl}: {e}")
                    
                    time.sleep(SLEEP_TIME)

                except Exception as e:
                    logger.info(f"Error occurred while processing {newsUrl}: {e}")
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
    
    NaverNewsCrawler_obj = NaverNewsCrawler(name, keyword, startDate, endDate, option, speed)
    NaverNewsCrawler_obj.main()
        
def tester(name= '최우철', startDate = str(20260301), endDate = str(20260302), keyword = '경찰대', option = 1, speed = 1):
    option_dic = {
        1: "\n1. 기사 + 댓글\n2. 기사 + 댓글/대댓글\n3. 기사\n4. 기사 + 댓글(추가정보)\n",
        2: "\n1. 블로그 본문\n2. 블로그 본문 + 댓글/대댓글\n",
        3: "\n1. 카페 본문\n2. 카페 본문 + 댓글/대댓글\n",
        4: "\n1. 영상 정보 + 댓글/대댓글 (100개 제한)\n2. 영상 정보 + 댓글/대댓글(무제한)\n",
        5: "\n1. 기사\n",
        6: "\n1. 기사\n2. 기사 + 댓글\n"
    }
    
    NaverNewsCrawler_obj = NaverNewsCrawler(name, keyword, startDate, endDate, option, speed)
    NaverNewsCrawler_obj.main()

if __name__ == "__main__":
    tester()