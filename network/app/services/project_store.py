# app/services/project_store.py
"""
분석 서버(network_service.py)가 만든 결과 zip(nodes*.csv, edges*.csv 포함)을 로그인한
사용자의 "프로젝트"로 저장한다. 그래프 JSON은 /mnt/ssd/network/{uid}/{project_id}/ 아래
디스크에 두고, 프로젝트 메타데이터(이름 등)는 MongoDB(network-projects 컬렉션)에 둔다.

세션 방식과 달리 TTL 자동 삭제가 없다 — 사용자가 명시적으로 삭제하기 전까지 보존된다.
"""

import io
import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.db import network_projects_db, network_folders_db, get_user_names

PROJECT_ROOT = os.getenv("NETWORK_PROJECT_ROOT", "/mnt/ssd/network")
os.makedirs(PROJECT_ROOT, exist_ok=True)

_NODES_RE = re.compile(r"^nodes(.*)\.csv$")
_RESERVED_NODE_COLS = {"word", "frequency", "x", "y", "community"}


class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


def _project_dir(uid: str, project_id: str) -> str:
    return os.path.join(PROJECT_ROOT, uid, project_id)


def _label_for_tag(tag: str) -> str:
    return "전체" if not tag else tag.lstrip("_")


def _find_network_pairs(root: str):
    """추출된 폴더에서 nodes*.csv / edges*.csv 짝을 모두 찾는다."""
    pairs = []
    for name in sorted(os.listdir(root)):
        m = _NODES_RE.match(name)
        if not m:
            continue
        tag = m.group(1)
        edges_name = f"edges{tag}.csv"
        if os.path.exists(os.path.join(root, edges_name)):
            pairs.append((tag, name, edges_name))
    return pairs


def _build_graph_json(root: str, tag: str, nodes_csv: str, edges_csv: str) -> dict:
    nodes_df = pd.read_csv(os.path.join(root, nodes_csv), encoding="utf-8-sig")
    edges_df = pd.read_csv(os.path.join(root, edges_csv), encoding="utf-8-sig")

    has_xy = "x" in nodes_df.columns and "y" in nodes_df.columns
    has_community = "community" in nodes_df.columns

    metric_cols = [c for c in nodes_df.columns if c not in _RESERVED_NODE_COLS]

    word_to_id = {w: i for i, w in enumerate(nodes_df["word"].astype(str))}

    nodes = []
    for i, row in nodes_df.iterrows():
        info = {}
        for c in metric_cols:
            v = row[c]
            if pd.isna(v):
                continue
            info[c] = float(v) if isinstance(v, (float, np.floating)) else v
        nodes.append(
            {
                "id": int(i),
                "label": str(row["word"]),
                "freq": int(row["frequency"]) if not pd.isna(row["frequency"]) else 0,
                "x": float(row["x"]) if has_xy and not pd.isna(row["x"]) else None,
                "y": float(row["y"]) if has_xy and not pd.isna(row["y"]) else None,
                "group": int(row["community"])
                if has_community and not pd.isna(row["community"])
                else 0,
                "info": info,
            }
        )

    edges = []
    for _, row in edges_df.iterrows():
        s = word_to_id.get(str(row["source"]))
        t = word_to_id.get(str(row["target"]))
        if s is None or t is None:
            continue
        edges.append(
            {
                "source": s,
                "target": t,
                "weight": float(row["weight"]),
                "cooccur": int(row["cooccur"])
                if "cooccur" in edges_df.columns and not pd.isna(row["cooccur"])
                else None,
            }
        )

    return {
        "tag": tag,
        "label": _label_for_tag(tag),
        "has_community": has_community,
        "has_layout": has_xy,
        "metric_keys": metric_cols,
        "nodes": nodes,
        "edges": edges,
    }


