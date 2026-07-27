import os
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from db import crawler_db, get_admin_discord_ids
from common.tokenization import tokenization
from common.notification import sendDiscordDM, notifyRequester
from common.storage import endCrawl, errorCrawl, appendCrawlLog
from config import CRAWL_LOG_PATH

logger = logging.getLogger(__name__)


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


def _admin_discord_recipients():
    """운영 가시성 목적으로 모든 크롤링 완료/중단을 항상 DM 받는 관리자 목록.
    요청자 본인에게는 별도로 notifyRequester()가 디스코드 우선/이메일 폴백을 처리한다."""
    return get_admin_discord_ids()


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

        sendDiscordDM(
            _admin_discord_recipients(), title + "\n" + text, requester=requester
        )
        notifyRequester(requester, userEmail, title, text)

        with open(os.path.join(CRAWL_LOG_PATH, DBname + "_log.txt"), "a") as log:
            log.write("\n\n" + text)

        if DBuid:
            appendCrawlLog(DBuid, "end", f"[크롤링 중단] {DBname}\n{text}")

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
        # "token_" 접두사가 붙은 파일은 이전 완료/중단 시점에 이미 생성된 토큰화 결과물이다
        # (이어받기로 같은 폴더에서 finishOperator/stopOperator가 두 번째로 실행되면 이 파일들도
        # .parquet로 남아있어, 걸러내지 않으면 원본 reply/rereply 테이블로 착각해 이미 컬럼이
        # 축소된 토큰화 파일을 다시 groupby하려다 KeyError("Article Day")로 죽는다).
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

            # 이어받기라면 resumePriorCounts에 기록된 기존 행 수 이후만 "새로 추가된
            # 부분"으로 취급해 증분 토큰화한다 — 단, 이건 그 기존 행들이 예전에 이미
            # 토큰화된 적이 있을 때만 맞는 얘기다(token 파일이 실제로 존재해야 함).
            # 에러/중단으로 죽어서 finishOperator를 한 번도 못 돌고 이어받은 경우엔
            # raw 데이터는 있어도 토큰 파일은 없으므로, 이 경우엔 prior_count를 무시하고
            # 처음부터(=raw 데이터 전체) 토큰화해야 누락이 없다.
            prior_count = (resumePriorCounts or {}).get(table_name, 0)
            if prior_count and not os.path.exists(token_file_path):
                prior_count = 0
            new_df = data_df.iloc[prior_count:].copy() if prior_count else data_df

            # Reply 관련 테이블이면 전처리 수행 (새로 추가된 행에 대해서만 그룹핑 —
            # 기존에 이미 그룹핑되어 토큰 파일에 들어간 기사와는 URL이 겹치지 않는다,
            # 같은 날짜를 두 번 크롤링하지 않기 때문)
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

        sendDiscordDM(
            _admin_discord_recipients(), title + "\n" + text, requester=requester
        )
        notifyRequester(requester, userEmail, title, text)

        with open(os.path.join(CRAWL_LOG_PATH, DBname + "_log.txt"), "a") as log:
            log.write("\n\n" + text)

        if DBuid:
            appendCrawlLog(DBuid, "end", f"[크롤링 완료] {DBname}\n{text}")
            endCrawl(DBuid)

    except Exception as e:
        logger.exception(f"finishOperator 실패: {DBname}")
