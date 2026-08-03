from app.db import crawlList_db, crawlLog_db, user_db, crawldata_path
from app.libs.exceptions import ConflictException, NotFoundException, HTTPException
from app.models.crawl_model import (
    CrawlDbCreateDto,
    CrawlLogUpdateDto,
    SaveCrawlDbOption,
)
from app.utils.zip import fast_zip
from app.utils.getsize import getFolderSize, format_size
from app.utils.csv_export import (
    replaceDatesInFilename,
    replaceKeywordInFilename,
    apply_date_filter,
    apply_word_filter,
    process_table_task,
)
from fastapi.responses import JSONResponse
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from starlette.background import BackgroundTask
from zoneinfo import ZoneInfo
from fastapi.responses import StreamingResponse
from starlette.responses import FileResponse
from io import BytesIO
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd
import itertools
import multiprocessing
from system.progress import send_message
from app.services.user_service import log_user
import time
import uuid
import os
import gc
import zipfile
import shutil


def createCrawlDb(crawlDb: CrawlDbCreateDto):
    crawlDb_dict = crawlDb.model_dump()

    existing_crawlDb = crawlList_db.find_one({"name": crawlDb_dict["name"]}, {"_id": 0})
    if existing_crawlDb:
        raise ConflictException("CrawlDB with this name already exists")

    userUid = crawlDb_dict["userUid"]

    ordered_dict = OrderedDict([("uid", str(uuid.uuid4()))])
    ordered_dict.update(crawlDb_dict)
    ordered_dict["stat"] = {"article": 0, "cmt": 0, "reply": 0}
    now_kst = (
        datetime.now(timezone.utc)
        .astimezone(timezone(timedelta(hours=9)))
        .strftime("%Y-%m-%d %H:%M")
    )

    ordered_dict["startTime"] = now_kst
    ordered_dict["endTime"] = "0%"

    crawlList_db.insert_one(ordered_dict)
    if "_id" in ordered_dict:
        del ordered_dict["_id"]
    log_user(
        userUid,
        "manager.crawl_db.create",
        f"Created crawl DB: {crawlDb_dict['name']}",
        target={"type": "crawl_db", "id": crawlDb_dict["name"]},
    )

    return JSONResponse(
        status_code=201,
        content={"message": "CrawlDB created", "data": ordered_dict},
    )


def updateCrawlLog(crawlLog: CrawlLogUpdateDto):
    crawlLog_dict = crawlLog.model_dump()

    crawlLog_db.update_one(
        {"uid": crawlLog_dict["uid"]},
        {"$set": {"content": crawlLog_dict["content"]}},
        upsert=True,
    )

    return JSONResponse(
        status_code=201,
        content={
            "message": "CrawlLog updated/created",
        },
    )


def getCrawlLog(uid: str):
    # DB에서 uid로 crawlLog 검색
    crawlLog = crawlLog_db.find_one({"uid": uid}, {"_id": 0})

    if not crawlLog:
        raise NotFoundException("CrawlLog not found")

    return JSONResponse(
        status_code=200, content={"message": "CrawlLog fetched", "data": crawlLog}
    )


def deleteCrawlDb(uid: str, userUid: str):
    crawlDb = crawlList_db.find_one({"uid": uid}, {"_id": 0})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    targetDB = crawlDb["name"]
    log_user(
        userUid,
        "manager.crawl_db.delete_request",
        f"Deleted crawl DB: {targetDB}",
        target={"type": "crawl_db", "id": targetDB},
    )

    crawlList_db.delete_one({"uid": uid})
    crawlLog_db.delete_one({"uid": uid})

    task = BackgroundTask(deleteCrawlDbBg, crawlDb["name"])

    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB deleted"},
        background=task,
    )


def stopCrawlDb(uid: str, userUid: str):
    target_data = crawlList_db.find_one({"uid": uid})

    if not target_data:
        raise HTTPException(status_code=404, detail="DB를 찾을 수 없습니다.")

    if target_data.get("status") == "stopped":
        return JSONResponse(
            status_code=200, content={"message": "이미 중단된 작업입니다."}
        )

    result = crawlList_db.update_one({"uid": uid}, {"$set": {"status": "stopped"}})

    if result.modified_count > 0:
        target_name = target_data.get("name", "Unknown")
        log_user(
            userUid,
            "manager.crawl_db.stop_request",
            f"Stopped crawl DB: {target_name}",
            target={"type": "crawl_db", "id": target_name},
        )

        return JSONResponse(
            status_code=200,
            content={"message": f"'{target_name}' 크롤링이 중단되었습니다."},
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"message": "상태 업데이트에 실패했습니다."},
        )


