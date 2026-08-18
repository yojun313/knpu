"""분석 결과 조립 — 지역/전역 가중치, 개인별 CR, 그룹 합의도, 극단값.

DB에서 이미 가져온 데이터(hierarchy nodes, survey matrices, 응답자별 최종 답)를
받아서 계산만 한다. 오프라인+온라인 응답을 한 분석에 합치는 것(PLAN.md 1절)은
호출부(result_routes)가 여러 collection의 응답을 하나의 respondent_id -> answers
딕셔너리로 미리 합쳐서 넘겨주기만 하면 여기는 그 출처를 몰라도 된다.
"""

from __future__ import annotations

from app.services.ahp_calc import derive_weights, global_weights, IncompleteMatrixError
from app.services.aggregate import (
    aggregate_aij,
    aggregate_aip,
    kendalls_w,
    find_outliers,
)


def build_results(
    hierarchy_nodes: list[dict],
    matrices: list[dict],
    submissions_by_respondent: dict[str, dict],
    settings: dict,
) -> dict:
    node_parent = {n["uuid"]: n["parent_id"] for n in hierarchy_nodes}
    node_name = {n["uuid"]: n["name"] for n in hierarchy_nodes}
    matrix_of_parent = {m["parent_uuid"]: m["matrix_id"] for m in matrices}
    aggregation = settings.get("aggregation", "AIP")

    per_respondent_cr: dict[str, dict] = {rid: {} for rid in submissions_by_respondent}
    local_weights_by_matrix: dict[str, dict] = {}
    consensus_by_matrix: dict[str, dict] = {}
    outliers_by_matrix: dict[str, list] = {}

    for m in matrices:
        node_ids = m["child_uuids"]
        matrix_id = m["matrix_id"]

        respondent_pairs = []
        respondent_ids_with_data = []
        for rid, answers in submissions_by_respondent.items():
            pairs = answers.get(matrix_id, {})
            if len(node_ids) >= 2 and not pairs:
                continue
            respondent_pairs.append(pairs)
            respondent_ids_with_data.append(rid)

            if len(node_ids) >= 3:
                try:
                    r = derive_weights(node_ids, pairs)
                    per_respondent_cr[rid][matrix_id] = r.cr
                except IncompleteMatrixError:
                    per_respondent_cr[rid][matrix_id] = None

        if not respondent_pairs:
            local_weights_by_matrix[matrix_id] = {nid: 0.0 for nid in node_ids}
            continue

        if len(node_ids) == 1:
            local_weights_by_matrix[matrix_id] = {node_ids[0]: 1.0}
            continue

        if aggregation == "AIJ":
            result, merged_pairs = aggregate_aij(node_ids, respondent_pairs)
            group_w = result.weights
        else:
            group_w, per_resp_results, skipped = aggregate_aip(
                node_ids, respondent_pairs
            )
        local_weights_by_matrix[matrix_id] = group_w

        # 쌍별 합의도(극단값) — 응답자가 3명 이상 있어야 의미가 있다
        if len(respondent_pairs) >= 3:
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
            outliers_by_matrix[matrix_id] = outliers

        # 순위 기반 합의도(Kendall's W) — 응답자별 지역 가중치 순위를 비교
        if len(node_ids) >= 2 and len(respondent_pairs) >= 2:
            rankings = []
            for pairs in respondent_pairs:
                try:
                    r = derive_weights(node_ids, pairs)
                    ranking = sorted(node_ids, key=lambda nid: -r.weights[nid])
                    rankings.append(ranking)
                except IncompleteMatrixError:
                    continue
            if len(rankings) >= 2:
                consensus_by_matrix[matrix_id] = {"kendalls_w": kendalls_w(rankings)}

    global_w = global_weights(node_parent, local_weights_by_matrix, matrix_of_parent)

    return {
        "node_names": node_name,
        "local_weights": local_weights_by_matrix,
        "global_weights": global_w,
        "per_respondent_cr": per_respondent_cr,
        "consensus": consensus_by_matrix,
        "outliers": outliers_by_matrix,
        "respondent_count": len(submissions_by_respondent),
        "cr_threshold": settings.get("cr_threshold", 0.1),
    }
