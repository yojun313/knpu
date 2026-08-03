# app/services/project_store.py
"""
분석 서버(manager/server, KemKim 파이프라인)가 만든 결과 zip(Data/, Result/, Trace/,
kemkim_info.txt 포함)을 로그인한 사용자의 "프로젝트"로 저장한다. 원본 결과와 좌표/신호
데이터는 /mnt/ssd/kemkim/{uid}/{project_id}/ 아래 디스크에 두고, 프로젝트 메타데이터(이름
등)는 MongoDB(kemkim-projects 컬렉션)에 둔다.

웹에서는 별도의 "조정" 단계 없이, 실행 결과(base.json)를 그대로 하나의 그래프로 두고
프론트엔드에서 사분면/단어 단위로 표시를 껐다 켰다 한다(서버 재계산 없음) — 그래서
network의 project_store.py와 달리 조정본(revision) 개념이 없다.
"""

import ast
import io
import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone

import pandas as pd

from app.db import kemkim_projects_db, kemkim_folders_db, get_user_names
from system.archive import UnsafeZipError, safe_extract_zip

PROJECT_ROOT = os.getenv("KEMKIM_PROJECT_ROOT", "/mnt/ssd/kemkim")
os.makedirs(PROJECT_ROOT, exist_ok=True)

_INFO_LABEL_MAP = {
    "분석 데이터": "csv_name",
    "분석 시각": "analyzed_at",
    "분석 시작일": "start_date",
    "분석 종료일": "end_date",
    "분석 기간 단위": "period",
    "상위 단어 개수": "topword",
    "계산 가중치": "weight",
    "비일관 단어 필터링 여부": "filter_option",
    "추적 데이터 계산 기준": "trace_standard",
    "애니메이션 여부": "ani_option",
    "제외 단어 여부": "except_option",
    "제외 단어 파일": "exception_filename",
    "분할 기준": "split_option",
    "분할 상위%": "split_custom",
}
_PERIOD_METRICS = ["TF", "DF", "TF-IDF", "DoV", "DoD"]


class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


def _project_dir(uid: str, project_id: str) -> str:
    return os.path.join(PROJECT_ROOT, uid, project_id)


def _raw_dir(uid: str, project_id: str) -> str:
    return os.path.join(_project_dir(uid, project_id), "raw")


def _interpretations_dir(uid: str, project_id: str) -> str:
    return os.path.join(_project_dir(uid, project_id), "interpretations")


def _source_csv_path(uid: str, project_id: str) -> str:
    return os.path.join(_project_dir(uid, project_id), "source.csv")


def _base_json_path(uid: str, project_id: str) -> str:
    return os.path.join(_project_dir(uid, project_id), "base.json")


# ---------------------------------------------------------------------------
# kemkim 결과 zip -> base.json 파싱
# ---------------------------------------------------------------------------


def _find_kemkim_root(extract_dir: str) -> str:
    """추출된 폴더에서 kemkim_info.txt가 있는 실제 결과 루트를 찾는다. zip이
    kemkim_xxx_MMDDHHMM 폴더 하나로 감싸져 있는 경우와 바로 풀린 경우를 모두 지원."""
    if os.path.exists(os.path.join(extract_dir, "kemkim_info.txt")):
        return extract_dir

    entries = [e for e in os.listdir(extract_dir) if not e.startswith("__MACOSX")]
    for entry in entries:
        candidate = os.path.join(extract_dir, entry)
        if os.path.isdir(candidate) and os.path.exists(
            os.path.join(candidate, "kemkim_info.txt")
        ):
            return candidate

    raise ValueError(
        "kemkim_info.txt를 찾지 못했습니다. KEMKIM 분석 결과 zip을 그대로 업로드해주세요."
    )


