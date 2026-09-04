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

    for m in groups:
        node_ids = m["child_uuids"]
        group_id = m["group_id"]
        plugin = get_method(m.get("method"))

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
                    m, pairs, cr_threshold=cr_threshold
                ).consistency
                per_respondent_cr[rid][group_id] = (
                    c.metrics.get("cr", c.metrics.get("cri")) if c else None
                )

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
