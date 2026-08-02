import os
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from db import crawler_db, get_userinfo, user_logs_db, get_admin_discord_ids
from common.tokenization import tokenization
from common.notification import notifyRequester, notifyRequesterAndAdmins
from common.storage import endCrawl, errorCrawl, appendCrawlLog
from config import CRAWL_LOG_PATH
from shared.user_log import insert_log

logger = logging.getLogger(__name__)


class IPBlockedException(Exception):
    pass


def is_ip_blocked_error(e: Exception) -> bool:
    response = getattr(e, "response", None)
    return response is not None and getattr(response, "status_code", None) == 403


def notifyIpBlocked(DBname, keyword, requester, userEmail, DBuid=None):
    title = "🚫 [IP 차단] 크롤링 중단 - " + DBname
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = (
        f"\nNaver가 요청을 거부했습니다(403 Forbidden) — 서버 IP가 차단됐을 가능성이 높습니다."
        f"\n프록시/서버 IP 업데이트가 필요합니다."
        f"\n\n검색어: {keyword}"
        f"\n중단 시각: {now_str}"
    )
    try:
        notifyRequesterAndAdmins(
            requester, userEmail, title, text, get_admin_discord_ids()
        )
    except Exception:
        logger.exception(f"IP 차단 알림 전송 실패: {DBname}")

    if DBuid:
        try:
            appendCrawlLog(DBuid, "error", f"{title}\n{text}")
        except Exception:
            logger.warning(f"IP 차단 크롤 로그 기록 실패: {DBuid}")


def _requester_uid(requester):
    info = get_userinfo(requester) if requester else None
    return info["userUid"] if info else None


def convertToParquet(folder_path):
    try:
        if not os.path.exists(folder_path):
            print(f"경로가 존재하지 않습니다: {folder_path}")
            return

        file_list = os.listdir(folder_path)
        csv_files = [f for f in file_list if f.lower().endswith(".csv")]

        if not csv_files:
            print("CSV 파일이 없습니다.")
            return

        for csv_file in csv_files:
            csv_path = os.path.join(folder_path, csv_file)
            parquet_path = os.path.join(
                folder_path, csv_file.rsplit(".", 1)[0] + ".parquet"
            )
            try:
                df = pd.read_csv(csv_path)
                df.to_parquet(parquet_path, index=False)
                os.remove(csv_path)  # 변환 성공 후 원본 CSV 삭제
            except Exception as e:
                print(f"변환 실패: {csv_file} → 오류: {e}")
    except Exception as e:
        logger.exception(f"convertToParquet 실패: {folder_path}")


def stopOperator(
    DBpath,
    DBtype,
    DBname,
    startTime,
    userEmail,
    status,
    DBuid=None,
    requester=None,
):
    try:
        job_col = crawler_db["job-queue"]
        job_col.update_one(
            {"db_uid": DBuid},
            {"$set": {"state": "stopped", "finished_at": datetime.now()}},
        )

        convertToParquet(DBpath)
        parquet_files = [
            f
            for f in os.listdir(DBpath)
            if f.endswith(".parquet") and not f.startswith("token_")
        ]
        for file_name in parquet_files:
            table_name = file_name.rsplit(".", 1)[0]
            file_path = os.path.join(DBpath, file_name)
            data_df = pd.read_parquet(file_path)

            # Reply 관련 테이블이면 전처리 수행
            if "reply" in table_name or "rereply" in table_name:
                date_column = (
                    "Rereply Date" if "rereply" in table_name else "Reply Date"
                )
                text_column = (
                    "Rereply Text" if "rereply" in table_name else "Reply Text"
                )

                data_df[date_column] = pd.to_datetime(
                    data_df[date_column], errors="coerce"
                ).dt.date
                data_df[text_column] = data_df[text_column].fillna("")

                grouped = data_df.groupby("Article URL")
                data_df = grouped.agg(
                    {text_column: lambda x: " ".join(x), "Article Day": "first"}
                ).reset_index()

                data_df = data_df.rename(columns={"Article Day": date_column})
                data_df = data_df.sort_values(by=date_column)

        title = "[크롤링 중단] " + DBname

        starttime = datetime.fromtimestamp(startTime).strftime("%Y-%m-%d %H:%M")
        endtime = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M")
        crawltime = str(timedelta(seconds=int(time.time() - startTime)))

        text = f"\n크롤링 시작 : {starttime}"
        text += f"\n크롤링 종료 : {endtime}"
        text += f"\n소요시간 : {crawltime}\n"
        text += f"\n완료율 : {status.get('percentage', 'N/A')}%"
        text += f"\n수집된 기사 수 : {status.get('articleCnt', 'N/A')}"
        text += f"\n수집된 댓글 수 : {status.get('commentCnt', 'N/A')}"
        text += f"\n수집된 대댓글 수 : {status.get('replyCnt', 'N/A')}"

        notifyRequester(requester, userEmail, title, text)

        with open(os.path.join(CRAWL_LOG_PATH, DBname + "_log.txt"), "a") as log:
            log.write("\n\n" + text)

        if DBuid:
            appendCrawlLog(DBuid, "end", f"[크롤링 중단] {DBname}\n{text}")

        insert_log(
            user_logs_db,
            _requester_uid(requester),
            "crawler.crawl.stop",
            "crawler",
            message=f"크롤링 중단: {DBname}",
            target={"type": "crawl_db", "id": DBuid, "name": DBname},
            metadata={
                "percentage": status.get("percentage"),
                "articleCnt": status.get("articleCnt"),
            },
        )

    except Exception as e:
        logger.exception(f"stopOperator 실패: {DBname}")


