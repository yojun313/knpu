# app/services/network_service.py
import os

os.environ.setdefault("OMP_NUM_THREADS", "1")  # period 병렬 시 워커 내부에서 재설정
import re
import json
import shutil
import traceback
from datetime import datetime
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import requests
from scipy.sparse import csr_matrix, vstack
import igraph as ig

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from app.libs.progress import send_message
from app.config import NETWORK_VIEWER_URL
from scipy.spatial import ConvexHull
from xml.sax.saxutils import escape


# 한글 폰트 (GPU 서버 환경에 맞게 경로/이름만 맞춰줘)
try:
    plt.rcParams["font.family"] = "NanumGothic"
except Exception:
    pass
plt.rcParams["axes.unicode_minus"] = False


# ────────────────────────── 유틸 ──────────────────────────
def _split_tokens(cell):
    if not isinstance(cell, str):
        return []
    return [t.strip() for t in cell.split(",") if t.strip()]


def _make_units(cell, scope, window):
    """하나의 셀(행) → 공출현을 셀 여러 '단위'(문서/문장/윈도우) 리스트로."""
    toks = _split_tokens(cell)
    if not toks:
        return []
    if scope == "document":
        return [toks]
    if scope == "window":
        w = max(2, int(window))
        if len(toks) <= w:
            return [toks]
        return [toks[i : i + w] for i in range(len(toks) - w + 1)]
    # sentence 단위는 이미 토큰화 단계에서 문장 경계가 사라졌다고 보고 document로 폴백
    return [toks]