def deleteCrawlDbBg(name: str):
    folder_path = os.path.join(crawldata_path, name)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)


def processDbInfo(crawlDb: dict):
    name = crawlDb["name"]
    parts = name.split("_")
    typ = parts[0]
    match typ:
        case "navernews":
            crawlType = "Naver News"
        case "naverblog":
            crawlType = "Naver Blog"
        case "navercafe":
            crawlType = "Naver Cafe"
        case "youtube":
            crawlType = "YouTube"
        case _:
            crawlType = typ

    crawlDb["crawlType"] = crawlType
    crawlDb["startDate"] = crawlDb["startDate"]
    crawlDb["endDate"] = crawlDb["endDate"]
    crawlDb["crawlOption"] = str(crawlDb["crawlOption"])
    crawlDb["crawlSpeed"] = str(crawlDb["crawlSpeed"])

    # 상태 처리
    if crawlDb["status"] == "completed":
        crawlDb["status"] = "Done"
    elif crawlDb["status"] == "error":
        crawlDb["status"] = "Error"
    elif crawlDb["status"] == "stopped":
        crawlDb["status"] = "Stop"
    elif crawlDb["status"] == "running":
        crawlDb["status"] = crawlDb["percent"]

    # dbSize 처리
    size = crawlDb.get("dbSize") or 0
    size = int(size)

    if size == 0:
        byte_size = getFolderSize(os.path.join(crawldata_path, name))
        size = byte_size

    crawlDb["dbSize"] = format_size(size)
    crawlDb["dbSize_int"] = size
    return crawlDb


def getCrawlDbList(sort_by: str, mine: int = 0, userUid: str = None):
    user = user_db.find_one({"uid": userUid}, {"_id": 0})
    username = user["name"]

    if mine == 0:
        if username == "문요준":
            query = {}
        else:
            query = {"requester": {"$ne": "문요준"}}
    else:
        query = {"requester": username}

    if sort_by == "keyword":
        crawlDbList = list(crawlList_db.find(query, {"_id": 0}).sort("keyword", 1))
    else:
        crawlDbList = list(crawlList_db.find(query, {"_id": 0}).sort("startTime", -1))

    if not crawlDbList:
        crawlDbList = []

    fullStorage = 0

    filteredList = []
    # 각 doc 가공
    for crawlDb in crawlDbList:
        processed = processDbInfo(crawlDb)
        if processed:
            fullStorage += processed["dbSize_int"] / (1024**3)
            filteredList.append(processed)

    crawlDbList = filteredList

    activeCrawl = crawlList_db.count_documents({"status": "running"})

    # 응답
    return JSONResponse(
        status_code=200,
        content={
            "message": "CrawlDB list retrieved",
            "data": crawlDbList,
            "fullStorage": round(fullStorage, 1),
            "activeCrawl": activeCrawl,
        },
    )


def getCrawlDbInfo(uid: str, userUid: str = None):
    crawlDb = crawlList_db.find_one({"uid": uid}, {"_id": 0})

    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    targetDB = crawlDb["name"]
    log_user(
        userUid,
        "manager.crawl_db.info_view",
        f"Viewed crawl DB info: {targetDB}",
        target={"type": "crawl_db", "id": targetDB},
    )

    crawlDb = processDbInfo(crawlDb)
    return JSONResponse(
        status_code=200,
        content={"message": "CrawlDB retrieved", "data": crawlDb},
    )


def endCrawlDb(uid: str, error: bool = False):
    crawlDb = crawlList_db.find_one({"uid": uid}, {"_id": 0})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    if error:
        result = crawlList_db.update_one(
            {"uid": uid},
            {"$set": {"endTime": "X"}},
        )
    else:
        now_kst = (
            datetime.now(timezone.utc)
            .astimezone(timezone(timedelta(hours=9)))
            .strftime("%Y-%m-%d %H:%M")
        )

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


def updateCount(uid: str, stat):
    crawlDb = crawlList_db.find_one({"uid": uid}, {"_id": 0})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    dbsize = getFolderSize(os.path.join(crawldata_path, crawlDb["name"]))
    data_info_dict = stat.model_dump()
    percent = data_info_dict["percent"]

    del data_info_dict["percent"]

    crawlList_db.update_one(
        {"uid": uid},
        {"$set": {"stat": data_info_dict, "dbSize": dbsize, "endTime": percent}},
    )

    return JSONResponse(
        status_code=200,
        content={
            "message": "CrawlDB updated",
        },
    )