def finishOperator(
    DBpath,
    DBtype,
    DBname,
    startTime,
    userEmail,
    status,
    DBuid=None,
    requester=None,
    resumePriorCounts=None,
):
    try:
        convertToParquet(DBpath)
        parquet_files = [
            f
            for f in os.listdir(DBpath)
            if f.endswith(".parquet") and not f.startswith("token_")
        ]

        if DBuid and parquet_files:
            appendCrawlLog(DBuid, "info", "토큰화 중...")

        for file_name in parquet_files:
            table_name = file_name.rsplit(".", 1)[0]
            file_path = os.path.join(DBpath, file_name)

            data_df = pd.read_parquet(file_path)

            token_file_path = os.path.join(DBpath, f"token_{table_name}.parquet")

            prior_count = (resumePriorCounts or {}).get(table_name, 0)
            if prior_count and not os.path.exists(token_file_path):
                prior_count = 0
            new_df = data_df.iloc[prior_count:].copy() if prior_count else data_df

            if len(new_df) and ("reply" in table_name or "rereply" in table_name):
                date_column = (
                    "Rereply Date" if "rereply" in table_name else "Reply Date"
                )
                text_column = (
                    "Rereply Text" if "rereply" in table_name else "Reply Text"
                )

                new_df[date_column] = pd.to_datetime(
                    new_df[date_column], errors="coerce"
                ).dt.date
                new_df[text_column] = new_df[text_column].fillna("")

                grouped = new_df.groupby("Article URL")
                new_df = grouped.agg(
                    {text_column: lambda x: " ".join(x), "Article Day": "first"}
                ).reset_index()

                new_df = new_df.rename(columns={"Article Day": date_column})
                new_df = new_df.sort_values(by=date_column)

            # Tokenization (새로 추가된 부분만)
            if len(new_df):
                lang = "en" if DBtype in ["chinadaily"] else "ko"
                new_token_df = tokenization(new_df, language=lang)

                for col in new_token_df.columns:
                    if new_token_df[col].apply(lambda x: isinstance(x, list)).any():
                        new_token_df[col] = new_token_df[col].apply(
                            lambda x: (
                                " ".join(map(str, x)) if isinstance(x, list) else x
                            )
                        )
            else:
                new_token_df = new_df

            if prior_count and os.path.exists(token_file_path):
                old_token_df = pd.read_parquet(token_file_path)
                combined_token_df = pd.concat(
                    [old_token_df, new_token_df], ignore_index=True
                )
            else:
                combined_token_df = new_token_df

            combined_token_df.to_parquet(token_file_path, index=False)

        title = "[크롤링 완료] " + DBname

        starttime = datetime.fromtimestamp(startTime).strftime("%Y-%m-%d %H:%M")
        endtime = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M")
        crawltime = str(timedelta(seconds=int(time.time() - startTime)))

        text = f"\n크롤링 시작 : {starttime}"
        text += f"\n크롤링 종료 : {endtime}"
        text += f"\n소요시간 : {crawltime}\n"
        text += f"\n수집된 기사 수 : {status.get('articleCnt', 'N/A')}"
        text += f"\n수집된 댓글 수 : {status.get('commentCnt', 'N/A')}"
        text += f"\n수집된 대댓글 수 : {status.get('replyCnt', 'N/A')}"

        notifyRequester(requester, userEmail, title, text)

        with open(os.path.join(CRAWL_LOG_PATH, DBname + "_log.txt"), "a") as log:
            log.write("\n\n" + text)

        if DBuid:
            appendCrawlLog(DBuid, "end", f"[크롤링 완료] {DBname}\n{text}")
            endCrawl(DBuid)

        insert_log(
            user_logs_db,
            _requester_uid(requester),
            "crawler.crawl.finish",
            "crawler",
            message=f"크롤링 완료: {DBname}",
            target={"type": "crawl_db", "id": DBuid, "name": DBname},
            metadata={
                "articleCnt": status.get("articleCnt"),
                "commentCnt": status.get("commentCnt"),
                "replyCnt": status.get("replyCnt"),
            },
        )

    except Exception as e:
        logger.exception(f"finishOperator 실패: {DBname}")
