import numpy as np


def _percentiles(values, ps=(50, 75, 90, 95)):
    if not values:
        return {f"p{p}": 0 for p in ps}
    arr = np.array(values, dtype=float)
    return {f"p{p}": round(float(np.percentile(arr, p)), 4) for p in ps}


def compute_summary(graph: dict) -> dict:
    nodes = graph["nodes"]
    edges = graph["edges"]
    n = len(nodes)
    e = len(edges)

    deg = {nd["id"]: 0 for nd in nodes}
    for ed in edges:
        deg[ed["source"]] = deg.get(ed["source"], 0) + 1
        deg[ed["target"]] = deg.get(ed["target"], 0) + 1
    isolated = sum(1 for v in deg.values() if v == 0)

    weights = [ed["weight"] for ed in edges]
    freqs = [nd["freq"] for nd in nodes]

    groups = {}
    for nd in nodes:
        groups.setdefault(nd["group"], 0)
        groups[nd["group"]] += 1
    communities = [
        {"id": g, "count": c} for g, c in sorted(groups.items(), key=lambda x: x[0])
    ]

    density = (2 * e) / (n * (n - 1)) if n > 1 else 0.0
    avg_degree = (2 * e) / n if n > 0 else 0.0

    return {
        "nodes": n,
        "edges": e,
        "density": round(density, 6),
        "avg_degree": round(avg_degree, 4),
        "isolated_nodes": isolated,
        "communities": communities,
        "has_community": graph.get("has_community", False),
        "metric_keys": graph.get("metric_keys", []),
        "max_freq": max(freqs) if freqs else 0,
        "weight_range": {
            "min": min(weights) if weights else 0,
            "max": max(weights) if weights else 0,
        },
        "weight_percentiles": _percentiles(weights),
        "freq_percentiles": _percentiles(freqs),
    }


def compute_community_keywords(graph: dict, top_k: int = 6) -> list:
    if not graph.get("has_community"):
        return []

    node_by_id = {nd["id"]: nd for nd in graph["nodes"]}
    internal_degree = {nd["id"]: 0 for nd in graph["nodes"]}
    for ed in graph["edges"]:
        s, t = ed["source"], ed["target"]
        ns, nt = node_by_id.get(s), node_by_id.get(t)
        if ns is None or nt is None:
            continue
        if ns["group"] == nt["group"]:
            internal_degree[s] += 1
            internal_degree[t] += 1

    by_group = {}
    for nd in graph["nodes"]:
        by_group.setdefault(nd["group"], []).append(nd)

    result = []
    for g, members in sorted(by_group.items(), key=lambda x: x[0]):
        top_freq = sorted(members, key=lambda x: -x["freq"])[:top_k]
        top_deg = sorted(members, key=lambda x: -internal_degree.get(x["id"], 0))[
            :top_k
        ]
        result.append(
            {
                "group": g,
                "size": len(members),
                "top_freq": [
                    {"id": m["id"], "label": m["label"], "freq": m["freq"]}
                    for m in top_freq
                ],
                "top_internal_degree": [
                    {
                        "id": m["id"],
                        "label": m["label"],
                        "internal_degree": internal_degree.get(m["id"], 0),
                    }
                    for m in top_deg
                ],
            }
        )
    return result