_CRAWL_TYPE_LABELS = {
    "navernews": "Naver News",
    "naverblog": "Naver Blog",
    "navercafe": "Naver Cafe",
    "youtube": "YouTube",
}


def _buildDownloadManifest(
    crawlDb: dict,
    targetDB: str,
    dbname: str,
    userUid: str,
    saveOption: dict,
    table_row_counts: dict,
) -> str:
    requester_user = user_db.find_one({"uid": userUid}, {"_id": 0})
    downloader_name = requester_user["name"] if requester_user else userUid

    typ = targetDB.split("_")[0]
    crawl_type_label = _CRAWL_TYPE_LABELS.get(typ, typ)

    now_kst = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))

    lines = [
        "=== 다운로드 정보 (Download Info) ===",
        f"내보낸 파일명: {dbname}",
        f"원본 DB 이름: {targetDB}",
        f"키워드: {crawlDb.get('keyword', '')}",
        f"크롤 타입: {crawl_type_label}",
        f"요청자(다운로드): {downloader_name}",
        f"다운로드 시각(KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}",
        f"원본 수집 기간: {crawlDb.get('startDate', '?')} ~ {crawlDb.get('endDate', '?')}",
        "",
        "--- 기간 옵션 ---",
    ]

    if saveOption.get("dateOption") == "part":
        lines.append(
            f"내보내기 기간: 부분 지정 ({saveOption.get('start_date')} ~ {saveOption.get('end_date')})"
        )
    else:
        lines.append("내보내기 기간: 전체 기간")

    lines.append("")
    lines.append("--- 단어 필터 옵션 ---")
    if saveOption.get("filterOption"):
        incl_words = saveOption.get("incl_words") or []
        excl_words = saveOption.get("excl_words") or []
        lines.append("필터링: 사용")
        lines.append(
            f"포함 조건: {'모두 포함 (AND)' if saveOption.get('include_all') else '하나 이상 포함 (OR)'}"
        )
        lines.append(f"포함 단어: {', '.join(incl_words) if incl_words else '(없음)'}")
        lines.append(f"제외 단어: {', '.join(excl_words) if excl_words else '(없음)'}")
        lines.append(
            f"파일명에 필터 조건 표시: {'예' if saveOption.get('filename_edit') else '아니오'}"
        )
    else:
        lines.append("필터링: 사용 안 함")

    lines.append("")
    lines.append("--- 파일 옵션 ---")
    lines.append(f"CSV 인코딩: {saveOption.get('encoding', 'utf-8-sig')}")
    lines.append(
        f"토큰 데이터(token_data) 포함: {'예' if saveOption.get('include_token_data', True) else '아니오'}"
    )

    lines.append("")
    lines.append("--- 저장된 테이블별 행 수 ---")
    if table_row_counts:
        for name, count in table_row_counts.items():
            lines.append(f"{name}.csv: {count:,}행")
    else:
        lines.append("(해당 없음)")

    return "\n".join(lines) + "\n"


