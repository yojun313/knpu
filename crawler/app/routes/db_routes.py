import io
import os
from urllib.parse import quote

import pandas as pd
import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.db import crawler_db
from app.models.job_model import CrawlSaveOption
from app.routes.dependencies import get_current_user, check_owner_or_admin
from config import MANAGER_SERVER_URL, CRAWL_DATA_PATH

router = APIRouter()

crawlList_db = crawler_db["db-list"]
crawlLog_db = crawler_db["log-list"]

MANAGER_CRAWLS_URL = f"{MANAGER_SERVER_URL}/crawls"


def _manager_headers(request: Request) -> dict:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    return {"Authorization": f"Bearer {token}"}


@router.get("/db-list")
def list_db(
    page: int = 1,
    per_page: int = 30,
    status: str = None,
    q: str = None,
    user=Depends(get_current_user),
):
    """매니저 앱의 Database 페이지와 동일한 전체 크롤 DB 목록. 검색/상태 필터 + 페이지네이션."""
    query = {}
    if status:
        query["status"] = status
    if q:
        query["$or"] = [
            {"keyword": {"$regex": q, "$options": "i"}},
            {"requester": {"$regex": q, "$options": "i"}},
            {"name": {"$regex": q, "$options": "i"}},
        ]

    page = max(1, page)
    per_page = max(1, min(100, per_page))
    total = crawlList_db.count_documents(query)
    docs = list(
        crawlList_db.find(query)
        .sort("startTime", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )
    for d in docs:
        d["_id"] = str(d["_id"])

    return {"items": docs, "total": total, "page": page, "per_page": per_page}


@router.get("/db-list/{uid}")
def get_db_detail(uid: str, request: Request, user=Depends(get_current_user)):
    """조회는 manager/server의 GET /crawls/{uid}/info를 그대로 프록시한다 —
    매니저 앱이 쓰는 것과 동일한 로직(가공된 상태/크기 표시, 조회 로그 기록 포함)."""
    try:
        resp = requests.get(
            f"{MANAGER_CRAWLS_URL}/{uid}/info",
            headers=_manager_headers(request),
            timeout=15,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"매니저 서버 요청 실패: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json().get("data")


@router.get("/db-list/{uid}/logs")
def get_db_logs(uid: str, request: Request, user=Depends(get_current_user)):
    """manager/server의 GET /crawls/{uid}/log를 그대로 프록시한다."""
    try:
        resp = requests.get(
            f"{MANAGER_CRAWLS_URL}/{uid}/log",
            headers=_manager_headers(request),
            timeout=15,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"매니저 서버 요청 실패: {e}")
    if resp.status_code != 200:
        return {"logs": []}
    data = resp.json().get("data") or {}
    return {"logs": data.get("logs", [])}


@router.get("/db-list/{uid}/files")
def list_db_files(uid: str, user=Depends(get_current_user)):
    """완료된 크롤 DB 폴더 안의 파일 목록을 token/raw로 분류해서 반환한다.
    네트워크/켐킴/통계분석 서비스가 '크롤링 DB에서 선택' 기능에서 사용한다."""
    doc = crawlList_db.find_one({"uid": uid}, {"name": 1, "status": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="해당 DB를 찾을 수 없습니다")
    if doc.get("status") != "completed":
        raise HTTPException(
            status_code=409, detail="완료된 크롤링만 분석에 사용할 수 있습니다"
        )

    folder_path = os.path.join(CRAWL_DATA_PATH, doc["name"])
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="데이터 폴더를 찾을 수 없습니다")

    files = []
    for f in sorted(os.listdir(folder_path)):
        if not f.endswith(".parquet"):
            continue
        is_token = f.startswith("token_")
        try:
            size = os.path.getsize(os.path.join(folder_path, f))
        except OSError:
            size = None
        files.append(
            {
                "name": f,
                "type": "token" if is_token else "raw",
                "size": size,
                "csv_name": f.rsplit(".", 1)[0] + ".csv",
            }
        )

    return {"uid": uid, "db_name": doc["name"], "files": files}


@router.get("/db-list/{uid}/file")
def get_db_file(uid: str, name: str, user=Depends(get_current_user)):
    """완료된 크롤 DB 폴더 안의 특정 parquet 파일을 CSV로 변환해서 반환한다.
    name은 반드시 해당 폴더에 실제로 존재하는 파일명과 정확히 일치해야 한다
    (경로 조작 방지 — os.path.basename으로 한 번 더 정규화하고 폴더 안 목록과 대조)."""
    doc = crawlList_db.find_one({"uid": uid}, {"name": 1, "status": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="해당 DB를 찾을 수 없습니다")
    if doc.get("status") != "completed":
        raise HTTPException(
            status_code=409, detail="완료된 크롤링만 분석에 사용할 수 있습니다"
        )

    folder_path = os.path.join(CRAWL_DATA_PATH, doc["name"])
    safe_name = os.path.basename(name)
    if safe_name != name or not safe_name.endswith(".parquet"):
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다")

    file_path = os.path.join(folder_path, safe_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

    try:
        df = pd.read_parquet(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일을 읽지 못했습니다: {e}")

    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)

    csv_name = safe_name.rsplit(".", 1)[0] + ".csv"
    # 파일명에 한글이 포함되므로 RFC 5987 filename*으로 인코딩 (ASCII 헤더 제약 회피)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"download.csv\"; "
                f"filename*=UTF-8''{quote(csv_name)}"
            )
        },
    )


@router.delete("/db-list/{uid}")
def delete_db(uid: str, request: Request, user=Depends(get_current_user)):
    """권한 확인(관리자 또는 요청자)은 크롤러가 하고, 실제 삭제(Mongo 기록 + 파일)는
    manager/server의 DELETE /crawls/{uid}에 위임한다 — 매니저 앱과 동일한 로직."""
    doc = crawlList_db.find_one({"uid": uid}, {"userUid": 1, "status": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="해당 DB를 찾을 수 없습니다")
    if doc.get("status") == "running":
        raise HTTPException(
            status_code=409, detail="진행 중인 작업은 먼저 중단한 뒤 삭제해주세요"
        )
    check_owner_or_admin(user, doc)

    try:
        resp = requests.delete(
            f"{MANAGER_CRAWLS_URL}/{uid}",
            headers=_manager_headers(request),
            timeout=30,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"매니저 서버 요청 실패: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return {"status": "ok"}


@router.post("/db-list/{uid}/download-via-manager")
def download_via_manager(
    uid: str,
    save_option: CrawlSaveOption,
    request: Request,
    user=Depends(get_current_user),
):
    """매니저 앱의 'CSV로 저장'과 완전히 동일하게 동작한다 — manager/server의
    POST /crawls/{uid}/save를 그대로 서버 간 호출로 프록시한다(날짜/키워드 필터링,
    CSV 재저장, zip 압축까지 전부 manager/server가 수행). 진행상황은 클라이언트가
    save_option.pid로 manager.knpu.re.kr/progress 웹소켓을 직접 구독해서 본다."""
    doc = crawlList_db.find_one({"uid": uid}, {"uid": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="해당 DB를 찾을 수 없습니다")

    try:
        upstream = requests.post(
            f"{MANAGER_CRAWLS_URL}/{uid}/save",
            json=save_option.model_dump(),
            headers=_manager_headers(request),
            stream=True,
            timeout=3600,
        )
        upstream.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=502,
            detail=f"매니저 서버에서 다운로드를 가져오지 못했습니다: {e}",
        )

    response_headers = {}
    if upstream.headers.get("content-disposition"):
        response_headers["Content-Disposition"] = upstream.headers[
            "content-disposition"
        ]
    if upstream.headers.get("content-length"):
        response_headers["Content-Length"] = upstream.headers["content-length"]

    def stream():
        try:
            for chunk in upstream.iter_content(chunk_size=65536):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return StreamingResponse(
        stream(),
        media_type=upstream.headers.get("content-type", "application/zip"),
        headers=response_headers,
    )
