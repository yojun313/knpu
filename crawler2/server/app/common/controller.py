import os
import pandas as pd
from datetime import datetime, timedelta
import time
import logging

from common.tokenization import tokenization
from common.notification import sendMail, sendPushOver
from common.storage import endCrawl, errorCrawl, appendCrawlLog
from config import CRAWL_LOG_PATH

logger = logging.getLogger(__name__)


def convertToParquet(folder_path):
    try:
        if not os.path.exists(folder_path):
            print(f"경로가 존재하지 않습니다: {folder_path}")
            return

        file_list = os.listdir(folder_path)
        csv_files = [f for f in file_list if f.lower().endswith('.csv')]

        if not csv_files:
            print("CSV 파일이 없습니다.")
            return

        for csv_file in csv_files:
            csv_path = os.path.join(folder_path, csv_file)
            parquet_path = os.path.join(
                folder_path, csv_file.rsplit('.', 1)[0] + '.parquet')
            try:
                df = pd.read_csv(csv_path)
                df.to_parquet(parquet_path, index=False)
                os.remove(csv_path)  # 변환 성공 후 원본 CSV 삭제
            except Exception as e:
                print(f"변환 실패: {csv_file} → 오류: {e}")
    except Exception as e:
        logger.exception(f"convertToParquet 실패: {folder_path}")


def stopOperator(DBpath, DBtype, DBname, startTime, pushoverKey, userEmail, status, DBuid=None):
    try:
        convertToParquet(DBpath)
        parquet_files = [f for f in os.listdir(
            DBpath) if f.endswith('.parquet')]
        for file_name in parquet_files:
            table_name = file_name.rsplit('.', 1)[0]
            file_path = os.path.join(DBpath, file_name)
            data_df = pd.read_parquet(file_path)

            # Reply 관련 테이블이면 전처리 수행
            if 'reply' in table_name or 'rereply' in table_name:
                date_column = 'Rereply Date' if 'rereply' in table_name else 'Reply Date'
                text_column = 'Rereply Text' if 'rereply' in table_name else 'Reply Text'

                data_df[date_column] = pd.to_datetime(data_df[date_column], errors='coerce').dt.date
                data_df[text_column] = data_df[text_column].fillna('')

                grouped = data_df.groupby('Article URL')
                data_df = grouped.agg({
                    text_column: lambda x: ' '.join(x),
                    'Article Day': 'first'
                }).reset_index()

                data_df = data_df.rename(
                    columns={'Article Day': date_column})
                data_df = data_df.sort_values(by=date_column)

        title = '[크롤링 중단] ' + DBname

        starttime = datetime.fromtimestamp(
            startTime).strftime('%Y-%m-%d %H:%M')
        endtime = datetime.fromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M')
        crawltime = str(
            timedelta(seconds=int(time.time() - startTime)))

        text  = f"\n크롤링 시작 : {starttime}"
        text += f"\n크롤링 종료 : {endtime}"
        text += f"\n소요시간 : {crawltime}\n"
        text += f"\n완료율 : {status.get('percentage', 'N/A')}%"
        text += f"\n최종 수집일 : {status.get('currentdate', 'N/A')}"
        text += f"\n수집된 URL 수 : {status.get('urlCnt', 'N/A')}"
        text += f"\n수집된 기사 수 : {status.get('articleCnt', 'N/A')}"
        text += f"\n수집된 댓글 수 : {status.get('commentCnt', 'N/A')}"
        text += f"\n수집된 대댓글 수 : {status.get('replyCnt', 'N/A')}"

        if pushoverKey == 'n' or pushoverKey == None:
            sendMail(userEmail, title, text)
        else:
            sendPushOver(msg=title + '\n' + text,
                                user_key=pushoverKey)

        with open(os.path.join(CRAWL_LOG_PATH, DBname + '_log.txt'), 'a') as log:
            log.write('\n\n' + text)

        # DB 상태 업데이트: 중단 → endTime = 'X'
        if DBuid:
            appendCrawlLog(DBuid, "end", f"[크롤링 중단] {DBname}\n{text}")
            errorCrawl(DBuid)

    except Exception as e:
        logger.exception(f"stopOperator 실패: {DBname}")


def finishOperator(DBpath, DBtype, DBname, startTime, pushoverKey, userEmail, status, DBuid=None):
    try:
        convertToParquet(DBpath)
        parquet_files = [f for f in os.listdir(
            DBpath) if f.endswith('.parquet')]
        for file_name in parquet_files:
            table_name = file_name.rsplit('.', 1)[0]
            file_path = os.path.join(DBpath, file_name)

            data_df = pd.read_parquet(file_path)

            # Reply 관련 테이블이면 전처리 수행
            if 'reply' in table_name or 'rereply' in table_name:
                date_column = 'Rereply Date' if 'rereply' in table_name else 'Reply Date'
                text_column = 'Rereply Text' if 'rereply' in table_name else 'Reply Text'

                data_df[date_column] = pd.to_datetime(data_df[date_column], errors='coerce').dt.date
                data_df[text_column] = data_df[text_column].fillna('')

                grouped = data_df.groupby('Article URL')
                data_df = grouped.agg({
                    text_column: lambda x: ' '.join(x),
                    'Article Day': 'first'
                }).reset_index()

                data_df = data_df.rename(
                    columns={'Article Day': date_column})
                data_df = data_df.sort_values(by=date_column)

            # Tokenization
            lang = 'en' if DBtype in ['chinadaily'] else 'ko'
            token_df = tokenization(data_df, language=lang)

            for col in token_df.columns:
                if token_df[col].apply(lambda x: isinstance(x, list)).any():
                    token_df[col] = token_df[col].apply(lambda x: ' '.join(
                        map(str, x)) if isinstance(x, list) else x)

            token_file_path = os.path.join(
                DBpath, f"token_{table_name}.parquet")
            token_df.to_parquet(token_file_path, index=False)

        title = '[크롤링 완료] ' + DBname

        starttime = datetime.fromtimestamp(
            startTime).strftime('%Y-%m-%d %H:%M')
        endtime = datetime.fromtimestamp(
            time.time()).strftime('%Y-%m-%d %H:%M')
        crawltime = str(
            timedelta(seconds=int(time.time() - startTime)))

        text  = f"\n크롤링 시작 : {starttime}"
        text += f"\n크롤링 종료 : {endtime}"
        text += f"\n소요시간 : {crawltime}\n"
        text += f"\n완료율 : {status.get('percentage', 'N/A')}%"
        text += f"\n최종 수집일 : {status.get('currentdate', 'N/A')}"
        text += f"\n수집된 URL 수 : {status.get('urlCnt', 'N/A')}"
        text += f"\n수집된 기사 수 : {status.get('articleCnt', 'N/A')}"
        text += f"\n수집된 댓글 수 : {status.get('commentCnt', 'N/A')}"
        text += f"\n수집된 대댓글 수 : {status.get('replyCnt', 'N/A')}"

        if pushoverKey == 'n' or pushoverKey == None:
            sendMail(userEmail, title, text)
        else:
            sendPushOver(msg=title + '\n' + text,
                                user_key=pushoverKey)

        with open(os.path.join(CRAWL_LOG_PATH, DBname + '_log.txt'), 'a') as log:
            log.write('\n\n' + text)

        # DB 상태 업데이트: 완료 → endTime = 현재 시각
        if DBuid:
            appendCrawlLog(DBuid, "end", f"[크롤링 완료] {DBname}\n{text}")
            endCrawl(DBuid)

    except Exception as e:
        logger.exception(f"finishOperator 실패: {DBname}")
