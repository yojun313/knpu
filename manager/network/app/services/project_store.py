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

from app.db import network_projects_db

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


def _extract_zip_and_build(root: str, upload_bytes: bytes) -> list:
    """zip을 root(프로젝트 디렉토리)에 풀고 graph{tag}.json들을 만들어 networks 메타 목록을 반환."""
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
    return networks


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
    }


def create_project(
    uid: str, upload_bytes: bytes, name: str, source: str = "upload"
) -> dict:
    project_id = uuid.uuid4().hex
    root = _project_dir(uid, project_id)
    os.makedirs(root, exist_ok=True)

    try:
        networks = _extract_zip_and_build(root, upload_bytes)
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
    }
    network_projects_db.insert_one(doc)
    return _doc_out(doc)


def list_projects(uid: str) -> list:
    docs = network_projects_db.find({"uid": uid}).sort("created_at", -1)
    return [_doc_out(d) for d in docs]


def _get_owned_doc(uid: str, project_id: str) -> dict:
    doc = network_projects_db.find_one({"_id": project_id})
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
    network_projects_db.update_one(
        {"_id": project_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc)}},
    )
    return _doc_out(_get_owned_doc(uid, project_id))


def delete_project(uid: str, project_id: str):
    _get_owned_doc(uid, project_id)
    network_projects_db.delete_one({"_id": project_id})
    shutil.rmtree(_project_dir(uid, project_id), ignore_errors=True)


def load_graph(uid: str, project_id: str, tag: str = "") -> dict:
    _get_owned_doc(uid, project_id)
    path = os.path.join(_project_dir(uid, project_id), f"graph{tag or '_main'}.json")
    if not os.path.exists(path):
        raise NotFound("네트워크를 찾을 수 없습니다.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