def _parse_info_txt(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    fields: dict = {}
    for line in content.splitlines():
        if line.startswith("=") or ":" not in line:
            continue
        label, _, value = line.partition(":")
        label = label.strip()
        if label in _INFO_LABEL_MAP:
            fields[_INFO_LABEL_MAP[label]] = value.strip()

    status_match = re.search(r"진행 상황:\s*(.*)", content)
    if status_match:
        fields["status_message"] = status_match.group(1).strip()

    return fields


def _parse_coordinates_csv(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path, encoding="utf-8-sig")
    coords = {}
    for _, row in df.iterrows():
        key = str(row["key"])
        try:
            x, y = ast.literal_eval(str(row["value"]))
            coords[key] = [float(x), float(y)]
        except (ValueError, SyntaxError):
            continue
    return coords


def _parse_signal_csv(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path, encoding="utf-8-sig")
    signals = {}
    for _, row in df.iterrows():
        signal = str(row["signal"])
        raw = row["word"]
        if pd.isna(raw):
            signals[signal] = []
            continue
        try:
            words = ast.literal_eval(str(raw))
        except (ValueError, SyntaxError):
            words = []
        signals[signal] = [str(w) for w in words]
    return signals


def _parse_trace_coordinates_csv(path: str) -> dict:
    """Trace/{DoV,DoD}_coordinates_trace.csv (Keyword, period_<p1>, period_<p2>, ... 열,
    각 셀은 좌표 튜플)를 {word: [{period, x, y}, ...]} 형태로 변환한다. 필터링 옵션을
    꺼둔 채 실행한 프로젝트는 이 파일이 아예 없을 수 있으므로 그런 경우 빈 dict."""
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty or len(df.columns) < 2:
        return {}
    key_col = df.columns[0]
    period_cols = list(df.columns[1:])
    result = {}
    for _, row in df.iterrows():
        word = str(row[key_col])
        points = []
        for col in period_cols:
            val = row[col]
            if pd.isna(val):
                continue
            try:
                x, y = ast.literal_eval(str(val))
                period_label = (
                    col[len("period_") :] if col.startswith("period_") else col
                )
                points.append({"period": period_label, "x": float(x), "y": float(y)})
            except (ValueError, SyntaxError):
                continue
        if points:
            result[word] = points
    return result


def _build_periods(root: str) -> dict:
    """Data/{TF,DF,TF-IDF,DoV,DoD}/{period}_<metric>.csv -> {period: {metric: {word: value}}}"""
    data_dir = os.path.join(root, "Data")
    periods: dict = {}
    for metric in _PERIOD_METRICS:
        metric_dir = os.path.join(data_dir, metric)
        if not os.path.isdir(metric_dir):
            continue
        suffix = f"_{metric}.csv"
        for fname in sorted(os.listdir(metric_dir)):
            if not fname.endswith(suffix):
                continue
            period_key = fname[: -len(suffix)]
            df = pd.read_csv(os.path.join(metric_dir, fname), encoding="utf-8-sig")
            if metric not in df.columns:
                continue
            values = {
                str(r["keyword"]): float(r[metric])
                for _, r in df.iterrows()
                if pd.notna(r[metric])
            }
            periods.setdefault(period_key, {})[metric] = values
    return periods


def _build_base_json(root: str) -> dict:
    metadata = _parse_info_txt(os.path.join(root, "kemkim_info.txt"))

    graph_dir = os.path.join(root, "Result", "Graph")
    signal_dir = os.path.join(root, "Result", "Signal")
    trace_dir = os.path.join(root, "Trace")

    dov_coords = _parse_coordinates_csv(os.path.join(graph_dir, "DOV_coordinates.csv"))
    dod_coords = _parse_coordinates_csv(os.path.join(graph_dir, "DOD_coordinates.csv"))
    dov_axis = dov_coords.pop("axis", None)
    dod_axis = dod_coords.pop("axis", None)

    filtered_words = []
    fw_path = os.path.join(root, "Result", "filtered_words.csv")
    if os.path.exists(fw_path):
        fw_df = pd.read_csv(fw_path, encoding="utf-8-sig")
        if "word" in fw_df.columns:
            filtered_words = fw_df["word"].dropna().astype(str).tolist()

    return {
        "metadata": metadata,
        "dov": {
            "axis": dov_axis,
            "coordinates": dov_coords,
            "signal": _parse_signal_csv(os.path.join(signal_dir, "DoV_signal.csv")),
        },
        "dod": {
            "axis": dod_axis,
            "coordinates": dod_coords,
            "signal": _parse_signal_csv(os.path.join(signal_dir, "DoD_signal.csv")),
        },
        "final_signal": _parse_signal_csv(os.path.join(signal_dir, "Final_signal.csv")),
        "filtered_words": filtered_words,
        "periods": _build_periods(root),
        "trace": {
            "dov": _parse_trace_coordinates_csv(
                os.path.join(trace_dir, "DoV_coordinates_trace.csv")
            ),
            "dod": _parse_trace_coordinates_csv(
                os.path.join(trace_dir, "DoD_coordinates_trace.csv")
            ),
        },
    }


def _extract_zip_and_build(root: str, upload_bytes: bytes) -> dict:
    """zip을 root/raw 에 풀고 base.json을 만들어 반환한다."""
    raw_dir = os.path.join(root, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(upload_bytes)) as zf:
            safe_extract_zip(zf, raw_dir)
    except zipfile.BadZipFile:
        raise ValueError("zip 파일이 아니거나 손상되었습니다.")
    except UnsafeZipError as e:
        raise ValueError(str(e))

    kemkim_root = _find_kemkim_root(raw_dir)
    base = _build_base_json(kemkim_root)

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
        "analysis_options": doc.get("analysis_options"),
        "summary": doc.get("summary", {}),
        "interpretations": doc.get("interpretations", []),
        "has_source": doc.get("has_source", False),
        "folder_id": doc.get("folder_id"),
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

    summary = {
        "dov_words": len(base.get("dov", {}).get("coordinates", {})),
        "dod_words": len(base.get("dod", {}).get("coordinates", {})),
        "strong_signal": len(base.get("final_signal", {}).get("strong_signal", [])),
    }

    now = datetime.now(timezone.utc)
    doc = {
        "_id": project_id,
        "uid": uid,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "source": source,
        "analysis_options": base.get("metadata", {}),
        "summary": summary,
        "interpretations": [],
        "has_source": False,
    }
    kemkim_projects_db.insert_one(doc)
    return _doc_out(doc)


def list_projects(uid: str) -> list:
    docs = kemkim_projects_db.find({"uid": uid}).sort("created_at", -1)
    return [_doc_out(d) for d in docs]


def list_all_projects() -> list:
    """관리자용: 모든 사용자의 프로젝트를 소유자 이름과 함께 반환한다."""
    docs = list(kemkim_projects_db.find({}).sort("created_at", -1))
    names = get_user_names([d["uid"] for d in docs])
    out = []
    for d in docs:
        item = _doc_out(d)
        item["owner_uid"] = d["uid"]
        item["owner_name"] = names.get(d["uid"], d["uid"])
        out.append(item)
    return out


def _get_owned_doc(uid: str, project_id: str, is_admin: bool = False) -> dict:
    doc = kemkim_projects_db.find_one({"_id": project_id})
    if not doc:
        raise NotFound("프로젝트를 찾을 수 없습니다.")
    if doc["uid"] != uid and not is_admin:
        raise Forbidden("이 프로젝트에 접근할 권한이 없습니다.")
    return doc


def get_project(uid: str, project_id: str, is_admin: bool = False) -> dict:
    return _doc_out(_get_owned_doc(uid, project_id, is_admin))


def rename_project(uid: str, project_id: str, new_name: str) -> dict:
    _get_owned_doc(uid, project_id)
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("이름을 입력해주세요.")
    kemkim_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc)}},
    )
    return _doc_out(_get_owned_doc(uid, project_id))


