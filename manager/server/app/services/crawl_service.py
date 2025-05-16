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
from multiprocessing import Pool, cpu_count
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


def replace_dates_in_filename(filename: str, new_start_date: str, new_end_date: str) -> str:
    pattern = r"_(\d{8})_(\d{8})_"
    return re.sub(pattern, f"_{new_start_date}_{new_end_date}_", filename)


def replace_keyword_in_name(name: str, new_keyword: str) -> str:
    parts = name.split('_')
    if len(parts) > 1:
        parts[1] = f"[{new_keyword}]"
    return '_'.join(parts)


def process_table(args):
    """
    Multiprocessing worker: fetches one table, applies filters, saves CSV, returns status message.
    """
    (
        tableName,
        idx,
        total,
        original_db_name,
        dateOption,
        start_date,
        end_date,
        start_date_formed,
        end_date_formed,
        filterOption,
        include_all,
        incl_words,
        excl_words,
        crawl_keyword,
        dbpath,
    ) = args

    # reconnect to MySQL in this process
    mysql_db.connectDB(original_db_name)

    # edit table name: dates and keyword
    edited = replace_dates_in_filename(
        tableName, start_date, end_date) if dateOption == 'part' else tableName
    edited = replace_keyword_in_name(edited, crawl_keyword)

    # load data
    if dateOption == 'part':
        df = mysql_db.TableToDataframeByDate(
            tableName, start_date_formed, end_date_formed)
    else:
        df = mysql_db.TableToDataframe(tableName)

    articleURLs = []
    statisticsURLs = []

    # article filtering
    if filterOption and 'article' in tableName:
        if 'token' not in tableName:
            cols = df.columns
            if include_all:
                if incl_words:
                    df = df[df['Article Text'].apply(
                        lambda c: all(w in str(c) for w in incl_words))]
                if excl_words:
                    df = df[df['Article Text'].apply(
                        lambda c: all(w not in str(c) for w in excl_words))]
            else:
                if incl_words:
                    df = df[df['Article Text'].apply(
                        lambda c: any(w in str(c) for w in incl_words))]
                if excl_words:
                    df = df[df['Article Text'].apply(
                        lambda c: any(w not in str(c) for w in excl_words))]
            if df.empty:
                df = pd.DataFrame(columns=cols)
            articleURLs = df['Article URL'].tolist()
        else:
            df = df[df['Article URL'].isin(articleURLs)]

    # statistics table
    if 'statistics' in tableName:
        if filterOption:
            df = df[df['Article URL'].isin(articleURLs)]
        statisticsURLs = df['Article URL'].tolist()
        save_dir = os.path.join(
            dbpath, 'token_data' if 'token' in tableName else '')
        os.makedirs(save_dir, exist_ok=True)
        df.to_csv(os.path.join(
            save_dir, f"{edited}.csv"), index=False, encoding='utf-8-sig')
        return f"[{idx+1}/{total}] '{edited}' 완료"

    # reply table filtering
    if 'reply' in tableName:
        if filterOption:
            df = df[df['Article URL'].isin(articleURLs)]

    # reply_statistics
    if 'reply' in tableName and statisticsURLs and 'navernews' in original_db_name:
        df = df[df['Article URL'].isin(statisticsURLs)]
        save_dir = os.path.join(
            dbpath, 'token_data' if 'token' in tableName else '')
        os.makedirs(save_dir, exist_ok=True)
        df.to_csv(os.path.join(
            save_dir, f"{edited}_statistics.csv"), index=False, encoding='utf-8-sig')
        return f"[{idx+1}/{total}] '{edited}_statistics' 완료"

    # other tables
    save_dir = os.path.join(
        dbpath, 'token_data' if 'token' in tableName else '')
    os.makedirs(save_dir, exist_ok=True)
    df.to_csv(os.path.join(
        save_dir, f"{edited}.csv"), index=False, encoding='utf-8-sig')

    # cleanup
    del df
    gc.collect()

    return f"[{idx+1}/{total}] '{edited}' 완료"


def saveCrawlDb(uid: str, saveOption: SaveCrawlDbOption):
    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    save_opts = saveOption.model_dump()
    crawlDb = crawlList_db.find_one({"uid": uid})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    original_db = crawlDb['name']
    pid = save_opts['pid']
    mysql_db.connectDB(original_db)

    temp_dir = os.path.join(os.path.dirname(__file__), '..', 'temp')
    send_message(pid, "DB에서 테이블 목록을 가져오는 중...")

    # get and sort tables
    tables = [t for t in sorted(
        mysql_db.showAllTable(original_db)) if 'info' not in t]
    tables = sorted(tables, key=lambda x: (
        'article' not in x, 'statistics' not in x, x))

    # date options
    dateOpt = save_opts['dateOption']
    start_date = save_opts.get('start_date', '')
    end_date = save_opts.get('end_date', '')
    if dateOpt == 'part':
        sd_form = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
        ed_form = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
    else:
        sd_form = ed_form = ''

    # build new db name
    kst_now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%m%d_%H%M")
    parts = original_db.split('_')
    parts[1] = f"[{crawlDb['keyword']}]"
    parts = parts[:-2] + kst_now.split('_')
    new_dbname = '_'.join(parts)

    # date-in-filename replacement if needed
    if dateOpt == 'part':
        new_dbname = replace_dates_in_filename(
            new_dbname, start_date, end_date)

    # filter options
    filtOpt = save_opts['filterOption']
    inc_all = save_opts.get('include_all', False)
    inc_words = save_opts.get('incl_words', [])
    exc_words = save_opts.get('excl_words', [])

    # create workspace
    dbpath = os.path.join(temp_dir, new_dbname)
    while True:
        try:
            os.makedirs(os.path.join(dbpath, 'token_data'), exist_ok=False)
            break
        except FileExistsError:
            dbpath += "_copy"

    # prepare multiprocessing args
    total_tables = len(tables)
    args_list = []
    for idx, tname in enumerate(tables):
        args_list.append((
            tname,
            idx,
            total_tables,
            original_db,
            dateOpt,
            start_date,
            end_date,
            sd_form,
            ed_form,
            filtOpt,
            inc_all,
            inc_words,
            exc_words,
            crawlDb['keyword'],
            dbpath,
        ))

    # process tables in parallel
    with Pool(cpu_count()) as pool:
        for status in pool.imap_unordered(process_table, args_list):
            send_message(pid, status)

    # zip and return response
    zip_path = shutil.make_archive(dbpath, "zip", root_dir=dbpath)
    filename = os.path.basename(zip_path)
    background = BackgroundTask(cleanup_folder_and_zip, dbpath, zip_path)
    return FileResponse(path=zip_path, media_type="application/zip", filename=filename, background=background)


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
