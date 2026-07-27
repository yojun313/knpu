import asyncio
import time
import json
import re
import warnings
from datetime import datetime, timedelta, timezone
import urllib3
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from user_agent import generate_navigator
from urllib.parse import urlparse, parse_qs
import logging
from db import load_proxy_list, checkState, get_userinfo
from db.util import makeDBname
from config import SLEEP_TIME, PROXY
from common.req import Request, RequestAsync, set_proxy_list
from common.async_run import speed_to_concurrency, run_with_concurrency
from common.naver_lib import parse_naver_query
from common.storage import (
    makeDB,
    updateCrawlStatus,
    initCrawlLog,
    appendCrawlLog,
    getResumeContext,
    computeResumeStartDate,
    getResumeDBPath,
    restoreCsvFromParquet,
    beginResume,
    validateResumeRange,
    countExistingRows,
    renameForResume,
)
from common.csv import makeCSV, addToCSV
from common.columns import navercafe_article_column, navercafe_reply_column
from common.controller import stopOperator, finishOperator

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

logger = logging.getLogger(__name__)


class NaverCafeCrawler:
    CRAWL_OBJECT = 3

    def __init__(self, requester, keyword, startDate, endDate, option, speed):

        if PROXY:
            proxy_list = load_proxy_list()
            set_proxy_list(proxy_list)

        self.DBname = makeDBname("navercafe", keyword, startDate, endDate)
        self.requester = requester
        self.keyword = keyword
        self.startDate = startDate
        self.endDate = endDate
        self.option = option
        self.speed = speed

        self.articleDB = self.DBname + "_article"
        self.replyDB = self.DBname + "_reply"

        self.startTime = time.time()

        self.startDate_form = datetime.strptime(startDate, "%Y%m%d").date()
        self.endDate_form = datetime.strptime(endDate, "%Y%m%d").date()

        self.currentDate = self.startDate_form
        self.date_range = (self.endDate_form - self.startDate_form).days + 1
        self.deltaD = timedelta(days=1)

        notification = get_userinfo(self.requester)
        if not notification:
            raise ValueError(f"사용자 정보를 찾을 수 없습니다: {self.requester}")
        self.Email = notification["Email"]
        self.requesterUid = notification["userUid"]

        self.running = True
        self.resuming = False
        self.resumePriorCounts = None
        self.DBuid = None
        self.status = {
            "percentage": "0",
            "currentdate": self.currentDate.strftime("%Y-%m-%d"),
            "urlCnt": 0,
            "articleCnt": 0,
            "commentCnt": 0,
            "replyCnt": 0,
        }

        self.DBPath, self.DBuid = makeDB(
            DBname=self.DBname,
            DBtype="navercafe",
            startdate=self.startDate,
            enddate=self.endDate,
            option=self.option,
            keyword=self.keyword,
            requester=self.requester,
            requesterUid=self.requesterUid,
            crawlObject=self.CRAWL_OBJECT,
            speed=self.speed,
        )

    @classmethod
    def fromResume(cls, DBuid, endDate=None):
        doc = getResumeContext(DBuid)

        obj = cls.__new__(cls)

        if PROXY:
            proxy_list = load_proxy_list()
            set_proxy_list(proxy_list)

        obj.DBname = doc["name"]
        obj.requester = doc["requester"]
        obj.keyword = doc["keyword"]
        obj.startDate = computeResumeStartDate(doc)
        obj.endDate = endDate or doc["endDate"]
        validateResumeRange(obj.startDate, obj.endDate)
        obj.option = doc["crawlOption"]
        obj.speed = doc.get("crawlSpeed", 3)

        obj.DBname = renameForResume(
            DBuid, "navercafe", obj.keyword, doc["startDate"], obj.endDate, obj.DBname
        )

        obj.articleDB = obj.DBname + "_article"
        obj.replyDB = obj.DBname + "_reply"

        obj.startTime = time.time()

        obj.startDate_form = datetime.strptime(obj.startDate, "%Y%m%d").date()
        obj.endDate_form = datetime.strptime(obj.endDate, "%Y%m%d").date()

        obj.currentDate = obj.startDate_form
        obj.date_range = (obj.endDate_form - obj.startDate_form).days + 1
        obj.deltaD = timedelta(days=1)

        notification = get_userinfo(obj.requester)
        if not notification:
            raise ValueError(f"사용자 정보를 찾을 수 없습니다: {obj.requester}")
        obj.Email = notification["Email"]
        obj.requesterUid = notification["userUid"]

        obj.running = True
        obj.resuming = True
        obj.DBuid = DBuid
        obj.DBPath = getResumeDBPath(obj.DBname)

        stat = doc.get("stat", {})
        obj.status = {
            "percentage": "0",
            "currentdate": obj.currentDate.strftime("%Y-%m-%d"),
            "urlCnt": 0,
            "articleCnt": stat.get("article", 0),
            "commentCnt": stat.get("cmt", 0),
            "replyCnt": stat.get("reply", 0),
        }

        tables = [obj.articleDB]
        if obj.option == 1:
            tables.append(obj.replyDB)
        restoreCsvFromParquet(obj.DBPath, tables)
        obj.resumePriorCounts = countExistingRows(obj.DBPath, tables)

        beginResume(DBuid, newEndDate=endDate)
        return obj

    # ── 유틸리티 ──────────────────────────────────────────────

    def extractArticleID(self, cafeURL):
        return cafeURL.split("/")[4].split("?")[0]

    def extractArt(self, url):  # art_code
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        return query_params.get("art", [None])[0]

    def extractTime(self, value):
        timestamp_s = value / 1000
        date = datetime.fromtimestamp(timestamp_s, timezone.utc).date()
        return date.strftime("%Y-%m-%d")

    # contentHtml 필드를 이스케이프 처리하여 JSON 문자열을 정리
    def escape_content_html(self, json_str):
        pattern = re.compile(r'("contentHtml":\s?")(.*?)(?=",\s*")', re.DOTALL)
        match = pattern.search(json_str)
        if match:
            content_html = match.group(2)
            escaped = (
                content_html.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
            )
            json_str = json_str[: match.start(2)] + escaped + json_str[match.end(2) :]
        return json_str

    async def extractCafeID(self, session, cafeURL):
        try:
            res = await RequestAsync(session, cafeURL)
            res.raise_for_status()
            text = res.text
            if text.startswith("\ufeff"):
                text = text[1:]
            bs = BeautifulSoup(text, "html.parser")
            pattern = re.compile(r"var g_sClubId = \"(.*?)\";")
            for script in bs.find_all("script"):
                if script.string:
                    match = pattern.search(script.string)
                    if match:
                        return match.group(1)
            return None
        except Exception as e:
            logger.info(f"cafeID 추출 실패 ({cafeURL}): {e}")
            return None

    # ── 수집 함수 ─────────────────────────────────────────────

    def collectUrl(self, keyword, startDate, endDate):
        try:

            def extract_cafeurls(text):
                pattern = (
                    r"https://cafe\.naver\.com/[a-zA-Z0-9_-]+/\d+\?art=[a-zA-Z0-9._-]+"
                )
                urls = re.findall(pattern, text)
                return list(dict.fromkeys(urls))

            def extract_nexturl(text):
                try:
                    json_data = json.loads(text)
                    if "url" in json_data and json_data["url"]:
                        return json_data["url"]
                    return None
                except Exception as e:
                    logger.info(f"Error occurred while extracting next URL: {e}")
                    return None

            def extract_api_url_from_html(html_text):
                pattern = r'url:\s*"(https://s\.search\.naver\.com/p/cafe/48/search\.naver\?[^"]+)"'
                match = re.search(pattern, html_text)
                if match:
                    return match.group(1)
                return None

            query_dict = parse_naver_query(keyword)
            urlList = []

            # 1단계: 검색 페이지 HTML 요청 후 API URL 추출
            search_params = {
                "ssc": "tab.cafe.all",
                "query": keyword,
                "sm": "mtb_opt",
                "st": "rel",
                "stnm": "date",
                "nso": f"so:r,p:from{startDate}to{endDate}",
                "date_from": startDate,
                "date_to": endDate,
                "prdtype": "0",
                "qdt": "1",
                "opt_tab": "0",
                "cafe_where": "",
                "nx_search_query": query_dict["nx_search_query"],
                "nx_and_query": query_dict["nx_and_query"],
                "nx_sub_query": query_dict["nx_sub_query"],
                "nx_search_hlquery": query_dict["nx_search_hlquery"],
            }
            search_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            }
            search_response = Request(
                "https://search.naver.com/search.naver",
                headers=search_headers,
                params=search_params,
            )
            search_response.raise_for_status()
            html_text = search_response.text

            # 1단계 HTML에서 카페 URL 수집
            for url in extract_cafeurls(html_text):
                if url not in urlList:
                    urlList.append(url)
                    self.status["urlCnt"] += 1

            api_url = extract_api_url_from_html(html_text)
            if api_url is None:
                logger.info(
                    f"No API URL found in search page HTML for keyword: {keyword}, date: {startDate}~{endDate}"
                )
                return urlList

            # 2단계: 추출된 API URL로 요청 (기존 방식 유지)
            response = Request(api_url)
            response.raise_for_status()
            json_text = response.text

            while True:
                if self.running == False:
                    break

                pre_urlList = extract_cafeurls(json_text)
                if not pre_urlList:
                    time.sleep(SLEEP_TIME)

                for url in pre_urlList:
                    if url not in urlList:
                        urlList.append(url)
                        self.status["urlCnt"] += 1

                nextUrl = extract_nexturl(json_text)
                if nextUrl is None:
                    break
                else:
                    time.sleep(SLEEP_TIME)
                    response = Request(nextUrl)
                    response.raise_for_status()
                    json_text = response.text

            return urlList
        except Exception as e:
            logger.info(f"Error occurred while collecting cafe URLs: {e}")
            appendCrawlLog(self.DBuid, "error", f"URL 수집 실패 ({keyword}): {e}")
            return []

    async def collectArticle(self, session, cafeURL):
        try:
            articleID = self.extractArticleID(cafeURL)
            cafeID = await self.extractCafeID(session, cafeURL)
            if not cafeID:
                return []
            artID = self.extractArt(cafeURL)

            api_url = "https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{}/articles/{}?query=&art={}&useCafeId=true&requestFrom=A".format(
                cafeID, articleID, artID
            )
            res = await RequestAsync(session, api_url)
            res.raise_for_status()
            bs = BeautifulSoup(res.text, "html.parser")
            json_string = self.escape_content_html(bs.text)

            try:
                temp = json.loads(json_string)
                cafe_name = temp["result"]["cafe"]["name"]
                memberCount = temp["result"]["cafe"]["memberCount"]
                writer = temp["result"]["article"]["writer"]["nick"]
                title = re.sub(
                    r"[^\w\s가-힣]", "", temp["result"]["article"]["subject"]
                )
                text = (
                    " ".join(
                        BeautifulSoup(
                            temp["result"]["article"]["contentHtml"], "html.parser"
                        )
                        .get_text()
                        .split()
                    )
                    .replace("\\n", "")
                    .replace("\\t", "")
                    .replace("\u200b", "")
                    .replace("\\", "")
                )
                date = self.extractTime(int(temp["result"]["article"]["writeDate"]))
                readCount = temp["result"]["article"]["readCount"]
                commentCount = temp["result"]["article"]["commentCount"]
                articleData = [
                    cafe_name,
                    memberCount,
                    writer,
                    title,
                    text,
                    date,
                    readCount,
                    commentCount,
                    cafeURL,
                ]

            except Exception as e:
                logger.info(f"Error occurred while extracting cafe article data: {e}")
                return []

            return (articleData, cafeID)

        except Exception as e:
            logger.info(f"Error occurred while collecting cafe article: {e}")
            appendCrawlLog(self.DBuid, "error", f"카페 본문 수집 실패 ({cafeURL}): {e}")
            return []

    async def collectCmt(self, session, cafeURL, cafeID):
        returnData = {"replyList": [], "replyCnt": 0}
        try:
            articleID = self.extractArticleID(cafeURL)
            artID = self.extractArt(cafeURL)

            replyList = []
            page = 1
            reply_idx = 1

            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "ko-KR,ko;q=0.9",
                "origin": "https://cafe.naver.com",
                "referer": cafeURL,
                "x-cafe-product": "pc",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            }

            while True:
                if self.running == False:
                    break

                api_url = "https://article.cafe.naver.com/gw/v4/cafes/{}/articles/{}/comments/pages/{}?requestFrom=A&orderBy=asc&art={}".format(
                    cafeID, articleID, page, artID
                )
                res = await RequestAsync(session, api_url, headers=headers)
                res.raise_for_status()
                bs = BeautifulSoup(res.text, "html.parser")
                json_string = self.escape_content_html(bs.text)

                try:
                    temp = json.loads(json_string)
                    comment_json = temp["result"]["comments"]["items"]
                    if comment_json == []:
                        break
                except Exception as e:
                    logger.info(f"Error occurred while parsing cafe comment list: {e}")
                    break

                for comment in comment_json:
                    if comment.get("isDeleted", False):
                        continue
                    writer = comment["writer"]["nick"]
                    date = self.extractTime(comment["updateDate"])
                    content = (
                        comment["content"]
                        .replace("\n", " ")
                        .replace("\r", " ")
                        .replace("\t", " ")
                        .replace("<br>", "")
                    )
                    is_reply = comment.get("isRef", False)
                    if content != "":
                        replyList.append(
                            [reply_idx, writer, date, content, is_reply, cafeURL]
                        )
                        reply_idx += 1

                if len(comment_json) < 100:
                    break

                page += 1

            returnData["replyList"] = replyList
            returnData["replyCnt"] = len(replyList)
            return returnData

        except Exception as e:
            logger.info(f"Error occurred while collecting cafe comments: {e}")
            appendCrawlLog(self.DBuid, "error", f"댓글 수집 실패 ({cafeURL}): {e}")
            return returnData

    def reportStatus(self):
        return self.status

    async def _processOneUrl(self, session, semaphore, cafeUrl):
        async with semaphore:
            try:
                if self.running == False:
                    return

                result = await self.collectArticle(session, cafeUrl)
                if not result:
                    return

                articleData, cafeID = result
                self.status["articleCnt"] += 1
                article_day = articleData[5]

                if self.option == 2:
                    addToCSV(
                        self.DBPath,
                        self.articleDB,
                        [articleData],
                        navercafe_article_column,
                    )

                elif self.option == 1:
                    try:
                        cmtData = await self.collectCmt(session, cafeUrl, cafeID)

                        reply_cnt = cmtData.get("replyCnt", 0)
                        self.status["commentCnt"] += reply_cnt

                        addToCSV(
                            self.DBPath,
                            self.articleDB,
                            [articleData],
                            navercafe_article_column,
                        )

                        replies = cmtData.get("replyList", [])
                        if replies:
                            processed_replies = [r + [article_day] for r in replies]
                            addToCSV(
                                self.DBPath,
                                self.replyDB,
                                processed_replies,
                                navercafe_reply_column,
                            )

                    except Exception as e:
                        logger.info(
                            f"Error occurred while processing cafe comment data for {cafeUrl}: {e}"
                        )

            except Exception as e:
                logger.info(f"Error occurred while processing {cafeUrl}: {e}")
                appendCrawlLog(self.DBuid, "error", f"카페 처리 실패 ({cafeUrl}): {e}")

    def main(self):
        if not self.resuming:
            initCrawlLog(
                self.DBuid,
                (
                    f"User: {self.requester}\n"
                    f"Object: navercafe\n"
                    f"Option: {self.option}\n"
                    f"Keyword: {self.keyword}\n"
                    f"Date Range: {self.startDate} ~ {self.endDate}"
                ),
            )

            makeCSV(self.DBPath, self.articleDB, navercafe_article_column)
            if self.option == 1:
                makeCSV(self.DBPath, self.replyDB, navercafe_reply_column)
        else:
            appendCrawlLog(
                self.DBuid,
                "info",
                f"이어받기 시작: {self.currentDate.strftime('%Y-%m-%d')} ~ {self.endDate_form}",
            )

        for dayCount in range(self.date_range + 1):
            currentDate_str = self.currentDate.strftime("%Y%m%d")

            state = checkState(self.DBuid)
            if not state:
                logger.info(f"DB has been deleted. Terminating crawl: {self.DBname}")
                return
            elif state == "stopped":
                stopOperator(
                    DBpath=self.DBPath,
                    DBtype="navercafe",
                    DBname=self.DBname,
                    startTime=self.startTime,
                    userEmail=self.Email,
                    status=self.status,
                    DBuid=self.DBuid,
                    requester=self.requester,
                )
                return

            if dayCount == self.date_range:
                finishOperator(
                    DBpath=self.DBPath,
                    DBtype="navercafe",
                    DBname=self.DBname,
                    startTime=self.startTime,
                    userEmail=self.Email,
                    status=self.status,
                    DBuid=self.DBuid,
                    requester=self.requester,
                    resumePriorCounts=self.resumePriorCounts,
                )
                break

            if self.date_range > 0:
                percent = str(round(((dayCount + 1) / self.date_range) * 100, 1))
                self.status["percentage"] = percent
                self.status["currentdate"] = currentDate_str

            urlList = self.collectUrl(
                keyword=self.keyword, startDate=currentDate_str, endDate=currentDate_str
            )

            concurrency = speed_to_concurrency(self.speed)
            asyncio.run(run_with_concurrency(urlList, self._processOneUrl, concurrency))

            updateCrawlStatus(
                self.DBuid,
                self.status["percentage"] + "%",
                self.status["articleCnt"],
                self.status["commentCnt"],
                self.status["replyCnt"],
                currentDate_str,
            )

            self.currentDate += self.deltaD


def tester(
    name="최우철",
    startDate=str(20260301),
    endDate=str(20260305),
    keyword='"경찰대"',
    option=1,
    speed=1,
):
    NaverCafeCrawler_obj = NaverCafeCrawler(
        name, keyword, startDate, endDate, option, speed
    )
    NaverCafeCrawler_obj.main()


if __name__ == "__main__":
    tester()
