"""분석 결과 조립 — 지역/전역 가중치, 개인별 CR, 그룹 합의도, 극단값.

DB에서 이미 가져온 데이터(hierarchy nodes, survey groups, 응답자별 최종 답)를
받아서 계산만 한다. 오프라인+온라인 응답을 한 분석에 합치는 것(PLAN.md 1절)은
호출부(result_routes)가 여러 collection의 응답을 하나의 respondent_id -> answers
딕셔너리로 미리 합쳐서 넘겨주기만 하면 여기는 그 출처를 몰라도 된다.
"""

from __future__ import annotations

from app.services.ahp_calc import global_weights
from app.services.aggregate import kendalls_w, find_outliers
from app.services.methods import get_method


def build_results(
    hierarchy_nodes: list[dict],
    groups: list[dict],
    submissions_by_respondent: dict[str, dict],
    settings: dict,
) -> dict:
    node_parent = {n["uuid"]: n["parent_id"] for n in hierarchy_nodes}
    node_name = {n["uuid"]: n["name"] for n in hierarchy_nodes}
    matrix_of_parent = {m["parent_uuid"]: m["group_id"] for m in groups}
    cr_threshold = settings.get("cr_threshold", 0.1)

    per_respondent_cr: dict[str, dict] = {rid: {} for rid in submissions_by_respondent}
    local_weights_by_matrix: dict[str, dict] = {}
    consensus_by_matrix: dict[str, dict] = {}
    outliers_by_matrix: dict[str, list] = {}
    bwm_by_group: dict[str, dict] = {}
    group_cr_by_matrix: dict[str, dict] = {}

    for m in groups:
        node_ids = m["child_uuids"]
        group_id = m["group_id"]
        plugin = get_method(m.get("method"))
        is_bwm = m.get("kind") == "bwm"

        respondent_pairs = []
        respondent_ids_with_data = []
        for rid, answers in submissions_by_respondent.items():
            pairs = answers.get(group_id, {})
            if len(node_ids) >= 2 and not pairs:
                continue
            respondent_pairs.append(pairs)
            respondent_ids_with_data.append(rid)

            if len(node_ids) >= 3:
                c = plugin.derive_local(
                    m, pairs, cr_threshold=cr_threshold, settings=settings
                ).consistency
                per_respondent_cr[rid][group_id] = c.value if c else None
                if is_bwm and c:
                    bg = bwm_by_group.setdefault(
                        group_id,
                        {
                            "bw_distribution": {"best": {}, "worst": {}},
                            "per_respondent": {},
                        },
                    )
                    bg["per_respondent"][rid] = {
                        "cri": c.metrics.get("cri"),
                        "cri_threshold": c.threshold,
                        "or": c.metrics.get("or"),
                    }
            if is_bwm:
                bg = bwm_by_group.setdefault(
                    group_id,
                    {
                        "bw_distribution": {"best": {}, "worst": {}},
                        "per_respondent": {},
                    },
                )
                for role in ("best", "worst"):
                    v = pairs.get(role)
                    if v:
                        d = bg["bw_distribution"][role]
                        d[v] = d.get(v, 0) + 1

        if not respondent_pairs:
            local_weights_by_matrix[group_id] = {nid: 0.0 for nid in node_ids}
            continue

        if len(node_ids) == 1:
            local_weights_by_matrix[group_id] = {node_ids[0]: 1.0}
            continue

        # 이 매트릭스에 응답은 있지만 전원이 불완전한 쌍만 갖고 있으면 플러그인의
        # aggregate_group이 complete=False + 0 가중치를 돌려준다. 위 "응답 없음"
        # 분기와 동일하게 취급해 이 매트릭스만 넘어간다(이전엔 예외가 /results
        # 전체를 500으로 죽였다).
        agg_lr = plugin.aggregate_group(m, respondent_pairs, settings)
        local_weights_by_matrix[group_id] = agg_lr.weights
        if not agg_lr.complete:
            continue

        # 그룹 집계 일관성 — AIJ 는 합성 행렬 CR, AIP 는 개인 CR 평균(개인별 표
        # 앞에서 "가중합의 합계 CR"로 보여줄 값). 방법이 metrics 로 이미 계산한다.
        if len(node_ids) >= 3 and agg_lr.consistency and agg_lr.consistency.metrics:
            gm = agg_lr.consistency.metrics
            if gm.get("avg_cr") is not None:
                group_cr_by_matrix[group_id] = {
                    "value": gm["avg_cr"],
                    "metric": "cr",
                    "threshold": cr_threshold,
                }
            elif gm.get("avg_cri") is not None:
                group_cr_by_matrix[group_id] = {
                    "value": gm["avg_cri"],
                    "metric": "cri",
                    "threshold": None,
                }

        # 쌍별 합의도(극단값) — 응답자가 3명 이상 있어야 의미가 있다.
        # 쌍대비교 전용 진단(값이 로그 스케일 비율이라는 전제). 비-pairwise kind는 건너뛴다.
        if m.get("kind", "pairwise") == "pairwise" and len(respondent_pairs) >= 3:
            outliers = []
            all_pair_ids = set()
            for p in respondent_pairs:
                all_pair_ids.update(p.keys())
            for pid in all_pair_ids:
                values = {i: p[pid] for i, p in enumerate(respondent_pairs) if pid in p}
                if len(values) < 3:
                    continue
                out_idx = find_outliers(values)
                if out_idx:
                    outliers.append(
                        {
                            "pair_id": pid,
                            "outlier_respondents": [
                                respondent_ids_with_data[i] for i in out_idx
                            ],
                        }
                    )
            outliers_by_matrix[group_id] = outliers

        # 순위 기반 합의도(Kendall's W) — 응답자별 지역 순위를 비교
        if len(node_ids) >= 2 and len(respondent_pairs) >= 2:
            rankings = []
            for pairs in respondent_pairs:
                lr = plugin.derive_local(m, pairs)
                if lr.complete:
                    rankings.append(lr.ranking)
            if len(rankings) >= 2:
                consensus_by_matrix[group_id] = {"kendalls_w": kendalls_w(rankings)}

    global_w = global_weights(node_parent, local_weights_by_matrix, matrix_of_parent)
    alternative_scores = synthesize_alternatives(
        groups, local_weights_by_matrix, global_w
    )
    alt_breakdown = alternative_breakdown(
        groups, local_weights_by_matrix, global_w, node_name
    )

    per_respondent_result = {
        rid: _one_respondent_result(
            node_parent, matrix_of_parent, groups, answers, cr_threshold, settings
        )
        for rid, answers in submissions_by_respondent.items()
    }

    return {
        "node_names": node_name,
        "local_weights": local_weights_by_matrix,
        "global_weights": global_w,
        "per_respondent_cr": per_respondent_cr,
        "consensus": consensus_by_matrix,
        "outliers": outliers_by_matrix,
        "respondent_count": len(submissions_by_respondent),
        "cr_threshold": settings.get("cr_threshold", 0.1),
        "alternative_scores": alternative_scores,
        "group_kinds": {m["group_id"]: m.get("kind", "pairwise") for m in groups},
        "bwm": bwm_by_group,
        "group_cr": group_cr_by_matrix,
        "per_respondent": per_respondent_result,
        "alternative_breakdown": alt_breakdown,
    }


