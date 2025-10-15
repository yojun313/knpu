from app.db import crawlList_db, crawlLog_db, user_db, crawldata_path
from app.libs.exceptions import ConflictException, NotFoundException
from app.models.crawl_model import CrawlDbCreateDto, CrawlLogCreateDto, SaveCrawlDbOption
from app.utils.mongo import clean_doc
from app.utils.getsize import getFolderSize
from fastapi.responses import JSONResponse
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from starlette.background import BackgroundTask
from zoneinfo import ZoneInfo
from fastapi.responses import StreamingResponse
from starlette.responses import FileResponse
from io import BytesIO
import pandas as pd
from app.libs.progress import send_message
from app.services.user_service import log_user
import time
import uuid
import os
import re
import gc
import zipfile
import shutil


def createCrawlDb(crawlDb: CrawlDbCreateDto):
    crawlDb_dict = crawlDb.model_dump()

    existing_crawlDb = crawlList_db.find_one({"name": crawlDb_dict["name"]})
    if existing_crawlDb:
        raise ConflictException("CrawlDB with this name already exists")

    ordered_dict = OrderedDict([("uid", str(uuid.uuid4()))])
    ordered_dict.update(crawlDb_dict)
    ordered_dict['dataInfo'] = {
        "totalArticleCnt": 0,
        "totalReplyCnt": 0,
        "totalRereplyCnt": 0
    }
    now_kst = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    ).strftime('%Y-%m-%d %H:%M')

    ordered_dict['startTime'] = now_kst
    ordered_dict['endTime'] = None

    crawlList_db.insert_one(ordered_dict)

    return JSONResponse(
        status_code=201,
        content={"message": "CrawlDB created",
                 "data": clean_doc(ordered_dict)},
    )


def createCrawlLog(crawlLog: CrawlLogCreateDto):
    crawlLog_dict = crawlLog.model_dump()

    existing_crawlLog = crawlLog_db.find_one({"uid": crawlLog_dict["uid"]})
    if existing_crawlLog:
        raise ConflictException("CrawlLog with this uid already exists")

    dict = {
        'uid': crawlLog_dict['uid'],
        'content': crawlLog_dict['content'],
    }

    crawlLog_db.insert_one(dict)

    return JSONResponse(
        status_code=201,
        content={"message": "CrawlLog created",
                 "data": clean_doc(crawlLog_dict)},
    )


def deleteCrawlDb(uid: str):
    crawlDb = crawlList_db.find_one({"uid": uid})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    result = crawlList_db.delete_one({"uid": uid})
    task = BackgroundTask(deleteCrawlDbBg, crawlDb['name'])

    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB deleted"},
        background=task,
    )


def deleteCrawlDbBg(name: str):
    folder_path = os.path.join(crawldata_path, name)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)


