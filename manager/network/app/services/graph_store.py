# app/services/graph_store.py
"""
분석 서버(network_service.py)가 만든 결과 zip(nodes*.csv, edges*.csv 포함)을 업로드받아
서버에서 파싱·정규화하고, 뷰어가 바로 그릴 수 있는 JSON으로 세션 디렉토리에 저장한다.

network_template.html처럼 데이터를 HTML 문자열 안에 통째로 박아 넣지 않고,
세션 단위로 디스크에 저장해두었다가 API(fetch)로 필요한 만큼만 내려준다.
"""
import io
import json
import os
import re
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

SESSION_TTL_SECONDS = 24 * 60 * 60  # 24시간 뒤 자동 정리

_NODES_RE = re.compile(r"^nodes(.*)\.csv$")
_RESERVED_NODE_COLS = {"word", "frequency", "x", "y", "community"}


def _session_dir(session_id: str) -> str:
    return os.path.join(STORAGE_DIR, session_id)


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
                "group": int(row["community"]) if has_community and not pd.isna(row["community"]) else 0,
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
                "cooccur": int(row["cooccur"]) if "cooccur" in edges_df.columns and not pd.isna(row["cooccur"]) else None,
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


def create_session(upload_bytes: bytes, original_filename: str) -> dict:
    session_id = uuid.uuid4().hex
    root = _session_dir(session_id)
    extract_dir = os.path.join(root, "extract")
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(upload_bytes)) as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(root, ignore_errors=True)
        raise ValueError("zip 파일이 아니거나 손상되었습니다.")

    # zip 안에 폴더가 한 겹 더 있는 경우(폴더를 그대로 압축한 경우) 보정
    search_root = extract_dir
    entries = [e for e in os.listdir(extract_dir) if not e.startswith("__MACOSX")]
    if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
        candidate = os.path.join(extract_dir, entries[0])
        if _find_network_pairs(candidate):
            search_root = candidate

    pairs = _find_network_pairs(search_root)
    if not pairs:
        shutil.rmtree(root, ignore_errors=True)
        raise ValueError(
            "nodes.csv / edges.csv 짝을 찾지 못했습니다. "
            "네트워크 분석 결과 zip을 그대로 업로드해주세요."
        )

    networks = []
    for tag, nodes_csv, edges_csv in pairs:
        graph = _build_graph_json(search_root, tag, nodes_csv, edges_csv)
        with open(os.path.join(root, f"graph{tag or '_main'}.json"), "w", encoding="utf-8") as f:
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

    meta = {
        "session_id": session_id,
        "original_filename": original_filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "networks": networks,
    }
    with open(os.path.join(root, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    return meta


def load_meta(session_id: str) -> dict:
    path = os.path.join(_session_dir(session_id), "meta.json")
    if not os.path.exists(path):
        raise FileNotFoundError("세션을 찾을 수 없습니다. (만료되었거나 잘못된 링크)")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_graph(session_id: str, tag: str = "") -> dict:
    path = os.path.join(_session_dir(session_id), f"graph{tag or '_main'}.json")
    if not os.path.exists(path):
        raise FileNotFoundError("네트워크를 찾을 수 없습니다.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cleanup_expired_sessions(ttl_seconds: int = SESSION_TTL_SECONDS) -> int:
    """오래된 업로드 세션을 정리한다. 삭제된 세션 수를 반환."""
    now = time.time()
    removed = 0
    if not os.path.isdir(STORAGE_DIR):
        return 0
    for name in os.listdir(STORAGE_DIR):
        path = os.path.join(STORAGE_DIR, name)
        try:
            mtime = os.path.getmtime(os.path.join(path, "meta.json"))
        except OSError:
            mtime = os.path.getmtime(path) if os.path.exists(path) else 0
        if now - mtime > ttl_seconds:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed
