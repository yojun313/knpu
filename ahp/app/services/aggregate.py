"""그룹 집계 — AIJ/AIP, 합의도, 극단값. 순수 함수, DB 의존 없음.

집계 방식은 프로젝트 설정(projects.settings.aggregation)에 따라 AIJ 또는 AIP를 쓴다.
기본값은 AIP다 — 개인 가중치를 먼저 구하므로 개별 응답의 CR을 그 자리에서 바로
확보할 수 있어서(PLAN.md 11절), 실시간 델파이에서 "이 사람 판단이 비일관적이다"를
즉시 알려주는 데 구조적으로 유리하다.

평균은 반드시 기하평균이다. 쌍대비교 값에 산술평균을 쓰면 역수 관계가 깨진다
(mean(a_ij) != 1/mean(a_ji)) — AHP에서 산술평균은 버그다.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from app.services.ahp_calc import derive_weights, pair_id, IncompleteMatrixError


def geometric_mean(values: list[float]) -> float:
    if not values:
        raise ValueError("빈 리스트의 기하평균은 정의되지 않는다")
    logs = [math.log(v) for v in values]
    return math.exp(sum(logs) / len(logs))


def aggregate_aij(node_ids: list[str], respondent_pairs: list[dict[str, float]]):
    """AIJ(판단 집계) — 응답자별 쌍대비교 "값"을 기하평균으로 먼저 합친 뒤,
    합쳐진 단일 행렬에서 가중치를 한 번만 구한다. 개인별 CR은 별도로 계산해야 한다."""
    merged: dict[str, list[float]] = defaultdict(list)
    for pairs in respondent_pairs:
        for pid, v in pairs.items():
            merged[pid].append(v)
    merged_pairs = {pid: geometric_mean(vs) for pid, vs in merged.items()}
    return derive_weights(node_ids, merged_pairs), merged_pairs


def aggregate_aip(node_ids: list[str], respondent_pairs: list[dict[str, float]]):
    """AIP(우선순위 집계) — 응답자마다 먼저 가중치(+CR)를 구하고, 그 가중치
    벡터들을 노드별로 기하평균 낸 뒤 다시 정규화한다. 완전하지 않은(누락 쌍이 있는)
    응답자는 건너뛰고 반환값의 skipped에 기록한다."""
    per_respondent = []
    skipped = []
    for i, pairs in enumerate(respondent_pairs):
        try:
            per_respondent.append(derive_weights(node_ids, pairs))
        except IncompleteMatrixError:
            skipped.append(i)

    if not per_respondent:
        raise ValueError("완전한 응답이 하나도 없어 AIP 집계를 할 수 없습니다")

    group_weights = {}
    for nid in node_ids:
        vals = [r.weights[nid] for r in per_respondent]
        group_weights[nid] = geometric_mean(vals)
    total = sum(group_weights.values())
    group_weights = {k: v / total for k, v in group_weights.items()}

    return group_weights, per_respondent, skipped


def coefficient_of_variation(values: list[float]) -> float:
    """쌍별 응답자 간 변동계수(표준편차/평균) — 값이 클수록 의견이 갈린다."""
    if len(values) < 2:
        return 0.0
    arr = np.array(values, dtype=float)
    mean = arr.mean()
    if mean == 0:
        return 0.0
    return float(arr.std(ddof=1) / mean)


def kendalls_w(rankings: list[list[str]]) -> float:
    """Kendall의 일치도 계수 W — 여러 순위(응답자별 또는 라운드별) 간 일치 정도.
    0(전혀 안 맞음) ~ 1(완전히 일치). 델파이 라운드 간 수렴을 보는 지표."""
    if len(rankings) < 2:
        return 1.0
    items = sorted(rankings[0])
    n = len(items)
    m = len(rankings)
    if n < 2:
        return 1.0

    rank_sums = {item: 0.0 for item in items}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            rank_sums[item] += rank

    mean_rank_sum = m * (n + 1) / 2
    s = sum((rs - mean_rank_sum) ** 2 for rs in rank_sums.values())
    denom = (m**2) * (n**3 - n) / 12
    if denom == 0:
        return 1.0
    return float(s / denom)


_MAD_ZERO_FALLBACK_LOG_THRESHOLD = math.log(
    1.5
)  # 과반 일치 시 남은 값이 "한눈에 다른" 정도


def find_outliers(pair_values: dict[int, float], z_threshold: float = 3.5) -> list[int]:
    """한 쌍에 대한 응답자별 값에서 극단값을 찾는다. AHP 값은 로그 스케일에서
    대칭이므로(2배 vs 0.5배가 대칭) log(value) 기준으로 판단한다.

    평균·표준편차 기반 z-점수는 작은 패널(실제 AHP 전문가 패널은 5~15명이 흔하다)에서
    치명적인 약점이 있다 — 극단값 자신이 표준편차 계산에 포함되어 자기 자신을
    가려버린다(masking effect). 예: [3,3,3,3,27]에서 27은 누가 봐도 튀는 값이지만,
    표준편차 기반 z는 이 값이 std 자체를 크게 부풀려서 임계값 2.5를 못 넘긴다(실측 ~1.79).
    대신 중앙값·MAD(중앙값 절대편차) 기반 수정 z-점수를 쓴다. 중앙값은 극단값 1~2개에
    거의 흔들리지 않아 이 문제를 피한다. 임계값 3.5는 Iglewicz & Hoaglin의 통상 권고치.
    """
    if len(pair_values) < 4:
        return []
    idx = list(pair_values.keys())
    logs = np.array([math.log(pair_values[i]) for i in idx])
    median = np.median(logs)
    abs_dev = np.abs(logs - median)
    mad = np.median(abs_dev)

    if mad > 0:
        modified_z = 0.6745 * (logs - median) / mad
        return [idx[i] for i in range(len(idx)) if abs(modified_z[i]) >= z_threshold]

    # 과반수가 정확히 같은 값을 준 경우(MAD=0)엔 수정 z-점수 자체가 정의되지 않는다.
    # 이때는 중앙값과 "한눈에 다른" 정도(약 1.5배 이상) 벗어난 값만 표시한다.
    return [
        idx[i] for i in range(len(idx)) if abs_dev[i] > _MAD_ZERO_FALLBACK_LOG_THRESHOLD
    ]