def saveCrawlDb(uid: str, saveOption: SaveCrawlDbOption, userUid: str):
    def cleanup_folder_and_zip(folder_path: str, zip_path: str):
        # 폴더와 ZIP 파일을 삭제
        shutil.rmtree(folder_path, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass

    saveOption = saveOption.model_dump()
    crawlDb = crawlList_db.find_one({"uid": uid}, {"_id": 0})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")

    targetDB = crawlDb["name"]
    log_user(
        userUid,
        "manager.crawl_db.save_request",
        f"Requested crawl DB download: {targetDB}",
        target={"type": "crawl_db", "id": targetDB},
    )

    pid = saveOption["pid"]

    encoding = saveOption.get("encoding") or "utf-8-sig"
    if encoding not in ("utf-8-sig", "cp949"):
        encoding = "utf-8-sig"
    include_token_data = saveOption.get("include_token_data", True)
    include_manifest = saveOption.get("include_manifest", True)

    temp_directory = os.path.join(os.path.dirname(__file__), "..", "temp")

    time.sleep(1)
    send_message(pid, f"DB에서 테이블 목록을 가져오는 중...")
    localDbpath = os.path.join(crawldata_path, targetDB)

    tableList = [
        f[:-8]
        for f in os.listdir(localDbpath)
        if f.endswith(".parquet") and "info" not in f
    ]

    # 정렬: article > statistics > 나머지
    tableList = sorted(
        tableList, key=lambda x: ("article" not in x, "statistics" not in x, x)
    )

    # 현재 시각
    kst_now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%m%d_%H%M")

    # targetDB 구조 예시:
    parts = targetDB.split("_")[:-2] + kst_now.split("_")
    dbname = "_".join(parts)
    dbname = replaceKeywordInFilename(dbname, crawlDb["keyword"])

    dateOption = saveOption["dateOption"]
    filterOption = saveOption["filterOption"]

    if dateOption == "part":
        start_date = saveOption["start_date"]
        end_date = saveOption["end_date"]
        start_date_formed = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
        end_date_formed = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
        dbname = replaceDatesInFilename(
            dbname, saveOption["start_date"], saveOption["end_date"]
        )
    if filterOption:
        include_all = saveOption["include_all"]
        incl_words = saveOption["incl_words"]
        excl_words = saveOption["excl_words"]

        if saveOption["filename_edit"]:
            inclexcl = "all" if include_all else "any"
            add_keyword = (
                f"(+{','.join(incl_words)} _ -{','.join(excl_words)} _{inclexcl})"
            )
            parts = dbname.split("_", 2)
            old_keyword = parts[1]
            parts[1] = old_keyword + add_keyword
            dbname = "_".join(parts)

    dbpath = os.path.join(temp_directory, dbname)
    base_dbpath = dbpath
    for i in itertools.count():
        candidate = base_dbpath if i == 0 else f"{base_dbpath}_{i}"
        try:
            os.makedirs(candidate, exist_ok=False)
            if include_token_data:
                os.makedirs(os.path.join(candidate, "token_data"), exist_ok=True)
            dbpath = candidate
            break
        except FileExistsError:
            continue

    table_row_counts = {}

    if not include_token_data:
        tableList = [t for t in tableList if not t.startswith("token_")]

    is_navernews = "navernews" in targetDB
    start_date_formed_arg = start_date_formed if dateOption == "part" else None
    end_date_formed_arg = end_date_formed if dateOption == "part" else None

    def build_edited_name(tableName: str) -> str:
        name = (
            replaceDatesInFilename(tableName, start_date, end_date)
            if dateOption == "part"
            else tableName
        )
        return replaceKeywordInFilename(name, crawlDb["keyword"])

    # ---- 1단계: article / statistics 원본 테이블을 순차 처리해 articleURL/statisticsURL을
    # 구한다. 나머지 테이블(reply, rereply, token_* 등)은 이 두 URL 목록만 있으면 서로
    # 완전히 독립적으로 필터링할 수 있어, 2단계에서 프로세스 풀로 병렬 처리한다.
    raw_article_name = next(
        (t for t in tableList if t.endswith("_article") and not t.startswith("token_")),
        None,
    )
    raw_statistics_name = next(
        (
            t
            for t in tableList
            if t.endswith("_statistics") and not t.startswith("token_")
        ),
        None,
    )
    phase1_names = [n for n in (raw_article_name, raw_statistics_name) if n]

    articleURL = None
    statisticsURL = None

    for i, tableName in enumerate(phase1_names):
        edited_tableName = build_edited_name(tableName)
        send_message(pid, f"[{i + 1}/{len(tableList)}] '{edited_tableName}' 처리 중")

        tableDF = pd.read_parquet(os.path.join(localDbpath, f"{tableName}.parquet"))
        tableDF = apply_date_filter(
            tableDF, dateOption, start_date_formed_arg, end_date_formed_arg
        )

        if tableName == raw_article_name:
            if filterOption:
                tableDF = apply_word_filter(
                    tableDF, "Article Text", incl_words, excl_words, include_all
                )
            articleURL = tableDF["Article URL"].tolist()
        else:  # raw_statistics_name
            if filterOption:
                tableDF = tableDF[tableDF["Article URL"].isin(articleURL)]
            statisticsURL = tableDF["Article URL"].tolist()

        save_path = os.path.join(dbpath, f"{edited_tableName}.csv")
        tableDF.to_csv(
            save_path, index=False, encoding=encoding, errors="replace", header=True
        )
        table_row_counts[edited_tableName] = len(tableDF)
        tableDF = None

    # ---- 2단계: 나머지 테이블을 프로세스 풀로 병렬 처리 ----
    remaining_names = [t for t in tableList if t not in phase1_names]
    tasks = []

    for tableName in remaining_names:
        edited_tableName = build_edited_name(tableName)
        is_tok = tableName.startswith("token_")
        save_dir = os.path.join(dbpath, "token_data") if is_tok else dbpath
        save_path = os.path.join(save_dir, f"{edited_tableName}.csv")

        if (
            is_tok
            and raw_statistics_name is not None
            and tableName[len("token_") :] == raw_statistics_name
        ):
            # token_statistics: raw statistics에서 구한 URL 집합을 그대로 재사용한다
            # (articleURL/token_article 관계와 동일한 패턴). 여기서 별도로 다시 계산하면
            # 토큰화가 원본보다 뒤처진 경우 이후 reply_statistics 결과가 누락될 수 있다.
            url_filter = statisticsURL
        elif "_article" in tableName:
            # token_article: 필터링 옵션이 켜져 있을 때만 articleURL로 제한한다.
            url_filter = articleURL if filterOption else None
        elif "reply" in tableName:  # reply / rereply / token_reply / token_rereply
            url_filter = articleURL if filterOption else None
        else:
            url_filter = None

        stats_variant = None
        if "reply" in tableName and is_navernews and statisticsURL is not None:
            stats_edited_name = edited_tableName + "_statistics"
            stats_variant = {
                "save_path": os.path.join(save_dir, f"{stats_edited_name}.csv"),
                "edited_name": stats_edited_name,
                "url_filter": statisticsURL,
            }

        tasks.append(
            dict(
                parquet_path=os.path.join(localDbpath, f"{tableName}.parquet"),
                save_path=save_path,
                edited_tableName=edited_tableName,
                encoding=encoding,
                date_option=dateOption,
                start_date_formed=start_date_formed_arg,
                end_date_formed=end_date_formed_arg,
                url_filter=url_filter,
                stats_variant=stats_variant,
            )
        )

    if tasks:
        max_workers = min(len(tasks), os.cpu_count() or 4, 8)
        send_message(
            pid,
            f"나머지 {len(tasks)}개 테이블 병렬 처리 중... (worker {max_workers}개)",
        )

        ctx = multiprocessing.get_context("spawn")
        done_count = 0
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
            futures = {
                executor.submit(process_table_task, **task): task["edited_tableName"]
                for task in tasks
            }
            for future in as_completed(futures):
                edited_tableName = futures[future]
                result = future.result()
                table_row_counts.update(result)
                done_count += 1
                send_message(
                    pid,
                    f"[{len(phase1_names) + done_count}/{len(tableList)}] '{edited_tableName}' 처리 완료",
                )

    gc.collect()

    if include_manifest:
        send_message(pid, f"다운로드 정보 파일 생성 중")
        manifest_text = _buildDownloadManifest(
            crawlDb=crawlDb,
            targetDB=targetDB,
            dbname=dbname,
            userUid=userUid,
            saveOption=saveOption,
            table_row_counts=table_row_counts,
        )
        with open(
            os.path.join(dbpath, "download_info.txt"), "w", encoding="utf-8-sig"
        ) as f:
            f.write(manifest_text)

    send_message(pid, f"데이터 압축 중")

    zip_path = f"{dbpath}.zip"
    fast_zip(dbpath, zip_path)
    filename = os.path.basename(zip_path)

    send_message(pid, f"데이터 처리 완료")
    send_message(pid, f"데이터 전송 중")
    background_task = BackgroundTask(cleanup_folder_and_zip, dbpath, zip_path)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
        background=background_task,
    )