def getCrawlDbList(sort_by: str, mine: int = 0, userUid: str = None):
    user = user_db.find_one({"uid": userUid})
    username = user['name']

    # 1) Mongo 에서 모두 불러오기
    cursor = crawlList_db.find()
    crawlDbList = [clean_doc(d) for d in cursor]
    if not crawlDbList:
        crawlDbList = []

    fullStorage = 0
    activeCrawl = 0

    filteredList = []
    # 2) 각 doc 가공
    for crawlDb in crawlDbList:
        name = crawlDb["name"]
        parts = name.split('_')
        typ = parts[0]
        match typ:
            case 'navernews':  crawlType = 'Naver News'
            case 'naverblog':  crawlType = 'Naver Blog'
            case 'navercafe':  crawlType = 'Naver Cafe'
            case 'youtube':    crawlType = 'YouTube'
            case _:            crawlType = typ

        crawlDb['crawlType'] = crawlType
        crawlDb['startDate'] = parts[2]
        crawlDb['endDate'] = parts[3]
        crawlDb['crawlOption'] = str(crawlDb['crawlOption'])
        crawlDb['crawlSpeed'] = str(crawlDb['crawlSpeed'])
        
        if username != 'admin' and crawlDb['requester'] == 'admin':
            continue

        if mine == 1 and crawlDb['requester'] != username:
            continue

        # 상태 처리
        status = "Done"
        endt = crawlDb.get('endTime')
        if "%" in endt:
            crawlDb['endTime'] = endt
            status = 'Working'
            activeCrawl += 1
        elif endt == 'X':
            crawlDb['endTime'] = '오류 중단'
            status = 'Error'
        crawlDb['status'] = status

        # dbSize 처리
        size = crawlDb.get('dbSize') or 0
        if float(size) == 0:
            dbsize = getFolderSize(os.path.join(crawldata_path, name))
            gb, mb = dbsize
            fullStorage += float(gb)
            crawlDb['dbSize'] = f"{mb} MB" if gb < 1 else f"{gb} GB"
        else:
            fullStorage += float(size)
            crawlDb['dbSize'] = f"{int(float(size)*1024)} MB" if float(size) < 1 else f"{size} GB"
        filteredList.append(crawlDb)

    crawlDbList = filteredList

    # 3) 정렬
    if sort_by == "keyword":
        crawlDbList.sort(key=lambda d: d.get('keyword', '').replace('"', ''))
    elif sort_by == "starttime":
        def _key(d):
            st = d.get('startTime')
            # 문자열이면 파싱, datetime 이면 그대로, 아니면 최소값
            if isinstance(st, str):
                try:
                    return datetime.strptime(st, "%Y-%m-%d %H:%M")
                except:
                    return datetime.min
            if isinstance(st, datetime):
                return st
            return datetime.min
        crawlDbList.sort(key=_key, reverse=True)

    # 4) 응답
    return JSONResponse(
        status_code=200,
        content={
            "message": "CrawlDB list retrieved",
            "data": crawlDbList,
            "fullStorage": round(fullStorage, 1),
            "activeCrawl": activeCrawl
        },
    )


def getCrawlDbInfo(uid: str):
    crawlDb = crawlList_db.find_one({"uid": uid})

    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    if not crawlDb['dbSize']:
        dbsize = getFolderSize(os.path.join(crawldata_path, crawlDb['name']))
        crawlDb['dbSize'] = dbsize

    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB retrieved", "data": clean_doc(crawlDb)},
    )


def endCrawlDb(uid: str, error: bool = False):
    crawlDb = crawlList_db.find_one({"uid": uid})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    if error:
        result = crawlList_db.update_one(
            {"uid": uid},
            {"$set": {"endTime": 'X'}},
        )
    else:
        now_kst = datetime.now(timezone.utc).astimezone(
            timezone(timedelta(hours=9))
        ).strftime('%Y-%m-%d %H:%M')

        result = crawlList_db.update_one(
            {"uid": uid},
            {"$set": {"endTime": now_kst}},
        )

    if result.matched_count == 0:
        raise NotFoundException("CrawlDB not found")

    return JSONResponse(
        status_code=200,
        content={
            "message": "CrawlDB updated",
        },
    )


def updateCount(uid: str, dataInfo):
    crawlDb = crawlList_db.find_one({"uid": uid})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    dbsize = getFolderSize(os.path.join(crawldata_path, crawlDb['name']))[0]
    data_info_dict = dataInfo.model_dump()
    percent = data_info_dict['percent']
    
    del data_info_dict['percent']

    crawlList_db.update_one(
        {"uid": uid},
        {"$set": {"dataInfo": data_info_dict, "dbSize": dbsize, "endTime": percent}},
    )

    return JSONResponse(
        status_code=200,
        content={
            "message": "CrawlDB updated",
        },
    )


