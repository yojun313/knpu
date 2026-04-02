import time
import json
import re
import copy
import warnings
import calendar
from datetime import datetime, timedelta, timezone
import urllib3
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from user_agent import generate_navigator
from urllib.parse import urlunparse, urlencode
import logging
from db import load_proxy_list, checkDB, get_userinfo
from db.util import makeDBname
from config import SLEEP_TIME, PROXY
from common.req import Request, set_proxy_list
from common.storage import makeDB, updateCrawlStatus, initCrawlLog, appendCrawlLog
from common.csv import makeCSV, addToCSV
from common.columns import chinasina_article_column, chinasina_reply_column
from common.controller import stopOperator, finishOperator

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

logger = logging.getLogger(__name__)


class ChinaSinaCrawler:

    def __init__(self, requester, keyword, startDate, endDate, option, speed):

        if PROXY:
            proxy_list = load_proxy_list()
            set_proxy_list(proxy_list)

        self.DBname = makeDBname('chinasina', keyword, startDate, endDate)
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
            'currentdate': '',
            'urlCnt': 0,
            'articleCnt': 0,
            'commentCnt': 0,
            'replyCnt': 0,
        }

    # ── 유틸리티 ──────────────────────────────────────────────

    def _dateSplitter(self, start_date, end_date):
        """날짜 범위를 월 단위로 분할"""
        start = datetime.strptime(str(start_date), '%Y%m%d')
        end = datetime.strptime(str(end_date), '%Y%m%d')

        result = []
        current = start

        while current <= end:
            _, last_day = calendar.monthrange(current.year, current.month)
            month_end = datetime(current.year, current.month, last_day)

            if month_end > end:
                month_end = end

            result.append([current.strftime('%Y%m%d'), month_end.strftime('%Y%m%d')])

            next_month = current.replace(day=28) + timedelta(days=4)
            current = next_month.replace(day=1)

        return result

    def _dateInverter(self, date_str):
        return int(time.mktime(time.strptime(date_str, '%Y%m%d')))

    def _sortUrlList(self, urls):
        date_pattern = re.compile(r'/(\d{4}-\d{2}-\d{2})/')

        def extract_date(url):
            match = date_pattern.search(url)
            if match:
                return datetime.strptime(match.group(1), '%Y-%m-%d')
            return datetime.min

        return sorted(urls, key=extract_date)

    def _newsURLChecker(self, newsURL):
        if 'https://news.sina.com.cn' in newsURL:
            return 1
        elif 'https://news.sina.cn' in newsURL:
            return 2
        elif 'https://mil.news.sina.com.cn' in newsURL:
            return 3
        else:
            return False

    def _newsChannelChecker(self, newsURL):
        param = newsURL.split('/')[3]
        if param in ['c', 'gov', 'sx']:
            return 'gn'
        elif param in ['o', 'zx', 'znl', 's', 'sh']:
            return 'sh'
        else:
            return ['gn', 'sh']

    def _newsidFormChecker(self, newsURL):
        try:
            int(newsURL.split('/')[4][0])
            return 1
        except Exception:
            return 2

    def _jsonFormatter(self, input_str):
        start_index = input_str.index('{')
        end_index = input_str.rindex('}') + 1
        return input_str[start_index:end_index]

    # ── 수집 함수 ─────────────────────────────────────────────

    def collectUrl(self, keyword, startDate, endDate):
        """Baidu 검색으로 Sina 뉴스 URL 수집"""
        try:
            endCnt = 0
            urlList = []
            previous_links = []
            previous_search_url = 'https://www.baidu.com/'
            startDate_ts = self._dateInverter(str(startDate))
            endDate_ts = self._dateInverter(str(endDate))
            site = 'news.sina.com.cn'

            page = 0
            while True:
                if not self.running:
                    break

                if endCnt > 5:
                    break

                query_params = {
                    'wd': keyword,
                    'pn': page,
                    'oq': keyword,
                    'ct': '2097152',
                    'ie': 'utf-8',
                    'si': site,
                    'fenlei': '256',
                    'rsv_idx': '1',
                    'gpc': f'stf={startDate_ts},{endDate_ts}|stftype=2'
                }

                search_url = urlunparse(('https', 'www.baidu.com', '/s', '', urlencode(query_params), ''))
                headers = {
                    'User-Agent': generate_navigator()['user_agent'],
                    'Referer': previous_search_url
                }

                try:
                    res = Request(search_url, headers=headers)
                    res.raise_for_status()
                except Exception as e:
                    logger.info(f"Baidu 검색 요청 실패: {e}")
                    break

                soup = BeautifulSoup(res.text, 'html.parser')
                result_divs = soup.find_all('div', class_='result')
                links = [div.get('mu') for div in result_divs if div.get('mu')]

                if links == previous_links or not links:
                    endCnt += 1

                for url in links:
                    if url not in urlList:
                        if 'news.sina.cn' in url or ('news.sina.com.cn' in url and url.count('/') >= 5):
                            urlList.append(url)
                            self.status['urlCnt'] += 1

                previous_links = copy.deepcopy(links)
                previous_search_url = search_url

                if links:
                    page += 10

                time.sleep(SLEEP_TIME)

            return self._sortUrlList(list(set(urlList)))

        except Exception as e:
            logger.info(f"Error occurred while collecting Sina URLs: {e}")
            appendCrawlLog(self.DBuid, "error", f"Sina URL 수집 실패 ({keyword}): {e}")
            return []

    def collectArticle(self, newsURL):
        """Sina 뉴스 기사 수집"""
        try:
            newsURL_type = self._newsURLChecker(newsURL)
            if not isinstance(newsURL_type, int):
                return []

            try:
                res = Request(newsURL)
                res.raise_for_status()
            except Exception as e:
                logger.info(f"Sina 기사 요청 실패 ({newsURL}): {e}")
                return []

            soup = BeautifulSoup(res.text, 'html.parser')

            # 날짜 추출
            if self._newsidFormChecker(newsURL) == 1:
                date = newsURL.split('/')[4]
            else:
                date = newsURL.split('/')[5]

            try:
                if newsURL_type in (1, 3):
                    title = soup.find('h1', {'class': 'main-title'}).text
                    paragraphs = soup.find('div', {'class': 'article', 'id': 'article'}).find_all('p')
                    text = " ".join(p.get_text(strip=True) for p in paragraphs)
                elif newsURL_type == 2:
                    title = soup.find('h1', {'class': 'art_tit_h1'}).text
                    paragraphs = soup.find('section', {'class': 'art_pic_card art_content'}).find_all('p')
                    text = " ".join(p.get_text(strip=True) for p in paragraphs)
                else:
                    return []
            except Exception as e:
                logger.info(f"Sina 기사 파싱 실패 ({newsURL}): {e}")
                return []

            articleData = [title, text, date, newsURL]
            return articleData

        except Exception as e:
            logger.info(f"Error occurred while collecting Sina article: {e}")
            appendCrawlLog(self.DBuid, "error", f"Sina 기사 수집 실패 ({newsURL}): {e}")
            return []

    def collectReply(self, newsURL):
        """Sina 뉴스 댓글 수집"""
        returnData = {
            'replyList': [],
            'replyCnt': 0
        }
        try:
            newsURL_type = self._newsURLChecker(newsURL)
            if not isinstance(newsURL_type, int):
                return returnData

            # newsid 추출
            if self._newsidFormChecker(newsURL) == 1:
                newsid = newsURL.split('/')[5].split('-')[1]
            else:
                newsid = newsURL.split('/')[6].split('-')[1]

            if newsid[0] == 'i':
                newsid = newsid[1:].split('.')[0]
            else:
                newsid = newsid.split('.')[0]

            channelid = self._newsChannelChecker(newsURL)
            channelidList_exists = False
            if isinstance(channelid, list):
                channelidList = copy.deepcopy(channelid)
                channelidList_exists = True
                channelid = channelidList[0]

            replyList = []
            reply_num = 1
            page = 1

            while True:
                if not self.running:
                    break

                try:
                    if newsURL_type == 1:
                        api_url = (
                            f'https://comment.sina.com.cn/page/info?version=1&format=json'
                            f'&channel={channelid}&newsid=comos-{newsid}'
                            f'&group=undefined&compress=0&ie=utf-8&oe=utf-8'
                            f'&page={page}&page_size=10&t_size=3&h_size=3&thread=1'
                            f'&uid=unlogin_user&callback=jsonp_{int(time.time())}&_={int(time.time())}'
                        )
                        res = Request(api_url)
                        res.raise_for_status()
                        main_text = res.text

                    elif newsURL_type == 2:
                        default_url = 'https://cmnt.sina.cn/aj/v2/list'
                        refer_url = f'https://cmnt.sina.cn/index?product=comos&index={newsid}&tj_ch=news&is_clear=0'
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
                            'Referer': refer_url
                        }
                        res = Request(default_url, headers=headers, params=params)
                        res.raise_for_status()
                        main_text = res.text

                    else:
                        break

                except Exception as e:
                    logger.info(f"Sina 댓글 API 요청 실패 ({newsURL}): {e}")
                    break

                try:
                    main_text = self._jsonFormatter(main_text)
                    temp = json.loads(main_text)
                    comment_json = temp['result']['cmntlist']
                except Exception:
                    if channelidList_exists and len(channelidList) > 1:
                        channelidList.pop(0)
                        channelid = channelidList[0]
                        continue
                    break

                if not comment_json:
                    break

                for data in comment_json:
                    nickname = data['nick']
                    date = data['time'].split()[0]
                    like = data['rank']
                    text = data['content'].replace('\u200b', '')

                    replyList.append([reply_num, nickname, date, text, like, newsURL])
                    reply_num += 1

                self.status['commentCnt'] += len(comment_json)
                page += 1
                time.sleep(SLEEP_TIME)

            returnData['replyList'] = replyList
            returnData['replyCnt'] = len(replyList)
            return returnData

        except Exception as e:
            logger.info(f"Error occurred while collecting Sina replies: {e}")
            appendCrawlLog(self.DBuid, "error", f"Sina 댓글 수집 실패 ({newsURL}): {e}")
            return returnData

    def reportStatus(self):
        return self.status

    def main(self):
        self.DBPath, self.DBuid = makeDB(
            DBname=self.DBname,
            DBtype='chinasina',
            startdate=self.startDate,
            enddate=self.endDate,
            option=self.option,
            keyword=self.keyword,
            requester=self.requester,
            requesterUid=self.requesterUid
        )

        initCrawlLog(self.DBuid, (
            f"User: {self.requester}\n"
            f"Object: chinasina\n"
            f"Option: {self.option}\n"
            f"Keyword: {self.keyword}\n"
            f"Date Range: {self.startDate} ~ {self.endDate}"
        ))

        makeCSV(self.DBPath, self.articleDB, chinasina_article_column)
        if self.option == 2:
            makeCSV(self.DBPath, self.replyDB, chinasina_reply_column)

        # 월 단위 분할 (ChinaSina 특성: 일 단위가 아닌 월 단위 iteration)
        dateRangeList = self._dateSplitter(self.startDate, self.endDate)
        total_ranges = len(dateRangeList)

        for rangeCount, dateRange in enumerate(dateRangeList):
            currentDate_start = dateRange[0]
            currentDate_end = dateRange[1]

            if checkDB(self.DBuid) == False:
                self.running = False

            if not self.running:
                stopOperator(DBpath=self.DBPath, DBtype='chinasina', DBname=self.DBname, startTime=self.startTime, pushoverKey=self.PushoverKey, userEmail=self.Email, status=self.status, DBuid=self.DBuid)
                return

            if total_ranges > 0:
                percent = str(round(((rangeCount + 1) / total_ranges) * 100, 1))
                self.status['percentage'] = percent
                start_fmt = datetime.strptime(currentDate_start, '%Y%m%d').strftime('%Y-%m-%d')
                end_fmt = datetime.strptime(currentDate_end, '%Y%m%d').strftime('%Y-%m-%d')
                self.status['currentdate'] = f"{start_fmt} ~ {end_fmt}"

            urlList = self.collectUrl(
                keyword=self.keyword,
                startDate=currentDate_start,
                endDate=currentDate_end
            )

            articleList = []
            for newsUrl in urlList:
                try:
                    if not self.running:
                        break

                    articleData = self.collectArticle(newsUrl)
                    if not articleData:
                        continue

                    self.status['articleCnt'] += 1
                    articleList.append(articleData)

                    if self.option == 2:
                        try:
                            cmtData = self.collectReply(newsUrl)
                            reply_cnt = cmtData.get('replyCnt', 0)

                            replies = cmtData.get('replyList', [])
                            if replies:
                                article_day = articleData[2]  # date
                                processed_replies = [r + [article_day] for r in replies]
                                addToCSV(self.DBPath, self.replyDB, processed_replies, chinasina_reply_column)

                        except Exception as e:
                            logger.info(f"Error occurred while processing Sina comment data for {newsUrl}: {e}")

                    time.sleep(SLEEP_TIME)

                except Exception as e:
                    logger.info(f"Error occurred while processing {newsUrl}: {e}")
                    appendCrawlLog(self.DBuid, "error", f"Sina 처리 실패 ({newsUrl}): {e}")
                    continue

            # 기사는 날짜순 정렬 후 일괄 저장 (원본 동작 유지)
            if articleList:
                try:
                    articleList_sorted = sorted(articleList, key=lambda x: datetime.strptime(x[2], "%Y-%m-%d"))
                except Exception:
                    articleList_sorted = articleList
                addToCSV(self.DBPath, self.articleDB, articleList_sorted, chinasina_article_column)

            updateCrawlStatus(
                self.DBuid,
                self.status['percentage'] + "%",
                self.status['articleCnt'],
                self.status['commentCnt'],
                self.status['replyCnt'],
            )

        # 모든 월 범위 완료
        finishOperator(DBpath=self.DBPath, DBtype='chinasina', DBname=self.DBname, startTime=self.startTime, pushoverKey=self.PushoverKey, userEmail=self.Email, status=self.status, DBuid=self.DBuid)