def delete_project(uid: str, project_id: str):
    _get_owned_doc(uid, project_id)
    kemkim_projects_db.delete_one({"_id": project_id})
    shutil.rmtree(_project_dir(uid, project_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# 폴더 (사이드바 프로젝트 정리용 — 각자 자기 폴더만 관리한다)
# ---------------------------------------------------------------------------


def _folder_out(doc: dict) -> dict:
    return {
        "folder_id": doc["_id"],
        "name": doc["name"],
        "created_at": _iso(doc["created_at"]),
        "updated_at": _iso(doc["updated_at"]),
    }


def list_folders(uid: str) -> list:
    docs = kemkim_folders_db.find({"uid": uid}).sort("name", 1)
    return [_folder_out(d) for d in docs]


def list_all_folders() -> list:
    """관리자용: 모든 사용자의 폴더를 소유자와 함께 반환한다(정리는 각자 자기 것만 하므로
    프로젝트처럼 읽기 전용으로만 보여준다)."""
    docs = list(kemkim_folders_db.find({}).sort("name", 1))
    names = get_user_names([d["uid"] for d in docs])
    out = []
    for d in docs:
        item = _folder_out(d)
        item["owner_uid"] = d["uid"]
        item["owner_name"] = names.get(d["uid"], d["uid"])
        out.append(item)
    return out


def create_folder(uid: str, name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("폴더 이름을 입력해주세요.")
    folder_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    doc = {"_id": folder_id, "uid": uid, "name": name, "created_at": now, "updated_at": now}
    kemkim_folders_db.insert_one(doc)
    return _folder_out(doc)


def _get_owned_folder(uid: str, folder_id: str) -> dict:
    doc = kemkim_folders_db.find_one({"_id": folder_id})
    if not doc:
        raise NotFound("폴더를 찾을 수 없습니다.")
    if doc["uid"] != uid:
        raise Forbidden("이 폴더에 접근할 권한이 없습니다.")
    return doc


def rename_folder(uid: str, folder_id: str, new_name: str) -> dict:
    _get_owned_folder(uid, folder_id)
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("이름을 입력해주세요.")
    kemkim_folders_db.update_one(
        {"_id": folder_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc)}},
    )
    return _folder_out(_get_owned_folder(uid, folder_id))


def delete_folder(uid: str, folder_id: str):
    _get_owned_folder(uid, folder_id)
    kemkim_folders_db.delete_one({"_id": folder_id})
    # 폴더 안에 있던 프로젝트는 삭제하지 않고 미분류(폴더 없음) 상태로 되돌린다.
    kemkim_projects_db.update_many(
        {"uid": uid, "folder_id": folder_id},
        {"$set": {"folder_id": None, "updated_at": datetime.now(timezone.utc)}},
    )


def move_project_folder(uid: str, project_id: str, folder_id: str | None) -> dict:
    """프로젝트를 폴더로 옮기거나(folder_id 지정) 미분류로 뺀다(folder_id=None).
    자기 프로젝트만 정리할 수 있으므로 관리자 우회 없이 소유자 전용이다."""
    doc = _get_owned_doc(uid, project_id)
    if folder_id:
        _get_owned_folder(uid, folder_id)
    kemkim_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"folder_id": folder_id, "updated_at": datetime.now(timezone.utc)}},
    )
    return _doc_out(kemkim_projects_db.find_one({"_id": project_id}))


