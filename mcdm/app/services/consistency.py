"""비일관성 진단 — CR 값만 보여주는 건 현장에서 아무 도움이 안 된다(PLAN.md 8절).
어느 판단이 문제인지 지목하고 권장값을 제시해야 실제로 조정할 수 있다.
"""

from __future__ import annotations

import math

import numpy as np

from app.services.ahp_calc import build_matrix, eigen_weights, pair_id

# Saaty 눈금 값(왼쪽 9배 … 동일 … 오른쪽 9배). 응답 화면·CSV가 받는 것과 동일.
_SAATY_VALUES = [1 / k for k in range(9, 1, -1)] + [1.0] + list(range(2, 10))


def nearest_saaty_label(value: float) -> str:
    """임의의 실수(예: 일관성 행렬이 함의하는 w_i/w_j)를 응답 가능한 Saaty 눈금 중
    로그거리 최근접 값으로 스냅해 사람이 읽는 형태("3", "1/3")로 돌려준다 —
    소수 추천값은 진행자·참여자 모두 이해하기 어렵다는 요청사항."""
    if value <= 0:
        return "1"
    best = min(_SAATY_VALUES, key=lambda s: abs(math.log(s) - math.log(value)))
    if best >= 1:
        return str(int(round(best)))
    return f"1/{int(round(1 / best))}"


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
            "given_label": nearest_saaty_label(self.given_value),
            "suggested_value": round(self.suggested_value, 3),
            "suggested_label": nearest_saaty_label(self.suggested_value),
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
