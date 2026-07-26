import time
import json
import re
import warnings
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import logging
from db import load_proxy_list, checkState, get_userinfo
from db.util import makeDBname
from config import SLEEP_TIME, PROXY
from common.req import Request, set_proxy_list
from common.storage import makeDB, updateCrawlStatus, initCrawlLog, appendCrawlLog
from common.csv import makeCSV, addToCSV
from common.columns import chinadaily_article_column
from common.controller import stopOperator, finishOperator

warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger(__name__)


class ChinaDailyCrawler:
    def __init__(self, requester, keyword, startDate, endDate, option, speed):

        if PROXY:
            proxy_list = load_proxy_list()
            set_proxy_list(proxy_list)

        self.DBname = makeDBname("chinadaily", keyword, startDate, endDate)
        self.requester = requester
        self.keyword = keyword
        self.startDate = startDate
        self.endDate = endDate
        self.option = option
        self.speed = speed

        self.articleDB = self.DBname + "_article"

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
        self.PushoverKey = notification["PushOver"]
        self.requesterUid = notification["userUid"]

        self.running = True
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
            DBtype="chinadaily",
            startdate=self.startDate,
            enddate=self.endDate,
            option=self.option,
            keyword=self.keyword,
            requester=self.requester,
            requesterUid=self.requesterUid,
        )

    # ── 유틸리티 ──────────────────────────────────────────────

    def _keywordParser(self, keyword):
        """키워드에서 +는 포함, -는 제외 조건 분리"""
        includeList = []
        excludeList = []

        parts = keyword.split("-")
        includeList.extend(parts[0].split("+"))

        if len(parts) > 1:
            excludeList.extend(parts[1].split("+"))

        return includeList, excludeList

    def _timeFormatter(self, date):
        date_obj = datetime.strptime(str(date), "%Y%m%d")
        return date_obj.strftime("%Y-%m-%d")

    def _escape_content_html(self, json_str):
        def escape_match(match):
            plain_text = match.group(2)
            escaped = (
                plain_text.replace("\\", "")
                .replace('"', "")
                .replace("\n", "")
                .replace("\r", "")
            )
            return match.group(1) + escaped

        json_str = re.sub(
            r'("plainText":\s?")(.*?)(?=",\s*")',
            escape_match,
            json_str,
            flags=re.DOTALL,
        )
        json_str = re.sub(
            r'("highlightContent":\s?")(.*?)(?=",\s*")',
            escape_match,
            json_str,
            flags=re.DOTALL,
        )
        return json_str

    # ── 수집 함수 ─────────────────────────────────────────────

    def collectArticle(self, keyword, startDate, endDate):
        """ChinaDaily 기사 직접 검색 및 수집 (URL 수집 단계 없음)"""
        try:
            includeList, excludeList = self._keywordParser(keyword)
            includeWord = "+".join(includeList).replace("&", "%26")
            excludeWord = "+".join(excludeList).replace("&", "%26")

            startDate_fmt = self._timeFormatter(startDate)
            endDate_fmt = self._timeFormatter(endDate)

            articleList = []
            page = 0
            base_url = "https://newssearch.chinadaily.com.cn/rest/en/search"

            while True:
                if not self.running:
                    break

                params = {
                    "publishedDateFrom": startDate_fmt,
                    "publishedDateTo": endDate_fmt,
                    "fullMust": includeWord,
                    "fullNot": excludeWord,
                    "channel": "",
                    "type": "",
                    "curType": "story",
                    "sort": "dp",
                    "duplication": "on",
                    "page": page,
                    "type[0]": "story",
                    "type[1]": "comment",
                    "type[2]": "blog",
                    "channel[0]": "2@cndy",
                    "channel[1]": "2@webnews",
                    "channel[2]": "2@bw",
                    "channel[3]": "2@hk",
                    "channel[4]": "ismp@cndyglobal",
                    "source": "",
                }

                referer_url = (
                    "https://newssearch.chinadaily.com.cn/en/search?cond="
                    "%7B%22publishedDateFrom%22%3A%22{}%22%2C%22publishedDateTo%22%3A%22{}%22"
                    "%2C%22fullMust%22%3A%22{}%22%2C%22fullNot%22%3A%22{}%22"
                    "%2C%22channel%22%3A%5B%222%40cndy%22%2C%222%40webnews%22%2C%222%40bw%22%2C%222%40hk%22%2C%22ismp%40cndyglobal%22%5D"
                    "%2C%22type%22%3A%5B%22story%22%2C%22comment%22%2C%22blog%22%5D"
                    "%2C%22curType%22%3A%22story%22%2C%22sort%22%3A%22dp%22%2C%22duplication%22%3A%22on%22%7D"
                    "&language=en&page={}"
                ).format(startDate_fmt, endDate_fmt, includeWord, excludeWord, page)

                try:
                    res = Request(base_url, params=params)
                    res.raise_for_status()
                except Exception as e:
                    logger.info(f"ChinaDaily 검색 요청 실패: {e}")
                    break

                try:
                    soup_text = BeautifulSoup(res.text, "html.parser").text
                    soup_text = self._escape_content_html(soup_text)
                    json_data = json.loads(soup_text)
                    contents = json_data["content"]

                    if not contents:
                        break

                    for content in contents:
                        source = content["source"]
                        title = content["title"]
                        text = content["plainText"]
                        date = content["pubDateStr"].split()[0]
                        theme = content["columnName"]
                        url = content["url"]
                        searchURL = referer_url

                        if text:
                            articleList.append(
                                [source, title, text, date, theme, url, searchURL]
                            )
                            self.status["articleCnt"] += 1

                    page += 1

                except Exception as e:
                    logger.info(f"ChinaDaily 검색 결과 파싱 실패 (page {page}): {e}")
                    page += 1

            return articleList

        except Exception as e:
            logger.info(f"Error occurred while collecting ChinaDaily articles: {e}")
            appendCrawlLog(
                self.DBuid, "error", f"ChinaDaily 기사 수집 실패 ({keyword}): {e}"
            )
            return []

    def reportStatus(self):
        return self.status

    def main(self):
        initCrawlLog(
            self.DBuid,
            (
                f"User: {self.requester}\n"
                f"Object: chinadaily\n"
                f"Option: {self.option}\n"
                f"Keyword: {self.keyword}\n"
                f"Date Range: {self.startDate} ~ {self.endDate}"
            ),
        )

        makeCSV(self.DBPath, self.articleDB, chinadaily_article_column)

        for dayCount in range(self.date_range + 1):
            currentDate_str = self.currentDate.strftime("%Y%m%d")

            state = checkState(self.DBuid)
            if not state:
                logger.info(f"DB has been deleted. Terminating crawl: {self.DBname}")
                return
            elif state == "stopped":
                stopOperator(
                    DBpath=self.DBPath,
                    DBtype="chinadaily",
                    DBname=self.DBname,
                    startTime=self.startTime,
                    pushoverKey=self.PushoverKey,
                    userEmail=self.Email,
                    status=self.status,
                    DBuid=self.DBuid,
                    requester=self.requester,
                )
                return

            if dayCount == self.date_range:
                finishOperator(
                    DBpath=self.DBPath,
                    DBtype="chinadaily",
                    DBname=self.DBname,
                    startTime=self.startTime,
                    pushoverKey=self.PushoverKey,
                    userEmail=self.Email,
                    status=self.status,
                    DBuid=self.DBuid,
                    requester=self.requester,
                )
                break

            if self.date_range > 0:
                percent = str(round(((dayCount + 1) / self.date_range) * 100, 1))
                self.status["percentage"] = percent
                self.status["currentdate"] = currentDate_str

            articleList = self.collectArticle(
                keyword=self.keyword, startDate=currentDate_str, endDate=currentDate_str
            )

            if articleList:
                addToCSV(
                    self.DBPath, self.articleDB, articleList, chinadaily_article_column
                )

            updateCrawlStatus(
                self.DBuid,
                self.status["percentage"] + "%",
                self.status["articleCnt"],
                self.status["commentCnt"],
                self.status["replyCnt"],
            )

            self.currentDate += self.deltaD
