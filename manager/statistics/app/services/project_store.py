# app/services/project_store.py
"""
분석 서버(manager/server, 통계분석 파이프라인)가 만든 결과 zip(csv_files/, graphs/,
description.txt, metadata.json 포함)을 로그인한 사용자의 "프로젝트"로 저장한다. 원본
결과는 /mnt/ssd/statistics/{uid}/{project_id}/ 아래 디스크에 두고, 프로젝트
메타데이터(이름 등)는 MongoDB(statistics-projects 컬렉션)에 둔다.

kemkim/network와 달리 통계분석 결과는 이미 "표"들의 모음이라, 분석 타입마다 다른
파서를 만드는 대신 csv_files/*.csv를 범용으로 JSON 표로 변환한다(base.json). graphs/의
PNG는 원본 zip 다운로드용으로만 두고, 뷰어는 표 데이터로 직접 인터랙티브 차트를 그린다.
"""

import io
import json
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone

import pandas as pd

from app.db import statistics_projects_db

PROJECT_ROOT = os.getenv("STATISTICS_PROJECT_ROOT", "/mnt/ssd/statistics")
os.makedirs(PROJECT_ROOT, exist_ok=True)

MAX_ROWS_PER_TABLE = 5000


class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


def _project_dir(uid: str, project_id: str) -> str:
    return os.path.join(PROJECT_ROOT, uid, project_id)


def _raw_dir(uid: str, project_id: str) -> str:
    return os.path.join(_project_dir(uid, project_id), "raw")


def _base_json_path(uid: str, project_id: str) -> str:
    return os.path.join(_project_dir(uid, project_id), "base.json")


# ---------------------------------------------------------------------------
# 통계분석 결과 zip -> base.json 파싱
# ---------------------------------------------------------------------------


def _find_result_root(extract_dir: str) -> str:
    """추출된 폴더에서 metadata.json이 있는 실제 결과 루트를 찾는다. zip이 폴더 하나로
    감싸져 있는 경우와 바로 풀린 경우를 모두 지원한다."""
    if os.path.exists(os.path.join(extract_dir, "metadata.json")):
        return extract_dir

    entries = [e for e in os.listdir(extract_dir) if not e.startswith("__MACOSX")]
    for entry in entries:
        candidate = os.path.join(extract_dir, entry)
        if os.path.isdir(candidate) and os.path.exists(
            os.path.join(candidate, "metadata.json")
        ):
            return candidate

    raise ValueError(
        "metadata.json을 찾지 못했습니다. 통계분석 결과 zip을 그대로 업로드해주세요."
    )


def _humanize(stem: str) -> str:
    return " ".join(w.capitalize() for w in stem.replace("-", "_").split("_"))


def _table_from_csv(path: str) -> dict:
    stem = os.path.splitext(os.path.basename(path))[0]
    df = pd.read_csv(path, encoding="utf-8-sig")
    truncated = len(df) > MAX_ROWS_PER_TABLE
    if truncated:
        df = df.head(MAX_ROWS_PER_TABLE)
    # NaN -> None (엄격한 JSON 직렬화를 위해)
    df = df.astype(object).where(pd.notnull(df), None)
    # pandas가 이름 없는 인덱스 열에 붙이는 "Unnamed: 0" 같은 헤더를 사람이 읽기 좋게 치환
    columns = [
        "항목" if str(c).startswith("Unnamed:") else str(c) for c in df.columns
    ]
    return {
        "id": stem,
        "title": _humanize(stem),
        "columns": columns,
        "rows": df.values.tolist(),
        "row_count": len(df),
        "truncated": truncated,
    }


def _build_base_json(root: str) -> dict:
    metadata_path = os.path.join(root, "metadata.json")
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    description = ""
    desc_path = os.path.join(root, "description.txt")
    if os.path.exists(desc_path):
        with open(desc_path, "r", encoding="utf-8", errors="ignore") as f:
            description = f.read()

    tables = []
    csv_dir = os.path.join(root, "csv_files")
    if os.path.isdir(csv_dir):
        for fname in sorted(os.listdir(csv_dir)):
            if fname.lower().endswith(".csv"):
                try:
                    tables.append(_table_from_csv(os.path.join(csv_dir, fname)))
                except Exception:
                    continue

    graphs = []
    graph_dir = os.path.join(root, "graphs")
    if os.path.isdir(graph_dir):
        graphs = sorted(f for f in os.listdir(graph_dir) if f.lower().endswith(".png"))

    return {
        "metadata": metadata,
        "description": description,
        "tables": tables,
        "graphs": graphs,
    }


