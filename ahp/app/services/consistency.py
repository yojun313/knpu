"""비일관성 진단 — CR 값만 보여주는 건 현장에서 아무 도움이 안 된다(PLAN.md 8절).
어느 판단이 문제인지 지목하고 권장값을 제시해야 실제로 조정할 수 있다.
"""

from __future__ import annotations

import math

import numpy as np

from app.services.ahp_calc import build_matrix, eigen_weights, pair_id


class WorstPair:
    __slots__ = (
        "uuid_a",
        "uuid_b",
        "pair_id",
        "given_value",
        "suggested_value",
        "deviation",
    )

    def __init__(self, uuid_a, uuid_b, given_value, suggested_value, deviation):
        self.uuid_a = uuid_a
        self.uuid_b = uuid_b
        self.pair_id = pair_id(uuid_a, uuid_b)
        self.given_value = given_value
        self.suggested_value = suggested_value
        self.deviation = deviation

    def to_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "uuid_a": self.uuid_a,
            "uuid_b": self.uuid_b,
            "given_value": round(self.given_value, 3),
            "suggested_value": round(self.suggested_value, 3),
            "deviation": round(self.deviation, 3),
        }


def worst_offending_pairs(
    node_ids: list[str], pairs: dict[str, float], top_k: int = 3
) -> list[WorstPair]:
    """일관성 행렬(w_i/w_j)과 실제 응답의 편차가 가장 큰 쌍을 지목한다.

    편차는 log(a_ij) - log(w_i/w_j)의 절댓값으로 잰다. AHP 값은 배수 관계라
    3배 vs 9배의 차이와 1/3배 vs 1/9배의 차이가 로그 스케일에서 같은 크기로
    잡혀야 공정하게 비교된다. suggested_value는 도출된 가중치가 내부적으로
    "완전히 일관됐다면 이랬을 것"이라 계산하는 w_i/w_j 값이다 — 정답이 아니라
    참고용 재고 지점이다.
    """
    n = len(node_ids)
    if n < 3:
        return []  # 3개 미만이면 비일관성 자체가 존재할 수 없다

    matrix = build_matrix(node_ids, pairs)
    weights, _lambda_max = eigen_weights(matrix)

    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            given = matrix[i, j]
            implied = weights[i] / weights[j] if weights[j] > 0 else float("inf")
            deviation = abs(math.log(given) - math.log(implied))
            candidates.append(
                WorstPair(
                    node_ids[i], node_ids[j], float(given), float(implied), deviation
                )
            )

    candidates.sort(key=lambda c: c.deviation, reverse=True)
    return candidates[:top_k]
