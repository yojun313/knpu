from datetime import datetime, timedelta, timezone
import time
import os
import uuid
import logging
from collections import OrderedDict

from config import CRAWL_DATA_PATH, CRAWL_LOG_PATH, CRAWLCOM
from db import crawler_db

logger = logging.getLogger(__name__)

crawlList_db = crawler_db['db-list']


def makeDB(DBname, DBtype, startdate, enddate, option, keyword, requester, requesterUid):
    DBpath = os.path.join(CRAWL_DATA_PATH, DBname)
    DBuid = str(uuid.uuid4())

    now_kst = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    ).strftime('%Y-%m-%d %H:%M')

    doc = OrderedDict([
        ("uid", DBuid),
        ("name", DBname),
        ("userUid", requesterUid),
        ("crawlOption", option),
        ("requester", requester),
        ("keyword", keyword),
        ("dbSize", 0),
        ("crawlCom", CRAWLCOM),
        ("crawlSpeed", 1),
        ("dataInfo", {
            "totalArticleCnt": 0,
            "totalReplyCnt": 0,
            "totalRereplyCnt": 0,
        }),
        ("startTime", now_kst),
        ("endTime", "0%"),
    ])

    crawlList_db.insert_one(doc)
    logger.info(f"DB 레코드 생성: {DBname} (uid: {DBuid})")

    os.makedirs(DBpath, exist_ok=True)

    log_path = os.path.join(CRAWL_LOG_PATH, DBname + '_log.txt')
    os.makedirs(CRAWL_LOG_PATH, exist_ok=True)
    with open(log_path, 'w+') as log:
        msg = (
            f"=======================================================================================================================================\n"
            f"{'User:':<15} {requester}\n"
            f"{'Object:':<15} {DBtype}\n"
            f"{'Option:':<15} {option}\n"
            f"{'Keyword:':<15} {keyword}\n"
            f"{'Date Range:':<15} {startdate} ~ {enddate}\n"
            f"{'Crawl Start:':<15} {datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M')}\n"
            f"{'Computer:':<15} {CRAWLCOM}\n"
            f"{'DB path:':<15} {DBpath}\n"
            f"=======================================================================================================================================\n"
        )
        log.write(msg + '\n\n')

    return DBpath, DBuid


def updateCrawlStatus(DBuid, percent, articleCnt, replyCnt, rereplyCnt):
    """크롤링 진행률 + 수집 건수를 DB에 직접 업데이트"""
    try:
        folder = crawlList_db.find_one({"uid": DBuid})
        if not folder:
            return

        dbSize = 0
        folder_path = os.path.join(CRAWL_DATA_PATH, folder['name'])
        if os.path.exists(folder_path):
            dbSize = sum(
                os.path.getsize(os.path.join(folder_path, f))
                for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f))
            )

        crawlList_db.update_one(
            {"uid": DBuid},
            {"$set": {
                "dataInfo": {
                    "totalArticleCnt": articleCnt,
                    "totalReplyCnt": replyCnt,
                    "totalRereplyCnt": rereplyCnt,
                },
                "dbSize": dbSize,
                "endTime": percent,
            }},
        )
    except Exception as e:
        logger.warning(f"진행률 업데이트 실패 (uid: {DBuid}): {e}")


def endCrawl(DBuid):
    """크롤링 정상 완료 → endTime에 현재 시각 기록"""
    try:
        now_kst = datetime.now(timezone.utc).astimezone(
            timezone(timedelta(hours=9))
        ).strftime('%Y-%m-%d %H:%M')

        crawlList_db.update_one(
            {"uid": DBuid},
            {"$set": {"endTime": now_kst}},
        )
        logger.info(f"크롤링 완료 (uid: {DBuid})")
    except Exception as e:
        logger.warning(f"완료 상태 업데이트 실패 (uid: {DBuid}): {e}")


def errorCrawl(DBuid):
    """크롤링 에러/중단 → endTime에 'X' 기록"""
    try:
        crawlList_db.update_one(
            {"uid": DBuid},
            {"$set": {"endTime": "X"}},
        )
        logger.info(f"크롤링 에러 처리 (uid: {DBuid})")
    except Exception as e:
        logger.warning(f"에러 상태 업데이트 실패 (uid: {DBuid}): {e}")
