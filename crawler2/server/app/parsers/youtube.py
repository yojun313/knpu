import time
import json
import re
import sys
import warnings
from datetime import datetime, timedelta, timezone
import urllib3
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
import logging
from db import load_proxy_list, checkStatus, get_userinfo, crawler_db
from db.util import makeDBname
from config import SLEEP_TIME, PROXY
from common.req import Request, set_proxy_list
from common.storage import makeDB, updateCrawlStatus, initCrawlLog, appendCrawlLog
from common.csv import makeCSV, addToCSV
from common.columns import youtube_article_column, youtube_reply_column, youtube_rereply_column
from common.controller import stopOperator, finishOperator

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)


class YouTubeCrawler:

    def __init__(self, requester, keyword, startDate, endDate, option, speed):

        if PROXY:
            proxy_list = load_proxy_list()
            set_proxy_list(proxy_list)

        self.DBname = makeDBname('youtube', keyword, startDate, endDate)
        self.requester = requester
        self.keyword = keyword
        self.startDate = startDate
        self.endDate = endDate
        self.option = option
        self.speed = speed

        self.articleDB = self.DBname + '_article'
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

        # YouTube API 키 목록 로드
        self.api_list = self._load_api_keys()
        if not self.api_list:
            raise ValueError("YouTube API 키가 없습니다")
        self.api_num = 1
        self.api_obj = build('youtube', 'v3', developerKey=self.api_list[0])

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

    # ── 유틸리티 ──────────────────────────────────────────────

    def _load_api_keys(self):
        """MongoDB crawler/youtube_api에서 API 키 목록 로드"""
        collection = crawler_db['youtube_api']
        api_list = []
        cursor = collection.find({}, {"_id": 0, "API code": 1})
        for doc in cursor:
            if "API code" in doc:
                api_list.append(doc["API code"])
        return api_list

    def _rotate_api_key(self):
        """API 할당량 초과 시 다음 키로 전환. 모두 소진 시 예외 발생."""
        if self.api_num >= len(self.api_list):
            raise RuntimeError("모든 YouTube API 키의 할당량이 초과되었습니다. 1일 후 재시도하세요.")
        self.api_num += 1
        self.api_obj = build('youtube', 'v3', developerKey=self.api_list[self.api_num - 1])
        logger.info(f"YouTube API 키 전환: {self.api_num}/{len(self.api_list)}")

    def _format_date_api(self, date_str, is_end=False):
        date_obj = datetime.strptime(date_str, "%Y%m%d")
        if is_end:
            return date_obj.strftime("%Y-%m-%dT23:59:59Z")
        else:
            return date_obj.strftime("%Y-%m-%dT00:00:00Z")

    # ── 수집 함수 ─────────────────────────────────────────────

    def collectUrl(self, keyword, startDate, endDate):
        try:
            published_after = self._format_date_api(startDate, is_end=False)
            published_before = self._format_date_api(endDate, is_end=True)
            urlList = []
            next_page_token = None

            while True:
                if not self.running:
                    break

                try:
                    request = self.api_obj.search().list(
                        q=keyword,
                        part='snippet',
                        type='video',
                        publishedAfter=published_after,
                        publishedBefore=published_before,
                        maxResults=50,
                        pageToken=next_page_token
                    )
                    response = request.execute()
                except Exception as e:
                    if "quotaExceeded" in str(e):
                        self._rotate_api_key()
                        continue
                    else:
                        logger.info(f"YouTube URL 수집 API 에러: {e}")
                        break

                for item in response.get('items', []):
                    video_id = item['id']['videoId']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    if video_url not in urlList:
                        urlList.append(video_url)
                        self.status['urlCnt'] += 1

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

            return list(dict.fromkeys(urlList))

        except Exception as e:
            logger.info(f"Error occurred while collecting YouTube URLs: {e}")
            appendCrawlLog(self.DBuid, "error", f"YouTube URL 수집 실패 ({keyword}): {e}")
            return []

    def collectArticle(self, url):
        """hadzy.com API로 영상 정보 수집"""
        try:
            video_id = url.replace("https://www.youtube.com/watch?v=", "")
            info_api_url = f"https://hadzy.com/api/videos/{video_id}"

            res = Request(info_api_url)
            res.raise_for_status()

            try:
                temp = json.loads(res.text)
                channel = temp['items'][0]['snippet']['channelTitle']
                video_title = temp['items'][0]['snippet']['title'].replace("\n", " ").replace("\r", "").replace("\t", "").replace("<br>", " ")
                video_description = temp['items'][0]['snippet']['description'].replace("\n", "").replace("\t", "").replace("\r", "").replace("<br>", " ")
                video_date = temp['items'][0]['snippet']['publishedAt']
                video_date = datetime.strptime(video_date, "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d")
                view_count = temp['items'][0]['statistics']['viewCount']
                like_count = temp['items'][0]['statistics']['likeCount']
                comment_count = temp['items'][0]['statistics']['commentCount']
            except Exception as e:
                logger.info(f"YouTube 영상 정보 파싱 실패 ({url}): {e}")
                return []

            articleData = [channel, url, video_title, video_description, video_date, view_count, like_count, comment_count]
            return articleData

        except Exception as e:
            logger.info(f"Error occurred while collecting YouTube article: {e}")
            appendCrawlLog(self.DBuid, "error", f"YouTube 영상 수집 실패 ({url}): {e}")
            return []

    def collectReply(self, url, option):
        """YouTube API로 댓글/대댓글 수집"""
        returnData = {
            'replyList': [],
            'rereplyList': [],
            'replyCnt': 0,
            'rereplyCnt': 0,
        }
        try:
            video_id = url.replace("https://www.youtube.com/watch?v=", "")
            replyList = []
            rereplyList = []
            reply_idx = 1
            rereply_idx = 1

            # 첫 댓글 요청
            while True:
                try:
                    request = self.api_obj.commentThreads().list(
                        part='snippet,replies',
                        videoId=video_id,
                        maxResults=100,
                        order='relevance'
                    )
                    response = request.execute()
                    break
                except Exception as e:
                    error_str = str(e)
                    if any(err in error_str for err in [
                        "operationNotSupported", "commentsDisabled", "forbidden",
                        "channelNotFound", "commentThreadNotFound", "videoNotFound",
                        "processingFailure"
                    ]):
                        return returnData
                    elif "quotaExceeded" in error_str:
                        self._rotate_api_key()
                    else:
                        logger.info(f"YouTube 댓글 API 에러 ({url}): {e}")
                        return returnData

            while request:
                if not self.running:
                    break

                for item in response['items']:
                    try:
                        comment = item['snippet']['topLevelComment']['snippet']
                        textdisplay = comment['textDisplay'].replace('<br>', ' ')
                        if '</a>' in textdisplay:
                            textdisplay = re.sub(r'<a[^>]*>(.*?)<\/a>', '', textdisplay)
                            if textdisplay:
                                textdisplay = textdisplay[1:]

                        replyData = [
                            reply_idx,
                            comment['authorDisplayName'],
                            datetime.strptime(comment['publishedAt'], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                            textdisplay,
                            comment['likeCount'],
                            url
                        ]
                        replyList.append(replyData)
                        reply_idx += 1

                        # 대댓글
                        try:
                            if item['snippet']['totalReplyCount'] > 0:
                                for reply_item in item['replies']['comments']:
                                    reply = reply_item['snippet']
                                    rereplyList.append([
                                        rereply_idx,
                                        reply['authorDisplayName'],
                                        datetime.strptime(reply['publishedAt'], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                                        reply['textDisplay'],
                                        reply['likeCount'],
                                        url
                                    ])
                                    rereply_idx += 1
                        except Exception as e:
                            logger.info(f"YouTube 대댓글 파싱 실패: {e}")

                    except Exception as e:
                        logger.info(f"YouTube 댓글 항목 파싱 실패: {e}")

                # option 1: 100개 제한, option 2: 무제한
                if option == 2:
                    if 'nextPageToken' in response:
                        while True:
                            try:
                                request = self.api_obj.commentThreads().list(
                                    part='snippet,replies',
                                    videoId=video_id,
                                    pageToken=response['nextPageToken'],
                                    maxResults=100,
                                    order='relevance'
                                )
                                response = request.execute()
                                break
                            except Exception as e:
                                error_str = str(e)
                                if any(err in error_str for err in [
                                    "operationNotSupported", "commentsDisabled", "forbidden",
                                    "channelNotFound", "commentThreadNotFound", "videoNotFound",
                                    "processingFailure"
                                ]):
                                    returnData['replyList'] = replyList
                                    returnData['rereplyList'] = rereplyList
                                    returnData['replyCnt'] = len(replyList)
                                    returnData['rereplyCnt'] = len(rereplyList)
                                    return returnData
                                elif "quotaExceeded" in error_str:
                                    self._rotate_api_key()
                    else:
                        break
                else:
                    break

            returnData['replyList'] = replyList
            returnData['rereplyList'] = rereplyList
            returnData['replyCnt'] = len(replyList)
            returnData['rereplyCnt'] = len(rereplyList)
            return returnData

        except Exception as e:
            logger.info(f"Error occurred while collecting YouTube replies: {e}")
            appendCrawlLog(self.DBuid, "error", f"YouTube 댓글 수집 실패 ({url}): {e}")
            return returnData

    def reportStatus(self):
        return self.status

    def main(self):
        self.DBPath, self.DBuid = makeDB(
            DBname=self.DBname,
            DBtype='youtube',
            startdate=self.startDate,
            enddate=self.endDate,
            option=self.option,
            keyword=self.keyword,
            requester=self.requester,
            requesterUid=self.requesterUid
        )

        initCrawlLog(self.DBuid, (
            f"User: {self.requester}\n"
            f"Object: youtube\n"
            f"Option: {self.option}\n"
            f"Keyword: {self.keyword}\n"
            f"Date Range: {self.startDate} ~ {self.endDate}"
        ))

        makeCSV(self.DBPath, self.articleDB, youtube_article_column)
        makeCSV(self.DBPath, self.replyDB, youtube_reply_column)
        makeCSV(self.DBPath, self.rereplyDB, youtube_rereply_column)

        for dayCount in range(self.date_range + 1):
            currentDate_str = self.currentDate.strftime('%Y%m%d')

            if checkStatus(self.DBuid) == False:
                self.running = False

            if not self.running:
                stopOperator(DBpath=self.DBPath, DBtype='youtube', DBname=self.DBname, startTime=self.startTime, pushoverKey=self.PushoverKey, userEmail=self.Email, status=self.status, DBuid=self.DBuid)
                break

            if dayCount == self.date_range:
                finishOperator(DBpath=self.DBPath, DBtype='youtube', DBname=self.DBname, startTime=self.startTime, pushoverKey=self.PushoverKey, userEmail=self.Email, status=self.status, DBuid=self.DBuid)
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

            for videoUrl in urlList:
                try:
                    if not self.running:
                        break

                    articleData = self.collectArticle(videoUrl)
                    if not articleData:
                        continue

                    self.status['articleCnt'] += 1
                    article_day = articleData[4]  # video_date

                    addToCSV(self.DBPath, self.articleDB, [articleData], youtube_article_column)

                    try:
                        cmtData = self.collectReply(videoUrl, self.option)

                        reply_cnt = cmtData.get('replyCnt', 0)
                        rereply_cnt = cmtData.get('rereplyCnt', 0)
                        self.status['commentCnt'] += reply_cnt
                        self.status['replyCnt'] += rereply_cnt

                        replies = cmtData.get('replyList', [])
                        if replies:
                            processed_replies = [r + [article_day] for r in replies]
                            addToCSV(self.DBPath, self.replyDB, processed_replies, youtube_reply_column)

                        rereplies = cmtData.get('rereplyList', [])
                        if rereplies:
                            processed_rereplies = [r + [article_day] for r in rereplies]
                            addToCSV(self.DBPath, self.rereplyDB, processed_rereplies, youtube_rereply_column)

                    except Exception as e:
                        logger.info(f"Error occurred while processing YouTube comment data for {videoUrl}: {e}")

                    time.sleep(SLEEP_TIME)

                except Exception as e:
                    logger.info(f"Error occurred while processing {videoUrl}: {e}")
                    appendCrawlLog(self.DBuid, "error", f"YouTube 처리 실패 ({videoUrl}): {e}")
                    continue

            updateCrawlStatus(
                self.DBuid,
                self.status['percentage'] + "%",
                self.status['articleCnt'],
                self.status['commentCnt'],
                self.status['replyCnt'],
            )

            self.currentDate += self.deltaD