def previewCrawlDb(uid: str, userUid: str):
    crawlDb = crawlList_db.find_one({"uid": uid}, {"_id": 0})
    if not crawlDb:
        raise NotFoundException("CrawlDB not found")
    targetDB = crawlDb["name"]
    log_user(
        userUid,
        "manager.crawl_db.preview_request",
        f"Requested crawl DB preview: {targetDB}",
        target={"type": "crawl_db", "id": targetDB},
    )

    target_folder = crawlDb["name"]  # 이 이름이 곧 디렉토리명
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
                if file.endswith(".parquet"):
                    df = pd.read_parquet(file_path)
                elif file.endswith(".csv"):
                    df = pd.read_csv(file_path, encoding="utf-8-sig")
                df_preview = pd.concat([df.head(50), df.tail(50)]).drop_duplicates()

                # ID 열 제거 (있을 경우)
                if "id" in df_preview.columns:
                    df_preview = df_preview.drop(columns=["id"])

                # DataFrame을 BytesIO로 저장
                df_buffer = BytesIO()
                df_preview.to_parquet(df_buffer, index=False)
                df_buffer.seek(0)

                table_name = file.replace(".parquet", "")
                zip_file.writestr(f"{table_name}.parquet", df_buffer.read())

            except Exception as e:
                print(f"[경고] {file} 처리 실패: {e}")

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=preview_data.zip"},
    )
