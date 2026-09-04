"""BWM 방법 플러그인 — Best-Worst Method (Rezaei 2015/2016).

한 질문 그룹의 응답(`responses.answers[group_id]`) shape:

    {
      "best":  "<criterion uuid>",          # 가장 중요한 기준 지목
      "worst": "<criterion uuid>",          # 가장 덜 중요한 기준 지목
      "BO:<uuid>": n,   # Best가 이 기준보다 n배 중요 (1~9). best 자신은 생략(=1)
      "OW:<uuid>": n,   # 이 기준이 Worst보다 n배 중요 (1~9). worst 자신은 생략(=1)
    }

가중치: 선형모형 LP(`mcdm.lp.bwm_linear_weights`). 판정: `mcdm.bwm_consistency`
(CR^I + 순서 일관성 OR). 둘 다 **안내용** — 제출을 막지 않는다(설계 §5-5).
"""

from __future__ import annotations

import math

from app.services.mcdm.bwm_consistency import (
    cri_threshold,
    input_consistency,
    ordinal_consistency,
)
from app.services.mcdm.lp import LPInfeasibleError, bwm_linear_weights
from app.services.methods.base import Consistency, LocalResult

BO = "BO:"
OW = "OW:"


def _parse(group: dict, responses: dict, overrides):
    child = list(group["child_uuids"])
    r = dict(responses or {})
    for ov in overrides or []:
        iid = ov.get("item_id")
        if iid:
            r[iid] = ov.get("value")
    best, worst = r.get("best"), r.get("worst")
    if best not in child or worst not in child or best == worst:
        return None
    bo = {}
    ow = {}
    for c in child:
        if c != best:
            v = r.get(BO + c)
            if v is None:
                return None
            bo[c] = float(v)
        if c != worst:
            v = r.get(OW + c)
            if v is None:
                return None
            ow[c] = float(v)
    return child, best, worst, bo, ow


def _cro(xi: float, a_bw: float) -> float | None:
    """CR^O ≈ ξ / ξ_max.  ξ_max 는 ξ²−(1+2a_BW)ξ+(a_BW²−a_BW)=0 의 큰 근.
    (정석은 비선형모형 ξ* 이지만 여기선 선형 ξ_L 로 근사 보고.)"""
    if a_bw <= 1:
        return 0.0
    b = 1 + 2 * a_bw
    disc = b * b - 4 * (a_bw * a_bw - a_bw)
    if disc < 0:
        return None
    xi_max = (b + math.sqrt(disc)) / 2
    return xi / xi_max if xi_max else None


class BwmPlugin:
    name = "bwm"

    def question_kinds(self) -> tuple[str, ...]:
        return ("bwm",)

    def generate_group(
        self,
        *,
        parent_uuid: str,
        operand_uuids: list[str],
        parent_name: str,
        is_alternative: bool,
        settings: dict,
    ) -> dict:
        return {
            "group_id": f"alt:{parent_uuid}" if is_alternative else parent_uuid,
            "parent_uuid": parent_uuid,
            "child_uuids": list(operand_uuids),
            "kind": "bwm",
            "question_text": (
                f"'{parent_name}' 하위 항목 중 가장 중요한 것과 가장 덜 중요한 것을 "
                f"고른 뒤, 각각에 대한 상대적 중요도를 매겨 주세요."
            ),
            "is_alternative": is_alternative,
        }

    # ── ④ 검증 / ⑤ 개인 계산 ────────────────────────────────────────────
    def derive_local(
        self,
        group: dict,
        responses: dict,
        *,
        overrides=None,
        cr_threshold: float = 0.1,
    ) -> LocalResult:
        parsed = _parse(group, responses, overrides)
        if parsed is None:
            return LocalResult(weights={}, ranking=[], complete=False, consistency=None)
        child, best, worst, bo, ow = parsed
        try:
            out = bwm_linear_weights(child, best, worst, bo, ow)
        except LPInfeasibleError:
            return LocalResult(weights={}, ranking=[], complete=False, consistency=None)

        weights = out["weights"]
        ranking = sorted(child, key=lambda c: -weights.get(c, 0.0))
        ic = input_consistency(child, best, worst, bo, ow)
        oc = ordinal_consistency(child, best, worst, bo, ow)
        a_bw = bo.get(worst, ow.get(best, 1.0))

        bad = [
            c
            for c in child
            if ic["CRI_by_criterion"].get(c, 0.0) > ic["threshold"]
            or oc["OR_by_criterion"].get(c, 0.0) > 1e-9
        ]
        bad.sort(key=lambda c: -(ic["CRI_by_criterion"].get(c, 0.0)))
        locus = [BO + c for c in bad] + [OW + c for c in bad]
        detail = [
            {
                "criterion": c,
                "cri_j": round(ic["CRI_by_criterion"].get(c, 0.0), 4),
                "or_j": round(oc["OR_by_criterion"].get(c, 0.0), 4),
            }
            for c in bad[:3]
        ]

        cons = Consistency(
            passed=ic["passed"] and oc["OR"] <= 1e-9,  # 안내용 — 게이트 아님
            metrics={
                "cri": ic["CRI"],
                "or": oc["OR"],
                "xi": out["xi"],
                "cro": _cro(out["xi"], a_bw),
            },
            threshold=ic["threshold"],
            locus=locus,
            detail=detail,
        )
        return LocalResult(
            weights=weights, ranking=ranking, complete=True, consistency=cons
        )

    def validate(
        self,
        group: dict,
        responses: dict,
        *,
        cr_threshold: float = 0.1,
        overrides=None,
    ) -> Consistency | None:
        return self.derive_local(
            group, responses, overrides=overrides, cr_threshold=cr_threshold
        ).consistency

    # ── ⑤ 그룹 계산 ────────────────────────────────────────────────────
    def aggregate_group(
        self,
        group: dict,
        responses_by_respondent: list[dict],
        settings: dict,
    ) -> LocalResult:
        child = list(group["child_uuids"])
        per: list[dict] = []
        skipped: list[int] = []
        cris: list[float] = []
        for i, r in enumerate(responses_by_respondent):
            lr = self.derive_local(group, r)
            if lr.complete:
                per.append(lr.weights)
                if lr.consistency:
                    cris.append(lr.consistency.metrics.get("cri", 0.0))
            else:
                skipped.append(i)

        if not per:
            return LocalResult(
                weights={c: 0.0 for c in child},
                ranking=list(child),
                complete=False,
                skipped=skipped,
            )

        mode = settings.get("bwm_aggregation", "geomean")
        agg: dict[str, float] = {}
        for c in child:
            vals = [w.get(c, 0.0) for w in per]
            if mode == "arithmetic":
                agg[c] = sum(vals) / len(vals)
            else:  # 기하평균 후 재정규화 (비율척도 정합, 기본)
                pos = [v for v in vals if v > 0]
                agg[c] = math.exp(sum(math.log(v) for v in pos) / len(pos)) if pos else 0.0
        total = sum(agg.values()) or 1.0
        agg = {c: v / total for c, v in agg.items()}

        return LocalResult(
            weights=agg,
            ranking=sorted(child, key=lambda c: -agg.get(c, 0.0)),
            complete=True,
            consistency=Consistency(
                passed=None,
                metrics={"avg_cri": sum(cris) / len(cris)} if cris else {},
                threshold=None,
            ),
            skipped=skipped,
        )


PLUGIN = BwmPlugin()