def _extract_zip_and_build(root: str, upload_bytes: bytes) -> dict:
    """zip을 root/raw 에 풀고 base.json을 만들어 반환한다."""
    raw_dir = os.path.join(root, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(upload_bytes)) as zf:
            zf.extractall(raw_dir)
    except zipfile.BadZipFile:
        raise ValueError("zip 파일이 아니거나 손상되었습니다.")

    result_root = _find_result_root(raw_dir)
    base = _build_base_json(result_root)

    with open(os.path.join(root, "base.json"), "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False)

    return base


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def _iso(dt) -> str:
    return dt.isoformat() if hasattr(dt, "isoformat") else dt


def _doc_out(doc: dict) -> dict:
    return {
        "project_id": doc["_id"],
        "name": doc["name"],
        "created_at": _iso(doc["created_at"]),
        "updated_at": _iso(doc["updated_at"]),
        "source": doc.get("source", "upload"),
        "category": doc.get("category"),
        "platform": doc.get("platform"),
        "summary": doc.get("summary", {}),
    }


def create_project(
    uid: str, upload_bytes: bytes, name: str, source: str = "upload"
) -> dict:
    project_id = uuid.uuid4().hex
    root = _project_dir(uid, project_id)
    os.makedirs(root, exist_ok=True)

    try:
        base = _extract_zip_and_build(root, upload_bytes)
    except ValueError:
        shutil.rmtree(root, ignore_errors=True)
        raise

    metadata = base.get("metadata", {})
    summary = {
        "table_count": len(base.get("tables", [])),
        "row_count": metadata.get("row_count"),
        "source_filename": metadata.get("source_filename"),
    }

    now = datetime.now(timezone.utc)
    doc = {
        "_id": project_id,
        "uid": uid,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "source": source,
        "category": metadata.get("category"),
        "platform": metadata.get("platform"),
        "summary": summary,
    }
    statistics_projects_db.insert_one(doc)
    return _doc_out(doc)


def list_projects(uid: str) -> list:
    docs = statistics_projects_db.find({"uid": uid}).sort("created_at", -1)
    return [_doc_out(d) for d in docs]


def _get_owned_doc(uid: str, project_id: str) -> dict:
    doc = statistics_projects_db.find_one({"_id": project_id})
    if not doc:
        raise NotFound("프로젝트를 찾을 수 없습니다.")
    if doc["uid"] != uid:
        raise Forbidden("이 프로젝트에 접근할 권한이 없습니다.")
    return doc


def get_project(uid: str, project_id: str) -> dict:
    return _doc_out(_get_owned_doc(uid, project_id))


def rename_project(uid: str, project_id: str, new_name: str) -> dict:
    _get_owned_doc(uid, project_id)
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("이름을 입력해주세요.")
    statistics_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc)}},
    )
    return _doc_out(_get_owned_doc(uid, project_id))


def delete_project(uid: str, project_id: str):
    _get_owned_doc(uid, project_id)
    statistics_projects_db.delete_one({"_id": project_id})
    shutil.rmtree(_project_dir(uid, project_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# 분석 결과 (표 + 설명)
# ---------------------------------------------------------------------------


def load_base(uid: str, project_id: str) -> dict:
    _get_owned_doc(uid, project_id)
    path = _base_json_path(uid, project_id)
    if not os.path.exists(path):
        raise NotFound("분석 결과를 찾을 수 없습니다.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 원본 zip 재다운로드
# ---------------------------------------------------------------------------


def zip_raw(uid: str, project_id: str) -> str:
    """raw/ 폴더를 즉석에서 압축해 zip 경로를 반환한다 (호출자가 응답 후 삭제 책임)."""
    _get_owned_doc(uid, project_id)
    raw_dir = _raw_dir(uid, project_id)
    if not os.path.isdir(raw_dir):
        raise NotFound("원본 분석 결과를 찾을 수 없습니다.")
    tmp_base = os.path.join(
        _project_dir(uid, project_id), f"download_{uuid.uuid4().hex}"
    )
    archive_path = shutil.make_archive(tmp_base, "zip", raw_dir)
    return archive_path
