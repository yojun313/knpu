from app.db import crawlList_db, mysql_db, crawlLog_db, user_db
from app.libs.exceptions import ConflictException, NotFoundException
from app.models.crawl_model import CrawlDbCreateDto, CrawlLogCreateDto, SaveCrawlDbOption
from app.utils.mongo import clean_doc
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
    mysql_db.connectDB()
    mysql_db.dropDB(name)


def getCrawlDbList(sort_by: str, mine: int = 0, userUid: str = None):
    if mine == 1:
        user = user_db.find_one({"uid": userUid})
        username = user['name']

    # 1) Mongo 에서 모두 불러오기
    cursor = crawlList_db.find()
    crawlDbList = [clean_doc(d) for d in cursor]
    if not crawlDbList:
        raise NotFoundException("No CrawlDBs found")

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

        if mine == 1 and crawlDb['requester'] != username:
            continue

        # 상태 처리
        status = "Done"
        endt = crawlDb.get('endTime')
        if not endt:
            crawlDb['endTime'] = '크롤링 중'
            status = 'Working'
            activeCrawl += 1
        elif endt == 'X':
            crawlDb['endTime'] = '오류 중단'
            status = 'Error'
        crawlDb['status'] = status

        # dbSize 처리
        size = crawlDb.get('dbSize') or 0
        if float(size) == 0:
            mysql_db.connectDB(database_name=name)
            dbsize = mysql_db.showDBSize(name) or [0, 0]
            gb, mb = dbsize
            fullStorage += float(gb)
            crawlDb['dbSize'] = f"{mb} MB" if gb < 1 else f"{gb} GB"
        else:
            fullStorage += float(size)
            crawlDb['dbSize'] = f"{int(float(size)*1024)} MB" if float(
                size) < 1 else f"{size} GB"
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
        mysql_db.connectDB(database_name=crawlDb['name'])
        dbsize = mysql_db.showDBSize(crawlDb['name'])
        crawlDb['dbSize'] = dbsize

    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB retrieved", "data": clean_doc(crawlDb)},
    )


def updateCrawlDb(uid: str, dataInfo, error: bool = False):
    crawlDb = crawlList_db.find_one({"uid": uid})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    mysql_db.connectDB(database_name=crawlDb['name'])
    dbsize = mysql_db.showDBSize(crawlDb['name'])[0]
    data_info_dict = dataInfo.model_dump()

    if error:
        result = crawlList_db.update_one(
            {"uid": uid},
            {"$set": {"dataInfo": data_info_dict, "endTime": 'X', "dbSize": dbsize}},
        )

    now_kst = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    ).strftime('%Y-%m-%d %H:%M')

    result = crawlList_db.update_one(
        {"uid": uid},
        {"$set": {"dataInfo": data_info_dict, "endTime": now_kst, "dbSize": dbsize}},
    )

    if result.matched_count == 0:
        raise NotFoundException("CrawlDB not found")

    return JSONResponse(
        status_code=200,
        content={
            "message": "CrawlDB updated",
        },
    )


def saveCrawlDb(uid: str, saveOption: SaveCrawlDbOption):
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

    pid = saveOption['pid']

    mysql_db.connectDB(targetDB)

    temp_directory = os.path.join(os.path.dirname(__file__), '..', 'temp')

    send_message(pid, f"DB에서 테이블 목록을 가져오는 중...")

    tableList = [table for table in sorted(
        mysql_db.showAllTable(targetDB)) if 'info' not in table]
    tableList = sorted(tableList, key=lambda x: (
        'article' not in x, 'statistics' not in x, x))

    def replace_dates_in_filename(filename, new_start_date, new_end_date):
        pattern = r"_(\d{8})_(\d{8})_"
        new_filename = re.sub(
            pattern, f"_{new_start_date}_{new_end_date}_", filename)
        return new_filename

    def replace_keyword_in_name(name: str, new_keyword: str) -> str:
        if 'token' in name:
            parts = name.split('_')
            parts[2] = f"[{new_keyword}]"  # 키워드만 대괄호 포함 교체
        else:
            parts = name.split('_')
            parts[1] = f"[{new_keyword}]"  # 키워드만 대괄호 포함 교체
        return '_'.join(parts)

    # 현재 시각
    kst_now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%m%d_%H%M")

    # targetDB 구조 예시:
    parts = targetDB.split('_')[:-2] + kst_now.split('_')
    dbname = '_'.join(parts)
    dbname = replace_keyword_in_name(dbname, crawlDb['keyword'])

    dateOption = saveOption['dateOption']
    filterOption = saveOption['filterOption']

    if dateOption == 'part':
        start_date = saveOption['start_date']
        end_date = saveOption['end_date']
        start_date_formed = datetime.strptime(
            start_date, "%Y%m%d").strftime("%Y-%m-%d")
        end_date_formed = datetime.strptime(
            end_date, "%Y%m%d").strftime("%Y-%m-%d")
        dbname = replace_dates_in_filename(
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
        edited_tableName = replace_dates_in_filename(
            tableName, start_date, end_date) if dateOption == 'part' else tableName
        edited_tableName = replace_keyword_in_name(
            edited_tableName, crawlDb['keyword'])

        send_message(
            pid, f"[{idx+1}/{len(tableList)}] '{edited_tableName}' 처리 중")

        if saveOption['dateOption'] == 'part':
            tableDF = mysql_db.TableToDataframeByDate(
                tableName, start_date_formed, end_date_formed)
        else:
            tableDF = mysql_db.TableToDataframe(tableName)

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

    zip_path = os.path.join(dbpath, f"{os.path.basename(dbpath)}.zip")
    # 완전 무압축으로 최대 속도를 원하면 ZIP_STORED 사용
    # 혹은 최소 압축(최고 속도)을 원하면 ZIP_DEFLATED + compresslevel=1
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_STORED) as zf:
        for root, dirs, files in os.walk(dbpath):
            for fname in files:
                full_path = os.path.join(root, fname)
                # 아카이브 내 경로는 dbpath 기준 상대경로로
                rel_path = os.path.relpath(full_path, dbpath)
                zf.write(full_path, rel_path)
                
    filename = os.path.basename(zip_path)  # 여기에 한글이 섞여 있어도 OK

    background_task = BackgroundTask(cleanup_folder_and_zip, dbpath, zip_path)
    # 4) FileResponse에 filename= 으로 넘기기
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

    targetDB = crawlDb['name']
    mysql_db.connectDB(targetDB)
    tableNameList = mysql_db.showAllTable(targetDB)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for tableName in tableNameList:
            if 'info' in tableName or 'token' in tableName:
                continue
            df_start = mysql_db.TableToDataframe(tableName, ":50")
            df_end = mysql_db.TableToDataframe(tableName, ":-50")
            df = pd.concat([df_start, df_end])
            df = df.drop(columns=['id'])

            # DataFrame을 BytesIO로 Parquet으로 저장
            df_buffer = BytesIO()
            df.to_parquet(df_buffer, index=False)
            df_buffer.seek(0)

            # ZIP에 저장
            zip_file.writestr(f"{tableName}.parquet", df_buffer.read())

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=preview_data.zip"}
    )