def _period_key(dt_series, period):
    if period == "1y":
        return dt_series.dt.to_period("Y").astype(str)
    if period == "6m":
        return (
            dt_series.dt.year.astype(str)
            + "-H"
            + ((dt_series.dt.month.sub(1) // 6) + 1).astype(str)
        )
    if period == "3m":
        return dt_series.dt.to_period("Q").astype(str)
    if period == "1m":
        return dt_series.dt.to_period("M").astype(str)
    if period == "1w":
        return dt_series.dt.to_period("W").astype(str)
    return None  # total


# ────────────────────── 공출현 행렬(병렬) ──────────────────────
def _build_vocab(texts, scope, window, min_freq, top_n):
    df_counter = Counter()
    for cell in texts:
        seen = set()
        for unit in _make_units(cell, scope, window):
            seen.update(unit)
        df_counter.update(seen)
    items = [(w, c) for w, c in df_counter.items() if c >= min_freq]
    items.sort(key=lambda x: -x[1])
    if top_n and top_n > 0:
        items = items[:top_n]
    vocab = {w: i for i, (w, _) in enumerate(items)}
    words = [w for w, _ in items]
    return vocab, words


def _transform_chunk(args):
    chunk, vocab, scope, window = args
    rows, cols = [], []
    r = 0
    for cell in chunk:
        for unit in _make_units(cell, scope, window):
            idxs = {vocab[w] for w in unit if w in vocab}
            if len(idxs) < 2:
                continue
            for c in idxs:
                rows.append(r)
                cols.append(c)
            r += 1
    data = np.ones(len(rows), dtype=np.float32)
    return csr_matrix((data, (rows, cols)), shape=(max(r, 1), len(vocab)))


def build_cooccurrence(texts, vocab, scope, window, n_workers=4):
    """문서-단어 이진행렬을 병렬 생성 후 DT.T @ DT 로 공출현 행렬."""
    texts = list(texts)
    if n_workers > 1 and len(texts) > 5000:
        n = max(1, len(texts) // n_workers)
        chunks = [texts[i : i + n] for i in range(0, len(texts), n)]
        args = [(c, vocab, scope, window) for c in chunks]
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            parts = list(ex.map(_transform_chunk, args))
        DT = vstack(parts).tocsr()
    else:
        DT = _transform_chunk((texts, vocab, scope, window)).tocsr()

    cooc = (DT.T @ DT).tocoo()  # 단어×단어, BLAS 병렬
    freq = np.asarray(DT.sum(axis=0)).ravel()  # 단어별 등장 단위 수
    n_units = DT.shape[0]
    return cooc, freq, n_units


# ────────────────────── 연관성 척도 ──────────────────────
def build_edges(cooc, freq, n_units, measure, min_edge_weight):
    """상삼각만, 척도 계산해서 (i, j, weight, raw) 리스트."""
    edges = []
    row, col, val = cooc.row, cooc.col, cooc.data
    for i, j, c in zip(row, col, val):
        if i >= j:
            continue
        if c < min_edge_weight:
            continue
        fi, fj = freq[i], freq[j]
        if measure == "raw":
            w = float(c)
        elif measure == "jaccard":
            w = c / (fi + fj - c) if (fi + fj - c) > 0 else 0.0
        elif measure == "cosine":
            w = c / np.sqrt(fi * fj) if fi > 0 and fj > 0 else 0.0
        elif measure == "dice":
            w = 2.0 * c / (fi + fj) if (fi + fj) > 0 else 0.0
        elif measure in ("pmi", "npmi"):
            p_ij = c / n_units
            p_i, p_j = fi / n_units, fj / n_units
            if p_ij <= 0 or p_i <= 0 or p_j <= 0:
                continue
            pmi = np.log(p_ij / (p_i * p_j))
            w = pmi / (-np.log(p_ij)) if measure == "npmi" else pmi
            if w <= 0:  # 음의 연관은 버림
                continue
        else:
            w = float(c)
        edges.append((int(i), int(j), float(w), int(c)))
    return edges


# ────────────────────── 백본(disparity filter) ──────────────────────
def disparity_filter(g, alpha):
    """Serrano et al. 백본 추출. 남길 edge 인덱스 집합."""
    strength = np.array(g.strength(weights="weight"))
    deg = np.array(g.degree())
    keep = set()
    for e in g.es:
        w = e["weight"]
        for node in (e.source, e.target):
            k = deg[node]
            s = strength[node]
            if k > 1 and s > 0:
                p = w / s
                sig = (1 - p) ** (k - 1)
                if sig < alpha:
                    keep.add(e.index)
                    break
    return keep


# ────────────────────── 그래프 분석 ──────────────────────
def analyze_graph(words, freq, edges, option, pid=None, tag=""):
    if not edges:
        return None

    g = ig.Graph()
    g.add_vertices(len(words))
    g.vs["name"] = words
    g.vs["freq"] = [int(x) for x in freq]
    g.add_edges([(e[0], e[1]) for e in edges])
    g.es["weight"] = [e[2] for e in edges]
    g.es["cooccur"] = [e[3] for e in edges]

    # 백본
    if option.get("backbone"):
        if pid:
            send_message(pid, f"{tag}백본(disparity) 추출 중...")
        keep = disparity_filter(g, float(option.get("backbone_alpha", 0.05)))
        if keep:
            g = g.subgraph_edges(list(keep), delete_vertices=False)

    # 고립 노드 제거
    g.delete_vertices([v.index for v in g.vs if g.degree(v.index) == 0])
    if g.vcount() == 0:
        return None

    # 중심성
    if pid:
        send_message(pid, f"{tag}중심성 계산 중...")
    sel = set(option.get("centralities", ["degree", "betweenness"]))
    cent = {}
    if "degree" in sel:
        cent["degree"] = g.degree()
    if "strength" in sel:
        cent["strength"] = g.strength(weights="weight")
    if "betweenness" in sel:
        # 큰 그래프면 cutoff로 근사
        cutoff = 3 if g.vcount() > 3000 else None
        cent["betweenness"] = g.betweenness(weights="weight", cutoff=cutoff)
    if "closeness" in sel:
        cent["closeness"] = g.closeness(weights="weight")
    if "eigenvector" in sel:
        cent["eigenvector"] = g.eigenvector_centrality(weights="weight")
    if "pagerank" in sel:
        cent["pagerank"] = g.pagerank(weights="weight")

    # 커뮤니티
    community = None
    modularity = None
    algo = option.get("community", "louvain")
    if algo and algo != "none":
        if pid:
            send_message(pid, f"{tag}커뮤니티 탐지({algo}) 중...")
        if algo == "leiden":
            part = g.community_leiden(objective_function="modularity", weights="weight")
        else:  # louvain
            part = g.community_multilevel(weights="weight")
        community = part.membership
        modularity = g.modularity(part, weights="weight")

    # ── 전역 지표 + 고급 노드 지표 ──
    if pid:
        send_message(pid, f"{tag}전역/고급 지표 계산 중...")
    global_metrics = {
        "nodes": g.vcount(),
        "edges": g.ecount(),
        "density": g.density(),
        "avg_degree": float(np.mean(g.degree())),
        "components": len(g.connected_components()),
        "avg_clustering": g.transitivity_avglocal_undirected(mode="zero"),
        "global_clustering": g.transitivity_undirected(mode="zero"),
    }
    # 지름·평균경로: 비연결 그래프면 최대 컴포넌트에서
    try:
        comp = g.connected_components()
        giant = comp.giant()
        global_metrics["diameter"] = giant.diameter(weights=None)
        global_metrics["avg_path_length"] = giant.average_path_length()
    except Exception:
        global_metrics["diameter"] = None
        global_metrics["avg_path_length"] = None

    # k-core 분해
    if option.get("compute_kcore", True):
        cent["coreness"] = g.coreness()

    # 구조적 공백 (Burt's constraint)
    if option.get("compute_structural_holes", True):
        try:
            cent["constraint"] = g.constraint(weights="weight")
        except Exception:
            cent["constraint"] = [None] * g.vcount()

    # 레이아웃
    if pid:
        send_message(pid, f"{tag}레이아웃 계산 중...")
    lay = option.get("layout", "fr")
    if lay == "kk":
        coords = np.array(g.layout_kamada_kawai().coords)
    elif lay == "circle":
        coords = np.array(g.layout_circle().coords)
    elif lay == "grid":
        coords = np.array(g.layout_grid().coords)
    else:
        coords = np.array(
            g.layout_fruchterman_reingold(weights=g.es["weight"], niter=500).coords
        )

    return {
        "graph": g,
        "cent": cent,
        "community": community,
        "modularity": modularity,
        "coords": coords,
        "global_metrics": global_metrics,
    }


def export_ego_networks(res, option, out_dir, tag=""):
    """상위 노드들의 ego 네트워크(1-hop)를 개별 저장."""
    g = res["graph"]
    ego_top = int(option.get("ego_top", 0))
    if ego_top <= 0:
        return
    ego_dir = os.path.join(out_dir, f"ego{tag}")
    os.makedirs(ego_dir, exist_ok=True)

    deg = np.array(g.degree())
    targets = np.argsort(deg)[::-1][:ego_top]
    for idx in targets:
        neighbors = g.neighbors(idx)
        sub_nodes = [int(idx)] + list(neighbors)
        sub = g.subgraph(sub_nodes)
        name = g.vs[int(idx)]["name"]
        safe = re.sub(r'[<>:"/\\|?*]', "_", str(name))
        sub.write_graphml(os.path.join(ego_dir, f"ego_{safe}.graphml"))
        pd.DataFrame(
            {
                "word": sub.vs["name"],
                "freq": sub.vs["freq"],
            }
        ).to_csv(
            os.path.join(ego_dir, f"ego_{safe}.csv"), index=False, encoding="utf-8-sig"
        )


# ────────────────────── 출력 ──────────────────────
def draw_network(res, option, out_png, title=""):
    g, coords = res["graph"], res["coords"]
    cent, community = res["cent"], res["community"]

    # ── 노드 크기 기준 ──
    size_by = option.get("node_size_by", "freq")
    if size_by == "freq":
        base = np.array(g.vs["freq"], dtype=float)
    else:
        base = np.array(cent.get(size_by, g.degree()), dtype=float)
    if base.max() > 0:
        sizes = 100 + 1500 * (base / base.max())
    else:
        sizes = np.full(g.vcount(), 200.0)

    # ── 노드 색 기준 (커뮤니티 or 중심성) ──
    color_by = option.get("node_color_by", "community")
    fig, ax = plt.subplots(figsize=(18, 14))

    if color_by == "community" and community is not None:
        cmap = plt.cm.tab20
        colors = [cmap(c % 20) for c in community]
        show_colorbar = False
    elif color_by in cent:
        cvals = np.array(cent[color_by], dtype=float)
        norm = (cvals - cvals.min()) / (np.ptp(cvals) or 1)
        cmap = plt.cm.viridis
        colors = [cmap(v) for v in norm]
        show_colorbar = True
    else:
        colors = ["#1428A0"] * g.vcount()
        show_colorbar = False

    # ── 커뮤니티별 배경 음영 (convex hull) ──
    if option.get("draw_hull") and community is not None:
        cmap_h = plt.cm.tab20
        for c in set(community):
            pts = coords[[i for i in range(len(community)) if community[i] == c]]
            if len(pts) < 3:
                continue
            try:
                hull = ConvexHull(pts)
                poly = pts[hull.vertices]
                ax.fill(
                    poly[:, 0], poly[:, 1], color=cmap_h(c % 20), alpha=0.08, zorder=0
                )
            except Exception:
                pass

    # ── 엣지 (가중치별 투명도 + 두께) ──
    segs, ews, ealphas = [], [], []
    ew = np.array(g.es["weight"])
    ew_norm = ew / ew.max() if len(ew) and ew.max() > 0 else ew
    for e, wn in zip(g.es, ew_norm):
        segs.append([coords[e.source], coords[e.target]])
        ews.append(0.2 + 2.5 * wn)
        ealphas.append(0.05 + 0.35 * wn)  # 약한 엣지는 더 투명
    lc = LineCollection(segs, colors="#888888", linewidths=ews, zorder=1)
    lc.set_alpha(None)
    lc.set_color([(0.53, 0.53, 0.53, a) for a in ealphas])
    ax.add_collection(lc)

    # ── 노드 ──
    sc = ax.scatter(
        coords[:, 0],
        coords[:, 1],
        s=sizes,
        c=colors,
        edgecolors="white",
        linewidths=0.6,
        zorder=2,
    )

    if show_colorbar:
        sm = plt.cm.ScalarMappable(
            cmap=cmap, norm=plt.Normalize(vmin=cvals.min(), vmax=cvals.max())
        )
        sm.set_array([])
        fig.colorbar(sm, ax=ax, shrink=0.6, label=color_by)

    # ── 라벨 (노드에 정확히 붙임) ──
    label_top = int(option.get("label_top", 40))
    top_idx = np.argsort(base)[::-1][:label_top]
    texts = []
    for i in top_idx:
        t = ax.text(
            coords[i, 0],
            coords[i, 1],
            g.vs[i]["name"],
            fontsize=9,
            ha="center",
            va="center",
            zorder=4,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7),
        )
        texts.append(t)

    # adjust_labels가 명시적으로 True일 때만 겹침 방지 시도 (기본 꺼짐)
    if option.get("adjust_labels", False) and texts:
        try:
            from adjustText import adjust_text

            adjust_text(
                texts,
                ax=ax,
                x=coords[top_idx, 0],
                y=coords[top_idx, 1],
                only_move={"text": "xy", "points": ""},
                force_text=(0.1, 0.15),
                arrowprops=dict(arrowstyle="-", color="#999999", lw=0.6),
            )
        except Exception:
            pass

    ax.set_title(title, fontsize=18)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)


_GEXF_PALETTE = [
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#E45756",
    "#72B7B2",
    "#FF9DA6",
    "#9D755D",
    "#BAB0AC",
    "#B279A2",
    "#EECA3B",
    "#59A14F",
    "#9C755F",
    "#79706E",
    "#D37295",
    "#8CD17D",
]


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _scale_coords(coords, span=1000.0):
    """igraph FR 좌표는 범위가 작아서 Gephi에서 다 겹친다. 넓게 펴준다."""
    c = np.asarray(coords, dtype=float)
    mins, maxs = c.min(axis=0), c.max(axis=0)
    rng = np.where(maxs - mins == 0, 1.0, maxs - mins)
    return (c - mins) / rng * span


def _xa(s):  # XML 속성값 안전하게 escape (따옴표까지)
    return escape(str(s), {'"': "&quot;"})


def _write_gexf(res, out_path):
    """Gephi가 좌표/크기/색을 그대로 반영하도록 viz 확장 포함 GEXF 저장."""
    g = res["graph"]
    cent = res["cent"]
    community = res["community"]
    coords = _scale_coords(res["coords"], span=1000.0)

    # 노드 크기: freq 기반 (Gephi 좌표계 기준 지름 10~50)
    freq = np.array(g.vs["freq"], dtype=float)
    fmax = freq.max() if freq.size and freq.max() > 0 else 1.0
    sizes = 10.0 + 40.0 * (freq / fmax)

    # 노드 속성 컬럼 정의: frequency + 중심성들 (+ community)
    attr_cols = [("frequency", "integer")]
    attr_cols += [(k, "double") for k in cent.keys()]
    if community is not None:
        attr_cols.append(("community", "integer"))
    attr_ids = {title: str(i) for i, (title, _) in enumerate(attr_cols)}

    def node_color(i):
        if community is not None:
            return _hex_to_rgb(_GEXF_PALETTE[int(community[i]) % len(_GEXF_PALETTE)])
        return (20, 40, 160)  # 기본 블루

    L = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append(
        '<gexf xmlns="http://gexf.net/1.3" version="1.3" '
        'xmlns:viz="http://gexf.net/1.3/viz" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://gexf.net/1.3 '
        'http://gexf.net/1.3/gexf.xsd">'
    )
    L.append(
        f'  <meta lastmodifieddate="{datetime.now():%Y-%m-%d}">'
        f"<creator>network_service</creator></meta>"
    )
    L.append('  <graph mode="static" defaultedgetype="undirected">')

    # 속성 정의
    L.append('    <attributes class="node">')
    for title, typ in attr_cols:
        L.append(
            f'      <attribute id="{attr_ids[title]}" title="{_xa(title)}" type="{typ}"/>'
        )
    L.append("    </attributes>")

    # 노드
    L.append("    <nodes>")
    for i, v in enumerate(g.vs):
        L.append(f'      <node id="{i}" label="{_xa(v["name"])}">')
        L.append("        <attvalues>")
        L.append(
            f'          <attvalue for="{attr_ids["frequency"]}" value="{int(v["freq"])}"/>'
        )
        for k, arr in cent.items():
            val = arr[i]
            if val is not None:
                L.append(
                    f'          <attvalue for="{attr_ids[k]}" value="{float(val):.6f}"/>'
                )
        if community is not None:
            L.append(
                f'          <attvalue for="{attr_ids["community"]}" value="{int(community[i])}"/>'
            )
        L.append("        </attvalues>")
        r, gc, b = node_color(i)
        L.append(f'        <viz:size value="{sizes[i]:.2f}"/>')
        L.append(
            f'        <viz:position x="{coords[i, 0]:.4f}" y="{coords[i, 1]:.4f}" z="0.0"/>'
        )
        L.append(f'        <viz:color r="{r}" g="{gc}" b="{b}"/>')
        L.append("      </node>")
    L.append("    </nodes>")

    # 엣지 (weight는 GEXF 네이티브 속성이라 Gephi가 바로 인식)
    L.append("    <edges>")
    for eid, e in enumerate(g.es):
        L.append(
            f'      <edge id="{eid}" source="{e.source}" target="{e.target}" weight="{float(e["weight"]):.6f}"/>'
        )
    L.append("    </edges>")

    L.append("  </graph>")
    L.append("</gexf>")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def export_files(res, option, out_dir, tag=""):
    os.makedirs(out_dir, exist_ok=True)
    g, cent, community = res["graph"], res["cent"], res["community"]
    coords = _scale_coords(res["coords"], span=1000.0)

    # nodes.csv (x/y: 온라인 뷰어(network.knpu.re.kr)가 분석 시 계산된 레이아웃을
    # 그대로 재사용할 수 있도록 함께 저장)
    node_rows = {
        "word": g.vs["name"],
        "frequency": g.vs["freq"],
        "x": coords[:, 0],
        "y": coords[:, 1],
    }
    for k, v in cent.items():
        node_rows[k] = v
    if community is not None:
        node_rows["community"] = community
    pd.DataFrame(node_rows).to_csv(
        os.path.join(out_dir, f"nodes{tag}.csv"), index=False, encoding="utf-8-sig"
    )

    # edges.csv
    pd.DataFrame(
        {
            "source": [g.vs[e.source]["name"] for e in g.es],
            "target": [g.vs[e.target]["name"] for e in g.es],
            "weight": g.es["weight"],
            "cooccur": g.es["cooccur"],
        }
    ).to_csv(
        os.path.join(out_dir, f"edges{tag}.csv"), index=False, encoding="utf-8-sig"
    )

    _write_gexf(res, os.path.join(out_dir, f"network{tag}.gexf"))

    # 시각화
    draw_network(
        res, option, os.path.join(out_dir, f"network{tag}.png"), title=tag or "Network"
    )

    # summary
    with open(os.path.join(out_dir, f"summary{tag}.txt"), "w", encoding="utf-8") as f:
        f.write(f"nodes: {g.vcount()}\nedges: {g.ecount()}\n")
        f.write(f"density: {g.density():.6f}\n")
        f.write(f"avg_degree: {np.mean(g.degree()):.4f}\n")
        f.write(f"components: {len(g.connected_components())}\n")
        if res["modularity"] is not None:
            f.write(f"modularity: {res['modularity']:.4f}\n")
            f.write(f"communities: {len(set(community))}\n")

    export_ego_networks(res, option, out_dir, tag=tag)


def _write_viewer_readme(out_dir):
    """온라인 인터랙티브 뷰어 안내. 뷰어 자체는 더 이상 결과에 동봉하지 않고,
    nodes.csv/edges.csv 를 뷰어 사이트에 업로드해 서버에서 렌더링한다."""
    path = os.path.join(out_dir, "인터랙티브_뷰어_안내.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "인터랙티브 네트워크 뷰어\n"
            "========================\n\n"
            f"이 폴더(zip)를 통째로 {NETWORK_VIEWER_URL} 에 업로드하면\n"
            "마우스로 확대·검색·필터가 되는 인터랙티브 네트워크를 바로 확인할 수 있습니다.\n"
            "(nodes.csv, edges.csv 를 읽어 서버에서 그래프를 구성합니다.)\n\n"
            "자세한 사용법은 매뉴얼의 '인터랙티브 뷰어' 장을 참고하세요:\n"
            "https://knpu.re.kr/manual/network\n"
        )


_MEASURE_LABELS = {
    "raw": "동시출현 빈도 (raw)",
    "jaccard": "Jaccard",
    "cosine": "Cosine",
    "dice": "Dice",
    "pmi": "PMI",
    "npmi": "NPMI",
}
_PERIOD_LABELS = {
    "total": "전체 통합",
    "1y": "1년",
    "6m": "6개월",
    "3m": "3개월",
    "1m": "1개월",
    "1w": "1주",
}
_COMMUNITY_LABELS = {"louvain": "Louvain", "leiden": "Leiden", "none": "사용 안 함"}
_LAYOUT_LABELS = {
    "fr": "Fruchterman-Reingold",
    "kk": "Kamada-Kawai",
    "circle": "Circle",
    "grid": "Grid",
}
_SCOPE_LABELS = {"document": "문서 단위", "window": "슬라이딩 윈도우"}


def _write_analysis_options(out_dir, option, project_name):
    """분석 시 사용한 옵션·시각을 결과 zip에 함께 저장한다 (analysis_options.json).
    온라인 뷰어가 이 파일을 읽어 '이 결과가 어떤 설정으로 만들어졌는지' 보여준다."""
    opts = {k: v for k, v in option.items() if k != "pid"}
    meta = {
        "analyzed_at": datetime.now().isoformat(),
        "source_filename": project_name,
        "options": opts,
        "options_label": {
            "대상 열": opts.get("text_col"),
            "공출현 단위": _SCOPE_LABELS.get(opts.get("scope"), opts.get("scope")),
            "윈도우 크기": opts.get("window")
            if opts.get("scope") == "window"
            else None,
            "연관성 척도": _MEASURE_LABELS.get(
                opts.get("measure"), opts.get("measure")
            ),
            "기간 분할": _PERIOD_LABELS.get(opts.get("period"), opts.get("period")),
            "최소 단어 빈도": opts.get("min_freq"),
            "최소 동시출현 횟수": opts.get("min_edge_weight"),
            "최대 노드 수(Top-N)": opts.get("top_n") or "제한 없음",
            "커뮤니티 탐지": _COMMUNITY_LABELS.get(
                opts.get("community"), opts.get("community")
            ),
            "레이아웃": _LAYOUT_LABELS.get(opts.get("layout"), opts.get("layout")),
            "백본 추출(disparity filter)": (
                f"사용 (alpha={opts.get('backbone_alpha')})"
                if opts.get("backbone")
                else "미사용"
            ),
            "계산한 중심성": ", ".join(opts.get("centralities") or []) or "없음",
            "ego 네트워크 수": opts.get("ego_top"),
        },
    }
    with open(
        os.path.join(out_dir, "analysis_options.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ────────────────────── 기간 병렬 워커 ──────────────────────
def _run_one_period(args):
    # 워커 내부에서는 BLAS 스레드 제한 (period 병렬과 중복 방지)
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["OPENBLAS_NUM_THREADS"] = "2"
    period_tag, texts, option = args
    vocab, words = _build_vocab(
        texts, option["scope"], option["window"], option["min_freq"], option["top_n"]
    )
    if len(vocab) < 2:
        return period_tag, None
    cooc, freq, n_units = build_cooccurrence(
        texts, vocab, option["scope"], option["window"], n_workers=1
    )
    edges = build_edges(
        cooc, freq, n_units, option["measure"], option["min_edge_weight"]
    )
    res = analyze_graph(words, freq, edges, option, pid=None, tag=period_tag + " ")
    return period_tag, res


def _export_period_comparison(period_summ, out_dir):
    df = pd.DataFrame(period_summ).sort_values("period")
    df.to_csv(
        os.path.join(out_dir, "period_comparison.csv"),
        index=False,
        encoding="utf-8-sig",
    )

    # 주요 지표 추이 그래프
    metrics = [
        m
        for m in [
            "nodes",
            "edges",
            "density",
            "avg_degree",
            "avg_clustering",
            "modularity",
        ]
        if m in df.columns
    ]
    if not metrics:
        return
    n = len(metrics)
    fig, axes = plt.subplots((n + 1) // 2, 2, figsize=(14, 3 * ((n + 1) // 2)))
    axes = np.array(axes).ravel()
    for ax, m in zip(axes, metrics):
        ax.plot(df["period"], df[m], marker="o", color="#1428A0")
        ax.set_title(m)
        ax.tick_params(axis="x", rotation=45)
        ax.grid(alpha=0.3)
    for ax in axes[len(metrics) :]:
        ax.axis("off")
    fig.suptitle("Period Comparison", fontsize=16)
    fig.tight_layout()
    fig.savefig(
        os.path.join(out_dir, "period_comparison.png"), dpi=130, bbox_inches="tight"
    )
    plt.close(fig)


# ────────────────────── 엔트리포인트 ──────────────────────
def _push_to_network_viewer(
    zip_path: str, uid: str, project_name: str, pid: str
) -> str | None:
    """분석 결과 zip을 온라인 뷰어(manager/network)의 사용자 프로젝트로 곧바로 밀어 넣는다.
    실패해도 분석 자체를 실패시키지 않는다 — zip 다운로드는 항상 그대로 내려간다."""
    internal_key = os.getenv("INTERNAL_API_KEY", "")
    try:
        with open(zip_path, "rb") as f:
            resp = requests.post(
                f"{NETWORK_VIEWER_URL}/api/internal/projects/ingest",
                headers={"X-Internal-Key": internal_key},
                data={"uid": uid, "name": project_name or "네트워크 분석"},
                files={"file": (os.path.basename(zip_path), f, "application/zip")},
                timeout=60,
            )
        if resp.status_code == 200:
            project_id = resp.json().get("project_id")
            send_message(
                pid,
                f"온라인 뷰어에 프로젝트로 저장했습니다: {NETWORK_VIEWER_URL}/viewer/{project_id}",
            )
            return project_id
        send_message(
            pid,
            "온라인 뷰어 자동 업로드에 실패했습니다. (결과 zip은 정상적으로 받으실 수 있습니다)",
        )
    except Exception:
        send_message(
            pid,
            "온라인 뷰어 서버에 연결할 수 없습니다. (결과 zip은 정상적으로 받으실 수 있습니다)",
        )
    return None


def run_network_analysis(
    pid: str,
    data: pd.DataFrame,
    option: dict,
    uid: str | None = None,
    project_name: str | None = None,
):
    def _cleanup(folder, zippath):
        shutil.rmtree(folder, ignore_errors=True)
        try:
            os.remove(zippath)
        except OSError:
            pass

    try:
        base_temp = os.path.join(os.path.dirname(__file__), "..", "temp")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = os.path.join(base_temp, f"network_{pid}_{ts}")
        os.makedirs(out_dir, exist_ok=True)

        text_col = option["text_col"]
        if text_col not in data.columns:
            return JSONResponse(
                status_code=400,
                content={"error": "열 없음", "message": f"{text_col} 열이 없습니다."},
            )

        period = option.get("period", "total")

        # 기간별로 쪼개서 병렬
        if period != "total":
            date_col = next((c for c in data.columns if "Date" in c), None)
            if date_col is None:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Date 열 없음",
                        "message": "기간 분석엔 Date 열 필요",
                    },
                )
            data[date_col] = pd.to_datetime(data[date_col], errors="coerce")
            data = data.dropna(subset=[date_col])
            data["_pk"] = _period_key(data[date_col], period)
            groups = [
                (str(k), sub[text_col].tolist()) for k, sub in data.groupby("_pk")
            ]
            send_message(pid, f"기간 {len(groups)}개 병렬 분석 시작...")
            n_workers = min(len(groups), os.cpu_count() or 4)
            args = [(f"_{k}", txts, option) for k, txts in groups]

            period_summ = []
            with ProcessPoolExecutor(max_workers=n_workers) as ex:
                for period_tag, res in ex.map(_run_one_period, args):
                    if res is not None:
                        export_files(res, option, out_dir, tag=period_tag)
                        row = {"period": period_tag.lstrip("_")}
                        row.update(res.get("global_metrics", {}))
                        row["modularity"] = res.get("modularity")
                        period_summ.append(row)
                    send_message(pid, f"{period_tag} 완료")

            # ── 기간 비교표 + 추이 그래프 ──
            if period_summ:
                _export_period_comparison(period_summ, out_dir)
        else:
            texts = data[text_col].tolist()
            send_message(pid, "단어 사전 구축 중...")
            vocab, words = _build_vocab(
                texts,
                option["scope"],
                option["window"],
                option["min_freq"],
                option["top_n"],
            )
            if len(vocab) < 2:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "단어 부족",
                        "message": "조건을 만족하는 단어가 부족합니다.",
                    },
                )
            send_message(pid, f"공출현 행렬 계산 중... (단어 {len(vocab)}개)")
            cooc, freq, n_units = build_cooccurrence(
                texts,
                vocab,
                option["scope"],
                option["window"],
                n_workers=min(4, os.cpu_count() or 4),
            )
            edges = build_edges(
                cooc, freq, n_units, option["measure"], option["min_edge_weight"]
            )
            send_message(pid, f"그래프 분석 중... (연결 {len(edges)}개)")
            res = analyze_graph(words, freq, edges, option, pid=pid)
            if res is None:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "네트워크 없음",
                        "message": "임계값을 만족하는 연결이 없습니다.",
                    },
                )
            export_files(res, option, out_dir)

        _write_viewer_readme(out_dir)
        _write_analysis_options(out_dir, option, project_name)

        send_message(
            pid,
            f"완료! 인터랙티브 뷰어: {NETWORK_VIEWER_URL} 에 결과 zip을 업로드하세요.",
        )
        send_message(pid, "결과 압축 중...")
        zip_path = out_dir + ".zip"
        shutil.make_archive(out_dir, "zip", out_dir)

        response_headers = {}
        if uid:
            project_id = _push_to_network_viewer(zip_path, uid, project_name, pid)
            if project_id:
                response_headers["X-Network-Project-Id"] = project_id

        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=os.path.basename(zip_path),
            background=BackgroundTask(_cleanup, out_dir, zip_path),
            headers=response_headers,
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "네트워크 분석 오류",
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
        )