def saveCrawlDb(uid: str, saveOption: SaveCrawlDbOption, userUid: str):
    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        # 폴더와 ZIP 파일을 삭제
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    saveOption = saveOption.model_dump()
    crawlDb = crawlList_db.find_one({"uid": uid})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    targetDB = crawlDb['name']
    log_user(userUid, f"Requested to save crawl DB: {targetDB}")

    pid = saveOption['pid']

    temp_directory = os.path.join(os.path.dirname(__file__), '..', 'temp')
    
    time.sleep(1)
    send_message(pid, f"DB에서 테이블 목록을 가져오는 중...")
    localDbpath = os.path.join(crawldata_path, targetDB)

    tableList = [
        f[:-8] for f in os.listdir(localDbpath)
        if f.endswith('.parquet') and 'info' not in f
    ]

    # 정렬: article > statistics > 나머지
    tableList = sorted(tableList, key=lambda x: (
        'article' not in x, 'statistics' not in x, x
    ))

    def replaceDatesInFilename(filename, new_start_date, new_end_date):
        pattern = r"_(\d{8})_(\d{8})_"
        new_filename = re.sub(
            pattern, f"_{new_start_date}_{new_end_date}_", filename)
        return new_filename

    def replaceKeywordInFilename(name: str, new_keyword: str) -> str:
        parts = name.split('_')

        if 'token' in name:
            parts[2] = f"[{new_keyword}]"  # 키워드만 대괄호 포함 교체
        else:
            parts[1] = f"[{new_keyword}]"  # 키워드만 대괄호 포함 교체
        dbname = '_'.join(parts)

        replacements = {
            '\\': '＼',  # U+FF3C
            '/': '／',   # U+FF0F
            ':': '：',   # U+FF1A
            '*': '＊',   # U+FF0A
            '?': '？',   # U+FF1F
            '"': '＂',   # U+FF02
            '<': '＜',   # U+FF1C
            '>': '＞',   # U+FF1E
            '|': '¦',    # U+00A6
        }

        # 3) 매핑 테이블을 이용해 한 번에 replace
        for illegal, safe in replacements.items():
            dbname = dbname.replace(illegal, safe)

        return dbname

    # 현재 시각
    kst_now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%m%d_%H%M")

    # targetDB 구조 예시:
    parts = targetDB.split('_')[:-2] + kst_now.split('_')
    dbname = '_'.join(parts)
    dbname = replaceKeywordInFilename(dbname, crawlDb['keyword'])

    dateOption = saveOption['dateOption']
    filterOption = saveOption['filterOption']

    if dateOption == 'part':
        start_date = saveOption['start_date']
        end_date = saveOption['end_date']
        start_date_formed = datetime.strptime(
            start_date, "%Y%m%d").strftime("%Y-%m-%d")
        end_date_formed = datetime.strptime(
            end_date, "%Y%m%d").strftime("%Y-%m-%d")
        dbname = replaceDatesInFilename(
            dbname, saveOption['start_date'], saveOption['end_date'])
    if filterOption:
        include_all = saveOption['include_all']
        incl_words = saveOption['incl_words']
        excl_words = saveOption['excl_words']

        if saveOption['filename_edit']:
            inclexcl = 'all' if include_all else 'any'
            add_keyword = f"(+{','.join(incl_words)} _ -{','.join(excl_words)} _{inclexcl})"
            parts = dbname.split('_', 2)
            old_keyword = parts[1]
            parts[1] = old_keyword + add_keyword
            dbname = '_'.join(parts)

    dbpath = os.path.join(temp_directory, dbname)
    while True:
        try:
            os.makedirs(os.path.join(dbpath, 'token_data'), exist_ok=False)
            break
        except FileExistsError:
            dbpath += "_copy"

    for idx, tableName in enumerate(tableList):
        edited_tableName = replaceDatesInFilename(
            tableName, start_date, end_date) if dateOption == 'part' else tableName
        edited_tableName = replaceKeywordInFilename(
            edited_tableName, crawlDb['keyword'])

        send_message(
            pid, f"[{idx+1}/{len(tableList)}] '{edited_tableName}' 처리 중")

        parquet_path = os.path.join(localDbpath, f"{tableName}.parquet")
        tableDF = pd.read_parquet(parquet_path)

        # 날짜 필터링 (dateOption이 'part'일 경우)
        if saveOption.get('dateOption') == 'part':
            date_columns = ['Article Date', 'Reply Date', 'Rereply Date']

            for col in date_columns:
                if col in tableDF.columns:
                    tableDF[col] = pd.to_datetime(
                        tableDF[col], errors='coerce')
                    tableDF = tableDF[
                        (tableDF[col] >= start_date_formed) &
                        (tableDF[col] <= end_date_formed)
                    ]
                    break  # 첫 번째 매칭된 날짜 컬럼 기준으로 필터링 후 종료

        # 단어 필터링 옵션이 켜져있을 때
        if filterOption == True and 'article' in tableName:
            if 'token' not in tableName:
                recover_columns = tableDF.columns
                if include_all == True:
                    if incl_words != []:
                        tableDF = tableDF[tableDF['Article Text'].apply(
                            lambda cell: all(word in str(cell) for word in incl_words))]
                    if excl_words != []:
                        tableDF = tableDF[tableDF['Article Text'].apply(
                            lambda cell: all(word not in str(cell) for word in excl_words))]
                else:
                    if incl_words != []:
                        tableDF = tableDF[tableDF['Article Text'].apply(
                            lambda cell: any(word in str(cell) for word in incl_words))]
                    if excl_words != []:
                        tableDF = tableDF[tableDF['Article Text'].apply(
                            lambda cell: any(word not in str(cell) for word in excl_words))]

                if tableDF.empty:
                    tableDF = pd.DataFrame(columns=recover_columns)  # 기존 열만 유지
                articleURL = tableDF['Article URL'].tolist()
            else:
                tableDF = tableDF[tableDF['Article URL'].isin(articleURL)]

        # statistics 테이블 처리
        if 'statistics' in tableName:
            if filterOption == True:
                tableDF = tableDF[tableDF['Article URL'].isin(articleURL)]
            statisticsURL = tableDF['Article URL'].tolist()
            save_path = os.path.join(
                dbpath, 'token_data' if 'token' in tableName else '', f"{edited_tableName}.csv")
            tableDF.to_csv(save_path, index=False,
                           encoding='utf-8-sig', header=True)
            continue

        if 'reply' in tableName:
            if filterOption == True:
                tableDF = tableDF[tableDF['Article URL'].isin(articleURL)]

        # reply_statistics 테이블 처리
        if 'reply' in tableName and 'statisticsURL' in locals() and 'navernews' in targetDB:
            if filterOption == True:
                filteredDF = tableDF[tableDF['Article URL'].isin(articleURL)]
            filteredDF = tableDF[tableDF['Article URL'].isin(statisticsURL)]
            save_path = os.path.join(
                dbpath, 'token_data' if 'token' in tableName else '', f"{edited_tableName + '_statistics'}.csv")
            filteredDF.to_csv(save_path, index=False,
                              encoding='utf-8-sig', header=True)

        # 기타 테이블 처리
        save_dir = os.path.join(
            dbpath, 'token_data' if 'token' in tableName else '')

        tableDF.to_csv(os.path.join(
            save_dir, f"{edited_tableName}.csv"), index=False, encoding='utf-8-sig', header=True)
        tableDF = None
        gc.collect()
    
    send_message(pid, f"데이터 압축 중")

    zip_path = shutil.make_archive(dbpath, "zip", root_dir=dbpath)
    filename = os.path.basename(zip_path)  # 여기에 한글이 섞여 있어도 OK

    background_task = BackgroundTask(
        cleanup_folder_and_zip, dbpath, zip_path)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
        background=background_task,
    )


