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


# csv_files/{id}.csv 표 이름 -> 사람이 읽는 설명. manager/server의
# app/libs/statistics_analysis.py(10개 분석 함수)가 만드는 표 이름은 대부분 겹치므로,
# 분석 함수마다 따로 만들지 않고 표 이름 하나로 전체 분석 종류를 커버한다.
TABLE_DESCRIPTIONS: dict[str, str] = {
    "basic_stats": "원본 데이터의 각 열에 대한 기초 통계량(개수·평균·표준편차·사분위수 등)입니다.",
    "time_analysis": "월 단위로 집계한 게시물/댓글 수 추이입니다.",
    "day_analysis": "일 단위로 집계한 게시물/댓글 수 추이입니다. 특정 날짜에 몰린 급증 패턴을 확인할 때 유용합니다.",
    "monthly_analysis": "월별 집계 추이입니다.",
    "month_analysis": "월별 집계 추이입니다.",
    "weekly_analysis": "주 단위 집계 추이입니다.",
    "daily_analysis": "일 단위 집계 추이입니다.",
    "article_day_analysis": "일 단위 게시물 수 추이입니다.",
    "article_type_analysis": "기사/게시물 유형별 개수와 유형당 평균 반응(댓글 수)입니다.",
    "press_analysis": "게시물 수 상위 10개 언론사의 기사 수와 언론사별 반응(댓글) 수입니다.",
    "day_of_week_analysis": "요일별 게시물 수와 평균 반응 수입니다. 어느 요일에 발행이 몰리는지 보여줍니다.",
    "hour_analysis": "시간대(0~23시)별 게시물 수와 평균 반응 수입니다.",
    "channel_analysis": "채널(운영 주체)별 게시물 수와 반응 수입니다.",
    "writer_analysis": "작성자별 게시물 수 상위 항목입니다.",
    "writer_reply_count": "댓글을 가장 많이 남긴 작성자 상위 목록입니다.",
    "writer_rereply_count": "대댓글을 가장 많이 남긴 작성자 상위 목록입니다.",
    "top_10_writers": "게시물/댓글 수 기준 상위 10명의 작성자입니다.",
    "top_10_articles": "반응(댓글) 수 기준 상위 10개 게시물입니다.",
    "top_10_videos": "조회수/반응 기준 상위 10개 영상입니다.",
    "top_10_liked_replies": "좋아요 수 기준 상위 10개 댓글입니다.",
    "top_10_liked_rereplies": "좋아요 수 기준 상위 10개 대댓글입니다.",
    "top_10_percent_users": "활동량 상위 10% 사용자 그룹의 통계입니다.",
    "top_controversial_replies": "찬반(공감/비공감)이 크게 엇갈린, 논쟁적인 댓글 상위 목록입니다.",
    "top_articles_by_demographic": "특정 독자층(성별/연령대)의 반응이 두드러진 게시물 상위 목록입니다.",
    "top10_days": "값이 가장 높았던 상위 10개 날짜입니다.",
    "top10_months": "값이 가장 높았던 상위 10개월입니다.",
    "user_activity": "사용자별 활동량(댓글/대댓글 작성 수) 통계입니다.",
    "user_activity_with_score": "사용자별 활동량과 점수(좋아요 등 반응 포함)를 함께 정리한 표입니다.",
    "user_activity_correlation": "사용자 활동 지표들 사이의 상관관계 행렬입니다. 값이 1에 가까울수록 두 지표가 함께 움직이는 경향이 강합니다.",
    "correlation": "주요 지표들 사이의 상관관계 행렬입니다. 값이 1에 가까울수록 두 지표가 함께 움직이는 경향이 강합니다.",
    "correlation_matrix": "주요 지표들 사이의 상관관계 행렬입니다. 값이 1에 가까울수록 두 지표가 함께 움직이는 경향이 강합니다.",
    "gender_reply_count": "성별에 따른 댓글 작성 수 비교입니다.",
    "age_group_reply_count": "연령대별 댓글 작성 수 비교입니다.",
    "type_demographic": "게시물 유형별 독자 인구통계(성별/연령대) 분포입니다.",
    "sentiment_counts": "감성(긍정/부정/중립 등) 분류별 개수입니다.",
    "article_analysis": "게시물 단위 핵심 지표 요약입니다.",
    "cafe_analysis": "카페 게시물 핵심 지표 요약입니다.",
    "daily_mean": "일별 평균 수치입니다.",
    "monthly_mean": "월별 평균 수치입니다.",
    "rolling7_mean": "7일 이동평균으로 완만하게 다듬은 추세입니다. 일별 변동폭이 크더라도 전체 흐름을 파악하기 쉽습니다.",
    "hour_dow_heatmap": "요일×시간대별 게시물 빈도를 색상 농도로 보여주는 히트맵입니다. 짙을수록 해당 요일·시간대에 게시물이 많이 올라왔다는 뜻입니다.",
}


def _fallback_description(stem: str, columns: list[str]) -> str:
    if stem.endswith("_trend"):
        base = stem[: -len("_trend")]
        base_label = TABLE_DESCRIPTIONS.get(base, _humanize(base))
        return (
            f"{base_label} 원본 수치와 7기간 이동평균을 함께 보여줍니다. "
            "값의 급등락을 제외한 전체적인 추세를 파악할 때 유용합니다."
        )
    if stem.endswith("_cumulative"):
        base = stem[: -len("_cumulative")]
        base_label = TABLE_DESCRIPTIONS.get(base, _humanize(base))
        return f"{base_label} 값을 시간순으로 누적 합산한 추이입니다. 전체 누적 성장 규모를 보여줍니다."
    label_col = columns[0] if columns else None
    numeric_cols = columns[1:] if len(columns) > 1 else []
    if label_col and numeric_cols:
        return f"{label_col}별 {', '.join(numeric_cols[:3])} 집계 표입니다."
    return "분석 결과 표입니다."


def _describe_table(stem: str, columns: list[str]) -> str:
    return TABLE_DESCRIPTIONS.get(stem) or _fallback_description(stem, columns)


def _is_heatmap_table(stem: str, df: pd.DataFrame) -> bool:
    if stem == "hour_dow_heatmap":
        return True
    if "correlation" in stem or "corr" in stem:
        # 상관행렬은 (라벨 열 + 숫자 열들)이고, 숫자 열 이름들이 각 행의 라벨과
        # 대체로 일치하는 정사각형 행렬이다.
        numeric_cols = df.select_dtypes(include="number").columns
        return len(numeric_cols) >= 2 and abs(len(numeric_cols) - len(df)) <= 1
    return False


def _table_from_csv(path: str) -> dict:
    stem = os.path.splitext(os.path.basename(path))[0]
    df = pd.read_csv(path, encoding="utf-8-sig")
    is_heatmap = _is_heatmap_table(stem, df)
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
        "description": _describe_table(stem, columns),
        "columns": columns,
        "rows": df.values.tolist(),
        "row_count": len(df),
        "truncated": truncated,
        "is_heatmap": is_heatmap,
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
