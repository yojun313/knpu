from datetime import datetime, timedelta, timezone
import time
import os
import uuid
import logging
from collections import OrderedDict

import pandas as pd

from config import CRAWL_DATA_PATH, CRAWL_LOG_PATH, CRAWLCOM
from db import crawler_db, add_userlog
from db.util import makeDBname

logger = logging.getLogger(__name__)

crawlList_db = crawler_db["db-list"]
crawlLog_db = crawler_db["log-list"]


def makeDB(
    DBname,
    DBtype,
    startdate,
    enddate,
    option,
    keyword,
    requester,
    requesterUid,
    crawlObject=None,
    speed=1,
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
            ("crawlObject", crawlObject),
            ("crawlOption", option),
            ("requester", requester),
            ("keyword", keyword),
            ("startDate", startdate),
            ("endDate", enddate),
            ("dbSize", 0),
            ("crawlCom", CRAWLCOM),
            ("crawlSpeed", speed),
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


def updateCrawlStatus(
    DBuid, percent, articleCnt, replyCnt, rereplyCnt, currentDateStr=None
):
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

        update = {
            "stat": {
                "article": articleCnt,
                "cmt": replyCnt,
                "reply": rereplyCnt,
            },
            "dbSize": dbSize,
            "percent": percent,
        }
        # 방금 완료한 날짜(구간)를 기록해둔다 — 이어받기 기능이 "어디까지 크롤링했는지" 판단하는
        # 유일한 근거이므로(reportStatus()의 currentdate는 프로세스가 죽으면 함께 사라진다).
        if currentDateStr:
            update["lastCrawledDate"] = currentDateStr

        crawlList_db.update_one({"uid": DBuid}, {"$set": update})
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


def getResumeContext(DBuid):
    doc = crawlList_db.find_one({"uid": DBuid})
    if not doc:
        raise ValueError(f"크롤링 작업을 찾을 수 없습니다: {DBuid}")
    if doc.get("status") not in ("stopped", "error", "completed"):
        raise ValueError("중단·에러·완료된 작업만 이어받기할 수 있습니다")
    if not doc.get("startDate") or not doc.get("endDate"):
        raise ValueError(
            "이어받기에 필요한 정보가 없는 예전 작업입니다 (날짜 정보 없음)"
        )
    return doc


def getResumeDBPath(DBname):
    return os.path.join(CRAWL_DATA_PATH, DBname)


def computeResumeStartDate(doc):
    lastDate = doc.get("lastCrawledDate")
    if lastDate:
        d = datetime.strptime(lastDate, "%Y%m%d").date() + timedelta(days=1)
        return d.strftime("%Y%m%d")
    return doc["startDate"]


def validateResumeRange(startDate, endDate):
    s = datetime.strptime(startDate, "%Y%m%d").date()
    e = datetime.strptime(endDate, "%Y%m%d").date()
    if e < s:
        raise ValueError(
            f"종료일({endDate})이 이어받기 시작일({startDate})보다 빠릅니다. "
            f"더 늦은 날짜를 종료일로 입력해주세요."
        )


def restoreCsvFromParquet(DBpath, tableNames):
    for name in tableNames:
        parquet_path = os.path.join(DBpath, f"{name}.parquet")
        csv_path = os.path.join(DBpath, f"{name}.csv")
        if os.path.exists(parquet_path) and not os.path.exists(csv_path):
            df = pd.read_parquet(parquet_path)
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            os.remove(parquet_path)
            logger.info(f"이어받기: {name}.parquet → {name}.csv 복원")


def countExistingRows(DBpath, tableNames):
    counts = {}
    for name in tableNames:
        csv_path = os.path.join(DBpath, f"{name}.csv")
        if not os.path.exists(csv_path):
            counts[name] = 0
            continue
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                counts[name] = max(0, sum(1 for _ in f) - 1)  # 헤더 제외
        except Exception as e:
            logger.warning(f"기존 행 수 계산 실패 ({name}): {e}")
            counts[name] = 0
    return counts


def renameForResume(DBuid, DBtype, keyword, originalStartDate, newEndDate, oldDBname):
    newDBname = makeDBname(DBtype, keyword, originalStartDate, newEndDate)
    if newDBname == oldDBname:
        return oldDBname

    oldPath = os.path.join(CRAWL_DATA_PATH, oldDBname)
    newPath = os.path.join(CRAWL_DATA_PATH, newDBname)

    try:
        if os.path.isdir(oldPath):
            for fname in os.listdir(oldPath):
                if oldDBname in fname:
                    new_fname = fname.replace(oldDBname, newDBname)
                    os.rename(
                        os.path.join(oldPath, fname),
                        os.path.join(oldPath, new_fname),
                    )
            os.rename(oldPath, newPath)

        old_log = os.path.join(CRAWL_LOG_PATH, oldDBname + "_log.txt")
        new_log = os.path.join(CRAWL_LOG_PATH, newDBname + "_log.txt")
        if os.path.exists(old_log):
            os.rename(old_log, new_log)

        crawlList_db.update_one({"uid": DBuid}, {"$set": {"name": newDBname}})
        logger.info(f"이어받기 리네임: {oldDBname} → {newDBname}")
    except Exception as e:
        logger.warning(f"이어받기 리네임 실패 ({oldDBname} → {newDBname}): {e}")
        return oldDBname

    return newDBname


def beginResume(DBuid, newEndDate=None):
    update = {"status": "running", "endTime": "진행 중"}
    if newEndDate:
        update["endDate"] = newEndDate
    crawlList_db.update_one({"uid": DBuid}, {"$set": update})
    logger.info(f"크롤링 이어받기 시작 (uid: {DBuid}, newEndDate: {newEndDate})")


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