def previewCrawlDb(uid: str):
    crawlDb = crawlList_db.find_one({"uid": uid})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    target_folder = crawlDb['name']  # 이 이름이 곧 디렉토리명
    base_path = os.path.join(crawldata_path, target_folder)  # 경로에 맞게 수정

    if not os.path.exists(base_path):
        raise NotFoundException(f"폴더가 존재하지 않습니다: {base_path}")

    # 압축 버퍼 생성
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file in os.listdir(base_path):
            if "token" in file:
                continue

            file_path = os.path.join(base_path, file)
            try:
                if file.endswith('.parquet'):
                    df = pd.read_parquet(file_path)
                elif file.endswith('.csv'):
                    df = pd.read_csv(file_path, encoding='utf-8-sig')
                df_preview = pd.concat(
                    [df.head(50), df.tail(50)]).drop_duplicates()

                # ID 열 제거 (있을 경우)
                if 'id' in df_preview.columns:
                    df_preview = df_preview.drop(columns=['id'])

                # DataFrame을 BytesIO로 저장
                df_buffer = BytesIO()
                df_preview.to_parquet(df_buffer, index=False)
                df_buffer.seek(0)

                table_name = file.replace('.parquet', '')
                zip_file.writestr(f"{table_name}.parquet", df_buffer.read())

            except Exception as e:
                print(f"[경고] {file} 처리 실패: {e}")

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=preview_data.zip"}
    )