def _read_analysis_options(search_root: str) -> dict | None:
    """MANAGER에서 분석할 때 쓴 옵션·분석 시각(analysis_options.json)이 있으면 읽어온다.
    수동으로 zip을 업로드한 경우 등 파일이 없으면 None."""
    path = os.path.join(search_root, "analysis_options.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _extract_zip_and_build(root: str, upload_bytes: bytes) -> tuple:
    """zip을 root(프로젝트 디렉토리)에 풀고 graph{tag}.json들을 만들어
    (networks 메타 목록, 분석 옵션 or None)을 반환."""
    extract_dir = os.path.join(root, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(upload_bytes)) as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        raise ValueError("zip 파일이 아니거나 손상되었습니다.")

    search_root = extract_dir
    entries = [e for e in os.listdir(extract_dir) if not e.startswith("__MACOSX")]
    if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
        candidate = os.path.join(extract_dir, entries[0])
        if _find_network_pairs(candidate):
            search_root = candidate

    pairs = _find_network_pairs(search_root)
    if not pairs:
        raise ValueError(
            "nodes.csv / edges.csv 짝을 찾지 못했습니다. "
            "네트워크 분석 결과 zip을 그대로 업로드해주세요."
        )

    analysis_options = _read_analysis_options(search_root)

    networks = []
    for tag, nodes_csv, edges_csv in pairs:
        graph = _build_graph_json(search_root, tag, nodes_csv, edges_csv)
        with open(
            os.path.join(root, f"graph{tag or '_main'}.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(graph, f, ensure_ascii=False)
        networks.append(
            {
                "tag": tag,
                "label": graph["label"],
                "nodes": len(graph["nodes"]),
                "edges": len(graph["edges"]),
            }
        )

    shutil.rmtree(extract_dir, ignore_errors=True)
    return networks, analysis_options


def _iso(dt) -> str:
    return dt.isoformat() if hasattr(dt, "isoformat") else dt


def _doc_out(doc: dict) -> dict:
    return {
        "project_id": doc["_id"],
        "name": doc["name"],
        "networks": doc["networks"],
        "created_at": _iso(doc["created_at"]),
        "updated_at": _iso(doc["updated_at"]),
        "source": doc.get("source", "upload"),
        "analysis_options": doc.get("analysis_options"),
        "folder_id": doc.get("folder_id"),
    }


def create_project(
    uid: str, upload_bytes: bytes, name: str, source: str = "upload"
) -> dict:
    project_id = uuid.uuid4().hex
    root = _project_dir(uid, project_id)
    os.makedirs(root, exist_ok=True)

    try:
        networks, analysis_options = _extract_zip_and_build(root, upload_bytes)
    except ValueError:
        shutil.rmtree(root, ignore_errors=True)
        raise

    now = datetime.now(timezone.utc)
    doc = {
        "_id": project_id,
        "uid": uid,
        "name": name,
        "networks": networks,
        "created_at": now,
        "updated_at": now,
        "source": source,
        "analysis_options": analysis_options,
    }
    network_projects_db.insert_one(doc)
    return _doc_out(doc)


def list_projects(uid: str) -> list:
    docs = network_projects_db.find({"uid": uid}).sort("created_at", -1)
    return [_doc_out(d) for d in docs]


def list_all_projects() -> list:
    """관리자용: 모든 사용자의 프로젝트를 소유자 이름과 함께 반환한다."""
    docs = list(network_projects_db.find({}).sort("created_at", -1))
    names = get_user_names([d["uid"] for d in docs])
    out = []
    for d in docs:
        item = _doc_out(d)
        item["owner_uid"] = d["uid"]
        item["owner_name"] = names.get(d["uid"], d["uid"])
        out.append(item)
    return out


def _get_owned_doc(uid: str, project_id: str, is_admin: bool = False) -> dict:
    doc = network_projects_db.find_one({"_id": project_id})
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
    network_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc)}},
    )
    return _doc_out(_get_owned_doc(uid, project_id))


def delete_project(uid: str, project_id: str):
    _get_owned_doc(uid, project_id)
    network_projects_db.delete_one({"_id": project_id})
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
    docs = network_folders_db.find({"uid": uid}).sort("name", 1)
    return [_folder_out(d) for d in docs]


def list_all_folders() -> list:
    """관리자용: 모든 사용자의 폴더를 소유자와 함께 반환한다(정리는 각자 자기 것만 하므로
    프로젝트처럼 읽기 전용으로만 보여준다)."""
    docs = list(network_folders_db.find({}).sort("name", 1))
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
    network_folders_db.insert_one(doc)
    return _folder_out(doc)


def _get_owned_folder(uid: str, folder_id: str) -> dict:
    doc = network_folders_db.find_one({"_id": folder_id})
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
    network_folders_db.update_one(
        {"_id": folder_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc)}},
    )
    return _folder_out(_get_owned_folder(uid, folder_id))


def delete_folder(uid: str, folder_id: str):
    _get_owned_folder(uid, folder_id)
    network_folders_db.delete_one({"_id": folder_id})
    # 폴더 안에 있던 프로젝트는 삭제하지 않고 미분류(폴더 없음) 상태로 되돌린다.
    network_projects_db.update_many(
        {"uid": uid, "folder_id": folder_id},
        {"$set": {"folder_id": None, "updated_at": datetime.now(timezone.utc)}},
    )


def move_project_folder(uid: str, project_id: str, folder_id: str | None) -> dict:
    """프로젝트를 폴더로 옮기거나(folder_id 지정) 미분류로 뺀다(folder_id=None).
    자기 프로젝트만 정리할 수 있으므로 관리자 우회 없이 소유자 전용이다."""
    doc = _get_owned_doc(uid, project_id)
    if folder_id:
        _get_owned_folder(uid, folder_id)
    network_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"folder_id": folder_id, "updated_at": datetime.now(timezone.utc)}},
    )
    return _doc_out(network_projects_db.find_one({"_id": project_id}))


def load_graph(uid: str, project_id: str, tag: str = "", is_admin: bool = False) -> dict:
    doc = _get_owned_doc(uid, project_id, is_admin)
    # 파일은 소유자(doc["uid"]) 아래에 있으므로 관리자가 대신 조회할 때도 그 경로를 써야 한다.
    path = os.path.join(
        _project_dir(doc["uid"], project_id), f"graph{tag or '_main'}.json"
    )
    if not os.path.exists(path):
        raise NotFound("네트워크를 찾을 수 없습니다.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