def synthesize_alternatives(
    groups: list[dict],
    local_weights_by_matrix: dict[str, dict],
    global_weights_: dict[str, float],
) -> dict[str, float]:
    """전통적 distributive AHP 합성 — 각 리프 기준의 전역 가중치 × 그 기준
    아래 대안 로컬 가중치를 모든 리프에 대해 더한다. 대안 계층을 안 쓰면
    (is_alternative 매트릭스가 없으면) 빈 dict를 돌려준다."""
    scores: dict[str, float] = {}
    for m in groups:
        if not m.get("is_alternative"):
            continue
        leaf_global = global_weights_.get(m["parent_uuid"], 0.0)
        alt_local = local_weights_by_matrix.get(m["group_id"], {})
        for aid, w in alt_local.items():
            scores[aid] = scores.get(aid, 0.0) + leaf_global * w

    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}
    return scores


def alternative_breakdown(
    groups: list[dict],
    local_weights_by_matrix: dict[str, dict],
    global_weights_: dict[str, float],
    node_name: dict[str, str],
) -> dict[str, dict]:
    """대안별 합성 과정 — 리프 기준마다 (리프 전역가중치 × 대안 국소가중치 =
    기여)를 남긴다. `synthesize_alternatives` 가 버리는 중간 계산(4.2)."""
    by_alt: dict[str, dict] = {}
    for m in groups:
        if not m.get("is_alternative"):
            continue
        leaf_uuid = m["parent_uuid"]
        leaf_g = global_weights_.get(leaf_uuid, 0.0)
        alt_local = local_weights_by_matrix.get(m["group_id"], {})
        for aid, w in alt_local.items():
            entry = by_alt.setdefault(aid, {"rows": [], "raw_total": 0.0})
            contribution = leaf_g * w
            entry["rows"].append(
                {
                    "leaf_uuid": leaf_uuid,
                    "leaf_name": node_name.get(leaf_uuid, leaf_uuid),
                    "leaf_global_w": leaf_g,
                    "alt_local_w": w,
                    "contribution": contribution,
                }
            )
            entry["raw_total"] += contribution
    grand = sum(e["raw_total"] for e in by_alt.values())
    for aid, e in by_alt.items():
        e["rows"].sort(key=lambda r: -r["contribution"])
        e["score"] = (e["raw_total"] / grand) if grand > 0 else 0.0
    return by_alt


def _one_respondent_result(
    node_parent: dict,
    matrix_of_parent: dict,
    groups: list[dict],
    answers: dict,
    cr_threshold: float,
    settings: dict | None = None,
) -> dict:
    """한 응답자의 답만으로 전역 가중치·대안 점수·그룹별 CR을 낸다.
    개인 종료 화면(3.1)과 결과 화면 개인별 카드(4.1)가 공유한다."""
    local: dict[str, dict] = {}
    cr_by_group: dict[str, float] = {}
    for m in groups:
        gid = m["group_id"]
        node_ids = m["child_uuids"]
        if len(node_ids) == 1:
            local[gid] = {node_ids[0]: 1.0}
            continue
        lr = get_method(m.get("method")).derive_local(
            m, answers.get(gid, {}), cr_threshold=cr_threshold, settings=settings
        )
        if lr.complete:
            local[gid] = lr.weights
            if lr.consistency and lr.consistency.value is not None:
                cr_by_group[gid] = lr.consistency.value
        else:
            local[gid] = {nid: 0.0 for nid in node_ids}
    gw = global_weights(node_parent, local, matrix_of_parent)
    return {
        "global": gw,
        "local_by_group": local,
        "alt_scores": synthesize_alternatives(groups, local, gw),
        "cr_by_group": cr_by_group,
    }
