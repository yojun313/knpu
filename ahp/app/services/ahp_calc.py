"""AHP 핵심 계산 — 순수 함수, DB·웹소켓 의존 없음 (단위 테스트 대상).

쌍대비교 응답은 DB에 pair_id = "<uuid_min>:<uuid_max>"(uuid 문자열의 사전식 정렬) 형태로
저장되고, 값은 "사전순으로 더 작은 uuid가 더 큰 uuid보다 얼마나 중요한가"를 뜻한다.
이렇게 저장 순서를 표시 순서와 분리해 두면, 화면에 보여주는 노드 순서가 바뀌어도
저장된 응답은 그대로 재사용할 수 있다(PLAN.md 4.4의 "이름/순서 변경은 응답을 안 건드린다"
원칙을 계산 계층에서 실제로 지탱하는 부분).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# Saaty 무작위 지수(Random Index). n=1,2는 정의상 완전 일관(행렬 크기가 너무 작아
# 비일관성이 존재할 수 없음)이라 CR을 정의하지 않는다 — 0으로 나누기 방지가 아니라
# 개념적으로 "물어볼 필요가 없는" 경우다.
RI_TABLE = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.48,
    13: 1.56,
    14: 1.57,
    15: 1.59,
}


def pair_id(uuid_a: str, uuid_b: str) -> str:
    lo, hi = sorted([uuid_a, uuid_b])
    return f"{lo}:{hi}"


def to_stored_pair(
    uuid_a: str, uuid_b: str, value_a_over_b: float
) -> tuple[str, float]:
    """ "uuid_a가 uuid_b보다 value_a_over_b배 중요하다"는 UI/CSV 표현을 저장 규약
    (pair_id는 사전순, 값은 "사전순 작은 쪽 / 사전순 큰 쪽")으로 변환한다.
    단일 셀 저장(entry_routes)과 CSV 가져오기가 이 변환을 각자 구현하면 둘이
    어긋날 수 있어 여기 한 곳에만 둔다."""
    pid = pair_id(uuid_a, uuid_b)
    lo, _hi = sorted([uuid_a, uuid_b])
    stored = value_a_over_b if uuid_a == lo else (1.0 / value_a_over_b)
    return pid, stored


class IncompleteMatrixError(Exception):
    """일부 쌍이 비어 있어 완전한 행렬을 만들 수 없을 때."""

    def __init__(self, missing_pairs: list[str]):
        self.missing_pairs = missing_pairs
        super().__init__(f"{len(missing_pairs)}개 쌍이 비어 있습니다")


def build_matrix(node_ids: list[str], pairs: dict[str, float]) -> np.ndarray:
    """표시 순서(node_ids) 기준의 n×n 역수 행렬을 만든다.

    pairs의 키는 pair_id()로 정규화된 사전순 조합이어야 한다. 값은 "사전순으로
    더 작은 쪽이 더 큰 쪽보다 얼마나 중요한가"이므로, node_ids 상의 실제 표시
    순서와 사전순이 다르면 여기서 역수를 취해 방향을 맞춘다.
    """
    n = len(node_ids)
    m = np.ones((n, n))
    missing = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = node_ids[i], node_ids[j]
            pid = pair_id(a, b)
            if pid not in pairs:
                missing.append(pid)
                continue
            v = float(pairs[pid])
            lo, _hi = sorted([a, b])
            # 저장값은 항상 "사전순 작은 쪽 / 사전순 큰 쪽"의 중요도.
            # 표시 순서(i가 사전순으로 큰 쪽일 수도 있음)에 맞춰 방향을 정한다.
            if a == lo:
                m[i, j] = v
                m[j, i] = 1.0 / v
            else:
                m[i, j] = 1.0 / v
                m[j, i] = v
    if missing:
        raise IncompleteMatrixError(missing)
    return m


@dataclass
class WeightResult:
    weights: dict[str, float]  # node_id -> 정규화된 지역 가중치(고유벡터법)
    weights_geomean: dict[str, float]  # 참고값(행 기하평균법)
    lambda_max: float | None
    ci: float | None
    cr: float | None  # n<=2면 None (정의되지 않음)
    n: int


def eigen_weights(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    """주 고유벡터(가중치)와 최대 고유값 λmax를 구한다."""
    eigvals, eigvecs = np.linalg.eig(matrix)
    idx = int(np.argmax(eigvals.real))
    lambda_max = float(eigvals[idx].real)
    vec = np.abs(eigvecs[:, idx].real)  # 페론-프로베니우스: 부호는 임의이므로 절댓값
    vec = vec / vec.sum()
    return vec, lambda_max


def geomean_weights(matrix: np.ndarray) -> np.ndarray:
    """행 기하평균법 — 각 행의 기하평균을 정규화."""
    row_gm = np.exp(np.log(matrix).mean(axis=1))
    return row_gm / row_gm.sum()


def derive_weights(node_ids: list[str], pairs: dict[str, float]) -> WeightResult:
    n = len(node_ids)
    if n == 1:
        return WeightResult(
            weights={node_ids[0]: 1.0},
            weights_geomean={node_ids[0]: 1.0},
            lambda_max=None,
            ci=None,
            cr=None,
            n=1,
        )

    matrix = build_matrix(node_ids, pairs)
    eig_vec, lambda_max = eigen_weights(matrix)
    gm_vec = geomean_weights(matrix)

    if n <= 2:
        ci = None
        cr = None
    else:
        ci = (lambda_max - n) / (n - 1)
        ri = RI_TABLE.get(n)
        cr = (ci / ri) if ri else None

    return WeightResult(
        weights=dict(zip(node_ids, eig_vec.tolist())),
        weights_geomean=dict(zip(node_ids, gm_vec.tolist())),
        lambda_max=lambda_max,
        ci=ci,
        cr=cr,
        n=n,
    )


def global_weights(
    node_parent: dict[str, str | None],
    local_weights_by_matrix: dict[str, dict[str, float]],
    matrix_of_parent: dict[str, str],
) -> dict[str, float]:
    """루트까지의 지역 가중치 곱 = 전역 가중치.

    node_parent: node_id -> parent_id(없으면 None, 즉 루트)
    local_weights_by_matrix: matrix_id -> {node_id: local_weight}
    matrix_of_parent: parent_id -> matrix_id (그 부모의 자식들을 비교한 행렬)
    """
    memo: dict[str, float] = {}

    def resolve(node_id: str) -> float:
        if node_id in memo:
            return memo[node_id]
        parent_id = node_parent.get(node_id)
        if parent_id is None:
            memo[node_id] = 1.0
            return 1.0
        matrix_id = matrix_of_parent.get(parent_id)
        local = local_weights_by_matrix.get(matrix_id, {}).get(node_id, 0.0)
        val = local * resolve(parent_id)
        memo[node_id] = val
        return val

    return {nid: resolve(nid) for nid in node_parent}


def sensitivity(
    local_weights_by_matrix: dict[str, dict[str, float]],
    matrix_of_parent: dict[str, str],
    node_parent: dict[str, str | None],
    target_node: str,
    delta_pct: float,
) -> dict[str, float]:
    """target_node가 속한 행렬(같은 부모를 공유하는 형제들) 안에서만 지역 가중치를
    delta_pct만큼(예: +0.1 = +10%p) 흔들고, 나머지 형제에게 비례 배분해 재정규화한
    뒤 전역 가중치를 다시 계산한다. "이 기준이 형제들 사이에서 더/덜 중요해지면
    전체 순위가 뒤집히는가"를 보는 표준적인 what-if 질문이다.

    주의: 전역 가중치 딕셔너리를 직접 흔들면 안 된다. 거기엔 루트의 가중치 1.0처럼
    형제 관계가 아닌 "곱셈 항등원" 값이 섞여 있어서, 그걸 같은 그룹으로 착각하고
    재정규화하면 무관한 항목이 결과를 오염시킨다(실제로 이 함수의 첫 구현이 그
    실수를 했다 — 형제가 아닌 루트의 1.0이 재분배 대상에 끼어들어 나머지 형제들의
    가중치가 0으로 무너졌었다). 그래서 반드시 로컬 가중치(형제끼리만 합=1인 값)
    수준에서 흔들고, 전역 가중치는 global_weights()로 다시 유도해야 한다.
    """
    parent_id = node_parent.get(target_node)
    matrix_id = matrix_of_parent.get(parent_id)
    local = dict(local_weights_by_matrix.get(matrix_id, {}))
    if target_node not in local:
        raise ValueError(f"{target_node}가 속한 지역 가중치를 찾을 수 없습니다")

    old_val = local[target_node]
    new_val = max(0.0, min(1.0, old_val + delta_pct))
    others = [k for k in local if k != target_node]
    others_old_sum = sum(local[k] for k in others)
    remaining = 1.0 - new_val
    if others_old_sum > 0:
        for k in others:
            local[k] = remaining * (local[k] / others_old_sum)
    elif others:
        for k in others:
            local[k] = remaining / len(others)
    local[target_node] = new_val

    new_local_by_matrix = dict(local_weights_by_matrix)
    new_local_by_matrix[matrix_id] = local
    return global_weights(node_parent, new_local_by_matrix, matrix_of_parent)
