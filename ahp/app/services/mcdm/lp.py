"""선형계획 프리미티브 — BWM 선형모형(Rezaei 2016) 가중치 도출.

`scipy.optimize.linprog` 래퍼. BWM 외 다른 방법(목표계획법 등)이 LP를 쓰면
여기에 함수만 추가한다.
"""

from __future__ import annotations

from scipy.optimize import linprog


class LPInfeasibleError(Exception):
    """LP가 풀리지 않음(불완전 입력 또는 수치 문제)."""


def bwm_linear_weights(
    criteria: list[str],
    best: str,
    worst: str,
    best_to_others: dict[str, float],
    others_to_worst: dict[str, float],
) -> dict:
    """BWM 선형모형(Rezaei 2016, Omega 64:126-130).

        min  ξ_L
        s.t. |w_B - a_Bj · w_j| ≤ ξ_L    ∀j
             |w_j - a_jW · w_W| ≤ ξ_L    ∀j
             Σ w_j = 1,  w_j ≥ 0

    절댓값을 부등식 2개로 쪼개 LP로 푼다. 유일해가 보장된다.

    best_to_others[j] = a_Bj (Best가 j보다 몇 배 중요), a_BB=1.
    others_to_worst[j] = a_jW (j가 Worst보다 몇 배 중요), a_WW=1.
    best/worst 자기 자신 항목은 없어도 된다(1로 간주).

    반환: {"weights": {criterion: w}, "xi": ξ_L*}.
    """
    n = len(criteria)
    if n < 2 or best not in criteria or worst not in criteria or best == worst:
        raise LPInfeasibleError("기준이 2개 미만이거나 Best/Worst가 유효하지 않습니다")
    idx = {c: i for i, c in enumerate(criteria)}
    bi, wi = idx[best], idx[worst]

    def a_b(j: str) -> float:
        v = 1.0 if j == best else best_to_others.get(j)
        if v is None or v <= 0:
            raise LPInfeasibleError(f"Best-to-Others 값 누락/오류: {j}")
        return float(v)

    def a_w(j: str) -> float:
        v = 1.0 if j == worst else others_to_worst.get(j)
        if v is None or v <= 0:
            raise LPInfeasibleError(f"Others-to-Worst 값 누락/오류: {j}")
        return float(v)

    # 변수: [w_0 .. w_{n-1}, xi]
    nv = n + 1
    xi = n
    c = [0.0] * n + [1.0]
    A_ub: list[list[float]] = []
    b_ub: list[float] = []

    def _abs_rows(pos: int, neg: int, coef: float):
        """|x_pos - coef·x_neg| ≤ xi 를 부등식 2개로."""
        r1 = [0.0] * nv
        r1[pos] += 1.0
        r1[neg] += -coef
        r1[xi] = -1.0
        A_ub.append(r1)
        b_ub.append(0.0)
        r2 = [0.0] * nv
        r2[pos] += -1.0
        r2[neg] += coef
        r2[xi] = -1.0
        A_ub.append(r2)
        b_ub.append(0.0)

    for j in criteria:
        if idx[j] != bi:  # |w_B - a_Bj · w_j|  (j=W 포함 → Best-Worst 제약)
            _abs_rows(bi, idx[j], a_b(j))
        if idx[j] != wi and idx[j] != bi:  # |w_j - a_jW · w_W|
            _abs_rows(idx[j], wi, a_w(j))

    A_eq = [[1.0] * n + [0.0]]
    b_eq = [1.0]
    bounds = [(0.0, None)] * nv

    res = linprog(
        c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs"
    )
    if not res.success:
        raise LPInfeasibleError(f"BWM LP 풀이 실패: {res.message}")

    raw = [max(0.0, float(v)) for v in res.x[:n]]
    total = sum(raw) or 1.0
    weights = {criteria[i]: raw[i] / total for i in range(n)}
    return {"weights": weights, "xi": float(res.x[xi])}
