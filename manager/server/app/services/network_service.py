# app/services/network_service.py
import os

os.environ.setdefault("OMP_NUM_THREADS", "0")  # period 병렬 시 워커 내부에서 재설정
import re
import json
import shutil
import traceback
from datetime import datetime
from itertools import combinations
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, vstack
import igraph as ig

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from app.libs.progress import send_message
from scipy.spatial import ConvexHull  # 파일 상단 import에 추가
from adjustText import adjust_text  # 라벨 겹침 방지 (pip install adjustText)

# 한글 폰트 (GPU 서버 환경에 맞게 경로/이름만 맞춰줘)
try:
    plt.rcParams["font.family"] = "NanumGothic"
except Exception:
    pass
plt.rcParams["axes.unicode_minus"] = False


# 템플릿 파일 경로 (이 파이썬 파일과 같은 폴더에 network_template.html 이 있다고 가정)
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "network_template.html")


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
        norm = (cvals - cvals.min()) / (cvals.ptp() or 1)
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


def export_files(res, option, out_dir, tag=""):
    os.makedirs(out_dir, exist_ok=True)
    g, cent, community = res["graph"], res["cent"], res["community"]

    # nodes.csv
    node_rows = {"word": g.vs["name"], "frequency": g.vs["freq"]}
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

    # graphml (Gephi/NetMiner import용)
    g.write_graphml(os.path.join(out_dir, f"network{tag}.graphml"))

    # 시각화
    draw_network(
        res, option, os.path.join(out_dir, f"network{tag}.png"), title=tag or "Network"
    )

    # 인터랙티브 html (vis-network, CDN)
    _export_interactive_html(res, os.path.join(out_dir, f"network{tag}.html"))

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


def _export_interactive_html(res, out_path, max_edges=1500):
    g = res["graph"]
    coords = res["coords"]
    cent, community = res["cent"], res["community"]

    all_edges = list(g.es)
    if len(all_edges) > max_edges:
        all_edges = sorted(all_edges, key=lambda e: e["weight"], reverse=True)[
            :max_edges
        ]
    used = set()
    for e in all_edges:
        used.add(e.source)
        used.add(e.target)

    # 좌표 정규화 (화면 스케일)
    xs = coords[:, 0]
    ys = coords[:, 1]
    xr = (xs.max() - xs.min()) or 1
    yr = (ys.max() - ys.min()) or 1

    palette = [
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

    nodes = []
    for i, v in enumerate(g.vs):
        if i not in used:
            continue
        grp = int(community[i]) if community is not None else 0
        info = {}
        for k, arr in cent.items():
            try:
                val = arr[i]
                info[k] = round(float(val), 4) if val is not None else None
            except Exception:
                pass
        nodes.append(
            {
                "id": i,
                "label": v["name"],
                "value": int(v["freq"]),
                "group": grp,
                "color": palette[grp % len(palette)],
                "x": float((xs[i] - xs.min()) / xr * 2400 - 1200),
                "y": float((ys[i] - ys.min()) / yr * 1600 - 800),
                "info": info,
            }
        )
    edges = [
        {"from": e.source, "to": e.target, "value": float(e["weight"])}
        for e in all_edges
    ]

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)
    max_w = max((e["value"] for e in edges), default=1)
    truncated = len(g.es) > max_edges
    n_comm = (max(community) + 1) if community is not None else 1

    warn = (
        f"⚠ 전체 엣지 {len(g.es):,}개 중 상위 {max_edges:,}개 표시"
        if truncated
        else f"엣지 {len(g.es):,}개 · 노드 {len(nodes):,}개"
    )

    # 외부 HTML 템플릿 로드
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    html = (
        html.replace("__WARN__", warn)
        .replace("__MAXW__", str(max_w))
        .replace("__STEP__", str(max(max_w / 100, 0.01)))
        .replace("__NC__", str(n_comm))
        .replace("__NODES__", nodes_json)
        .replace("__EDGES__", edges_json)
        .replace("__PALETTE__", json.dumps(palette))
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


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
def run_network_analysis(pid: str, data: pd.DataFrame, option: dict):
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

        send_message(pid, "결과 압축 중...")
        zip_path = out_dir + ".zip"
        shutil.make_archive(out_dir, "zip", out_dir)
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename=os.path.basename(zip_path),
            background=BackgroundTask(_cleanup, out_dir, zip_path),
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