# ---------------------------------------------------------------------------
# 분석 결과 (좌표/신호/기간별 표/추적)
# ---------------------------------------------------------------------------


def load_graph(uid: str, project_id: str, is_admin: bool = False) -> dict:
    doc = _get_owned_doc(uid, project_id, is_admin)
    # 파일은 소유자(doc["uid"]) 아래에 있으므로 관리자가 대신 조회할 때도 그 경로를 써야 한다.
    path = _base_json_path(doc["uid"], project_id)
    if not os.path.exists(path):
        raise NotFound("분석 결과를 찾을 수 없습니다.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 해석용 원본 CSV
# ---------------------------------------------------------------------------


def save_source_csv(uid: str, project_id: str, content: bytes):
    _get_owned_doc(uid, project_id)
    with open(_source_csv_path(uid, project_id), "wb") as f:
        f.write(content)
    kemkim_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"has_source": True, "updated_at": datetime.now(timezone.utc)}},
    )


def load_source_csv(uid: str, project_id: str, is_admin: bool = False) -> pd.DataFrame:
    doc = _get_owned_doc(uid, project_id, is_admin)
    path = _source_csv_path(doc["uid"], project_id)
    if not os.path.exists(path):
        raise NotFound(
            "해석에 사용할 원본(토큰화 전) CSV가 아직 첨부되지 않았습니다. 먼저 업로드해주세요."
        )
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


# ---------------------------------------------------------------------------
# 해석 결과
# ---------------------------------------------------------------------------


def save_interpretation(uid: str, project_id: str, interpretation: dict) -> dict:
    _get_owned_doc(uid, project_id)
    interp_dir = _interpretations_dir(uid, project_id)
    os.makedirs(interp_dir, exist_ok=True)
    with open(
        os.path.join(interp_dir, f"{interpretation['id']}.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(interpretation, f, ensure_ascii=False)

    now = datetime.now(timezone.utc)
    kemkim_projects_db.update_one(
        {"_id": project_id},
        {
            "$push": {
                "interpretations": {
                    "id": interpretation["id"],
                    "keywords": interpretation["keywords"],
                    "match_mode": interpretation["match_mode"],
                    "has_ai": bool(interpretation.get("ai_analysis")),
                    "created_at": interpretation["created_at"],
                }
            },
            "$set": {"updated_at": now},
        },
    )
    return interpretation


def list_interpretations(uid: str, project_id: str, is_admin: bool = False) -> list:
    doc = _get_owned_doc(uid, project_id, is_admin)
    return doc.get("interpretations", [])


def load_interpretation(
    uid: str, project_id: str, interpretation_id: str, is_admin: bool = False
) -> dict:
    doc = _get_owned_doc(uid, project_id, is_admin)
    path = os.path.join(
        _interpretations_dir(doc["uid"], project_id), f"{interpretation_id}.json"
    )
    if not os.path.exists(path):
        raise NotFound("해석 결과를 찾을 수 없습니다.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 원본 zip 재다운로드
# ---------------------------------------------------------------------------


def zip_raw(uid: str, project_id: str, is_admin: bool = False) -> str:
    """raw/ 폴더를 즉석에서 압축해 zip 경로를 반환한다 (호출자가 응답 후 삭제 책임)."""
    doc = _get_owned_doc(uid, project_id, is_admin)
    owner_uid = doc["uid"]
    raw_dir = _raw_dir(owner_uid, project_id)
    if not os.path.isdir(raw_dir):
        raise NotFound("원본 분석 결과를 찾을 수 없습니다.")
    tmp_base = os.path.join(
        _project_dir(owner_uid, project_id), f"download_{uuid.uuid4().hex}"
    )
    archive_path = shutil.make_archive(tmp_base, "zip", raw_dir)
    return archive_path
