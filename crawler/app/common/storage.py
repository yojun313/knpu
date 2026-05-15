from datetime import datetime, timedelta, timezone
import time
import os
import uuid
import logging
from collections import OrderedDict

from config import CRAWL_DATA_PATH, CRAWL_LOG_PATH, CRAWLCOM
from db import crawler_db, add_userlog

logger = logging.getLogger(__name__)

crawlList_db = crawler_db["db-list"]
crawlLog_db = crawler_db["log-list"]


def makeDB(
    DBname, DBtype, startdate, enddate, option, keyword, requester, requesterUid
):
    DBpath = os.path.join(CRAWL_DATA_PATH, DBname)
    DBuid = str(uuid.uuid4())

    now_kst = (
        datetime.now(timezone.utc)
        .astimezone(timezone(timedelta(hours=9)))
        .strftime("%Y-%m-%d %H:%M")
    )

    doc = OrderedDict(
        [
            ("uid", DBuid),
            ("name", DBname),
            ("userUid", requesterUid),
            ("crawlOption", option),
            ("requester", requester),
            ("keyword", keyword),
            ("dbSize", 0),
            ("crawlCom", CRAWLCOM),
            ("crawlSpeed", 1),
            (
                "stat",
                {
                    "article": 0,
                    "cmt": 0,
                    "reply": 0,
                },
            ),
            ("startTime", now_kst),
            ("endTime", "진행 중"),
            ("percent", "0%"),
            ("status", "running"),
        ]
    )

    crawlList_db.insert_one(doc)
    logger.info(f"DB 레코드 생성: {DBname} (uid: {DBuid})")

    os.makedirs(DBpath, exist_ok=True)

    log_path = os.path.join(CRAWL_LOG_PATH, DBname + "_log.txt")
    os.makedirs(CRAWL_LOG_PATH, exist_ok=True)
    with open(log_path, "w+") as log:
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
        log.write(msg + "\n\n")

    add_userlog(requesterUid, DBname)

    return DBpath, DBuid


def updateCrawlStatus(DBuid, percent, articleCnt, replyCnt, rereplyCnt):
    try:
        folder = crawlList_db.find_one({"uid": DBuid})
        if not folder:
            return

        dbSize = 0
        folder_path = os.path.join(CRAWL_DATA_PATH, folder["name"])
        if os.path.exists(folder_path):
            dbSize = sum(
                os.path.getsize(os.path.join(folder_path, f))
                for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f))
            )

        crawlList_db.update_one(
            {"uid": DBuid},
            {
                "$set": {
                    "stat": {
                        "article": articleCnt,
                        "cmt": replyCnt,
                        "reply": rereplyCnt,
                    },
                    "dbSize": dbSize,
                    "percent": percent,
                }
            },
        )
    except Exception as e:
        logger.warning(f"진행률 업데이트 실패 (uid: {DBuid}): {e}")


def endCrawl(DBuid):
    try:
        now_kst = (
            datetime.now(timezone.utc)
            .astimezone(timezone(timedelta(hours=9)))
            .strftime("%Y-%m-%d %H:%M")
        )

        crawlList_db.update_one(
            {"uid": DBuid},
            {"$set": {"endTime": now_kst, "status": "completed"}},
        )
        logger.info(f"크롤링 완료 (uid: {DBuid})")
    except Exception as e:
        logger.warning(f"완료 상태 업데이트 실패 (uid: {DBuid}): {e}")


def stopCrawl(DBuid):
    try:
        now_kst = (
            datetime.now(timezone.utc)
            .astimezone(timezone(timedelta(hours=9)))
            .strftime("%Y-%m-%d %H:%M")
        )

        crawlList_db.update_one(
            {"uid": DBuid},
            {"$set": {"endTime": now_kst, "status": "stopped"}},
        )
        logger.info(f"크롤링 정지 (uid: {DBuid})")
    except Exception as e:
        logger.warning(f"정지 상태 업데이트 실패 (uid: {DBuid}): {e}")


def errorCrawl(DBuid):
    try:
        crawlList_db.update_one(
            {"uid": DBuid},
            {"$set": {"endTime": "에러 발생", "status": "error"}},
        )
        logger.info(f"크롤링 에러 처리 (uid: {DBuid})")
    except Exception as e:
        logger.warning(f"에러 상태 업데이트 실패 (uid: {DBuid}): {e}")


def _now_kst_str():
    return (
        datetime.now(timezone.utc)
        .astimezone(timezone(timedelta(hours=9)))
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def initCrawlLog(DBuid, message):
    try:
        crawlLog_db.update_one(
            {"uid": DBuid},
            {
                "$set": {
                    "uid": DBuid,
                    "logs": [
                        {"time": _now_kst_str(), "type": "start", "message": message}
                    ],
                }
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"로그 초기화 실패 (uid: {DBuid}): {e}")


def appendCrawlLog(DBuid, log_type, message):
    """log-list에 로그 항목 즉시 추가. log_type: 'error' | 'info' | 'end'"""
    try:
        crawlLog_db.update_one(
            {"uid": DBuid},
            {
                "$push": {
                    "logs": {
                        "time": _now_kst_str(),
                        "type": log_type,
                        "message": message,
                    }
                }
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"로그 추가 실패 (uid: {DBuid}): {e}")
