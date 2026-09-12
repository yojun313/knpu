"""BWM 일관성 — 순서 일관성 OR, 입력기반 CR^I, 출력기반 CR^O.

Liang, Brunelli & Rezaei (2020), Omega 96:102175.

**사용자 결정(설계 §5-5): 하드 게이트로 쓰지 않는다.** AHP CR과 동일하게 높게
나오면 "가장 모순적인 기준"을 지목해 재고를 권고할 뿐, 제출을 막지 않는다.

- OR  : 순서 일관성. OR>0 이면 논리적 모순(bo/ow 순위가 어긋남). 최적화 불필요.
- CR^I: 입력기반. 최적화 없이 즉시 계산 → 실시간 피드백·locus 산출용.
- CR^O: 출력기반(보고용). ξ*/ξ_max. 여기선 선형모형 ξ_L 로 근사 보고한다
        (정석은 비선형모형 ξ* — 필요해지면 nlp 모듈로 분리).
"""

from __future__ import annotations

# 임계값 표 — 세로축 척도(= a_BW, Best-to-Worst 값), 가로축 기준 수.
# 2척도(a_BW=2)면 임계값 0. n>9 / 척도>9 는 각각 마지막 값을 쓴다.
_N_COLS = (3, 4, 5, 6, 7, 8, 9)

CRI_THRESHOLD = {
    3: (0.1667, 0.1667, 0.1667, 0.1667, 0.1667, 0.1667, 0.1667),
    4: (0.1121, 0.1529, 0.1898, 0.2206, 0.2527, 0.2577, 0.2683),
    5: (0.1354, 0.1994, 0.2306, 0.2546, 0.2716, 0.2844, 0.2960),
    6: (0.1330, 0.1990, 0.2643, 0.3044, 0.3144, 0.3221, 0.3262),
    7: (0.1294, 0.2457, 0.2819, 0.3029, 0.3144, 0.3251, 0.3403),
    8: (0.1309, 0.2521, 0.2958, 0.3154, 0.3408, 0.3620, 0.3657),
    9: (0.1359, 0.2681, 0.3062, 0.3337, 0.3517, 0.3620, 0.3662),
}

CRO_THRESHOLD = {
    3: (0.2087, 0.2087, 0.2087, 0.2087, 0.2087, 0.2087, 0.2087),
    4: (0.1581, 0.2352, 0.2738, 0.2928, 0.3102, 0.3154, 0.3273),
    5: (0.2111, 0.2848, 0.3019, 0.3309, 0.3479, 0.3611, 0.3741),
    6: (0.2164, 0.2922, 0.3565, 0.3924, 0.4061, 0.4168, 0.4225),
    7: (0.2090, 0.3313, 0.3734, 0.3931, 0.4035, 0.4108, 0.4298),
    8: (0.2267, 0.3409, 0.4029, 0.4230, 0.4379, 0.4543, 0.4599),
    9: (0.2122, 0.3653, 0.4055, 0.4225, 0.4445, 0.4587, 0.4747),
}


def _lookup(table: dict, a_bw: float, n: int) -> float:
    scale = int(round(a_bw))
    if scale <= 2:
        return 0.0
    scale = min(max(scale, 3), 9)
    col = min(max(n, 3), 9)
    return table[scale][_N_COLS.index(col)]


def cri_threshold(a_bw: float, n: int) -> float:
    return _lookup(CRI_THRESHOLD, a_bw, n)


def cro_threshold(a_bw: float, n: int) -> float:
    return _lookup(CRO_THRESHOLD, a_bw, n)


def _F(x: float) -> float:
    if x < -1e-12:
        return 1.0
    if abs(x) <= 1e-12:
        return 0.5
    return 0.0


def ordinal_consistency(
    criteria: list[str],
    best: str,
    worst: str,
    best_to_others: dict[str, float],
    others_to_worst: dict[str, float],
) -> dict:
    """OR_j = (1/n) Σ_{i≠j} F((a_Bi − a_Bj)(a_jW − a_iW)),  OR = max_j OR_j.

    OR>0 이면 bo(Best 기준 순위)와 ow(Worst 기준 순위)가 어긋나는 쌍이 있다.
    """
    n = len(criteria)
    ab = {
        c: (1.0 if c == best else float(best_to_others.get(c, 0.0))) for c in criteria
    }
    aw = {
        c: (1.0 if c == worst else float(others_to_worst.get(c, 0.0))) for c in criteria
    }
    by_c: dict[str, float] = {}
    for j in criteria:
        s = 0.0
        for i in criteria:
            if i == j:
                continue
            s += _F((ab[i] - ab[j]) * (aw[j] - aw[i]))
        by_c[j] = s / n if n else 0.0
    return {"OR": max(by_c.values()) if by_c else 0.0, "OR_by_criterion": by_c}


def input_consistency(
    criteria: list[str],
    best: str,
    worst: str,
    best_to_others: dict[str, float],
    others_to_worst: dict[str, float],
) -> dict:
    """CR^I_j = |a_Bj·a_jW − a_BW| / (a_BW² − a_BW)  (a_BW>1),  0  (a_BW≤1).

    CR^I = max_j CR^I_j. 기준별 값이 그대로 locus(어느 비교를 고칠지) 근거가 된다.
    """
    n = len(criteria)
    a_bw = float(best_to_others.get(worst, others_to_worst.get(best, 1.0)))
    thr = cri_threshold(a_bw, n)
    if a_bw <= 1:
        by_c = {c: 0.0 for c in criteria}
        return {"CRI": 0.0, "CRI_by_criterion": by_c, "threshold": thr, "passed": True}

    denom = a_bw * a_bw - a_bw
    by_c: dict[str, float] = {}
    for c in criteria:
        ab = 1.0 if c == best else float(best_to_others.get(c, 0.0))
        aw = 1.0 if c == worst else float(others_to_worst.get(c, 0.0))
        by_c[c] = abs(ab * aw - a_bw) / denom if denom else 0.0
    cri = max(by_c.values()) if by_c else 0.0
    return {
        "CRI": cri,
        "CRI_by_criterion": by_c,
        "threshold": thr,
        "passed": cri <= thr,
    }
